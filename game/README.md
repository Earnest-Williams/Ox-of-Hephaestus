# Ox of Hephaestus — playable ship fixture

**Status:** first playable **real Evennia game world** with an optional,
short-lived, in-process Concordia control trial. This is NOT the external
AI-to-Evennia socket transport or a production spaceship simulation.

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
automatic watch scheduler. The three crew are usually idle, but the
experimental in-process trial below can temporarily drive Ari through
Concordia without creating a privileged world action API.
Names, roles, duty descriptions and room positions are persisted as game
objects and will be used for later agent/character mapping.

## Experiment: can an AI engineer physically fix P-01?

The operator stages a pump fault and places **Ari Sen on the Bridge**.
Ari's Concordia entity receives only ordinary game text (starting with
`look`). It selects from commands visible in its **current compartment**.
Movement, `inspect`, `isolate`, `repair`, and `commission` pass through
the *real* Evennia command dispatcher with Ari as the acting character. The
AI has no direct access to the pump's database Attributes. The operator
independently checks the actual game state and event actor IDs.

The deterministic CI test runs a **scripted model** through Concordia: it
checks mechanical end-to-end integration, physical location checks and
anti-cheating rules. It **does not** prove that a language model could infer
the repair sequence. The *live* experiment below makes the model itself
choose each next action; it may succeed, take wrong actions or fail.

To run the offline integration tests (Python 3.12+, from repo root):

```bash
python -m pip install -e .
python -m pip install -e './services/ai-handler[concordia]'
cd game
evennia test world.tests.test_agent_repair --verbosity=2
```

To run a **real model** against your local test database, use an OpenAI-
compatible local endpoint such as a separately installed Ollama or vLLM
server. Here is an example configuration; replace the model ID with a
model actually served on your machine. From the repository root:

```bash
python -m pip install -e .
python -m pip install -e './services/ai-handler[concordia]'
cd game
evennia migrate
export OX_LLM_BASE_URL=http://127.0.0.1:11434/v1
export OX_LLM_MODEL=your-local-model-id
export OPENAI_API_KEY=local-placeholder
export OX_TRIAL_TRACE=../.ox-state/pump-trial.jsonl
evennia shell --command="from world.ai_repair import live_trial; live_trial()"
```

Set `OPENAI_API_KEY` to a real key, omit `OX_LLM_BASE_URL`, and select a
supported OpenAI model if using the hosted service instead. The hosted
Concordia GPT adapter and the generic local-compatible adapter have
different completion-parameter support.

**Side effects:** The live command really moves Ari, faults P-01 if normal,
and can alter its persistent game state. Use only on a disposable/local test
database. The test starts with a physical fault; it does not reset any prior
pump event history. It caps the number of AI decisions at 16 by default
(`OX_TRIAL_MAX_STEPS` can change that, up to 50). The JSONL trace records
observations, proposed commands and returned text, while the shell prints
each action and the authoritative verdict. No inference endpoint, API key,
network access or model weights are provided by this repo.

The *physical* success condition is strict: Ari must choose to finish **and**
have used ordinary character commands to isolate, repair and commission
P-01 in that order, with the game recording Ari's DBRef as actor and the
pump returning to normal. A final text claim alone fails.

This remains **a development harness embedded in Evennia's local process**,
not a completed `WorldPort` transport or independently running agent. The
next production-oriented integration still needs ordinary external client
sessions, reconnection and action reconciliation.

## Test without launching the server

From the repository root, install Evennia and run the targeted DB-backed suite:

```bash
python -m pip install -e .
cd game
evennia test world.tests.test_ship --verbosity=2
```

Use `--verbosity=2` rather than `-v 2`: Evennia reserves `-v` for its version display, which would skip the test suite. The command above uses Evennia's default testing configuration; the separate CI bootstrap validates the real Ox game settings against a persistent database.

This command runs the five ship-only tests without requiring an LLM framework;\nthe separate agent repair suite above installs Concordia explicitly.\n\nThis uses a temporary Django test database and exercises the actual
Evennia objects, exit topology, persisted pump state, permission and location
checks, bounded inspection, roster, and idempotent bootstrap. The
`Ox spaceship game tests` CI job runs these tests when `game/` changes.
It is separate from the nine-environment inherited upstream Evennia matrix.

**Next step:** connect the external handler through ordinary character
sessions; no agent is allowed to write pump state directly or observe a remote
compartment except through deliberate in-game instrumentation.
