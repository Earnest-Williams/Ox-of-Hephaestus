# Ox of Hephaestus — architecture and authority boundaries

**Current implementation (21 October 2026):** P4a–P4j, G3–G5 and
G6–G12 are merged and scoped. The primary ship remains **seven rooms and
three equipment systems**, with five independently authenticated specialists
and an opt-in sixth captain; G6 terminal loss and G7's apartment are
*separate experimental fixtures*, not a larger general ship. Evennia owns
world state, roles, receipts, bilateral agreements and physical outcomes.
Native Concordia/GOAP owns actor-private beliefs, interpretations, memory
and decisions; native private-memory prompts are read-only and time-indexed.
The handler restores only supported stages, not arbitrary mid-scene actions.
The G11 A/B harness and G12 profiler do not establish open-ended agent
competence or a 40-character live simulation.
[Verified feature matrix](design/STATUS.md) · [Development setup](INSTALL.md).

## Current G6–G12 and journal/transport boundaries

- **G6/G6b:** an opt-in six-authenticated-character terminal atmosphere
  scenario uses world-owned irreversible damage, finite reserves, witnessed
  operations, survival/mortality state, and bounded decisions. Model-free GOAP
  and opt-in hosted trials are distinct forms of evidence. A successful
  A-01 diagnostic cartridge exchange never proves the wider crisis resolved.
- **G7/G7b:** the separate adult apartment is an explicit social GOAP
  testbed. Typed negotiations can create Evennia-persistent, participant-
  scoped agreements and receipts. Assent to terms is not proof of desire,
  disclosure is not proof of truth, and unimplemented material transfers
  cannot be claimed as fulfilled.
- **G8/G9:** subjective memories carry separate occurrence/learning times,
  provenance, confidence and bounded interpretations. The character owns
  mutation and rehearsal; the independent cognition revision prevents a
  detached Concordia inference from overwriting intervening private changes.
  `OxMemoryContext` is a bounded, read-only native prompt projection;
  it has no authority to modify the ship or other actors' private history.
- **G10/G10b:** G8's deterministic social-turn clock is distinct from
  absolute Evennia game seconds. `MemoryClockBridge` converts explicitly;
  the normal live decision path reads actor-authenticated `oxclock` before
  inference and ages private context even when no addressed event arrived.
  It never substitutes handler wall time or modifies the world clock.
- **G11/G12:** a manual, matched-evidence hosted-model A/B pilot isolates
  the added private prompt projection; local G12 profiling instantiates
  6/20/40 native brains without hosted inference. Neither is a production
  scaling or model-quality certification.
- **PRs #82–83:** PostgreSQL journal appenders acquire one transaction-held
  serialization lock before allocating global sequences, so recipient
  cursors cannot skip a late-committing earlier insert. An `oxwork` receipt
  captures its own operation's emitted event identity rather than guessing
  from a sequence interval. Captain alarm creation follows the world
  P-01 lock → obligation lock → journal lock order, with real PostgreSQL
  contention and rollback gates.
- **Authenticated transport:** response matching keeps unrelated frames in
  wire order under a finite buffer. It refuses to read when that buffer is
  already full; malformed unattributable receipts remain unmatched, and
  actor/receipt status checks on the matching request still fail closed.
- **PR #85 incremental addressed inbox:** each authenticated recipient's
  first handler read hydrates historical context once per *process*.
  Following reads request `oxinbox` strictly after the saved actor cursor.
  The live per-actor compatibility history remains complete, not truncated,
  because pump, social, captain and investigation recovery still verify old
  world event IDs. Five-crew epistemics/agenda use binary-searched deltas
  against their own independently durable cursors. A cold process still
  rehydrates full history; in-memory retention is still unbounded. No
  additional server authority or journal mutation is introduced.
  These are transport/handler optimizations, not independent world authority.

The older milestone-specific sections below describe the implementation at
those milestones. Their former "next step" statements are historical; for the
live scope and limitations use [STATUS](design/STATUS.md).

## G3d: optional independent crew initiative (PR #46, merged)

The world's persistent duty Script can run an explicitly armed, deterministic
`tick_rounds` schedule. Missed game-time windows coalesce, avoiding per-tick
model inference and unbounded alarm replay. Each of the five independently
authenticated crew sees only their own world-addressed invitation to perform
local rounds, never the world's latent equipment wear.

The five-crew supervisor's optional independent-round dispatcher is subordinate
to existing incident and supply duties. Each crewmember may choose to inspect,
navigate by learned local GOAP exits, receive an authenticated local readout,
and file a globally receipted `round_report`. The world verifies station,
role, present observation and cycle, and delivers the verified report to the
bridge. An inspected finding of overdue wear can motivate Mara or Teo to
individually choose a world-receipted preventive `retension` or `purge`.
These actions cannot repair a failed device or spend an unobserved consumable.
An unobserved fact remains actor-relative unknown, regardless of whether an
operator knows it exists.

The enabling switch is `OX_G3D_INDEPENDENT_ROUNDS=1` *in addition* to
the operator's one-time world schedule. The contained acceptance scenario
is deterministic; provider-driven individual initiative is not yet proven
and a comprehensive general work-order engine does not exist.
[Design and acceptance](design/prototypes/g3d-independent-rounds.md).

## G4: person-owned capability and provenance (merged PRs #55–60)

The world maintains **one authoritative set** of per-person records for:
(1) relatively stable formative aptitudes, (2) continuous psychological
dispositions, (3) learned professional proficiency, (4) independent
theoretical foundations, and (5) procedure familiarity on individually
identified equipment. OCEAN/MBTI-inspired blueprint styles remain expressive
starting-character material, not duplicate physics engines or authority grants.
Personal beliefs, self-assessment, hypotheses and uncertainty continue to
live with each Concordia character and can diverge from world truth.

G4d removed the temporary 0–4 Evennia role competency vector. The captain's
limited firsthand bridge inspection reads `investigation.instrument_analysis`
from the authoritative skill ledger (minimum 40/100), separately from command
authority and actual bridge presence. No agent-provided skill claim can
satisfy this gate. G4e stores actual theoretical and exact procedure records
rather than manufacturing them from related practical skills. Initial values
for the six original people are **estimates**, not proven classroom or
employment histories. A world-side shadow resolver can compare synthetic
ordinary-veteran, gifted-veteran and gifted-novice scenarios; its numerical
weights do **not** yet change physical action outcomes.

G4f introduced `CharacterLearningEvidence` and bounded independent practice
progress on `CharacterSkill` and `CharacterTechnique`. A successful,
authorised P-01 repair, C-01 restow or A-01 cartridge replacement can award
practice credit only from the corresponding **global WorkReceipt**, in the
same database transaction. The first uniqueness guard is the request/receipt
and the second is the actual equipment source-event identity. Failed world
refusals, hails, ordinary talk and retries do not award skill credit; repeated
real work receives diminishing learning credit. Generic repairs do not
increase theoretical knowledge, nor does a high score reveal an unobserved
failure cause.

G4g adds a separate supervised conceptual-learning activity. The world
records a qualified instructor, consenting learner, co-presence, duration,
curriculum, private transfer exercise, submitted answers and receipt-backed
result. Correct assessments advance `CharacterKnowledge.study_progress`
under bounded thresholds and a curriculum ceiling. Instruction and study
do not improve practical skill, grant duties or expose hidden ship causes.
Normal movement interrupts supervision, and assessment/evidence/progression
commit atomically. The first curriculum and its two-client restart gate are
[specified here](design/prototypes/g4g-verified-conceptual-learning.md).

G4h adds a second, independent conceptual activity grounded in firsthand
investigation. The world records a prediction before an actor's real local
probe, binds its receipted report, then assesses evidence limits and a fresh
source-independence example. It grades only actor-available evidence and
method, without loading the latent cause, private noise or bridge theories.
Passed reflections can advance `investigation.methods` under the same
learning ledger and transaction, with per-case uniqueness, daily spacing and
a 70/100 ceiling. Forecast accuracy and diagnosis agreement grant no credit;
neither case closure nor physical competence is inferred. See the
[activity and restart gate](design/prototypes/g4h-investigative-learning.md).
Autonomous study scheduling remains future work.

**Evennia contraction:** character and account command sets are explicit
Ox allowlists instead of inheriting all stock MUD actions. User-level
`charcreate`, `chardelete`, `home`, unvalidated object pickup/drop/give,
generic builder/admin controls and unscoped communication are unavailable
through ordinary ship commands. Evennia's session/login/puppet machinery,
spatial typeclasses, traversal locks, authoritative database, transactions,
Scripts and event/receipt transport are retained.

[World skill calibration](design/prototypes/g4d-skill-shadow.md) ·
[Knowledge and procedures](design/prototypes/g4e-independent-knowledge-techniques.md) ·
[Receipt-driven progression](design/prototypes/g4f-world-receipt-learning.md).

## G5-a: adversarial failure modes (verified code gate, PR #45)

The G5 harness adds seeded world/handler stress, cross-connection PostgreSQL
races for concurrent hails and duty ticks, and failure injection into *direct*
character commands that bypass the durable `oxwork` adapter. Normal crew
commands still require their native world permissions. The P-01 work lock
serializes shared hail mutation; direct safety/watch transitions acquire P-01
then the roster before evaluating changing world Attributes. The world clock
acquires the roster only. Hardware-room change messages are emitted on DB
commit, never before a journal and physical transition become durable.

[Detailed G5 scenario and limitations](design/prototypes/g5-adversarial-voyage.md).
This remains a bounded reliability trial rather than an autonomous simulated
voyage or an exhaustive concurrency proof.

## G3 — individual epistemics, real inventory and cooperative delivery (PRs #38–40)

**Rumsfeld/open-world invariant:** a missing proposition is not false.
Each agent has a separate versioned, DBref-bound epistemic ledger for (1)
locally or world-receipt observed statements with time, provenance and
expiry, (2) actor hypotheses and testimony that remain *beliefs* even at
confidence 1.0, and (3) explicitly posed known-unknown questions. Unmodeled
propositions are absent from that character's ledger, not false.

**Unknown unknown is actor-relative but world-identifiable.** An actual pirate
hidden on the far side of a moon can already be known to Evennia yet be an
unknown unknown to Lin right now, without any promised future discovery.
The character cannot enumerate those hidden facts. A trusted, operator-only
audit may compare actual world facts against a correctly matched actor's
private ledger and exposure history; its result must NEVER be sent as agent
prompt context, an observation, a navigation hint or a game command.
Discovering an unexpected fact later may create a *retrospective surprise*,
which is distinct from the unknown unknown's earlier existence.
Cross-character events and private memories are not readable by other agents.

**World scarcity:** serialised InventoryItem rows contain a physical state,
single real room or carrier, and permanent consumed status. Earlier A-01
local spares remain separate preserved world stock; delivery of a new
serialised unit does not reset or double-count existing inventory.
SupplyOrder and globally unique WorkReceipt rows record Teo's request,
Mara's accepted obligation, physical collection and delivery. An order
or in-transit notice is not proof of physical stock. World events are
recipient-addressed; local oxinventory observations use Evennia's clock
and return null, never guessed zero, for unverifiable local stock.

**Cooperation:** a separate five-person supervisor may coordinate the
bounded Teo/Mara A-01 supply cycle. Mara cannot proceed before her own
authenticated world assignment event. She must visit Cargo Hold, verify
stock and carry a real item through normal exits; Teo must receive a
world delivery event and observe newly available stock locally before
retrying a previously refused A-01 replacement. Each stage retains its
own original world receipt ID across crashes. Production automatic
cooperation is opt-in while earlier regression scenarios remain stable.
[Epistemic model](design/prototypes/g3-epistemics.md) ·
[World supply model](design/prototypes/g3-inventory.md) ·
[Cooperative trial](design/prototypes/g3-cooperation.md).

## G2c: actor-scoped world capabilities and learned GOAP travel (PRs #35–36)

The ordinary, nonprivileged `oxcapabilities <nonce>` game command returns
the calling character's **current local** room identity, traversable stock
Evennia exits and currently eligible local equipment actions. Exit locks,
physical presence, role, inspection and inventory come from Evennia.
Capability advertisements are not durable permissions; actual world
commands and receipts revalidate every consequential precondition.

`CapabilityPort` authenticates each nonce/actor/version/schema over an
ordinary character WebSocket. `NavigationKnowledge` persists only
character-bound observations of rooms personally reached and their local
exits. `CrewNavigator` converts that knowledge into finite
`GoapAction` room transitions and explores unknown reachable frontiers
without a complete ship map. Each action is a **normal exit command**,
preceded and followed by fresh world observations. Closed/stale exits are
excluded for that run; if no route can be found, the character remains
blocked without movement shortcuts or remote equipment operations.

Shipboard `CrewCharacter` overrides stock Evennia's unpuppet storage.
Disconnected AI or player sessions do not remove a crew person from the
physical world; locations persist for other observers and on re-puppet.
This makes a handler restart independent of a physical crew position.

The live supervisors use this mechanism to verify engineering and
specialist duty-station access before local work. A private map is not an
authoritative location; restarts begin with a real local observation.
[Implementation and acceptance](design/prototypes/g2-navigation.md).

## G2b: nonblocking per-agent cognition and process exclusion (PR #33)

The handler now uses a `DecisionScheduler` for ordinary role-bound Concordia
choices. The main asyncio loop never runs synchronous provider inference.
Instead, each decision starts from a deep-copied per-character native Concordia
snapshot, executed in a bounded worker thread. Actual private observations can
still be ingested on the live mind. A changed observation revision rejects the
detached result; only a valid current result can become a pending *proposal*.
Neither the fork nor scheduler can submit world actions.

At most two inference calls are in flight by default, with independent
per-character single-flight reservations, timeouts and hourly admission quotas.
Timeouts fail closed and quarantine the outstanding actor until its provider
worker finishes; Python cannot forcibly interrupt a synchronous running model.
This requires explicit transport timeouts. Concurrent hails are handled over
separate character sockets and retain the world-owned global WorkReceipt
reconciliation. Consequential physical work remains serialized by existing
world-grounded duties and the world's rules.

The three-person and five-person controllers now acquire the SAME stable POSIX
lock file in `.ox-state/supervisor.lock` before logging into Evennia. A second
controller on that host is denied; crash releases the kernel-managed lock.
The recorded epoch is diagnostic only. There is **no distributed/world-enforced
fencing yet**, so this architecture must not be deployed as multiple hosts
controlling the same ship. [Tests and scope](design/prototypes/g2-nonblocking-cognition.md).

## G2a: persistent, actor-bound crew agendas (merged PR #29)

`services/ai-handler/src/ox_ai/runtime/crew_agenda.py` introduces one
private, JSON-serializable intention ledger **per world character**, bound
to their authenticated DB ref. The agenda is kept beside (but distinct
from) each role's native Concordia state and restored from the handler
checkpoint. It does not create world-owned `WorkOrder` records or
grant itself permissions, supplies, or equipment effects.

An agenda obligation is keyed by the **real recipient-addressed event ID**,
with a source sequence, local priority, state, reason, bounded transition
history and an explicit reconsideration trigger. The handler rejects events
addressed to another crewmember. Inbox replay is idempotent: a deferral
cannot be dismissed by rereading the same old event. A newer authoritative
world observation of a subscribed kind can restore a blocked/deferred task
to the ready queue. A world refusal is saved as a permanent failed receipt;
a later genuinely authorized attempt has a different ID.

This first G2a integration uses the general ledger for cargo and
environmental work. It dispatches ready tasks by priority instead of the
hardcoded Teo-before-Mara loop and permits preemption **only between
validated world actions**, resuming the older duty thereafter. All five
agents have separate agenda records, but bridge, watches, hails, time-based
deadlines and independent goal selection still need subsequent integration.
Station-recovery navigation is described in G2c. MockModel remains the default deterministic
acceptance model; these tests are not proof of open-ended intelligence.

## G1 PostgreSQL concurrency gate (merged PR #28)

The default Ox game remains a loopback-only SQLite development fixture.
`server.conf.settings_postgres_ci` is a separate, explicitly opt-in
Django settings module for disposable PostgreSQL CI only. Its database
has no durable gameplay state and is not a production deployment
recommendation.

The real concurrency probe uses two independent database connections
to race the same actor and request ID (exactly one world receipt),
then races two appropriately credentialled world characters for one
replacement scrubber cartridge (one success, one lasting refusal).
It also holds a genuine PostgreSQL `SELECT FOR UPDATE` lock and proves
another writer cannot commit ahead of the releasing transaction, and
tests rollback of world events and work receipts together.

This exercises **world-owned** transactions. No AI agent is permitted
to connect directly to the database, and no new gameplay capability
is inferred from the test. Migration, backups, production database
configuration and load/endurance validation remain separate concerns.

## P4j: one global receipt namespace for specialist work (merged PR #27)

Cargo C-01 and environmental scrubber A-01 **new work** now use the
existing handler-owned `WorkStepLedger` for each named physical step,
persisting one global world-work ID before submission. A restarted handler
reconciles that ID first; authenticated `no_authorised_receipt` is the
only reason to resend the **same** ID. Real equipment transitions and
cartridge consumption remain owned by Evennia.

An in-flight pre-P4j specialist checkpoint may already contain the old
fixture-specific `pending` request ID. It remains valid: such work
reconciles against the original `oxreceipt` fixture namespace before
subsequent stages migrate to the global ledger. Never mint a new ID to
replace an ambiguous legacy operation. Skills, actor goals, interdepartment
inventory transfer and PostgreSQL contention validation were **later
implemented and tested** in G3b/G3c and G1-PG, respectively. The surrounding
P4g description preserves the original incremental scope.

## P4i: restartable addressed crew coordination (merged PR #26)

The bridge now persists a `begin_alarm` incident before any radio relay,
then issues that world-validated social operation using a stable `WorkStepLedger`
ID. The next independent handler can reconcile the existing receipt and
verify the precise addressed radio event before isolating equipment.

Scheduled handover stores its original world-issued due observation and
separate `offer` and `accept` work IDs. If interrupted after the
world's watch transfer, it validates the independent receipt, both
characters' addressed events and the posted roster rather than repeating
the transfer. Recipient-private hails similarly retain their chosen
bounded answer, actor identity, source hail and one work ID through
process restarts. They are completed only after an addressed
`hail_answered` event is independently replayed.

Original `oxradio`, `oxhandover`, `oxaccept`, and `oxanswer` commands
remain valid character interfaces; the supervisor uses the authenticated
typed `oxwork` path for these persisted jobs. Specialist work still uses
fixture-specific receipts and must migrate separately.

## P4h: restartable engineering work stages

`services/ai-handler/src/ox_ai/runtime/work_steps.py` owns the handler's
persisted **intent ledger** for each named action within a pump incident.
Before transmission it records a fresh 32-digit request ID, actor, target,
operation and bounded arguments. A resumed handler first checks the world's
`oxworkreceipt` for that original ID. Only an explicit authenticated
`no_authorised_receipt` can permit retransmission of the *same* ID;
unknown transport state fails closed. World acknowledgments are saved
before a stage completes; replayed observations are deduplicated.

The watch supervisor's `resume` path uses this ledger for pump repair,
engineer release request, reviewer approval, commissioning and resolution.
Safety decisions and physical inspections remain character-local and
Evennia still decides their validity. A committed prior stage is never
executed again, even if the handler stops between receipt and checkpoint.
The initial isolation still uses the backwards-compatible P4b receipt;
scheduled handover and human hails are **not** yet migrated.

## P4g stage 1: world-owned work receipts

A versioned Django `world.WorkReceipt` record binds one globally unique
request ID to an authenticated actor, operation, physical target or shipboard
social procedure, typed arguments, and a committed authoritative outcome.
The `oxwork` / `oxworkreceipt` character commands provide a common
reconciliation surface while keeping `oxaction` / `oxreceipt` intact for
existing P3–P4e clients. World-side permission and physical-presence tests
remain unchanged. A refused action is also a durable outcome and cannot
later be retried under the same ID to acquire new authority.

PR #23 merged the additive world protocol. PR #24 supplied a durable
private handler stage ledger for pump repair, safety request, independent
reviewer approval, commissioning and final resolution. Watch handovers,
player hails, initial alarm radio and specialist work bookkeeping still
need migration to the same resumable work pattern.

## P4f addressed, indexed world-event journal

[PR #22](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/22)
introduces a dedicated `world.CrewEvent` Django model (with migration)
and ordered, recipient-filtered pages. Legacy P4e events on P-01 are
imported idempotently on first journal use, preserving source IDs; new events
use `oxevt-v2-...` identifiers. A transaction rollback cannot publish
an event, and live OOB messages are sent only when the journal commit succeeds.

`oxinbox` now replies with version, count, `next_cursor` and `has_more`
and only returns observations addressed to its caller. The external handler
scans all pages and durably checkpoints consumed per-character high-water
marks **after** the corresponding native Concordia snapshots.

**Follow-up PR #85:** one full authenticated hydration per actor per handler
process preserves those older event proofs. Subsequent reads use
`oxinbox <persisted-cursor>` and append new recipient-only events.
The per-process compatibility history and cold-start replay remain
unbounded; only the repeated per-turn **world** pagination is removed.
Unread page counts/sequence continuations are validated before accepting
a cursor. Future bounded historical indexes and retention compaction require
migrating the remaining legacy lookup sites explicitly.

## P4e verified five-agent extension

**Historical milestone:** this section describes P4e as implemented in PR #19. Later G3f/G4a–G4h work added an opt-in sixth captain, authoritative skill/knowledge records and verified learning. Refer to the current summary above for today's feature set.

Merged PR #19 extends the **optional external agent handler** to five distinct
accounts and five private native Concordia entities. Mara and Teo receive
only their own addressed cargo/atmospheric events and local equipment
inspections. Specialist `oxaction`/`oxreceipt` requests now bind the
actor, fixture and operation to durable game-side physical outcomes.
The handler checkpoints pending actions before sending; restart may
reconcile the original request ID, never mint a new ID for an unknown
outcome. The original pump supervisor remains supported and must not be
run concurrently on the same ship.

The new handler has a finite event-driven safety-priority order, not a
general auction/agenda scheduler, and specialist procedures are authored
actions rather than unstructured model-generated commands. At this historical point, distinct skill labels existed; **verified
practical progression was subsequently implemented in G4f**, and G4g/G4h
added narrow assessed conceptual learning.
See [P4e scope and acceptance](design/prototypes/p4e-five-crew-autonomy.md).
The full-server five-agent integration test and all 12 other triggered Ox
workflows passed before merge.

## 1. Independently operable components

~~~text
 Human MUD clients                 Planned human observatory (NOT built)
        |                                /                \
        v                         world-facing API     handler API
  +------------+                         |                  |
  |  Evennia   | <--- ordinary authenticated clients ---+    |
  | world/game |           AI handler (Concordia + GOAP) <---+
  +------------+              separate OS process
    WORLD TRUTH                CHARACTER BELIEFS / INTENT
~~~

**Evennia (implemented)** is the sole authority on rooms, characters,
equipment, permissions, engineering assignments, the world-owned duty
timer, physical transitions and validation of equipment operations. The
game remains accessible to human players using ordinary Telnet/web
clients. The AI handler does not read or mutate the game database.

**Ox AI handler (implemented for three or five specialists plus optional captain)** owns each character's
Concordia entity, private memory, proposed actions, pending requests,
journals, snapshots and event wake-up policy. P4e connects as five ordinary,
nonprivileged Evennia client accounts. The handler can be stopped while the world keeps
its own state, alarms and event journal. Production process supervision, multi-host process fencing and full
crash-resume coverage are future work; G2b already supplies bounded local
inference concurrency and a single-host controller lease.

**Human interface (deferred)** is a separately packaged skeleton under
`services/interface/`. The intended UI will join authoritative world
readings with handler-owned cognitive records through **two distinct
authenticated read APIs**. Neither the joined API nor the browser app
exists. The interface must never create a second store of ship truth.

## 2. The currently implemented ship

`game/world/bootstrap.py` installs Bridge, Connecting Passage, Engineering,
Cargo Hold, Environmental Plant, Crew Mess and Machine Shop. Existing crew
Lin Sato, Ari Sen and Iona Vek remain alongside independently autonomous
cargo officer Mara Voss and environmental technician Teo Hale. The Bridge
has separate cooling and cargo/environmental status consoles. The original
pump P-01 retains the lifecycle:

~~~text
normal --fault--> low_pressure --isolate--> isolated
isolated --repair--> repaired --commission--> normal
~~~

Pump operations check actual state, presence and game-owned role. The
`oxaction <request-id> <operation>` route produces a durable, actor-bound
P-01 `ox_receipt` for uncertain-outcome reconciliation. A proposed plan
has **no game effect** until Evennia validates and executes it.

Additional installed equipment lives in `typeclasses.departments`:
C-01 cargo restraints (`secured → unsecured → restowed → secured`) and A-01
atmospheric scrubber (`nominal → saturated → isolated → serviced → nominal`).
Each requires its own specialist role, local inspection and valid transition;
A-01 consumes finite spare cartridges. Their separate physical journals
survive game restart. Both now implement actor-bound durable equipment-specific action receipts;
the five-agent handler checkpoints pending world requests and can reconcile
a lost cartridge ACK without repeating a physical transition. Cargo and atmosphere alarms are addressed to their specialist and
the Bridge, never broadcast to all crew. The public duty board lists
responsibilities; it is not a character memory store.

World events (`ox_event`) are stored in an indexed world journal for a **single recipient** with a
source event ID, game timestamp, sender and flat scalar details. On an
ordinary Evennia `v1.evennia.com` WebSocket connection the handler sends
normal character commands and receives in-world observations or the
explicit Ox out-of-band event/receipt messages. `oxinbox` replays only
events addressed to the logged-in character. We do **not** have an
operator-omnipotent AI service endpoint.

A live bridge alarm first reaches Lin, who may radio the engineer on
active watch. Ari and Iona inspect and service equipment **locally**;
an independently assigned reviewer inspects before commissioning.
During the first watch Ari works and Iona reviews. After the world-owned
handover, Iona works and Ari is delegated review authority; self-approval
is forbidden. The reviewer and active engineer can be determined from
world-owned roster state, not an agent's assertion.

## 3. Cognition is not causality

**Chosen foundation:** [Concordia](https://github.com/google-deepmind/concordia)
`EntityAgentWithLogging` for each full NPC; the optional source dependency
is pinned to a reviewed commit (see [ADR 0001](design/decisions/0001-concordia-first.md)).
The current entity graph uses identity, duties/goals, observations and
list memory. Each entity receives only its **own** addressed world events
and direct local readouts.

- **GOAP** is a model-free STRIPS-like search for familiar engineering
  procedures; its predicted effects are not state changes.
- **Concordia** offers a bounded finite action menu and produces a
  **proposal**, including the option to defer. Choices have agent revision
  and request IDs; a later world response is separately recorded.
- **LLM usage** is optional, not a per-tick prerequisite. CI uses a native
  deterministic MockModel, not three independently improvising language
  models. A single-engineer Gemini experiment is opt-in. General dialogue,
  unstructured new procedures and robust semantic cooperation are not
  proven by the current integration tests.
- **Game Master:** deterministic P2 mock tests use a tiny world/event
  resolver; no continuously narrating language-model GM governs the live
  ship. The Ox handler directly activates Concordia entities as needed.

An agent's belief may be incorrect or stale. Any future observatory must
show the difference between **Evennia says P-01 is normal** and **Ari
believes it may still be isolated**, with each source identified.

## 4. Time, handovers and the external loop

The persistent `world.live_clock.ShipDutyClock` Evennia Script checks a
game-owned duty deadline, emits addressed `handover_due` events **once**,
and never invokes Concordia. The test fixture uses a short real world-timer
delay while labelling the watch change at 07:55; the earlier P3 test
optionally used an artificial clock jump after incident closure. P4b
specifically tests handover **without** that shortcut.

`ox_ai.runtime.watch_service serve` is the independent event-driven
handler entry point for **Lin/Ari/Iona only**. It can restore native
Concordia checkpoints from `.ox-state/`, rejoin the world, dispatch
coolant faults, time-owned handover and addressed player hails, then
wait on authenticated sockets when idle; idle cycles do not require
model calls.
One world-side fault can wake the crew, and subsequent faults can occur
under a different active watch.

The P4b GitHub test deliberately stops and restarts the **handler as a
separate OS process** after Evennia has committed an isolation but before
its acknowledgment has been remembered. The new process reconciles the
existing request ID; it never repeats that physical isolation. The
verifier independently checks exactly two complete pump cycles in one
persistent game database. PR #24 separately tested repeated restarts at each later pump-work stage.
Neither test proves recovery from every possible social or specialist
interruption, or production 24/7 uptime.

## 5. Security and provenance

- Only in-world account/character permissions authorize actions.
  A successful login is followed by a character-identity challenge.
- Non-TLS `ws://` connections are restricted to loopback in the client;
  a remote service would require audited authentication and `wss://`.
- Development `game/server/conf/settings.py` uses `LOCKDOWN_MODE`,
  disables registration and binds game ports to loopback.
- Test provisioning (`game/world/transport_probe.py`) intentionally uses
  throwaway bot accounts and is unsuitable for production identity
  management. Never commit keys or credentials.
- Ox wire event IDs, common world work receipts, game timestamps and
  actor dbrefs support attribution. The typed social-work interface is
  transactional, but the existing hail/handover supervisor paths have not
  all been migrated to checkpointed intent and restart reconciliation.
- Individual cognitive journals are private operator diagnostics, not
  authorized input for other crew or a public dashboard.

## 6. Planned systems and explicit non-goals for P4

The eventual bulk freighter will add propulsion, freight economics,
large-scale cargo handling, staffing constraints and wider departments.
Today's **seven-compartment** fixture already contains cargo/environmental
systems, a six-person character foundation and narrow receipt-backed learning;
it is not yet the full commercial ship. The postponed P5 observatory would join
Evennia readings to handler beliefs through permissioned, versioned APIs;
no UI framework or deployment architecture is selected.

A dedicated multi-character AI transport endpoint remains a **possible
later optimization**, not a reason to bypass normal game authorization.
Do not add a second general agent framework or an always-generative GM
without a measured reason. Prefer lazy background work, event-driven
decisions and causal consistency over full high-frequency continuous
simulation.

## 7. Source map and acceptance evidence

| Concern | Code or document |
| --- | --- |
| Game world, equipment, roster | [`game/`](game/README.md) and `game/world/live_crew.py` |
| Persistent game duty clock | `game/world/live_clock.py` |
| Authenticated client and durable receipt port | `services/ai-handler/src/ox_ai/ports/evennia/` |
| Individual native cognition | `services/ai-handler/src/ox_ai/agents/live_concordia.py` |
| Persistent event-driven process | `services/ai-handler/src/ox_ai/runtime/watch_service.py` |
| P2 mock scenarios | [watch handover](scenarios/shift_handover/README.md), [coolant fault](scenarios/coolant_fault/README.md) |
| P3/P4 acceptance | [status and PR evidence](design/STATUS.md), [P4a](design/prototypes/p4a-live-cognition.md), [P4b](design/prototypes/p4b-autonomous-watch.md) |
| Future interface | [interface roadmap](services/interface/README.md), [contracts](contracts/README.md) |

The `ox-p4b-autonomy.yml` workflow is the executable test of the
world-clock, changed-watch and crash-reconciliation claims. Its success
does not expand the scope of the demonstrated mechanics.


## G3e actor-relative uncertainty and revision (experimental)

The G3e-1 case is one world-owned hidden anomaly whose underlying cause
exists independently of crew knowledge; five native Concordia characters
observe separate local fallible readings. G3e-2 (verified and merged in PR #48) adds
independent specialist challenges, one world-drawn station test per actor,
source-event-backed reported measurements, private post-test positions,
and an optional Lin reassessment. World records are kept separately from
per-actor memories; the model sees neither hidden cause nor test noise
distribution or other characters' undelivered events.

Global `WorkReceipt` permits an immutable actor-/argument-bound work
attempt; case changes and both recipient notifications occur atomically.
The handler checkpoints intended requests before socket submission and
reconciles unknown outcomes using original request identity, while
`oxprobe` is a locally authenticated, persisted read-through diagnostic.
Experiment outcomes are informative but non-conclusive, and even the final
bridge position remains an explicitly unconfirmed hypothesis. This is
a bounded case-specific proving ground, not generalized diagnosis, skill
progression, or automatic repair.

## G3e-3 — Actor-authorized unanswered questions

G3e-3 (merged PR #51) adds a world-authoritative, actor-bound `anomaly_question`
receipt distinct from a `anomaly_challenge`. Specialists may request one
additional measurement of a world-known physical anomaly from their
existing installed instrument after filing their own firsthand report.
They need neither a bridge theory nor a competing hypothesis. The second
reading is privately sampled, repeat-safe and separately reported to Lin;
reporting a reading does not require asserting its cause. The external
Concordia handler `IndependentInquiry` is opt-in with
`OX_G3E_INDEPENDENT_QUESTIONS=1`, and the original G3e-2 challenge-only path
remains available when disabled. Case truth, sample noise and
character-specific knowledge stay in their existing authority domains.
Only one follow-up measurement per eligible actor is supported; this is
**bounded initiative**, not arbitrary experimental design or a world-oracle
diagnosis. [Canonical protocol and flags](design/prototypes/g3e-independent-questions.md).
[Observed A/B behavior and remaining limits](design/prototypes/g3e3-independent-questions-results.md).
