# G19 T0 — live world-time integration inventory

**Status:** audit tooling, not runtime time control. Supports the
[unified time-authority contract](time-authority.md), accepted in PR #160.

`design/ci/audit_world_time.py` performs a deterministic, standard-library
AST scan of the Ox's own production Python code. It deliberately excludes
vendored Evennia, migrations and tests. It lists timer-script `at_repeat`
entry points, game-time and wall-time reads, scheduled work, known
world-step calls and canonical event-write sites. For each discovery it
records the file, line, containing function/class, and classification.

Run from the repository root:

```sh
python -m unittest discover -s design/ci -p 'test_time_authority_audit.py' -v
python design/ci/audit_world_time.py
python design/ci/audit_world_time.py --json --output time-audit.json
```

The targeted GitHub workflow uploads `time-audit.json` as a short-lived
review artifact and reports counts in the run summary. It validates the
presence of four known integration anchors before accepting its output:

- `game/world/continuous_ship_physics.py` — the bounded G18/G19 world physics clock
- `game/world/live_clock.py` — existing engineering watch, rounds and captain duties
- `game/commands/clock.py` — authenticated character-visible game seconds
- `services/ai-handler/src/ox_ai/ports/evennia/clock.py` — crew AI transport clock observation

## Trust boundaries

This audit is **static discovery, not completeness certification**.
Lexical AST matching cannot prove a timer is installed, that an event was
delivered, which tasks mutate the world at runtime, or which external
plugins and Python aliases indirectly schedule work. It does not inspect
the vendored Evennia implementation. It does not write world state,
advance time, grant authority or publish a private world journal.

The output is a **review queue** for T1, not a green light to enable
player pause. Before implementing pause or watch-until, developers must
trace every potential world mutator (including indirect scheduled
callbacks, backend services and AI tools), confirm it shares the
authoritative clock barrier, and add installed-world tests.

## Next implementation gate

The first migration slice should make source-time ownership explicit
without changing user-visible time: identify every production scheduler,
capture direct/indirect world mutator call chains, and add a
machine-enforceable owner manifest with an intentionally reviewed
baseline. New unclassified time producers should cause the CI audit to
ask for classification rather than silently escaping the migration.
Only then should the atomic pause and stepper be added.
