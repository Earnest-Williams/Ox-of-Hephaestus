# Ox AI handler — native Concordia, GOAP and live crew

**Current boundary (30 October 2026):** The normal external handler runs
five independently authenticated specialists (optional sixth captain);
the historical three-person supervisor is a separate compatibility mode.
Their ordinary autonomous operations still use the **seven-compartment
proving ground**, not the accepted G19 full-ship physics world. Private
Concordia memory, authenticated world time, durable receipt reconciliation
and bounded GOAP are implemented. G6/G7 scenarios, G11 hosted choice
evaluation and G16 personality policies remain separately scoped or
disabled by default; native G12/G16 model profiling is not a live-crew
simulation. The handler does not autonomously schedule G4g/G4h education
and is not a managed production service.
[Current status](../../design/STATUS.md) ·
[full-ship acceptance](../../design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md).

## G6–G12 accepted experiments and existing transport

- **G6/G6b:** the optional continuous six-client atmospheric crisis uses
  real world receipts, finite resources, evidence-sensitive assessments,
  explicit movement and decision caps. Model-free GOAP and optional hosted
  runs represent different evidence.
  [G6b scope](../../design/prototypes/g6b-continuous-crisis.md).
- **G7/G7b:** an apartment social GOAP domain tests adult conversations,
  changing preferences and negotiated obligations. World-recorded social
  terms bind participants only within the authenticated agreement protocol.
  [Social authority](../../design/prototypes/g7c-world-social-authority.md).
- **G8/G9:** private temporal memories can be seeded at construction and
  reinterpreted from subsequently admitted typed events. Admission,
  rehearsal and reconsideration belong to the owner and advance
  `cognition_revision` whenever private state changes. Detached
  inference is rejected when its world or cognition revision is stale.
  Native `OxMemoryContext` provides bounded, relevant read-only context.
  [G8](../../design/prototypes/g8-private-memory-seeding.md) ·
  [G9](../../design/prototypes/g9-native-memory-context.md).
- **G10/G10b:** G8 virtual turns remain separate from Evennia game seconds.
  `WorldClockPort` validates actor and nonce on an `oxclock` response
  before ordinary native model choices. Quiet periods age private memory
  without handler wall-clock inference.
  [Time contract](../../design/prototypes/g10b-world-clock-read.md).
- **G11/G12:** a manual matched-evidence hosted-model A/B harness is
  distinct from deterministic native profiling at 6/20/40 instantiated
  Concordia brains, not live-world scaling.
  [G11](../../design/prototypes/g11-model-memory-ab.md) ·
  [G12](../../design/prototypes/g12-concordia-profile.md).
- **Current WebSocket:** unrelated frames are buffered in arrival order
  under a finite bound. A full queue causes failure **before** reading
  the next wire frame; malformed unattributable receipts remain unmatched
  while the requested ID, actor and status are verified normally.

G8's real six-client, 500-decision acceptance was **model-free GOAP**,
with five real-world fault repairs, private interpretation revisions,
fixed rotating turns and mostly templated speech. It is not evidence of
general unscripted hosted-model interpersonal reasoning. The sections
below retain their stage-specific historical limitations; consult
[live STATUS](../../design/STATUS.md) for the current feature inventory.

## PR #85 — incremental inbox consumption and its current boundary

PR #85 established full authenticated `oxinbox` hydration and warm
incremental reads. An empty warm read still uses only one completion
page. The attested-cache implementation below now avoids that initial
full-network hydration when an existing local archive passes both local
and world continuity verification.

**PR #86 follow-up:** the handler no longer retains a voyage-length Python
list of old addressed events. Actor-specific SQLite indexes receive validated
128-event world pages. Legacy callers see stable, lazy `EvidenceView`
snapshots, exact event IDs, and indexed receipt/ticket/case/hail queries.
The index enforces the authenticated actor dbref for each record.

**Attested cache reuse:** each actor's local SQLite archive persists across
process restarts. Before reuse, the handler recomputes the digest of every
retained original event and validates the indexed obligation state. It
requires agreement with the atomically saved local seal and a fresh,
nonce-bound `oxjournal` world certificate for that actor's exact prefix.
A successful check permits `oxinbox` to resume **after the verified local
cursor**, instead of transferring and rebuilding the old archive again.
Newly received events, the updated digest, obligation indexes, and hot/cold
compression commit in one SQLite transaction. A crash after that commit but
before a brain checkpoint is recovered by replaying the missed observations
from the verified local archive. Corruption, generation changes, a rewind
or historical divergence fail closed.

World history and local disk deliberately remain O(history). Initial
creation without an archive still replays every addressed event. On later
starts, verification requires O(history) **local** I/O, but old network
pages are not retransmitted. The OOB wake-frame deque remains capped at
256 per actor, without limiting Concordia memory or character snapshots.
[Cache reuse protocol](../../design/prototypes/p4f-attested-cache-reuse.md).

**Hot/cold follow-up:** once fully authenticated pages have been indexed,
the handler keeps the newest 256 addressed event bodies plus exact sources
needed for unresolved world hails/captain tickets and unfinished character
checkpoint work/agenda immediately hot. Other full original events are
losslessly compressed into a separate SQLite cold tier; all old typed
selectors, exact IDs, indexed case/ticket evidence, historical snapshots
and completed-work references still return the original records on demand.
The effective hot cap is 256 **plus actual live pins**; genuine unresolved
obligations cannot be removed to enforce an arbitrary fixed number. Local
cold bodies are integrity-checked, not authoritative. This reduces
uncompressed evidence, **not** total disk records. A repack is eligible
only after at least 2,048 accumulated hot-to-cold demotions **and**
demotions amounting to 25% of the current cold history. This amortizes
whole-archive rewriting as the voyage grows. SQLite's transactional
repack runs **after** the authenticated page/prefix-seal commit and before
advancing a native brain checkpoint. This reclaims allocated B-tree
space without dropping a single old event, receipt or unfinished task.
The durable maintenance counter resets only after successful repack, so
an interruption cannot silently advance world or cognition evidence.
[Lossless physical repack](../../design/prototypes/p4f-lossless-repack.md).
Old world-page retransmission is avoided only after full local and
world-prefix checks.
[Retention and pinning contract](../../design/prototypes/p4f-hot-cold-evidence.md).

The entire inbox read is indexed in one transaction; a broken later page
rolls back all new local rows. Native brain checkpoints are saved before
the supervisor cursor; private agenda and epistemic cursors can backfill
from indexed history after a partial checkpoint. No local cache entry
grants independent world authority. [Full invariants](../../design/prototypes/p4f-indexed-evidence-v2.md).

A partial inbox page, inconsistent event sequence or cursor,
cross-recipient packet, or interrupted WebSocket replay fails closed.
The handler checkpoints each native character *before* advancing the
durable supervisor cursor. No world timestamp, action permission or
ownership boundary changed.

The new authenticated `WorldJournalPort` additionally obtains a
nonce/character/cursor-bound journal generation and historical prefix
digest from the world-owned `oxjournal` command. Its typed client checks
epoch, nonce, actor, digest and head consistency before the result can
be used as continuity evidence. The handler now separately verifies its
entire local archive and pending-obligation projection before trusting
that certificate, while cognition and agenda checkpoint cursors remain
independent.
[Continuity contract](../../design/prototypes/p4f-journal-continuity.md).

The new authenticated `WorldEventPort` supports a separate *exact*
`oxevent <nonce> <event-id>` query without replaying the entire journal.
It verifies the actor, nonce, requested identity and complete original
event in an `ox_event_lookup` reply; `missing` includes both absent and
foreign-recipient IDs, and `oversized` refuses partial events. The
supervisor can obtain an old source proof using `prove_world_event`,
serialized with its own inbox page reads. It does not permit historical
event deletion or allow an old receipt to authorise new physical work.
[Full contract](../../design/prototypes/p4f-world-exact-evidence.md).

The PR #85 fixture covers 2,401 mixed-recipient events and asserts one
world request on a warm empty read. PR #86 additionally tests 8,001
mixed-recipient streamed frames, 12,800 indexed records, exact old-receipt
selection, cross-character rejection and transaction rollback. These are
bounded **request/structure** assertions, not measured provider-model
latency or a proven disk-usage ceiling.

## G3d optional independently elected crew rounds (PR #46, merged)

The existing external five-crew supervisor has an opt-in
`OX_G3D_INDEPENDENT_ROUNDS=1` decision source, independent of fault alarms.
The world must first arm `schedule_rounds` (see
[game notes](../../game/README.md)); a timer event alone says that a
duty window exists, not that equipment has deteriorated.

Each person separately chooses to take a round or defer, uses ordinary
GOAP room travel and authentic `inspect`, and can file a typed, persistent
`round_report` with the world. The world refuses reports without current
first-hand local evidence. Only after the person's own addressed world
report says `maintenance_due` can Mara choose `retension` or Teo
choose `purge`; both physical effects remain role, room and receipt
validated. Normal emergency duties remain higher priority.

Disposable CI trials use
`python -m ox_ai.runtime.five_crew_service round-drain` and require the
feature flag. This executes at most one newly eligible round per actor,
then stops. Ordinary `serve` remains the ongoing event-driven mode,
which never polls models when idle. [Detailed scope and test gate](../../design/prototypes/g3d-independent-rounds.md).
The feature does not implement unrestricted self-generated goals, cross-team
negotiation, independent assignments, or continuous life simulation.

## G3 actor knowledge and real interdepartment supply (PRs #38–40)

Each of five minds has a persistent private epistemic ledger distinguishing
time-scoped world observations from beliefs and source testimony, explicit
known unknowns, unmodeled gaps, and optional retrospective surprises.
Absence of an observation is never automatically zero or false. A world fact
can ALREADY be an unknown unknown from one character's perspective (such as
a pirate hidden behind a moon) while the world/operator knows it. The
agent cannot enumerate that world-side category, and the game must not
feed the answer into its memory, LLM context, or offered actions. The
separate world/operator audit lives in `game/world/epistemic_audit.py`;
it is not an actor command or a world-truth API for the handler.

The world now owns serialised physical cartridge stock and supply orders.
An ordinary oxinventory command reveals only the authenticated actor's
local observable stock, carried items and Evennia timestamp (null means
unverified). Real global WorkReceipt operations request_supply,
accept_supply, collect_supply and deliver_supply move a single physical
item through Mara's own carrier and local station, and only A-01 physically
consumes it in the end.

The optional five-crew cooperative dispatcher makes Teo and Mara reason and
act separately using individually addressed events and world readings.
Enable with OX_G3_COOPERATIVE_SUPPLY=1 when launching five_crew_service
serve. The real cross-restart acceptance trial uses
ox_ai.runtime.supply_trial request, drop-delivery-ack and finish modes.
No browser UI or general-purpose hiring/inventory economy has been added.
[Epistemics](../../design/prototypes/g3-epistemics.md) ·
[Supply model](../../design/prototypes/g3-inventory.md) ·
[Cooperation](../../design/prototypes/g3-cooperation.md).

## G2c local capability discovery and GOAP ship travel (PRs #35–36)

`ox_ai.ports.evennia.capabilities.CapabilityPort` asks the **world** for
only this authenticated character's visible exits and local equipment
affordances, with a nonce and actor-bound typed OOB response. The
`CrewNavigator` stores individual learned room graphs and runs the existing
bounded GOAP planner over those observed edges. It executes stock Evennia
exit commands and confirms the actual destination from fresh world
observations; it never teleports or treats a predicted effect as truth.

Live engineering and department work now explicitly verify that the assigned
character can travel to the relevant station. Unreachable locations
stop physical work; maps are private role-bound additive supervisor state.

The physical `CrewCharacter` now remains at its last authoritative
world location across a handler disconnection, instead of stock Evennia's
offstage storage. This does not grant commands or movement permissions.

A disposable real-server acceptance run:

    python -m ox_ai.runtime.navigation_trial direct

The test fixture must provision a nonprivileged Ari account and place the
character in Crew Mess before launching the server. Other modes are
`blocked` and `reroute`, which require operator-created hatch conditions.
See [full G2c test protocol](../../design/prototypes/g2-navigation.md).
No operator browser UI or generic inventory/skill system is added.

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

**Historical P4f limitation, partially lifted by PR #85:** P4e consumers
still require historic alarm, handover and hail records, but the handler
now loads that context from world truth only once after startup and
fetches later events by its saved cursor. Cold-start full hydration
and in-process unbounded compatibility history remain. This is not
general event-retention compaction or arbitrary mid-scene recovery.

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
| `src/ox_ai/agents/live_concordia.py` | Five specialist Concordia entities and optional independent sixth-captain cognition; actor-private observations, bounded choices and restoration |
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

## G4 character development is world-owned

The persistent formative traits, 55 skills, independent knowledge and exact
procedure familiarity are **world data**, not personality claims from a
Concordia prompt. Successful selected physical work earns bounded practical
and procedural credit only after an authoritative receipt. The G4g lesson
and G4h investigation-reflection activities likewise earn theory credit only
through assessed world records and receipts, **never** from a model's own
story about learning. Their first live authentication/restart tests were
merged in [PR #62](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/62)
and [PR #63](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/63).

These are presently explicit actor-authorized world activities; normal
`five_crew_service serve` does not autonomously plan enrollment or reflection.
The routine/novel task resolver remains an operator-only shadow comparison,
not the equipment physics. See [G4 status](../../design/STATUS.md),
[the lesson protocol](../../design/prototypes/g4g-verified-conceptual-learning.md)
and [inquiry protocol](../../design/prototypes/g4h-investigative-learning.md).

## Known runtime limits

1. The standard supervisor runs **five specialist crew**, with an opt-in
   sixth captain. The world implements bounded practical progression and
   two assessed conceptual activities, **not** graded physical task success,
   autonomous teaching/study agendas, full-ship autonomous operation, a freight economy or unscripted
   social intelligence.
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


## G3e actor-driven scientific disagreement (experimental)

The optional `OX_G3E_INVESTIGATION=1` first-stage dispatcher from merged
PR #47 obtains five separate local measurements and one unconfirmed bridge
hypothesis. The verified G3e-2 extension (merged PR #48; 46/46 checks) additionally requires
`OX_G3E_FOLLOWUP=1`: specialists may submit a different hypothesis,
perform a fresh world-local `oxprobe`, send the verified *reading* (not an
asserted cause) to Lin, and reconsider independently. Lin sees only their
addressed reports and can change, retain or defer a new explanation.

`python -m ox_ai.runtime.five_crew_service followup-drain` is a disposable
bounded trial mode; ordinary `serve` stays event-driven and opt-in,
with fault/hail/handover priority. Private, persisted intentions and
per-person epistemics never receive operator cause records. Offline
MockModel tests demonstrate world/action integration, not AI diagnostic
accuracy. [Full boundary](../../design/prototypes/g3e-contradictory-evidence.md).


## G3e-3: evidence-first specialist autonomy

Enable `OX_G3E_INDEPENDENT_QUESTIONS=1` alongside the existing G3e
investigation and follow-up flags to allow existing specialists to pursue
known unanswered questions before or without formally disagreeing with
Lin. Each request is executed through the authenticated, durable
`anomaly_question` work verb and local `oxprobe`, followed by
a separately receipted report; tentative interpretation is optional.
Lin can make a new unconfirmed bridge assessment from firsthand
cross-department test reports even if the first diagnosis was deferred.
Set the new flag to `0` to retain legacy G3e-2 challenge-first control.
No LLM is exposed to the root cause or an actor-unaddressed event.

[Source-of-truth boundary, scenario reruns and limitations](../../design/prototypes/g3e-independent-questions.md).
