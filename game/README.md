# Ox of Hephaestus — playable ship fixture

**Status:** first small **real Evennia game world**, before the AI handler
connects. This is not a ship simulator or a multiplayer deployment.

The game lives under `game/`, alongside but **not inside** the forked
`evennia/` engine package. A fresh database contains three connected ship
compartments, three ordinary game-world crew characters, a persistent cooling
pump with four operational states, an instrumented bridge console, and a posted
watch roster. The crew are *idle bodies*, not autonomous agents or sessions.

## Start locally

Use Python 3.12+ from the repository root, in a virtual environment:

```bash
python -m pip install -e .
cd game
evennia migrate
evennia start
```

Evennia's first-startup account/setup process creates Limbo. After initial
setup, the `at_initial_setup` hook seeds the ship. Connect locally using a MUD
client on `localhost:4000` or the web client at
`http://localhost:4001`. From Limbo, type `board` to enter the bridge.

If the initial hook was skipped or the database already existed from an older
setup, explicitly run **from the `game/` directory**:

```bash
evennia shell --command="from world.bootstrap import build_ship; print(build_ship())"
```

This builder uses stable tags and is safe to rerun: it does **not** duplicate
rooms, reset pump faults, reposition crew or discard event history.

The default settings listen only on loopback and set `LOCKDOWN_MODE`. A unique
local Django signing secret is generated in an ignored
`game/server/conf/.local-secret` file; optionally supply `OX_SECRET_KEY`
instead. Do not use these development settings for a public server.

## Explore and operate

The miniature floor plan is:

```text
      Bridge --aft --> Connecting Passage -- engineering --> Engineering
             <-- fore --                    <-- out --------
```

From the ordinary user character:

```text
board
look
look console
look roster
aft
engineering
look pump
inspect pump
```

A developer-controlled character can run `shipengineer` to assume an
engineering role, then `shipfault pump` while physically present in
Engineering to introduce the deterministic failure. Test the recovery:

```text
inspect pump
shipfault pump
inspect pump
isolate pump
repair pump
commission pump
inspect pump
```

State transitions are `normal -> low_pressure -> isolated -> repaired ->
normal`. The state and event journal are stored in Evennia's database.
`look console` on the bridge reads live pump telemetry, but it does not
provide remote physical access to the pump. A bridge officer or character
outside Engineering cannot repair the pump.

The roster is currently static **assignment metadata**; it is not yet an
automatic watch scheduler. Nor are the three crew connected to an AI backend.
Names, roles, duty descriptions and room positions are persisted as game
objects and will be used for later agent/character mapping.

## Test without launching the server

From the repository root, install Evennia and run the targeted DB-backed suite:

```bash
python -m pip install -e .
cd game
evennia test world.tests --verbosity=2
```

Use `--verbosity=2` rather than `-v 2`: Evennia reserves `-v` for its version display, which would skip the test suite. The command above uses Evennia's default testing configuration; the separate CI bootstrap validates the real Ox game settings against a persistent database.

This uses a temporary Django test database and exercises the actual
Evennia objects, exit topology, persisted pump state, permission and location
checks, bounded inspection, roster, and idempotent bootstrap. The
`Ox spaceship game tests` CI job runs these tests when `game/` changes.
It is separate from the nine-environment inherited upstream Evennia matrix.

**Next step:** connect the external handler through ordinary character
sessions; no agent is allowed to write pump state directly or observe a remote
compartment except through deliberate in-game instrumentation.
