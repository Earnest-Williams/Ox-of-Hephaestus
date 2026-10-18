# Ox AI handler — native Concordia, GOAP and live crew

**Status (18 October 2026):** Two independently runnable supervisor
variants exist: three legacy crew or five crew with cargo and environmental
specialists. Five ordinary nonprivileged Evennia characters have their own
native Concordia memory/checkpoints. The P4e full-server trial passed actual
cargo, atmospheric and coolant work, hails and a deliberately lost cartridge
ACK across a handler restart. This is **not** deployed production software
or proof of unconstrained multi-agent intelligence.
[Current status](../../design/STATUS.md).

## G2b isolated nonblocking cognition (PR #33)

The three- and five-crew handler supervisors now ask Concordia to choose via
`await self.choose(...)`, with a `DecisionScheduler` running native
synchronous LLM calls against a **detached per-agent snapshot**, off the
asyncio I/O loop. A new private observation on the live agent invalidates the
older response; only a still-current, identity-bound proposed action is
adopted. No inference worker has world command or database access.

The scheduler limits global concurrent model calls, one worker per character,
inference deadlines, hourly quotas and safe failure. Timed-out threads are
quarantined until their provider finishes. Addressed hails from different
characters can progress concurrently on separate authenticated sockets, with
ordinary durable social-action receipts. Actual repair and inspection
sequencing remains tied to existing world-grounded duties.

**Single-host control:** both supervisor entry points use a common POSIX
`.ox-state/supervisor.lock` acquired before socket login. Starting another
three- or five-crew controller on the same host is refused. This does NOT
provide remote-host/distributed fencing or guarantee an immediate stop for a
blocking Python thread.

See [G2b design and evidence](../../design/prototypes/g2-nonblocking-cognition.md)
and the [new CI workflow](../../.github/workflows/ox-g2-nonblocking-cognition.yml).

## G2a event-triggered private crew agendas (merged PR #29)

Each of the five independent characters now owns a separate
`AgentAgenda` record under `agendas[role]` in the existing supervisor
checkpoint. Each record is bound to the character DB ref; neither world
permissions nor the separate Concordia memories are shared. A work item
stores its actual addressed world-event ID/sequence, scheduling priority,
disposition, reason, reconsideration event kinds, and bounded history.

The five-crew handler materializes the cargo and environmental duties
first. `service_departments()` now chooses a ready world-grounded
obligation by priority rather than looping Teo then Mara. A new urgent
world alarm may interrupt an in-progress lower-priority task **only after
a real step**, and the interrupted job resumes its saved `WorkStepLedger`
records later. A model-deferred or world-blocked task persists with an
explicit world-event trigger and is not silently deleted or immediately
rerun on replay. An operator-supplied A-01 replenishment event is used
only in CI to demonstrate reopening a real failed attempt: the original
failed request remains immutable, and a new request ID is generated
after new source-world evidence arrives.

The [G2a workflow](../../.github/workflows/ox-g2-crew-agendas.yml)
includes local schema/security tests and two separate full-server
process-restart trials: urgent life support preempts partly completed
cargo work, and a missing-cartridge refusal is reconsidered after
the world physically resupplies and addresses Teo.

**Scope:** The agenda data structure is generic across all five agents,
but actual automatic work creation is currently integrated only into the
two specialist jobs. Time-based due dates, independent goal selection,
delegation/escalation communications and independent goal selection remain
future G2 work. G2b adds nonblocking *choice inference* without implementing
open-ended parallel physical action scheduling. Never treat the private status `completed`
as proof without the corresponding world-authoritative action receipts.

## P4j globally receipted cargo and environmental work (merged PR #27)

New cargo-restraint and scrubber operations from the five-crew supervisor
are now recorded in that specialist job's own `work_steps` under
`physical-<step-index>-<operation>`. Each stores the actor, immutable
operation/target binding, ID and world receipt. A handler crash before
send or after world commit can be recovered under the original global ID.

**Upgrade compatibility:** when an existing P4e checkpoint contains a
non-null `specialist_jobs[role].pending`, the handler reconciles the
original actor-bound **fixture** receipt, then resumes new steps using
the shared world ledger. It must never manufacture a fresh request ID
to substitute for that prior uncertain outcome.

The CI-only commands `interrupt-mara-restow-<point>`,
`interrupt-teo-replace-<point>` and `finish-<mara|teo>`
support independent-process fault injection. The
[specialist recovery matrix](../../.github/workflows/ox-p4j-specialist-recovery.yml)
also seeds a genuine old-format P4e checkpoint.

World inventory is not yet transferable between crew, and postponed
specialist tasks do not yet have agenda-style reconsideration triggers.

## P4i bridge, watch and hail recovery (merged PR #26)

The three- and five-crew supervisors persist the bridge alarm's
`begin_alarm` stage before attempting an `oxwork radio ship`. If
the handler loses the radio acknowledgment or stops before its initial
isolation, it resumes the same global request and validates the actual
radio observation delivered to the current watch.

Engineering handover and addressed player hails also use
`WorkStepLedger` with original request IDs, world-owned
`oxworkreceipt` reconciliation, and independent recipient-only evidence.
The handler can stop before transmission or after the world commit
without repeating the same decision as a new external action.
`handover_work` and `hail_work` are private per-supervisor checkpoint
entries; they do not grant world authority.

CI-only entry points `begin-radio-interrupt-<point>`,
`handover-interrupt-<offer|accept>-<point>` and
`hails-interrupt-answer-<point>` simulate loss at
`prepared`, `committed` and `ack` boundaries. The
[real-server coordination tests](../../.github/workflows/ox-p4i-coordination-recovery.yml)
exercise three separate full-server scenarios in isolated worlds.

This stage does not convert cargo/environmental supervisor requests or
guarantee PostgreSQL concurrent-writer isolation.

## P4h restartable pump-work supervisor

P4h adds `src/ox_ai/runtime/work_steps.py`: a durable per-incident
handler-side stage ledger. For `watch_service resume`, each of repair,
release request, separate safety approval, commissioning and incident
resolution now checkpoints the exact work ID **before** sending a command.
A restarted process reconciles the same ID using ordinary authenticated
`oxworkreceipt` and never generates a substitute ID for an unknown result.
Only the world's explicit no-receipt response permits resubmitting the
same ID. The legacy isolation stage retains its existing receipt for
backward compatibility.

The CI-only modes are
`resume-interrupt-<repair|request|approve|commission|resolve>-<prepared|committed|ack>`.
They deliberately stop execution around a world commit and require a fresh
external handler process to finish without double action. The
[real-server restart gate](../../.github/workflows/ox-p4h-pump-recovery.yml)
exercises interrupted work on both sides of the network.

This is **pump-cycle recovery**, not universal crew recovery. Initial radio,
human hails, engineering watch transfers and specialist task bookkeeping
still use their previous bounded procedures. A full all-action recovery
guarantee, PostgreSQL writer-contention testing and wider ship automation
remain outstanding.

## P4g typed work adapter (first stage)

`DurableEvenniaPort.submit_work(ActionRequest)` and
`reconcile_work(request_id)` use ordinary authenticated character sessions
and world-owned `oxwork` / `oxworkreceipt` commands. Physical operations
and a finite set of coordination verbs now share a typed, actor-bound global
request namespace. Invalid targets, arguments and another character's
identity are refused before the client sends anything.

The legacy `submit()` and `reconcile()` methods remain in place so that
P3–P4e integration tests keep their existing command behavior. The
new methods do **not**, by themselves, persist intent prior to transmission:
callers must checkpoint the request ID first. The merged P4h pump
supervisor now uses this ledger for five later stages; handover and hail
stages still need conversion.

## P4f complete addressed event replay (PR #22)

`src/ox_ai/runtime/watch_service.py` now reads the version-2
`oxinbox` protocol page by page, rather than stopping at 128 events.
Pages are fetched through each character's ordinary authenticated Evennia
connection; cross-recipient frames and nonprogressing cursors fail closed.
Each character's newly authorized events enter that character's own
Concordia state before `inbox_cursors` is saved in the supervisor ledger.
This ordering makes interrupted replay safe to repeat.

**Compatibility limitation:** current P4e consumers need historic alarm,
handover and hail context, so they still scan all recipient-private pages
from cursor zero on each processing pass. The saved high-water cursors do
not yet eliminate those full scans. Independent incremental agenda and
retention support are planned in `design/ROADMAP.md`. This milestone does
not make every arbitrary physical or social action crash-transactional.

## P4e merged five-crew runtime

[Merged PR #19](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/19)
adds `src/ox_ai/runtime/five_crew_service.py` with five independently
authenticated native Concordia agents and scoped crew-event dispatch. It
handles real cargo and environmental faults through world-confirmed
equipment-specific receipts. For an **ephemeral, empty test world only**:

~~~sh
# From game/, using disposable credentials and no existing bot accounts:
evennia shell --command="from world.transport_probe import provision; provision(include_specialists=True)"

# From repository root, after starting Evennia and seeding game events:
python -m ox_ai.runtime.five_crew_service serve
~~~

This handler requires `.ox-state/p4e-ids.json` for five distinct
character dbrefs and also retains the original `.ox-state/p3a-ids.json`.
It persists per-character native checkpoints under `.ox-state/p4e/` and a
specialist task ledger in `.ox-state/p4e-supervisor.json`.
**Do not run it alongside the original three-person `watch_service`.**

The five-person CI simulates a real A-01 replacement with a lost
acknowledgement and verifies safe recovery by a new process, alongside
cooling, cargo, player hails and the game-owned watch handover.
Read [P4e design and limitations](../../design/prototypes/p4e-five-crew-autonomy.md).
All 13 focused Ox workflows passed on the final PR commit; P4e is merged.

## Components actually implemented

| Location | Function |
| --- | --- |
| `src/ox_ai/agents/crew.py` | Single native Concordia `EntityAgentWithLogging`, bounded proposals, per-agent journal and native checkpoint |
| `src/ox_ai/agents/live_concordia.py` | Five role-specific Concordia entities (Lin, Ari, Iona, Mara, Teo), individual observations, deferred choices and restoration |
| `src/ox_ai/agents/goap_crew.py` and `src/ox_ai/planning/` | Deterministic engineering action search; beliefs checked against observations |
| `src/ox_ai/ports/evennia/client.py` | Normal `v1.evennia.com` authenticated WebSocket and character identity proof |
| `src/ox_ai/ports/evennia/durable.py` | World-owned actor-bound equipment action receipts and recovery queries |
| `src/ox_ai/runtime/watch_service.py` | Historical three-crew watch supervisor with `serve`, `begin` and `resume` |
| `src/ox_ai/runtime/work_steps.py` | P4h private durable intent ledger, world-work reconciliation and explicit pre-send/post-commit interruption gates |
| `src/ox_ai/runtime/five_crew_service.py` | P4e five-crew event-driven watch, cargo and environmental work with a durable interrupted-cartridge test |
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

1. The current implementation covers **five distinct crew** across
   cooling, cargo and environmental departments, not general skill
   progression, a complete freighter or unscripted social AI.
2. `serve` is code that can run as a separate process; no init system,
   deployment recipe, load testing or long-running uptime guarantee
   has been validated.
3. P4h tested exact-ID reconciliation of **repair, release request,
   independent reviewer approval, commissioning and resolution** across
   several handler process restarts, building on P4b isolation recovery.
   Initial radio, autonomous watch handovers, player hails and specialist
   work bookkeeping still lack a universal all-action restart guarantee.
   Unverifiable results fail closed rather than being fabricated or
   retried under a new ID.
4. CI does not measure generalized unscripted hosted-model behavior,
   tokens or economics for many concurrently acting agents.
5. There is **no public handler API** or browser observatory; P5 was
   expressly deferred.

The external handler and the game can operate without any visual
dashboard. See [architecture](../../ARCHITECTURE.md) and
[contracts](../../contracts/README.md) for the authority boundary.
