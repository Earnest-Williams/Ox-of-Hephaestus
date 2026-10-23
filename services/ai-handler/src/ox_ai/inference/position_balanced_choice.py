"""Experimental three-way position-balanced Decider option scorer.

This is a nonproduction Concordia-compatible choice adapter. It calls the
publisher's actual native System One scorer three times for the same
three-option social decision, once with every semantic option in every code
position. It averages probabilities by stable semantic identity, not letter
or display index, and returns one ordinary bounded CommandOption choice.

No Evennia authority; no model-generated text; no fallback after a failed
partial consultation. G13 measured substantial single-pass position effects.
This adapter is an experimental response, NOT evidence that a character's
personality is psychologically convincing.
"""
from __future__ import annotations

from collections.abc import Sequence
import math
from pathlib import Path
from typing import Any

from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel


class PositionBalancedDeciderChoiceModel:
    """Three native forwards, balanced code positions, one proposed action.

    options must be in caller display order and have distinct stable,
    semantic action keys. The responses provided by Concordia correspond
    to that same display order. Sorting semantic keys before rotating makes
    the aggregated semantic result independent of caller menu order.

    This does not alter the actor's original prompt, admit observations,
    mutate memory or send world commands. It does triple native inference
    cost per choice. Callers must account for three engine forwards even
    though Concordia records one top-level sample_choice request.
    """

    def __init__(
        self,
        gguf_path: str | Path,
        options: Sequence[tuple[str, str]],
        *,
        engine: Any | None = None,
        n_threads: int = 4,
    ) -> None:
        if (not isinstance(options, (list, tuple))
                or len(options) != 3
                or any(not isinstance(x, (list, tuple)) or len(x) != 2
                       or not all(isinstance(part, str) and part.strip()
                                  for part in x)
                       for x in options)):
            raise ValueError("Exactly three typed semantic options required")
        triples = tuple((str(key), str(description)) for key, description in options)
        if (len({key for key, _ in triples}) != 3
                or len({description for _, description in triples}) != 3):
            raise ValueError("Ambiguous or duplicate semantic options")
        self.options = triples
        self.engine = DeciderGGUFChoiceModel(
            gguf_path, tuple(description for _, description in triples),
            engine=engine, n_threads=n_threads,
        ).engine
        self.last: dict | None = None

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ):
        del seed
        self.last = None
        codes = tuple(responses)
        if (not isinstance(prompt, str) or not prompt.strip()
                or len(codes) != 3
                or len(set(codes)) != 3
                or any(not isinstance(code, str) or not code.strip()
                       for code in codes)):
            raise ValueError("Three unique model response codes are required")
        by_key = dict(self.options)
        canonical_keys = tuple(sorted(by_key))
        sums = {key: 0.0 for key in canonical_keys}
        native_picks = []
        positions = {key: set() for key in canonical_keys}

        for offset in range(3):
            # A true cyclic Latin square: each semantic option appears once
            # in each of the three response-token positions.
            order = canonical_keys[offset:] + canonical_keys[:offset]
            questions = {
                "next_action": {
                    "type": "choice",
                    "instructions": (
                        "Which action should this specific crewmember attempt "
                        "next given their private beliefs, personality and "
                        "currently observed circumstances? Select an offered "
                        "action, without asserting that it has succeeded."
                    ),
                    "criteria": {
                        code: by_key[key] for code, key in zip(codes, order)
                    },
                },
            }
            result = self.engine.system_one(prompt, questions)
            if not isinstance(result, dict):
                raise ValueError("Native Decider result was not a mapping")
            answers = result.get("answers", {})
            if not isinstance(answers, dict):
                raise ValueError("Native Decider answers were malformed")
            answer = answers.get("next_action", {})
            if not isinstance(answer, dict):
                raise ValueError("Native Decider choice was malformed")
            picked = answer.get("choice")
            probabilities = answer.get("probabilities")
            if (picked not in codes
                    or not isinstance(probabilities, dict)
                    or set(probabilities) != set(codes)
                    or any(type(p) not in (int, float) or not math.isfinite(p)
                           or not 0 <= p <= 1 for p in probabilities.values())
                    or not math.isclose(
                        sum(probabilities.values()), 1, abs_tol=0.02
                    )):
                raise ValueError("Invalid native option-token probability record")
            for position, (code, key) in enumerate(zip(codes, order)):
                sums[key] += probabilities[code]
                positions[key].add(position)
            native_picks.append(order[codes.index(picked)])

        if any(positions[key] != {0, 1, 2} for key in canonical_keys):
            raise AssertionError("Option order failed position balance")
        mean = {key: sums[key] / 3 for key in canonical_keys}
        # Stable semantic-key tie break, never first displayed option or
        # first option-token index. Returning only a caller-offered response
        # preserves the finite typed command boundary.
        best = max(mean.values())
        winner = next(key for key in canonical_keys if mean[key] >= best - 1e-9)
        caller_keys = tuple(key for key, _ in self.options)
        selected_code = codes[caller_keys.index(winner)]
        record = {
            "selected_semantic_key": winner,
            "semantic_probabilities": mean,
            "underlying_native_calls": 3,
            "permutation_native_picks": tuple(native_picks),
            "all_three_positions_per_semantic_option": True,
        }
        self.last = record
        return codes.index(selected_code), selected_code, {
            "decider_position_balanced_choice": record
        }

    def sample_text(self, *args, **kwargs):
        raise RuntimeError("Position-balanced Decider cannot generate text")
