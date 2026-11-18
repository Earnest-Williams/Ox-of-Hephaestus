# G19 T0 — live world-time integration inventory

**Status:** audit tooling, not runtime time control. Supports the
[unified time-authority contract](https://github.com/Earnest-Williams/Ox-of-Hephaestus/blob/main/design/operations/time-authority.md), accepted in PR #160.

`design/ci/audit_world_time.py` performs a deterministic, standard-library
AST scan of the Ox's own production Python code. It deliberately excludes
vendored Evennia, migrations and tests. It lists timer-script `at_repeat`
entry points, game-time and wall-time reads, scheduled work, known
world-step calls and canonical event-write sites. For each discovery it
records the file, line, containing function/class, and classification.

Run from the repository root:

```sh
python -m unittest discover -s design/ci -p 'test_time_*.py' -v
python design/ci/audit_world_time.py
python design/ci/audit_world_time.py --json --output time-audit.json
python design/ci/time_source_owners.py --audit time-audit.json --output time-script-owners.json
```

The targeted GitHub workflow uploads `time-audit.json` and
`time-script-owners.json` as short-lived review artifacts and reports
discovery counts in the run summary. A second T0 gate,
`design/ci/time_source_owners.py`, requires all directly discovered
`at_repeat` world scripts to match an explicit owner manifest. A newly
introduced `at_repeat` source fails review until consciously classified.
This is a **script entrypoint inventory**, not runtime proof that only
three independently scheduled operations exist.

The initial static run scanned 247 production Python files and found 107
candidate sites. The corrected scan also counts the G6 terminal step, for
108 sites overall: 32 canonical event writers, 25 game-time reads, 18
world-step calls, 17 wall-time reads, 13 scheduler calls, and three directly
declared `at_repeat` scripts. The reviewed scripts are the continuous
G18/G19 physics clock, engineering duty/rounds/captain `ShipDutyClock`,
and operator-only disposable G6 `TerminalClock`. The last one modifies
an explicitly armed terminal-atmosphere scenario and must also obey the
future scenario-specific pause barrier.

The audit validates the presence of five known integration anchors before
accepting its output:

- `game/world/continuous_ship_physics.py` — the bounded G18/G19 world physics clock
- `game/world/live_clock.py` — existing engineering watch, rounds and captain duties
- `game/world/terminal_failure.py` — opt-in G6 terminal incident and its world-step timer
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
