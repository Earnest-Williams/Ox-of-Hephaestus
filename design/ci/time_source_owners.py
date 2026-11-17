#!/usr/bin/env python3
"""Reviewable ownership gate for independently scheduled Ox world scripts.

This covers *only* statically found class-level at_repeat entrypoints from
audit_world_time.py. It is not proof of dynamic coverage of callbacks,
handler processes, imported aliases, or Evennia's internal schedulers.

Every new directly detected world timer must be deliberately classified here
before the repository can claim it is ready for time-authority migration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_world_time import audit

SCHEMA = "ox-world-time-script-owners/1"
AUDIT_SCHEMA = "ox-world-time-audit/1"

# Ownership is descriptive, not permission for any clock to advance paused
# gameplay. The unified time controller does not exist yet.
OWNERS = {
    ("game/world/continuous_ship_physics.py",
     "ContinuousShipPhysicsClock.at_repeat"): {
        "owner": "continuous_physics",
        "role": "installed_authoritative_physics_stepper",
        "pause_migration": "shared_clock_barrier_required",
    },
    ("game/world/live_clock.py",
     "ShipDutyClock.at_repeat"): {
        "owner": "engineering_duty_and_social",
        "role": "watch_rounds_captain_obligations",
        "pause_migration": "shared_clock_barrier_required",
    },
    ("game/world/terminal_failure.py",
     "TerminalClock.at_repeat"): {
        "owner": "disposable_terminal_scenario",
        "role": "opt_in_g6_atmosphere_emergency",
        "pause_migration": "scenario_isolation_and_barrier_required",
    },
}


def classify_scripts(report: dict) -> dict:
    """Reject unknown/missing direct timers and return stable review metadata."""
    if (not isinstance(report, dict)
            or report.get("schema_version") != AUDIT_SCHEMA
            or report.get("dynamic_coverage") is not False
            or not isinstance(report.get("sites"), list)):
        raise ValueError("Missing or incompatible static time audit")
    found = []
    for site in report["sites"]:
        if not isinstance(site, dict):
            raise ValueError("Malformed inventory site")
        if site.get("kind") != "scheduled_script":
            continue
        path, symbol = site.get("path"), site.get("symbol")
        if not isinstance(path, str) or not isinstance(symbol, str):
            raise ValueError("Invalid scheduled script identity")
        found.append((path, symbol))
    if len(found) != len(set(found)):
        raise ValueError("Duplicate script entrypoint in time audit")
    unexpected = sorted(set(found) - set(OWNERS))
    missing = sorted(set(OWNERS) - set(found))
    if unexpected or missing:
        raise ValueError(
            "World script owner review required. "
            f"Unclassified: {unexpected}; Missing expected: {missing}")
    entries = [
        {"path": path, "entrypoint": symbol, **OWNERS[path, symbol]}
        for path, symbol in sorted(found)
    ]
    return {
        "schema_version": SCHEMA,
        "source_schema_version": AUDIT_SCHEMA,
        "scheduled_entrypoints": len(entries),
        "runtime_completeness_claim": False,
        "pause_enabled": False,
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = (
        json.loads(args.audit.read_text(encoding="utf-8"))
        if args.audit else audit(args.root)
    )
    owners = classify_scripts(report)
    result = json.dumps(owners, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
