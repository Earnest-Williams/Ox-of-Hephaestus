# Ox AI handler — native Concordia, GOAP and live crew

**Status (18 October 2026):** An independent Python process can puppet
three nonprivileged Evennia characters, maintain separate native
Concordia memories and watch obligations, use GOAP for known pump work,
and wait for authenticated world events. A two-incident recovery test
passed on real persistent Evennia. This is **not** a deployed production
service or proof of general unscripted social intelligence.
[Current status](../../design/STATUS.md).

## Components actually implemented

| Location | Function |
| --- | --- |
| `src/ox_ai/agents/crew.py` | Single native Concordia `EntityAgentWithLogging`, bounded proposals, per-agent journal and native checkpoint |
| `src/ox_ai/agents/live_concordia.py` | Three role-specific Concordia entities (Lin, Ari, Iona), individual observations, deferred choices and restoration |
| `src/ox_ai/agents/goap_crew.py` and `src/ox_ai/planning/` | Deterministic engineering action search; beliefs checked against observations |
| `src/ox_ai/ports/evennia/client.py` | Normal `v1.evennia.com` authenticated WebSocket and character identity proof |
| `src/ox_ai/ports/evennia/durable.py` | World-owned actor-bound equipment action receipts and recovery queries |
| `src/ox_ai/runtime/watch_service.py` | Event-driven external watch loop, normal `serve` mode and acceptance `begin`/`resume` modes |
| `src/ox_ai/scenarios/` | Historical P2 mocks and real P3/P4 integration demonstrations |
| `src/ox_ai/scheduler/`, `src/ox_ai/ports/mock/` | Deterministic P2 mock-world supervision and fault acceptance |
| `src/ox_ai/inference/` | Metering and optional bounded Gemini/local-model adapters |
| `src/ox_ai/api/` | **Package marker only; no implemented HTTP inspection API** |

The provisional `src/ox_ai/ports/base.py` `WorldPort` Protocol is not
a published versioned network API. The deployed remote endpoint
envisioned in early documents was **not** needed for the P3/P4 tests:
each character uses normal Evennia client connections.

## Install and test

From the repository root, Python 3.12+:

~~~sh
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests -v
~~~

Install actual native Concordia and WebSocket transport for live clients:

~~~sh
python -m pip install -e './services/ai-handler[concordia,transport]'
python -m unittest discover -s services/ai-handler/tests -p 'test_concordia_*.py' -v
python -m unittest discover -s services/ai-handler/tests -p 'test_p4a_cognition.py' -v
python -m unittest discover -s services/ai-handler/tests -p 'test_p4b_watch_runtime.py' -v
~~~

Concordia is pinned in `pyproject.toml` to the reviewed source revision;
the published 2.4.0 release lacks the interrupt scheduling files
examined during selection. Do not silently replace the pin with a
floating branch or assume a newer model API has identical parameters.
The hosted model, credentials and model weights are not bundled.

## Run the independent live supervisor

The actual runtime entry is:

~~~sh
# From the repository ROOT, with Evennia running and crew accounts ready:
python -m ox_ai.runtime.watch_service serve
~~~

It needs `OX_PROBE_PASSWORD`, three already provisioned ordinary accounts
`OxBotLin`, `OxBotAri`, `OxBotIona` with valid puppet locks, and
`.ox-state/p3a-ids.json` matching each persistent character's Evennia
dbref. In P4 tests, the characters share a randomly generated
**disposable CI credential**; this is not a production credential design.

### Reproduce the development fixture (DISPOSABLE DATABASE ONLY)

Install the root Evennia package as described in
[INSTALL.md](../../INSTALL.md). From the root before provisioning, set
a private test password of at least 20 characters, for example:

~~~sh
export OX_PROBE_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export EVENNIA_SUPERUSER_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export EVENNIA_SUPERUSER_USERNAME=OxTrialOwner
export EVENNIA_SUPERUSER_EMAIL=owner@example.invalid
cd game
evennia migrate --noinput
evennia shell --command="from world.transport_probe import provision; provision(); from world.live_crew import fixture_setup; fixture_setup(scheduled_clock=True)"
evennia start
cd ..
~~~

Only use these commands on a **fresh, isolated game database**:
`transport_probe.provision()` refuses to overwrite accounts;
`fixture_setup` injects a physical test fault and resets prototype
incident context. First server start must have the necessary owner
account bootstrap environment. The fixture stores the bot/character
mapping in the repository-local ignored `.ox-state/` directory.

The P4a scenario may then be run from the root using
`python -m ox_ai.scenarios.p4a_concordia_crew`. It drives the initial
fault and watch handover as a bounded CI-style demonstration.
Do **not** concurrently launch `serve` or a second character controller
using those same bot sessions.

The normal `serve` entry point loads stored individual brain snapshots
from `.ox-state/p4b/` (or earlier P4a snapshots), reads recipient-scoped
world inboxes, identifies the world-posted active engineer, and
suspends on incoming game events when idle. An operator must still
inject or generate a legitimate new world incident; the handler itself
does not fabricate pump failures or advance the world clock.

**`begin` and `resume` are special acceptance-test modes**, not
an everyday operational protocol. The first intentionally checkpoints
an unknown pump-isolation ACK and terminates; the second starts a
new process, queries Evennia's same actor-bound receipt and completes
the incident without resubmitting isolation. The
[P4b full-server workflow](../../.github/workflows/ox-p4b-autonomy.yml)
runs the two processes against one persisted SQLite game and verifies
exactly two complete cooling-pump lifecycles, with Iona as second-watch
repairer and Ari as independent reviewer.

## What an agent can and cannot infer

- Each character's native Concordia state contains only recipient-authorized
  world `ox_event` messages and physical readouts genuinely delivered
  through that character's socket. Private inbox replay is filtered
  by world identity and checked again by the handler.
- Routine P-01 procedures are represented as GOAP actions with
  preconditions and predicted effects. These are *beliefs*, not writes
  to the game.
- Concordia chooses among explicit, validated action options,
  including **defer**. A declined action cannot silently become
  a physical pump command. An observation revision protects against
  selecting from obsolete context.
- Actual physical `isolate`/`repair`/`commission` transitions require
  an accepted Evennia `oxaction` request and an actor-bound receipt.
  Unknown outcomes must be reconciled; ordinary room text or the
  model's narrative is never a receipt.
- Lin's bridge alarm is not an omniscient engineer event; Iona and Ari
  learn about it through legitimate communications. A reviewer
  must independently inspect P-01 before release authorization.

The current world rules implement one known pump and finite social
procedures. They are not an open-ended general crew planner.

## Deterministic vs hosted models

**CI uses a deterministic native Concordia `MockModel`**, which
chooses offered actions so we can test session plumbing, state
ownership and failure handling reproducibly. Success is **not**
evidence that three hosted models spontaneously negotiate, infer
novel equipment physics or maintain long-term relationships.

A prior *single-engineer* Gemini trial in the local command harness
succeeded; it remains an opt-in hosted model evaluation and is
separate from P4. For the P4 actor factory, `OX_COGNITION_PROVIDER=gemini`
plus private `GEMINI_API_KEY` enables its bounded-choice adapter.
The current multi-crew hosted-model quality/cost evaluation is not
a passing required CI gate. Timeouts, quota failures and invalid
selections fail closed.

The standalone model-free GOAP unit tests still require no Concordia:

~~~sh
python -m unittest discover -s services/ai-handler/tests -p 'test_goap_*.py' -v
~~~

Older single-engineer in-process experiments are described in
[`game/README.md`](../../game/README.md#earlier-single-engineer-experiments-retained).
Use them to compare GOAP and bounded model decisions against the
same physical fixture; do not confuse them with the independent
handler runtime.

## Historical P2 mocks retained as regression fixtures

The stdlib-only deterministic world is still useful for rapid tests:

~~~sh
python -m ox_ai.scenarios.watch_handover
python -m ox_ai.scenarios.coolant_fault
~~~

These simulate private observations, scripted watch behavior,
an urgent-recheck interruption and an unknown action receipt,
**without** real Evennia sockets. The live P3 and P4 workflows now
cover external transport, world state and actual two-incident
behavior separately.

Read [Scenario 0](../../scenarios/shift_handover/README.md),
[Scenario 1](../../scenarios/coolant_fault/README.md),
[P4a integration](../../design/prototypes/p4a-live-cognition.md)
and [P4b runtime](../../design/prototypes/p4b-autonomous-watch.md).

## Known runtime limits

1. The current proof covers **three existing crew** and **one real pump**,
   not general skill progression, an entire starship or social AI.
2. `serve` is code that can run as a separate process; no init system,
   deployment recipe, load testing or long-running uptime guarantee
   has been validated.
3. Restart-after-unknown-**isolation** is tested. Later non-idempotent
   social commands and arbitrary mid-episode service failures do not
   yet have a general crash-safe workflow. The handler must fail
   closed instead of fabricating completion or blindly replaying.
4. CI does not measure generalized unscripted hosted-model behavior,
   tokens or economics for many concurrently acting agents.
5. There is **no public handler API** or browser observatory; P5 was
   expressly deferred.

The external handler and the game can operate without any visual
dashboard. See [architecture](../../ARCHITECTURE.md) and
[contracts](../../contracts/README.md) for the authority boundary.
