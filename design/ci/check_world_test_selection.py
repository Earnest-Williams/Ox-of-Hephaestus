"""Fail if a world test module is not selected by any workflow.

Since world tests moved into ``ox-world-regression.yml`` (shards listed by
label) and feature workflows went thin, a new test module would otherwise
never run. Every ``game/world/tests/test_*.py`` must be named, as
``world.tests.<module>`` or by module name, in some workflow, unless listed
in ``UNSELECTED`` with a reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
TESTS: Path = ROOT / "game" / "world" / "tests"
WORKFLOWS: Path = ROOT / ".github" / "workflows"
UNSELECTED: dict[str, str] = {}


def main() -> int:
    text: str = "\n".join(
        p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml")
    )
    modules: list[str] = sorted(p.stem for p in TESTS.glob("test_*.py"))
    missing: list[str] = [m for m in modules if m not in text and m not in UNSELECTED]
    stale: list[str] = [m for m in UNSELECTED if m not in modules]
    for module in missing:
        print(f"::error::game/world/tests/{module}.py is not selected by any workflow")
    for module in stale:
        print(f"::error::UNSELECTED names {module}, which no longer exists")
    print(f"{len(modules) - len(missing)}/{len(modules)} world test modules selected")
    return 1 if missing or stale else 0


if __name__ == "__main__":
    sys.exit(main())
