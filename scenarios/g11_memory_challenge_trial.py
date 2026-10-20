"""G11 second-stage discrimination: temporal evidence under observation churn.

These are deliberately *balanced* pairs: recent private evidence sometimes
authorizes proceeding and sometimes reverses earlier permission. Unlike the
four easy G11 fixtures, the latest public observation contains only a pending
decision, while older addressed evidence must be remembered. Every baseline
and augmented agent receives the EXACT same world events and typed history.
No world actions are executed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import time

from g11_memory_ab_trial import CaptureModel, PromptMeasuredModel, matched
from ox_ai.agents.crew import CrewAgent, CrewIdentity, CommandOption
from ox_ai.memory.seeds import SeededMemory
from ox_ai.memory.temporal import TemporalMemory
from ox_ai.ports.base import WorldObservation


def cases():
    return (
        dict(name="mara_withdrew",category="reconsideration",subject="mara",
             claim="mara_watch_swap",prior=1,later=-1,kind="witnessed_speech",
             seed="Mara once agreed to exchange an evening watch.",
             update="Mara privately and explicitly withdrew the watch-swap agreement.",
             decision="Operations asks whether Mara's watch swap is settled.",
             options=(("Record Mara's watch swap as confirmed","confirm"),
                      ("Record Mara's watch swap as unconfirmed","unconfirm")),
             expected="unconfirm"),
        dict(name="mara_reconfirmed",category="reconsideration",subject="mara",
             claim="mara_watch_swap",prior=1,later=1,kind="witnessed_speech",
             seed="Mara once agreed to exchange an evening watch.",
             update="Mara privately reconfirmed the watch swap and agreed to cover it.",
             decision="Operations asks whether Mara's watch swap is settled.",
             options=(("Record Mara's watch swap as confirmed","confirm"),
                      ("Record Mara's watch swap as unconfirmed","unconfirm")),
             expected="confirm"),
        dict(name="teo_denied",category="privacy",subject="teo",
             claim="teo_share_permission",prior=-1,later=-1,kind="witnessed_speech",
             seed="Teo has previously restricted circulation of his shift note.",
             update="Teo directly refused permission to share his shift note summary.",
             decision="Mara asks whether to receive Teo's shift note summary.",
             options=(("Send Mara a summary of Teo's shift note","send"),
                      ("Withhold Teo's shift note summary from Mara","withhold")),
             expected="withhold"),
        dict(name="teo_authorized",category="privacy",subject="teo",
             claim="teo_share_permission",prior=-1,later=1,kind="witnessed_speech",
             seed="Teo has previously restricted circulation of his shift note.",
             update="Teo directly gave explicit permission to share his shift note summary with Mara.",
             decision="Mara asks whether to receive Teo's shift note summary.",
             options=(("Send Mara a summary of Teo's shift note","send"),
                      ("Withhold Teo's shift note summary from Mara","withhold")),
             expected="send"),
        dict(name="cargo_still_unsafe",category="counterevidence",subject="cargo",
             claim="cargo_secured",prior=-1,later=-1,kind="world_receipt",
             seed="The cargo grid previously had a loose restraint.",
             update="A newer authenticated inspection receipt still shows an unsecured cargo restraint.",
             decision="The cargo officer must now choose disposition of the grid.",
             options=(("Sign off the cargo restraints","signoff"),
                      ("Request another cargo restraint inspection","inspect")),
             expected="inspect"),
        dict(name="cargo_newly_secured",category="counterevidence",subject="cargo",
             claim="cargo_secured",prior=-1,later=1,kind="world_receipt",
             seed="The cargo grid previously had a loose restraint.",
             update="A newer authenticated final inspection confirms every cargo restraint secured.",
             decision="The cargo officer must now choose disposition of the grid.",
             options=(("Sign off the cargo restraints","signoff"),
                      ("Request another cargo restraint inspection","inspect")),
             expected="signoff"),
    )


class PromptRecorder(PromptMeasuredModel):
    def __init__(self, model, needle):
        super().__init__(model)
        self.needle = needle
        self.deciding_prompt_contains_old_event = False
        self.has_extra_memory_context = False

    def sample_choice(self, prompt, responses, *, seed=None):
        self.deciding_prompt_contains_old_event |= self.needle in prompt
        self.has_extra_memory_context |= (
            "Private remembered context (fallible" in prompt)
        return super().sample_choice(prompt, responses, seed=seed)


def build(case, mode, model):
    name = case["name"]
    subject = case["subject"]
    seed = SeededMemory(
        "seed." + name,
        case["seed"],
        subject,
        occurred_turn=-80,
        claim_key=case["claim"],
        claim_subject=subject,
        claim_stance=case["prior"],
        source_group=name + ".source",
    )
    brain = CrewAgent(
        CrewIdentity("ox.g11.discrimination", "#77", "Duty Officer",
                     "Resolve outstanding watch decisions from known evidence",
                     "Select an appropriate next operational request"),
        model, initial_memories=(seed,),
        memory_projection_enabled=mode,
    )
    event_id = "historical." + name
    brain.observe(WorldObservation(
        event_id, "#77", 10.0, case["update"], source_event_id=event_id,
    ))
    brain.remember_timed(TemporalMemory(
        "memory." + name, subject, case["update"], case["kind"],
        10, 10, 100, 94, source_event_id=event_id,
        claim_key=case["claim"], claim_subject=subject,
        claim_stance=case["later"], source_group=name + ".source",
    ))
    # Move decisive prior event well outside native LastNObservations(32).
    # No other role or equipment details are introduced by these bulletins.
    for i in range(43):
        fid = f"routine.{name}.{i}"
        brain.observe(WorldObservation(
            fid, "#77", float(11 + i),
            f"Routine navigation bulletin {i}: scheduled diagnostics acknowledged.",
            source_event_id=fid,
        ))
    current = "decision." + name
    brain.observe(WorldObservation(
        current, "#77", 54.0, case["decision"], source_event_id=current,
    ))
    # Age is an explicit simulation cursor, not the last memory admission.
    brain.advance_memory_turn(120)
    return brain


def options(case):
    return tuple(CommandOption(label, verb, case["subject"])
                 for label, verb in case["options"])


def run(provider="gemini", repetitions=2):
    if provider not in ("capture","gemini"):
        raise ValueError("Provider must be explicit")
    if type(repetitions) is not int or not 1 <= repetitions <= 2:
        raise ValueError("Bound run to at most 2 paired repetitions")
    if provider == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("Missing Gemini API key; no model fallback")
        from ox_ai.agents.live_concordia import make_model
    records = []
    for repeat in range(repetitions):
        for i, case in enumerate(cases()):
            def model():
                return make_model("gemini") if provider == "gemini" else CaptureModel()
            wrappers = {mode: PromptRecorder(model(), case["update"])
                        for mode in (False,True)}
            brains = {mode: build(case, mode, wrappers[mode])
                      for mode in (False,True)}
            if not matched(brains[False], brains[True]):
                raise AssertionError("Unequal actor-visible evidence")
            offered = options(case)
            # Reverse order between cases/repetitions to limit request-order bias.
            for mode in ((False,True) if (repeat+i)%2==0 else (True,False)):
                start = time.perf_counter()
                request = brains[mode].decide(offered)
                records.append({
                    "case":case["name"], "category":case["category"],
                    "repetition":repeat, "arm":"augmented" if mode else "baseline",
                    "verb":request.verb, "expected":case["expected"],
                    "correct":request.verb==case["expected"],
                    "choice_index":next(j for j,o in enumerate(offered) if o.verb==request.verb),
                    "latency_seconds":round(time.perf_counter()-start,4),
                    "prompt_chars":wrappers[mode].prompt_chars,
                    "historical_evidence_in_prompt":wrappers[mode].deciding_prompt_contains_old_event,
                    "ox_memory_projection_in_prompt":wrappers[mode].has_extra_memory_context,
                })
    result={}
    for arm in ("baseline","augmented"):
        own=[row for row in records if row["arm"]==arm]
        result[arm]={
            "samples":len(own),
            "correct":sum(x["correct"] for x in own),
            "accuracy":sum(x["correct"] for x in own)/len(own),
            "median_latency_seconds":statistics.median(x["latency_seconds"] for x in own),
            "median_prompt_chars":statistics.median(x["prompt_chars"] for x in own),
            "historical_evidence_in_prompt_count":sum(x["historical_evidence_in_prompt"] for x in own),
            "ox_memory_projection_in_prompt_count":sum(x["ox_memory_projection_in_prompt"] for x in own),
        }
    return {
        "experiment":"g11_discriminative_history_under_churn",
        "provider":provider,
        "real_hosted_model":provider=="gemini",
        "valid_quality_evidence":provider=="gemini",
        "repetitions":repetitions,
        "limitation":"Six deliberately constructed counterbalanced scenarios; not a naturalistic independent sample.",
        "summary":result,"decisions":records,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--provider",choices=("capture","gemini"),default="gemini")
    p.add_argument("--repetitions",type=int,default=2)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    outcome=run(args.provider,args.repetitions)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(outcome,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"real_hosted_model":outcome["real_hosted_model"],
                      "summary":outcome["summary"]},sort_keys=True))


if __name__=="__main__":
    main()
