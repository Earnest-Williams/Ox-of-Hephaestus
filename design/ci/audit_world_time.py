#!/usr/bin/env python3
"""Deterministic source inventory for Ox's future unified world-time authority.

This is a read-only *static* audit, not a game clock or a claim of full
dynamic coverage. It intentionally excludes vendored Evennia, tests and
migrations. The first stage identifies independent world timer entrypoints,
explicit game/wall time reads, and world step calls so the future pause
barrier has a reviewable migration inventory.

Examples:
  python design/ci/audit_world_time.py
  python design/ci/audit_world_time.py --json
  python design/ci/audit_world_time.py --json --output /tmp/ox-time-audit.json
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path

ROOTS = (
    "game/world",
    "game/commands",
    "game/typeclasses",
    "game/server",
    "services/ai-handler/src/ox_ai",
)
REQUIRED = (
    "game/world/continuous_ship_physics.py",
    "game/world/live_clock.py",
    "game/commands/clock.py",
    "services/ai-handler/src/ox_ai/ports/evennia/clock.py",
)

# Deliberately lexical: an audit cannot infer all runtime calls. Each result
# remains a code-review prompt, not evidence that any work actually ran.
TIME_READS = {
    "gametime.gametime", "gametime.runtime",
    "datetime.now", "datetime.utcnow", "datetime.datetime.now",
    "datetime.datetime.utcnow", "timezone.now",
}
WALL_READS = {
    "time.time", "time.monotonic", "time.perf_counter",
    "datetime.now", "datetime.utcnow", "datetime.datetime.now",
    "datetime.datetime.utcnow", "timezone.now",
}
SCHEDULERS = {
    "asyncio.sleep", "asyncio.create_task", "time.sleep", "delay",
    "create_script", "gametime.schedule", "gametime.real_seconds_until",
}
WORLD_STEPS = {
    "tick_continuous_physics", "tick_game_clock",
    "tick_rounds", "tick_captain_obligations",
}


@dataclass(frozen=True, order=True)
class Site:
    path: str
    line: int
    kind: str
    symbol: str
    context: str


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return prefix + "." + node.attr if prefix else node.attr
    return ""


def classify_call(name: str) -> str | None:
    if not name:
        return None
    if name in TIME_READS or name.endswith(".gametime"):
        return "external_game_clock"
    if name in WALL_READS:
        return "wall_clock"
    if name in WORLD_STEPS or any(
            name.endswith("." + target) for target in WORLD_STEPS):
        return "world_tick"
    if (name in SCHEDULERS
            or any(name.endswith("." + target) for target in (
                "delay", "schedule", "create_script", "sleep", "create_task"))):
        return "scheduler"
    if (name in {"CanonicalShipEvent.objects.create", "CrewEvent.objects.create"}
            or name.endswith(".emit_event")):
        return "event_writer"
    return None


class Visitor(ast.NodeVisitor):
    def __init__(self, path: str):
        self.path = path
        self.context: list[str] = []
        self.found: set[Site] = set()

    def record(self, node: ast.AST, kind: str, symbol: str) -> None:
        self.found.add(Site(
            path=self.path, line=node.lineno, kind=kind, symbol=symbol,
            context=".".join(self.context),
        ))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.context.append(node.name)
        if any(isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
               and child.name == "at_repeat" for child in node.body):
            self.record(node, "scheduled_script", node.name + ".at_repeat")
        self.generic_visit(node)
        self.context.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.context.append(node.name)
        self.generic_visit(node)
        self.context.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.context.append(node.name)
        self.generic_visit(node)
        self.context.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = dotted(node.func)
        kind = classify_call(name)
        if kind is not None:
            self.record(node, kind, name)
        self.generic_visit(node)


def is_production(path: Path) -> bool:
    return (path.suffix == ".py"
            and not any(part in {"tests", "test", "migrations", "__pycache__"}
                        for part in path.parts)
            and not path.name.startswith("test_")
            and not path.name.endswith("_test.py"))


def inspect_source(path: str, source: str) -> list[Site]:
    parsed = ast.parse(source, filename=path)
    visitor = Visitor(path)
    visitor.visit(parsed)
    return sorted(visitor.found)


def audit(root: Path) -> dict:
    root = root.resolve()
    missing = [path for path in REQUIRED if not (root / path).is_file()]
    if missing:
        raise ValueError(
            "Required current world-time integration sources missing: "
            + ", ".join(missing))
    sites: list[Site] = []
    scanned = 0
    for directory in ROOTS:
        base = root / directory
        if not base.is_dir():
            continue
        for source_path in sorted(base.rglob("*.py")):
            relative = source_path.relative_to(root)
            if not is_production(relative):
                continue
            scanned += 1
            sites.extend(inspect_source(
                relative.as_posix(), source_path.read_text(encoding="utf-8")))
    sites.sort()
    counts = Counter(site.kind for site in sites)
    return {
        "schema_version": "ox-world-time-audit/1",
        "scope": list(ROOTS),
        "scanned_files": scanned,
        "site_count": len(sites),
        "counts": dict(sorted(counts.items())),
        "sites": [asdict(site) for site in sites],
        "dynamic_coverage": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.root)
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    if args.json:
        print(encoded, end="")
    else:
        print("Ox world-time static inventory (not dynamic coverage)")
        print(f"Files scanned: {report['scanned_files']}; sites: {report['site_count']}")
        for kind, count in report["counts"].items():
            print(f"  {kind}: {count}")
        for site in report["sites"]:
            print(
                f"{site['path']}:{site['line']} "
                f"{site['kind']} {site['symbol']} [{site['context']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
