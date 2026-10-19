#!/usr/bin/env python3
"""Regression guard for focused Ox Actions workflow triggering.

Runs without third-party dependencies inside ox-documentation.yml.
Only tests workflow scope, not GitHub's event delivery or branch protection.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
DOCUMENTATION = "ox-documentation.yml"
NEGATIVE_MARKDOWN = "!**/*.md"

# Test narrow representative paths, including the exact prior regression.
DOCUMENT_ONLY = (
    "README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "design/ROADMAP.md",
    "design/prototypes/g3-epistemics.md",
    "game/README.md",
    "services/ai-handler/README.md",
    "services/interface/README.md",
    "contracts/README.md",
    ".agents/docs/testing.md",
)


def read_filters(source: str) -> dict[str, list[str]]:
    """Read the limited, existing Ox 'on: <event>: paths:' YAML convention.

    This is intentionally not a general YAML parser: unexpected trigger
    formatting must fail visibly rather than silently weakening a gate.
    """
    lines = source.splitlines()
    if "on:" not in lines:
        return {}
    start = lines.index("on:") + 1
    result: dict[str, list[str]] = {}
    event: str | None = None
    inside_paths = False
    for line in lines[start:]:
        if line and not line.startswith((" ", "#")):
            break
        found = re.fullmatch(r"  (pull_request|push|workflow_dispatch):\s*", line)
        if found:
            event = found.group(1)
            inside_paths = False
            continue
        if re.match(r"^  [a-z_]+:", line):
            event = None
            inside_paths = False
            continue
        if event not in ("push", "pull_request"):
            continue
        if line == "    paths:":
            result[event] = []
            inside_paths = True
            continue
        if inside_paths:
            entry = re.fullmatch(r"      -\s+(.+?)\s*", line)
            if entry:
                result[event].append(entry.group(1).strip().strip("\"'"))
            elif line.strip():
                inside_paths = False
    return result


def match(pattern: str, path: str) -> bool:
    """Translate the small GitHub glob subset in these Ox path filters."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append(r"(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.fullmatch("".join(out), path) is not None


def would_run(patterns: list[str], paths: tuple[str, ...]) -> bool:
    for path in paths:
        enabled = False
        for pattern in patterns:
            negative = pattern.startswith("!")
            if match(pattern[1:] if negative else pattern, path):
                enabled = not negative
        if enabled:
            return True
    return False


def main() -> int:
    failures = []
    checked = 0
    doc = (WORKFLOWS / DOCUMENTATION).read_text(encoding="utf-8")
    doc_events = read_filters(doc)
    for event in ("pull_request", "push"):
        patterns = doc_events.get(event)
        if not patterns:
            failures.append(f"{DOCUMENTATION} missing {event} document paths")
        elif not would_run(patterns, DOCUMENT_ONLY):
            failures.append(f"{DOCUMENTATION} does not cover Markdown documentation")
        elif not would_run(patterns, (".github/ci/check_ox_ci_scope.py",)):
            failures.append(f"{DOCUMENTATION} does not monitor its regression guard")
        elif not would_run(patterns, (".github/workflows/ox-p4e-five-crew.yml",)):
            failures.append(f"{DOCUMENTATION} does not monitor code-workflow edits")

    for workflow in sorted(WORKFLOWS.glob("ox-*.yml")):
        if workflow.name == DOCUMENTATION:
            continue
        source = workflow.read_text(encoding="utf-8")
        events = read_filters(source)
        for event, patterns in events.items():
            checked += 1
            if not patterns:
                failures.append(f"{workflow.name}:{event} has no paths")
                continue
            # The existing broad Ox directory globs are intentionally
            # retained for code changes; markdown must be excluded AFTER
            # positives, so even explicit historical design links cannot
            # cause a code-test run.
            broad = any(
                not p.startswith("!") and
                (p.endswith("/**") or p.endswith(".md"))
                for p in patterns
            )
            if broad and patterns[-1] != NEGATIVE_MARKDOWN:
                failures.append(
                    f"{workflow.name}:{event} needs final {NEGATIVE_MARKDOWN}"
                )
            if would_run(patterns, DOCUMENT_ONLY):
                failures.append(
                    f"{workflow.name}:{event} launches code tests for docs-only edits"
                )
            if not would_run(patterns, (f".github/workflows/{workflow.name}",)):
                failures.append(
                    f"{workflow.name}:{event} does not cover its own workflow file"
                )
        if any(
            any(not p.startswith("!") and
                (p.endswith("/**") or p.endswith(".md")) for p in patterns)
            for patterns in events.values()
        ):
            if not re.search(
                r"(?m)^  cancel-in-progress:\s*\$\{\{\s*github.event_name == 'pull_request'\s*\}\}\s*$",
                source,
            ):
                failures.append(f"{workflow.name} missing PR-only supersession cancellation")

    # Both sides of a mixed change must be visible: negative Markdown
    # filters must not silence real Python changes.
    for name, expected in (
        ("ox-ship-world.yml", "game/world/bootstrap.py"),
        ("ox-scaffold.yml", "services/ai-handler/src/ox_ai/agents/live_concordia.py"),
        ("ox-g5-adversarial-voyage.yml", "game/world/bootstrap.py"),
    ):
        events = read_filters((WORKFLOWS / name).read_text(encoding="utf-8"))
        if not would_run(events.get("pull_request", []), (expected, "game/README.md")):
            failures.append(f"{name} must still run for mixed code/documentation")

    for failure in failures:
        print(f"CI scope ERROR: {failure}", file=sys.stderr)
    print(f"Ox CI scope: checked {checked} automatic code-workflow event filters; {len(failures)} errors")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
