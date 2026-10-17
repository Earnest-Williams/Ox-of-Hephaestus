# AGENTS.md

This file provides guidance to AI coding agents working in this repository.

Evennia is a Python (>= 3.12) framework for building text-based multiplayer online games (MUD/MUX/MUSH/MOO). It is a library, not a game.

## Fork-specific context: Ox of Hephaestus

**Read [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md) before changing this fork.**
This repository hosts the *planned* Ox of Hephaestus spaceship MUD and autonomous
crew simulation, built on Evennia. The game systems and AI handler do **not**
exist yet in the current checkout; most existing source and docs are inherited
from upstream Evennia.

- Preserve the upstream `evennia/` package, its metadata, license, and attribution
  unless a specific justified task requires an engine change.
- Prefer isolated game extensions and a **separately running AI handler** rather
  than modifying the engine to embed each agent.
- First integration: each AI character connects through a normal game client;
  eventual integration: an authenticated dedicated service API. Keep the
  communication adapter replaceable.
- NPC agents may have distinct memory, goals, and schedules, but must follow the
  same world rules and permissions as ordinary characters.
- Treat the human interface as a **third independent component**. It consumes
  an Evennia-facing API for world truth and game actions, and an AI-handler API
  for agent state, inspection, and authorised operator controls.
- Keep the interface out of both databases; distinguish player permissions
  from privileged AI-observability and operator permissions. The game and
  agents must run without a connected interface.
- Background world progress can use meaningful events, deferred catch-up, and
  coarse ticks; do not assume an always-detailed real-time AI call for every NPC.
- Do not describe unimplemented Ox features as operational.
- Engine-specific development commands and the existing links below remain
  useful for work on inherited Evennia components.

## Quick Reference

Use `uv run` to execute commands in the project venv. Prefer `uv` over `pip`.

```bash
uv pip install -e .                          # dev install
make format                                  # black + isort
make lint                                    # black --check
make cleanrot                                # check agent context for rot
uv run pytest .agents/tools/tests/ -v        # agent tooling tests (pytest)
```

**Running Evennia tests**: `make test` requires `evennia` on PATH. With `uv run`, you must init a test game dir first and run from inside it — see [Testing](.agents/docs/testing.md).

## Key Rules

- **TDD**: write tests first. Prefer no-DB tests > mocks > full DB-backed tests.
- **Don't manually format code.** Run `make format` after editing.
- **All code must have Google-style docstrings.** See [Code Style](.agents/docs/code-style.md).
- **After editing agent context files** (anything under `.agents/` or `AGENTS.md`), run `make cleanrot` and fix all warnings before reporting done.

## Skills

Vendor-agnostic skills live in `.agents/skills/`. Vendor directories (`.claude/skills/`, `.codex/skills/`) symlink there.

## Docs

- [Core Beliefs](.agents/docs/core-beliefs.md) — design principles that guide tradeoffs (toolkit not game, think in Python not SQL, hooks not patches, compose don't branch)
- [Architecture](.agents/docs/architecture.md) — two-process model, typeclass system, command system, subsystems, flat API, settings
- [Testing](.agents/docs/testing.md) — running tests, test base classes, DB setup, CI matrix
- [Code Style](.agents/docs/code-style.md) — docstring conventions, command docstring format
- [Development Commands](.agents/docs/commands.md) — install, game lifecycle, test/format commands, PR conventions
- [CI/CD](.agents/docs/ci.md) — GitHub Actions workflows, test matrix, database configs, Docker, secrets
- [GitHub Issues & PRs](.agents/docs/github.md) — listing, searching, and reviewing issues/PRs with `gh` CLI
