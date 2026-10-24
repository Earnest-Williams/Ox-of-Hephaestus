"""G16g: offline character voice generation, NEVER finite-action selection.

Six authenticated historical role blueprints are rendered in numeric and
prose form. A separate generative provider speaks a fixed *preselected*
speech intent; its free text never becomes an ActionRequest or world fact.
Native/hosted costs are measured separately. No model quality is inferred
from a synthetic backend or an unreviewed text sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "design/prototypes/g16g-speech-preregistration-v1.json"
sys.path.insert(0, str(Path(__file__).resolve().parent / "g8_soap_opera"))

from g13_matched_personality import load_g9_trial
from g14_profile_salience import prose_profile

MAX_CHARS = 1200


class FakeSpeechBackend:
    """Bounded synthetic text only for strict contract smoke tests."""

    label = "fixture"
    def generate(self, system: str, user: str, *, max_tokens: int,
                 temperature: float, seed: int):
        if not system or not user or max_tokens <= 0:
            raise ValueError("Invalid speech fixture")
        return {
            "text": "I hear you. We can talk, but I won't claim we've settled anything yet.",
            "prompt_tokens": 0, "completion_tokens": 0,
            "model_id": "synthetic-fixture-not-a-language-model",
        }


class LocalQwenSpeech:
    label = "qwen-local"

    def __init__(self, gguf_path: Path, expected_hash: str,
                 base_url: str = "http://127.0.0.1:8080/v1"):
        if not gguf_path.is_file():
            raise FileNotFoundError("Pinned local generative model missing")
        digest = hashlib.sha256()
        with gguf_path.open("rb") as source:
            while chunk := source.read(8 * 1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != expected_hash:
            raise PermissionError("Local speech GGUF SHA-256 changed")
        if base_url != "http://127.0.0.1:8080/v1":
            raise ValueError("G16g native interface must stay on the isolated loopback")
        self.url = base_url + "/chat/completions"
        self.model_hash = expected_hash

    def generate(self, system: str, user: str, *, max_tokens: int,
                 temperature: float, seed: int):
        payload = json.dumps({
            "model": "qwen3.5-4b",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature, "seed": seed,
            "max_tokens": max_tokens, "stream": False,
        }).encode("utf-8")
        request = Request(self.url, data=payload, method="POST",
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=180) as res:
            result = json.loads(res.read(16384).decode("utf-8"))
        choices = result.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Native speech provider returned an invalid completion")
        text = choices[0].get("message", {}).get("content")
        usage = result.get("usage", {})
        return {
            "text": text,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "model_id": "qwen3.5-4b-local-q4km",
        }


class HostedGeminiSpeech:
    """Optional provider, never used unless a real secret is configured."""

    label = "gemini-hosted"
    def __init__(self, model: str):
        if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]{3,90}", model):
            raise ValueError("Hosted model name must be explicit and bounded")
        self.model = model
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise PermissionError("G16g hosted comparison requires an explicit Gemini API key")

    def generate(self, system: str, user: str, *, max_tokens: int,
                 temperature: float, seed: int):
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.model + ":generateContent"
        )
        req = Request(
            endpoint, method="POST",
            headers={"Content-Type": "application/json",
                     "x-goog-api-key": self.api_key},
            data=json.dumps({
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "candidateCount": 1,
                    "seed": seed,
                },
            }).encode("utf-8"),
        )
        try:
            with urlopen(req, timeout=180) as response:
                result = json.loads(response.read(32768).decode("utf-8"))
        except (HTTPError, URLError) as exc:
            # Never print provider response bodies: they can contain
            # submitted private prompts or credential details.
            raise RuntimeError("Hosted speech generation unavailable") from None
        candidates = result.get("candidates", [])
        if len(candidates) != 1:
            raise ValueError("Hosted speech has no bounded text candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        speech = "".join(str(part.get("text", "")) for part in parts)
        usage = result.get("usageMetadata", {})
        return {
            "text": speech,
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
            "model_id": self.model,
        }


def verified_protocol() -> dict:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if (protocol.get("schema_version") != 1
            or protocol.get("status") != "g16g_speech_preregistered_before_model_generation"
            or protocol["generation"]["expected_sample_count_per_provider"] != 48
            or len(protocol["roles"]) != 6 or len(set(protocol["roles"])) != 6
            or len(protocol["scenes"]) != 4
            or len({x["id"] for x in protocol["scenes"]}) != 4
            or protocol["profiles"] != ["numeric_original","prose_original"]
            or protocol["generation"]["no_action_selection"] is not True):
        raise ValueError("Speech evaluation protocol differs from the frozen G16g manifest")
    return protocol


def prompt_for(role: str, scene: dict, arm: str) -> tuple[str, str, str]:
    protocol = verified_protocol()
    if role not in protocol["roles"] or arm not in protocol["profiles"]:
        raise ValueError("Unknown G9 role or voice intervention")
    if scene not in protocol["scenes"]:
        raise ValueError("Speech scene not in the authored protocol")
    blueprint = load_g9_trial().g9_blueprint(role)
    profile = (
        blueprint.cognition_context() if arm == "numeric_original"
        else prose_profile(blueprint)
    )
    system = (
        "Speak as " + blueprint.name + ", a particular Ox crew member. "
        "Your characterisation shapes sentence rhythm, attitude, confidence, "
        "pride, courtesy and interpersonal boundaries, but does not compel "
        "an answer. " + profile + "\n"
        "The intended speech act has ALREADY been chosen by a separate "
        "finite-action controller. You may ONLY phrase that intent. "
        "Do not choose another action, announce an agreement, certify a "
        "repair, assert a diagnosis or impersonate ship authority. "
        "Do not write JSON, stage directions, analysis or instructions. "
        "Produce one to three natural spoken sentences and nothing else."
    )
    user = (
        "Situation (hypothetical; not a world observation): "
        + scene["known_context"] + "\n"
        "Preselected speech intent: " + scene["speech_intent"]
    )
    if not 100 <= len(system) <= 3000 or not 100 <= len(user) <= 1500:
        raise ValueError("Speech prompt exceeded fixed token-budget proxy")
    return system, user, blueprint.person_id


def checked_generated(result: object) -> dict:
    if not isinstance(result, dict):
        raise ValueError("Provider returned nonmapping")
    text = result.get("text")
    if (not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_CHARS
            or any(ord(c) < 32 and c not in "\n\t" for c in text)):
        raise ValueError("Generated speech missing, too long or includes control data")
    tokens = {}
    for field in ("prompt_tokens", "completion_tokens"):
        value = result.get(field)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid provider usage counter")
        tokens[field] = value
    model = result.get("model_id")
    if not isinstance(model, str) or not 1 <= len(model) <= 120:
        raise ValueError("Provider model identity missing")
    return {"text": text.strip(), "model_id": model, **tokens}


def evaluate(backend, *, max_output: int | None = None) -> dict:
    protocol = verified_protocol()
    generation = protocol["generation"]
    max_tokens = generation["max_output_tokens"]
    if max_output is not None and max_output != max_tokens:
        raise ValueError("Provider cannot override the preregistered response budget")
    rows = []
    original_blueprints = {}
    for role in protocol["roles"]:
        bp = load_g9_trial().g9_blueprint(role)
        original_blueprints[role] = hashlib.sha256(
            json.dumps(bp.to_record(), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        for scene in protocol["scenes"]:
            for arm in protocol["profiles"]:
                system, user, person_id = prompt_for(role, scene, arm)
                prompt_sha = hashlib.sha256(
                    (system + "\n\n" + user).encode("utf-8")
                ).hexdigest()
                start = time.perf_counter()
                response = backend.generate(
                    system, user, max_tokens=max_tokens,
                    temperature=generation["temperature"],
                    seed=generation["seed"],
                )
                seconds = time.perf_counter() - start
                generated = checked_generated(response)
                key = f"{role}:{scene['id']}:{arm}"
                rows.append({
                    "role": role, "person_id": person_id,
                    "scene": scene["id"], "profile_arm": arm,
                    "preselected_speech_intent": scene["speech_intent"],
                    "actor_original_blueprint_sha256": original_blueprints[role],
                    "prompt_sha256": prompt_sha,
                    "generation_seconds": seconds,
                    "fixture_only": backend.label == "fixture",
                    **generated,
                    "blind_id": hashlib.blake2b(
                        key.encode("utf-8"), digest_size=8,
                        person=b"ox-g16g-voice").hexdigest(),
                })
    if len(rows) != 48 or len({r["blind_id"] for r in rows}) != 48:
        raise AssertionError("Incomplete six-actor voice factorial")
    reviewer = sorted(({
        "blind_id": row["blind_id"], "scene": row["scene"],
        "speech": row["text"],
        "known_context": next(x["known_context"] for x in protocol["scenes"]
                              if x["id"] == row["scene"]),
        "intended_speech_act": row["preselected_speech_intent"],
    } for row in rows), key=lambda x: x["blind_id"])
    durations = [x["generation_seconds"] for x in rows]
    return {
        "schema": 1, "provider": backend.label,
        "fake_provider": backend.label == "fixture",
        "real_text_generation_measured": backend.label != "fixture",
        "actors": len(protocol["roles"]), "scenario_types": 4,
        "profile_arms": protocol["profiles"],
        "samples": len(rows),
        "median_generation_seconds": statistics.median(durations),
        "p95_generation_seconds": sorted(durations)[47],
        "total_generation_seconds": sum(durations),
        "total_prompt_tokens_reported": sum(
            x["prompt_tokens"] or 0 for x in rows
        ),
        "total_completion_tokens_reported": sum(
            x["completion_tokens"] or 0 for x in rows
        ),
        "evennia_commands_sent": 0,
        "action_requests_generated": 0,
        "human_blind_review_complete": False,
        "model_choice_adopted": False,
        "original_blueprint_sha256_by_role": original_blueprints,
        "rows": rows, "blind_review_sheet": reviewer,
        "limitations": (
            "Generated text was not submitted as an action. Automated shape "
            "checks cannot establish naturalness, fidelity, voice or trust. "
            "A separate blinded human evaluation is required. CPU latency "
            "is hardware-specific, not a measured dollar price."
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=("fixture","qwen-local","gemini-hosted"),
                   required=True)
    p.add_argument("--gguf-path", type=Path)
    p.add_argument("--gemini-model")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    protocol = verified_protocol()
    if args.provider == "fixture":
        backend = FakeSpeechBackend()
    elif args.provider == "qwen-local":
        if args.gguf_path is None:
            p.error("Native speech test requires verified local GGUF")
        backend = LocalQwenSpeech(
            args.gguf_path,
            protocol["providers"]["local_qwen"]["gguf_sha256"],
        )
    else:
        if not args.gemini_model:
            p.error("Hosted speech requires explicit selected model ID")
        backend = HostedGeminiSpeech(args.gemini_model)
    outcome = evaluate(backend)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "provider": outcome["provider"], "samples": outcome["samples"],
        "real_generation": outcome["real_text_generation_measured"],
        "seconds": outcome["total_generation_seconds"],
        "prompt_tokens": outcome["total_prompt_tokens_reported"],
        "completion_tokens": outcome["total_completion_tokens_reported"],
    }, sort_keys=True))
    print("OX_G16G_SPEECH_ONLY_48_SAMPLES_RECORDED")


if __name__ == "__main__":
    main()
