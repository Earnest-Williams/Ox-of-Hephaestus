"""Verify and aggregate the G10 six-actor experiment without cherry-picking."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

ROLES = ("lin", "ari", "iona", "mara", "teo", "captain")
CASES = (
    "restraint_disclosure", "new_scrubber_alarm", "conflicting_testimony",
    "watch_swap", "finite_spares", "fatigued_watch",
)
ORDERS = ("canonical", "reverse", "rotate")


def assess(root: Path) -> dict:
    seen_roles, rows, pair_events, stability, routing = set(), [], [], [], []
    role_reports = {}
    for role in ROLES:
        path = root / (role + ".json")
        if not path.is_file():
            raise FileNotFoundError("A required actor report is missing: " + role)
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("role") != role or report.get("engine") != "decider-q4":
            raise PermissionError("Report contains wrong actor or mock inference")
        if (report.get("schema") != 1 or not report.get("hypothetical_only")
                or report.get("world_commands_sent") != 0
                or report.get("fixture_run") != 39872687597
                or report.get("reference_work_receipt_count") != 5):
            raise PermissionError("Actor report lacks authenticated world provenance")
        local = report["rows"]
        if (len(local) != 36 or report["model_calls"] != 36
                or len(report["memory_pairs"]) != 18
                or len(report["order_stability"]) != 12
                or len(report["routing_trials"]) != 6):
            raise AssertionError("Missing factor arm or route coverage")
        expected = {(case, order, projection)
                    for case in CASES for order in ORDERS
                    for projection in (True, False)}
        recorded = {(r["case"], r["position_pattern"], r["projection"])
                    for r in local}
        if recorded != expected or len(recorded) != len(local):
            raise AssertionError("Missing/duplicated paired decision treatment")
        for row in local:
            if (row["role"] != role or row["model"] != "decider-q4"
                    or row["model_calls"] != 1 or row["world_commands_sent"] != 0
                    or not 0 <= row["chosen_position"] < 5
                    or len(row["native_scores"]) != 5
                    or not abs(sum(row["native_scores"].values()) - 1) < .021
                    or row["indexed_memory_count"] < 100):
                raise AssertionError("Unverified native actor decision record")
        pair_events.extend(dict(pair, role=role) for pair in report["memory_pairs"])
        stability.extend(dict(item, role=role) for item in report["order_stability"])
        routing.extend(dict(item, role=role) for item in report["routing_trials"])
        rows.extend(local)
        seen_roles.add(role)
        role_reports[role] = {
            "choices": dict(Counter(x["choice"] for x in local)),
            "against_goap": sum(x["different_from_goap"] for x in local),
            "potentially_unsafe": report["unsafe_intents"],
            "memory_changes": report["memory_choice_changes"],
            "order_stable": report["order_stable_case_arms"],
            "routing_llm_chances": {
                item["case"]: item["probability"]
                for item in report["routing_trials"]
            },
        }
    if seen_roles != set(ROLES) or len(rows) != 216:
        raise AssertionError("Incomplete six-person factorial experiment")
    per_case = {}
    for key in CASES:
        subset = [r for r in rows if r["case"] == key]
        if len(subset) != 36:
            raise AssertionError("Missing one factorial case")
        per_case[key] = {
            "choice_counts": dict(Counter(r["choice"] for r in subset)),
            "memory_changes": sum(p["changed"] for p in pair_events
                                  if p["case"] == key),
            "position_stable": sum(x["order_invariant"] for x in stability
                                   if x["case"] == key),
            "position_compared": 12,
            "goap_departures": sum(r["different_from_goap"] for r in subset),
            "unsafe_hypothetical_proposals": sum(
                r["potentially_unsafe_intent"] for r in subset
            ),
        }
    natural_rates = defaultdict(list)
    for r in routing:
        if r["trials"] != 256 or not 0 < r["probability"] < 1:
            raise AssertionError("Missing deterministic routing rate coverage")
        natural_rates[r["role"]].append(r["llm_routes"])
    if any(len(natural_rates[role]) != 6 for role in ROLES):
        raise AssertionError("Role does not have all six routing situations")
    return {
        "schema": 1,
        "model": "Decider 4B Q4_K_M",
        "input": "6 actual G9 actor states after authenticated 205-turn voyage",
        "hypothetical_new_situations": True,
        "world_actions_sent": 0,
        "actor_count": 6,
        "scenario_count": 6,
        "memory_arms": 2,
        "menu_order_arms": 3,
        "native_model_decisions": len(rows),
        "routing_draws": len(routing) * 256,
        "distinct_actions_selected": sorted({row["choice"] for row in rows}),
        "memory_sensitive_pairs": sum(r["changed"] for r in pair_events),
        "memory_pair_count": len(pair_events),
        "position_invariant_case_arms": sum(x["order_invariant"] for x in stability),
        "position_case_arm_count": len(stability),
        "choices_different_from_goap": sum(
            r["different_from_goap"] for r in rows
        ),
        "potentially_unsafe_hypothetical_proposals": sum(
            r["potentially_unsafe_intent"] for r in rows
        ),
        "native_choice_distribution": dict(Counter(r["choice"] for r in rows)),
        "chosen_index_counts": dict(Counter(r["chosen_position"] for r in rows)),
        "roles": role_reports,
        "cases": per_case,
        "warnings": [
            "Hypothetical situations were explicitly authored; only personal memories and the original past world incident receipts are authenticated.",
            "The model only proposes among five bounded planning options; none are submitted to Evennia.",
            "Order sensitivity is a measurement, not an invitation to tune a prompt to cherry-pick results.",
            "The GOAP baseline is symbolic in the same hypothetical beliefs and does not assert that an operation actually occurred.",
            "High or low risky-intent counts alone do not demonstrate realistic character motivation or real-world safety."
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = assess(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps({
        k: v for k, v in result.items()
        if k in ("native_model_decisions", "routing_draws", "memory_sensitive_pairs",
                 "position_invariant_case_arms", "choices_different_from_goap",
                 "potentially_unsafe_hypothetical_proposals",
                 "native_choice_distribution", "chosen_index_counts")
    }, sort_keys=True))
    print("OX_G10_WIDE_DECIDER_ASSAY_PASS")


if __name__ == "__main__":
    main()
