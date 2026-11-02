"""Native one-pass Decider GGUF choice adapter for a bounded Concordia menu.

The GGUF file and its exact tokenizer/config must already be installed
locally. No downloading, remote inference, or ability to issue world actions.
Only Decider option-token logits count; never use generated chat text.
"""
from __future__ import annotations

from collections.abc import Sequence
import math
import os
from pathlib import Path
from typing import Any


GPU_LAYERS_ENV = "OX_GGUF_GPU_LAYERS"


def gpu_layers() -> int:
    """Layers to offload to a GPU; 0 (CPU only) unless explicitly opted in.

    GPU offload changes the model's floating-point results, so trial runs
    with it set form a separate baseline from CPU runs.
    """
    raw: str = os.environ.get(GPU_LAYERS_ENV, "0").strip() or "0"
    if not raw.isdigit():
        raise ValueError(GPU_LAYERS_ENV + " must be a non-negative integer")
    return int(raw)

class DeciderGGUFChoiceModel:
    def __init__(self, gguf_path: str | Path, descriptions: Sequence[str],
                 *, engine: Any | None = None, n_threads: int = 4,
                 alternate_descriptions: dict[int, Sequence[str]] | None = None):
        self.descriptions=tuple(descriptions)
        if not 2<=len(self.descriptions)<=16 or any(
            not isinstance(x,str) or not x.strip() for x in self.descriptions
        ):
            raise ValueError("Model needs two to sixteen nonempty choices")
        # A character may face distinct, explicitly enumerated, finite
        # decision domains (seven speech intents versus three *existing*
        # agreement replies). Bind each menu cardinality to its precise
        # semantic descriptions. Never infer choices from arbitrary text,
        # truncate criteria, or authorize a world operation.
        self._menus = {len(self.descriptions): self.descriptions}
        for size, options in (alternate_descriptions or {}).items():
            if (type(size) is not int or not 2 <= size <= 16
                    or not isinstance(options, (tuple, list))
                    or len(options) != size
                    or any(not isinstance(x, str) or not x.strip()
                           for x in options)):
                raise ValueError("Alternate Decider menu is not a finite typed choice set")
            options = tuple(options)
            if size in self._menus and self._menus[size] != options:
                raise ValueError("Conflicting descriptions for the same menu size")
            self._menus[size] = options
        if engine is None:
            from decider.infer import Decider
            path=Path(gguf_path)
            if not path.is_file() or path.suffix!=".gguf":
                raise FileNotFoundError("Native Decider GGUF was not provisioned")
            engine=Decider(
                str(path),gguf_options={
                    "n_gpu_layers":gpu_layers(), "n_threads":n_threads,
                    "n_ctx":4096, "n_batch":4096,"n_seq_max":1,
                },
            )
        self.engine=engine
        self.last=None

    def sample_choice(self, prompt: str, responses: Sequence[str], *, seed=None):
        del seed
        codes=tuple(responses)
        descriptions=self._menus.get(len(codes))
        if (not isinstance(prompt,str) or not prompt.strip() or
                descriptions is None or len(set(codes))!=len(codes)
                or any(not isinstance(x,str) or not x for x in codes)):
            raise ValueError("Invalid Concordia finite decision menu")
        # The publisher's System One API scores option letters natively.
        result=self.engine.system_one(prompt,{
            "next_action":{
                "type":"choice",
                "instructions":(
                    "Which action should this specific crewmember attempt next "
                    "given their private beliefs, personality and currently "
                    "observed circumstances? Select an offered action, without "
                    "asserting that any action has already succeeded."
                ),
                "criteria":dict(zip(codes,descriptions)),
            },
        })
        answer=result.get("answers",{}).get("next_action",{})
        chosen=answer.get("choice")
        probabilities=answer.get("probabilities")
        if (chosen not in codes or not isinstance(probabilities,dict)
                or set(probabilities)!=set(codes)
                or any(type(p) not in (int,float) or not math.isfinite(p)
                       or not 0<=p<=1 for p in probabilities.values())
                or not math.isclose(sum(probabilities.values()),1,abs_tol=.02)):
            raise ValueError("Invalid native GGUF option-logit decision")
        self.last={"choice":chosen, "probabilities":probabilities}
        return codes.index(chosen),chosen,{"decider_native_choice":self.last}

    def sample_text(self,*args,**kwargs):
        raise RuntimeError("Decider cannot generate text; only native choices are supported")
