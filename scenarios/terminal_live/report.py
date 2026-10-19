"""CI operator-side summary; reads only artifacts AFTER Evennia has stopped."""
import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--crew", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    world = json.loads(a.world.read_text())
    crew = json.loads(a.crew.read_text())
    ids = crew["connected_characters"]
    assert len(ids) == 6 and len(set(ids.values())) == 6
    assert world["all_six_dead"] and world["fatal"]
    assert all(v.startswith("#") for v in ids.values())
    assert {row["role"] for row in crew["decisions"]} == set(ids)
    assert all(x["operation"].startswith("terminal_")
               and x["role"] in ids for x in world["receipted_attempts"])
    assert len(world["receipted_attempts"]) == len(crew["decisions"])
    assert {x["request_id"] for x in world["receipted_attempts"]} == {
        x["receipt_id"] for x in crew["decisions"]
    }
    if crew["controller"] == "goap":
        assert crew["inference_calls"] == 0
    else:
        assert crew["inference_calls"] >= len(crew["decisions"])
    # World secret must never appear in a handler-side actor observation or
    # action trace. Read the raw file to include all nested fields.
    hidden = world["operator_only_hidden_cause"]
    assert hidden not in a.crew.read_text()
    counts = Counter(row["operation"] for row in world["receipted_attempts"])
    lines = [
        "# G6: authenticated Evennia terminal-failure trial",
        "",
        f"**Controller:** {crew['controller']}, **seed:** {crew['seed']}",
        f"**Actual authenticated characters:** {len(ids)} (one socket each)",
        f"**World fatality:** {world['all_six_dead']} at scenario minute {world['world_minute']}",
        f"**Reserve bottles unused:** {world['reserve_left']}",
        f"**Work receipts:** {len(world['receipted_attempts'])}; **model calls:** {crew['inference_calls']}",
        "",
        "## Authenticated work attempts",
        "",
        "| World min | Role | World command | Receipt status |",
        "|---:|---|---|---|",
    ]
    receipts = {x["request_id"]: x for x in world["receipted_attempts"]}
    for decision in crew["decisions"]:
        result = receipts[decision["receipt_id"]]
        lines.append(
            f"| {decision['world_minute_at_attempt']} | {decision['role']} "
            f"| {decision['decision']} | {result['status']} |"
        )
    lines.extend(["", "## Work distribution", ""])
    for action, qty in sorted(counts.items()):
        lines.append(f"- {action}: {qty}")
    lines.extend([
        "",
        "These are six authenticated Evennia characters, actual rooms and "
        "real world-verified commands. The catastrophic atmosphere subsystem "
        "and death clock are new opt-in G6 mechanics; the rest of the freighter "
        "is not a completed voyage simulation.",
        "",
    ])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text("\n".join(lines), encoding="utf-8")
    print("OX_G6_AUTHENTICATED_WORLD_AUDIT_PASS", crew["controller"], crew["seed"], flush=True)


if __name__ == "__main__":
    main()
