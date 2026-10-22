"""Controlled Decider 4B GGUF speed audit: one CPU runner, ABBA model order.

No normal chat, no GOAP: score identical native System One option logits.
The original Q2/Q4 matrix measured on SEPARATE VMs; these measurements
alternate model order on one runner with exactly the same prompt corpus.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import statistics
import struct
import time

from scenarios import counterfactual_decision_trial as cf
from scenarios import g11_memory_ab_trial as g11
from scenarios.decider_gguf_quant_trial import INSTRUCTIONS


class PromptCapture:
    def __init__(self):
        self.calls = []

    def sample_choice(self, prompt, responses, *, seed=None):
        self.calls.append((prompt, tuple(responses)))
        return 0, responses[0], {}

    def sample_text(self, *args, **kwargs):
        raise AssertionError("The benchmark must capture choice prompts only")


def prompts():
    """Twelve exact native-Concordia choice prompts, with fixed offered labels."""
    examples = []
    for spec in g11.fixtures():
        for augmented in (False, True):
            capture = PromptCapture()
            agent = g11.build(spec, augmented, capture)
            agent.decide(spec["options"])
            if len(capture.calls) != 1:
                raise AssertionError("Capture did not issue one model request")
            prompt, responses = capture.calls[0]
            examples.append({
                "name": "g11." + spec["name"] + (".aug" if augmented else ".base"),
                "prompt": prompt,
                "criteria": dict(zip(responses, [o.label for o in spec["options"]])),
            })
    for case in cf.fixtures()[:2]:
        for variant in ("earlier", "changed"):
            capture = PromptCapture()
            agent, options = cf.make_agent(case, variant, capture)
            agent.decide(options, expected_revision=1)
            if len(capture.calls) != 1:
                raise AssertionError("Capture did not issue one model request")
            prompt, responses = capture.calls[0]
            examples.append({
                "name": "cf." + case.name + "." + variant,
                "prompt": prompt,
                "criteria": dict(zip(responses, [o.label for o in options])),
            })
    if len(examples) != 12 or len({e["name"] for e in examples}) != 12:
        raise AssertionError("Expected twelve independent captured decisions")
    return examples


def gguf_metadata(path: Path):
    """Read bounded, non-sensitive header fields without ingesting tensor weights."""
    sizes = {0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}
    keep = ("general.name", "general.basename", "general.architecture",
            "general.file_type", "general.quantization_version",
            "general.source.url", "general.source.repo_url",
            "general.size_label", "general.finetune")
    with path.open("rb") as fh:
        def u32():
            raw=fh.read(4)
            if len(raw)!=4: raise ValueError("Short GGUF header")
            return struct.unpack("<I",raw)[0]
        def u64():
            raw=fh.read(8)
            if len(raw)!=8: raise ValueError("Short GGUF header")
            return struct.unpack("<Q",raw)[0]
        def read_str(return_value=True):
            length=u64()
            if length>30_000_000: raise ValueError("Unbounded GGUF string")
            if return_value:
                raw=fh.read(length)
                if len(raw)!=length: raise ValueError("Short GGUF string")
                return raw.decode("utf-8","replace")
            fh.seek(length,1)
        def value(t,record=False):
            if t==8: return read_str(record)
            if t==9:
                item_type=u32()
                length=u64()
                if length>1_000_000: raise ValueError("Unbounded GGUF metadata array")
                for _ in range(length): value(item_type,False)
                return None
            if t not in sizes: raise ValueError("Unknown GGUF metadata kind " + str(t))
            raw=fh.read(sizes[t])
            if len(raw)!=sizes[t]: raise ValueError("Short GGUF scalar")
            if record and t in (4,10):return int.from_bytes(raw,"little")
            return None
        if fh.read(4)!=b"GGUF":raise ValueError("Not GGUF")
        version=u32()
        count_tensors=u64()
        count_meta=u64()
        if count_meta>5000:raise ValueError("Unbounded GGUF metadata")
        saved={}
        for _ in range(count_meta):
            key=read_str()
            kind=u32()
            wanted=key in keep
            result=value(kind,wanted)
            if wanted: saved[key]=result
        return {"version":version,"tensor_count":count_tensors,
                "metadata_fields":count_meta,"identifiers":saved}


def score(model, sample):
    reply=model.system_one(sample["prompt"], {"next_action": {
        "type": "choice", "instructions":INSTRUCTIONS,
        "criteria":sample["criteria"],
    }})
    answer=reply.get("answers",{}).get("next_action",{})
    if (answer.get("choice") not in sample["criteria"] or
        set(answer.get("probabilities",{})) != set(sample["criteria"])):
        raise ValueError("Model returned invalid typed option")
    return answer["choice"]


def run(model_dir, manifests, repeat=1):
    from decider.infer import Decider
    corpus=prompts()
    order=["Q2_K","Q4_K_M","Q4_K_M","Q2_K"]
    all_rows=[]
    meta={}
    for stage,quant in enumerate(order):
        info=manifests[quant]
        file=model_dir / info["gguf_file"]
        meta[quant]=gguf_metadata(file)
        before=time.perf_counter()
        model=Decider(str(file), gguf_options={
            "n_gpu_layers":0, "n_threads":4,
            "n_ctx":4096, "n_batch":4096, "n_seq_max":1,
        })
        load_time=round(time.perf_counter()-before,3)
        # First call is warmup and not counted; no llama KV cache reused
        score(model,corpus[0])
        for k in range(repeat):
            # reverse input order in second pass to mitigate prompt order bias
            cases=corpus if stage in (0,2) else list(reversed(corpus))
            for sample in cases:
                start=time.perf_counter()
                answer=score(model,sample)
                all_rows.append({
                    "stage":stage,"quant":quant,"name":sample["name"],
                    "repeat":k,"latency_seconds":round(time.perf_counter()-start,5),
                    "choice":answer,"prompt_chars":len(sample["prompt"]),
                    "load_seconds":load_time,
                })
        del model
        gc.collect()
    summary={}
    for quant in ("Q2_K","Q4_K_M"):
        vals=[r["latency_seconds"] for r in all_rows if r["quant"]==quant]
        summary[quant]={
            "sample_count":len(vals),
            "median_seconds":statistics.median(vals),
            "mean_seconds":round(statistics.mean(vals),5),
            "min_seconds":min(vals),
            "max_seconds":max(vals),
            "per_stage_median":{
                str(i):statistics.median(r["latency_seconds"] for r in all_rows
                       if r["quant"]==quant and r["stage"]==i)
                for i in range(4) if order[i]==quant
            },
        }
    return {
        "protocol":"ox_decider_4b_same_runner_ABBA_v1",
        "model_order":order,
        "runner":{"cpu_count":os.cpu_count()},
        "checkpoint":manifests,
        "gguf_headers":meta,
        "summary":summary,
        "decisions":all_rows,
        "command_submissions":0,
        "caution":"4 serial phases on one CPU, two identical quant-revision models. "
                  "Warmup excluded, model load excluded. Native typed GGUF scoring.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model-dir",type=Path,required=True)
    p.add_argument("--q2-manifest",type=Path,required=True)
    p.add_argument("--q4-manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    manifests={}
    for quant,filename in (("Q2_K",args.q2_manifest),("Q4_K_M",args.q4_manifest)):
        manifests[quant]=json.loads(filename.read_text(encoding="utf-8"))
        if manifests[quant]["quant"]!=quant:
            raise ValueError("Manifest's quant disagrees with filename")
    if (manifests["Q2_K"]["quant_repo_revision"] !=
            manifests["Q4_K_M"]["quant_repo_revision"]):
        raise ValueError("Quant source commits differ")
    if (manifests["Q2_K"]["tokenizer_repo_revision"] !=
            manifests["Q4_K_M"]["tokenizer_repo_revision"]):
        raise ValueError("Tokenizer revisions differ")
    report=run(args.model_dir,manifests)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps({"summary":report["summary"],
                      "gguf_headers":report["gguf_headers"]},sort_keys=True))


if __name__=="__main__":
    main()
