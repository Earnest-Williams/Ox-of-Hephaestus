"""G9 acceptance of staged, six-client real-Evennia Decider/GOAP decisions.

Consumes actual G8 actor checkpoint records and trace from the same
authenticated six-client world session. It does not simulate people, repair
faults, substitute responses, or infer unrecorded private beliefs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


WORKED = {"cargo": ("restow", "certify"),
          "scrubber": ("isolate", "replace", "restart")}


def evaluate(root: Path, *, turns: int = 205) -> dict:
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    if state.get("turn") != turns or state.get("cognition_mode") != "decider":
        raise AssertionError("Incomplete real-Decider longitudinal run")
    trace = state["trace"]
    if len(trace) != turns or [r["turn"] for r in trace] != list(range(1, turns + 1)):
        raise AssertionError("Every operational/social turn needs one recorded event")
    seen_receipts = set()
    world_work = []
    for fault in state["faults"]:
        if fault["at"] > turns:
            continue
        if not fault["seen"] or not fault["completed"]:
            raise AssertionError("Fault not recovered: " + fault["name"])
        receipts = fault["receipts"]
        if [r["operation"] for r in receipts] != list(WORKED[fault["kind"]]):
            raise AssertionError("Missing/reordered world work receipts")
        for receipt in receipts:
            request_id = receipt["request_id"]
            if request_id in seen_receipts or not receipt["source_event_id"]:
                raise AssertionError("Missing/duplicated world work proof")
            seen_receipts.add(request_id)
            world_work.append(receipt)

    # The decision's private witness IDs may only refer to earlier speech
    # delivered to that actor by the authenticated room-local clients.
    heard_by = {}
    for entry in trace:
        if not entry["kind"].startswith("spoken_"):
            continue
        speaker = entry["actor"]
        for listener in entry["heard_by"]:
            if listener == speaker:
                continue
            event = "g8-speech-" + str(entry["turn"]) + "-" + speaker
            heard_by[(listener, event)] = entry["turn"]

    roster = ("lin", "ari", "iona", "mara", "teo", "captain")
    counts = {}
    for role in roster:
        brain = json.loads((root / (role + ".brain.json")).read_text(encoding="utf-8"))
        if brain["identity"]["agent_id"] != "ox.person.g9." + role:
            raise PermissionError("Checkpoint belongs to another person")
        if brain.get("character_blueprint", {}).get("person_id") != "g9." + role:
            raise PermissionError("Checkpoint personality not actor-bound")
        if brain["memory_now_turn"] != turns or brain["pending_requests"]:
            raise AssertionError("Incomplete or unresolved actor cognition")
        records = brain["temporal_memories"]
        if len(records) <= 3:
            raise AssertionError("No witnessed memory acquisition")
        ids = [r["memory_id"] for r in records]
        if len(ids) != len(set(ids)):
            raise AssertionError("Repeated memory identity after process restart")
        counts[role] = {
            "memories": len(records),
            "witnessed_speech": sum(r["kind"] == "witnessed_speech" for r in records),
            "world_receipts": sum(r["kind"] == "world_receipt" for r in records),
            "cognition_revision": brain["cognition_revision"],
            "observation_revision": brain["revision"],
        }

    audit = state.get("route_audit", [])
    if len(audit) < 8:
        raise AssertionError("Insufficient operational G9 boundaries reached")
    if len({(x["actor"], x["turn"]) for x in audit}) != len(audit):
        raise AssertionError("A decision boundary was repeated")
    model_calls = 0
    departures = 0
    witnessed_boundaries = 0
    for item in audit:
        if item["route"] not in ("llm", "goap"):
            raise AssertionError("Unrecorded strategy")
        expected_calls = int(item["route"] == "llm")
        if item["model_calls"] != expected_calls:
            raise AssertionError("Unexpected native model call accounting")
        model_calls += item["model_calls"]
        departures += item["deviated"]
        if item["deviated"] and item["route"] != "llm":
            raise AssertionError("GOAP baseline cannot be changed on the GOAP route")
        for source in item["latest_encounter_ids"]:
            if source is None:
                raise AssertionError("Encounter without source provenance")
            witnessed_turn = heard_by.get((item["actor"], source))
            if witnessed_turn is None or witnessed_turn >= item["turn"]:
                raise AssertionError("Private routing context included unwitnessed speech")
            witnessed_boundaries += 1
        actual = trace[item["turn"] - 1]
        if (actual["actor"] != item["actor"]
                or actual["kind"] != "spoken_" + item["chosen_intent"]
                or actual.get("g9_route") != item):
            raise AssertionError("Model intent did not result in witnessed speech")
    if model_calls < 2 or witnessed_boundaries < 2:
        raise AssertionError("Not enough actual memories reached real Decider choices")
    if len({x["actor"] for x in audit}) < 4:
        raise AssertionError("Insufficient differentiated characters")
    if sum(r["witnessed_speech"] for r in counts.values()) < 30:
        raise AssertionError("No sustained multi-character world conversation")
    report = {
        "schema": 1,
        "mode": "live-evennia-decider-q4-longitudinal",
        "turns": turns,
        "actors": list(roster),
        "route_boundaries": len(audit),
        "decider_calls": model_calls,
        "goap_routes": len(audit) - model_calls,
        "deviations_from_goap": departures,
        "witnessed_context_references": witnessed_boundaries,
        "verified_world_work": world_work,
        "private_memory_counts": counts,
        "choice_trace": audit,
        "notes": [
            "Character-specific memories accumulate from authenticated room-local client-heard speech and world receipts, not from omniscient transcript imports.",
            "Speech source IDs are G8 verifier keys built from authenticated delivery; only work receipt IDs are server-issued.",
            "Model-selected speech is still submitted as an ordinary bounded say and is verified by counterpart clients.",
            "Not a psychological accuracy benchmark, a fully autonomous production supervisor, or a model comparison."
        ],
    }
    (root / "g9-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(".ox-state/g9"))
    parser.add_argument("--turns", type=int, default=205)
    args = parser.parse_args()
    report = evaluate(args.root, turns=args.turns)
    print(json.dumps({
        "turns": report["turns"],
        "route_boundaries": report["route_boundaries"],
        "decider_calls": report["decider_calls"],
        "goap_routes": report["goap_routes"],
        "deviations_from_goap": report["deviations_from_goap"],
        "witnessed_context_references": report["witnessed_context_references"],
        "world_work_receipts": len(report["verified_world_work"]),
        "private_memory_counts": report["private_memory_counts"],
        "decider_choice_trace": [
            {
                "turn": row["turn"], "actor": row["actor"],
                "counterpart": row["target"],
                "symbolic_intent": row["baseline_intent"],
                "decider_intent": row["chosen_intent"],
                "encountered_witnesses": row["encountered_history_count"],
                "world_receipt_memories": row["world_receipt_memory_count"],
            }
            for row in report["choice_trace"] if row["route"] == "llm"
        ],
    }, sort_keys=True))
    print("OX_G9_REAL_LONGITUDINAL_PASS")


if __name__ == "__main__":
    main()
