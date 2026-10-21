# Install and run the Ox prototype

> **Scope:** These are **local development** instructions for the playable
> Evennia ship and the independent AI handler. They do not deploy a
> publicly accessible MUD or the postponed observatory.
> [Current feature status](design/STATUS.md).

## Prerequisites

- Python **3.12+**, a virtual environment, Git and dependency access.
- A local machine capable of running Evennia; ports **4000**, **4001** and
  **4002** must be available on loopback.
- No LLM server, hosted API key or GPU is required for the **deterministic**
  P4 integration tests.

## Current scope versus optional trials

The instructions below bring up the **seven-room primary ship** and the
normal authenticated external handler. The G6 terminal-loss scenario,
G7 social GOAP apartment, G8 six-client 500-decision memory experiment,
G11 manually dispatched hosted-model A/B trial, and G12 6/20/40
local-brain profiler are **separate, bounded research/test entry points**.
They are not automatically enabled by installing Ox and do not constitute
a deployed simulation with 40 active ship crew. See the
[verified milestone index](design/STATUS.md) and
[AI handler experiments](services/ai-handler/README.md).

## 1. Install the game and service

From the root of this checkout:

~~~sh
python -m venv .venv
# Activate .venv using your shell's normal command.
python -m pip install -e .
python -m pip install -e './services/ai-handler[concordia,transport]'
~~~

Concordia is deliberately pinned to a reviewed Git commit; installing the
`[concordia]` extra requires Git/network access. `[transport]` installs the
Evennia WebSocket client dependency. The separate interface scaffold is
optional: `python -m pip install -e ./services/interface`.

## 2. Start the playable ship

From the **game directory**:

~~~sh
cd game
evennia migrate
evennia start
~~~

First setup runs `game/server/conf/at_initial_setup.py` and builds the
ship without modifying the inherited `evennia/` engine. If working with
an older game database, run once in `game/`:

~~~sh
evennia shell --command="from world.bootstrap import build_ship; build_ship()"
~~~

Connect with a MUD client to `127.0.0.1:4000`, or open
`http://127.0.0.1:4001` for Evennia's web client. From Limbo, `board`
enters the Bridge; then `aft`, `engineering`, `inspect pump`,
`inspect console` and `look roster` explore the fixture.

Stop the local server with `evennia stop` from `game/`. Development
settings bind to loopback, disable new account registration and use
`LOCKDOWN_MODE`. Do not expose them to untrusted networks.

## 3. Run tests

Most handler tests need neither an Evennia server nor any hosted model:

~~~sh
# From the repository root:
python -m unittest discover -s services/ai-handler/tests -v
python -m unittest discover -s services/ai-handler/tests -p 'test_p4a_cognition.py' -v
python -m unittest discover -s services/ai-handler/tests -p 'test_p4b_watch_runtime.py' -v
~~~

SQLite-backed game rule tests run from `game/`:

~~~sh
cd game
evennia test world.tests.test_ship world.tests.test_live_cooperation world.tests.test_autonomy --verbosity=2
~~~

Use `--verbosity=2`; Evennia treats `-v` as its version switch.

**Recommended full integration:** GitHub **Actions → Ox P4b autonomous
two-incident ship → Run workflow**, branch `main`. It creates throwaway
accounts and a temporary game database and tests the entire two-incident
handover and loss-of-ACK recovery from separate processes. It does not
require you to supply a model key or maintain a local game database.
Other focused P3/P4 Actions remain available; the inherited broad
Evennia test matrix is not the default Ox workflow.

## 4. Run the external AI supervisor (development only)

The handler is a real separate process, but the repository **does not**
provide production-grade provisioning, a daemon unit or monitoring.
Before starting it you need:

1. An already-running Evennia ship with Ari, Lin and Iona;
2. Dedicated accounts authorised to puppet their respective game
   characters, and a local `.ox-state/p3a-ids.json` mapping;
3. The `OX_PROBE_PASSWORD` environment variable matching the current
   **development fixture** accounts.

The test-only `game/world/transport_probe.py` module can provision these
accounts *once on an empty, disposable database* (see the
[handler README](services/ai-handler/README.md) and
[P4b CI recipe](.github/workflows/ox-p4b-autonomy.yml)).
Its shared test password and resettable fault fixture are not a secure
production identity-management solution.

With the test accounts provisioned and Evennia already started:

~~~sh
# Run from the repository root, NOT game/
python -m ox_ai.runtime.watch_service serve
~~~

The external process opens the normal character WebSockets, restores its
private checkpoints, responds to legitimately delivered ship events and
sleeps on the socket between incidents. The scheduler itself does not
inject faults or repeatedly call a model. The in-game Evennia Script owns
the watch deadline. Do not run this service concurrently with a separate
P4a scenario puppeting the **same** three accounts.

For restart testing, `begin` and `resume` are **special acceptance
commands**: they intentionally forget an isolation ACK so the next
process can reconcile it without repeating the physical action. They
are not normal operational commands; `serve` is the runtime entry point.

### Five-specialist and optional captain mode

The `watch_service` example above is the historical **three-person**
configuration. For the standard five-specialist runtime, provision separate
Lin/Ari/Iona/Mara/Teo accounts in a **disposable world**, configure the
five-person identity mapping, and launch
`python -m ox_ai.runtime.five_crew_service serve` instead. Optional
`OX_CAPTAIN_OVERSIGHT=1` adds the independently authenticated sixth captain,
who follows unresolved obligations without inheriting technical permissions.
Do not run the three-person and five/six-person supervisors against the same
world concurrently. Exact fixture provisioning and checkpoint paths are in
the [handler guide](services/ai-handler/README.md) and
[captain protocol](design/prototypes/g3f-captain-followthrough.md).

The current game also exposes G4g/G4h assessed learning via ordinary
character-authorized `oxwork` requests; running the handler does not
automatically schedule study. See the [world guide](game/README.md).

## Model configuration and boundaries

By default the Concordia actor factory uses a **deterministic MockModel**;
this verifies wiring and access control, not emergent reasoning. For a
separate opt-in hosted evaluation, set `OX_COGNITION_PROVIDER=gemini` and
supply `GEMINI_API_KEY` privately. A failed, declined or malformed
decision does not authorize a physical transition. The live
three-agent hosted-model benchmark remains **unverified**.

Equipment isolation, repair and commissioning have durable world-owned,
actor-bound receipts. The two-process test exercises unknown-isolation
recovery, **not arbitrary crash recovery during every later social
command**. There is no permanent public server or browser observatory.

See [game commands](game/README.md), [handler operations](services/ai-handler/README.md)
and the [authority boundary](ARCHITECTURE.md). For framework-only install
questions see the [upstream Evennia setup guide](https://www.evennia.com/docs/latest/).
