"""Operator-only G6b postmortem: correlate continuous choices with world receipts."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--crew", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    world = json.loads(args.world.read_text(encoding="utf-8"))
    crew = json.loads(args.crew.read_text(encoding="utf-8"))
    ids = crew["connected_characters"]
    assert set(ids) == {"lin", "ari", "iona", "mara", "teo", "captain"}
    assert len(set(ids.values())) == 6, "Six unique authenticated body bindings required"
    assert world["all_six_dead"] and world["fatal"]
    assert crew["all_six_confirmed_dead"]
    assert crew["termination_reason"] == "all_six_world_confirmed_deaths"
    assert not crew["turn_cap_reached"]
    assert crew["turn_count"] == len(crew["decisions"])
    assert crew["turn_count"] <= crew["turn_limits"]["total"]
    assert all(
        n <= crew["turn_limits"]["per_character"]
        for n in crew["turn_counts_by_role"].values()
    )
    assert crew["inference_calls"] == 0 and crew["controller"] == "goap"
    assert world["seed"] == crew["seed"]
    assert world["case_id"] not in ("", None)
    assert world["operator_only_hidden_cause"] not in args.crew.read_text(encoding="utf-8")

    decisions = crew["decisions"]
    assert len(decisions) > 24, "Agents must outlive the old 24-total-decision cutoff"
    assert set(d["role"] for d in decisions) == set(ids)
    assert all(crew["heard_critical"].values()), "Each crew must receive the actual critical alarm"
    assert all(
        any(d["heard_critical_at_choice"] and d["role"] == role for d in decisions)
        for role in ids
    ), "Each actor must reconsider once AFTER the critical warning"

    work = [d for d in decisions if d["kind"] == "work"]
    movement = [d for d in decisions if d["kind"] == "travel"]
    waiting = [d for d in decisions if d["kind"] == "monitor"]
    actual = {r["request_id"]: r for r in world["receipted_attempts"]}
    assert len(actual) == len(work), "Each physical action needs one world WorkReceipt"
    assert set(actual) == {d["receipt_id"] for d in work}
    for d in work:
        receipt = actual[d["receipt_id"]]
        assert receipt["role"] == d["role"]
        assert receipt["operation"] == d["decision"]
        assert receipt["status"] == d["result"]
        assert receipt["request_id"] == d["receipt_id"]
    assert not any(d["kind"] == "travel" and d.get("arrived_at") is None for d in decisions)
    assert all(d["result"] == "arrived" for d in movement)
    assert all(d["result"] == "waiting_for_new_evidence" for d in waiting)

    counts = Counter(d["decision"] for d in decisions)
    lines = [
        "# G6b: continuous GOAP during terminal atmosphere loss",
        "",
        "**Actual Evennia universe:** six separately authenticated accounts, persistent fatality.",
        f"**Seed:** {crew['seed']}   **World death minute:** {world['world_minute']}",
        f"**Termination:** {crew['termination_reason']} "
        f"(ceiling {crew['turn_limits']['total']} total, "
        f"{crew['turn_limits']['per_character']} per crew member).",
        f"**Decisions:** {len(decisions)} including {len(work)} receipted actions, "
        f"{len(movement)} chosen movements and {len(waiting)} monitoring choices.",
        f"**Model calls:** {crew['inference_calls']}   "
        f"**A-01 spare cartridges after scenario:** {world['cartridges_at_a01']}   "
        f"**Emergency bottles left:** {world['reserve_left']}",
        "",
        "## Per-character choices (chronological)",
        "",
    ]
    for role in ids:
        own = sorted((d for d in decisions if d["role"] == role),
                     key=lambda d: d["world_minute"])
        lines.extend([
            f"### {role} — {len(own)} decisions",
            "",
            "| Minute | Reported oxygen (kPa) | Action | Outcome | After critical? |",
            "|---:|---:|---|---|---|",
        ])
        for row in own:
            lines.append(
                f"| {row['world_minute']} | {row['oxygen_kpa']} "
                f"| {row['decision']} | {row['result']} "
                f"| {'yes' if row['heard_critical_at_choice'] else 'no'} |"
            )
        lines.append("")
    lines.extend(["## Action distribution", ""])
    for verb, qty in sorted(counts.items()):
        lines.append(f"- {verb}: {qty}")
    lines.extend([
        "",
        "### Interpretation rules",
        "",
        "- A cartridge exchange receipt reports only the physical maintenance; "
        "any effect on atmosphere must be checked with a later observation.",
        "- The decision limits stop runaway trials without fabricating deaths.",
        "- An action rejected by the world is not a successful physical transition.",
        "- A monitor or movement decision is a genuine decision, but not a WorkReceipt.",
        "- An independently received critical alarm must lead to reconsideration.",
        "- This remains a bounded menu and authored GOAP policy, not unconstrained AGI.",
        "",
    ])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("OX_G6B_CONTINUOUS_OPERATOR_AUDIT_PASS",
          "decisions", len(decisions), "work", len(work),
          "travel", len(movement), "watch", len(waiting), flush=True)


if __name__ == "__main__":
    main()
