# Ox playable ship — authoritative Evennia game

**Status (30 October 2026):** G19's installed 421-room / 517-link ship, fitted 808-equipment operational register, finite resources, damage control and world-gated character traversal are merged and accepted. The existing five-specialist Concordia/GOAP crew (optional sixth captain) still operates the separate seven-compartment, three-machine proving ground. The commands and original role examples below primarily document that smaller compatibility fixture. See [G19 ship acceptance](../design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md), [ship engineering index](../design/ship/README.md) and [current status](../design/STATUS.md).

All Ox ship content is under `game/`; the inherited `evennia/` engine has
not been converted into a different distribution.

## Current world extensions beyond G4h

G6/G6b optionally arm terminal atmospheric failure and a six-client
world-owned mortality/reserve trial. A cartridge exchange is authenticated
maintenance, **not** an assertion that an unrelated pressure breach is
resolved. The experiment is bounded; it does not make the primary ship a
production life-support simulator.
[G6b scope](../design/prototypes/g6b-continuous-crisis.md).

G7b persists participant-only proposals, counteroffers, replies and
witnessed performance in `SocialAgreement` and `WorkReceipt` rows,
with exact revision, actor identity and replay rules. The apartment
is a separate test fixture, and no inner desire/consent is inferred
from a model-only declaration.
[Social authority](../design/prototypes/g7c-world-social-authority.md).

Authenticated `oxclock <nonce>` emits one actor-scoped `ox_clock`
response with authoritative Evennia game seconds. It never sets world
time. [Clock read](../design/prototypes/g10b-world-clock-read.md).

Under PostgreSQL the indexed journal acquires one transaction-held
serialization lock before allocating a global sequence, so recipient
cursors cannot skip an earlier-inserted event that commits later.
Ship-work receipts carry their **own** operation's event ID. A-01
alarms acquire the P-01 and captain-obligation locks **before**
journal writes; a pair of separate-connection tests covers races.
Future event writers must retain these acquisition orders.

## G4 character development and narrow Evennia command sets

The authoritative world now has six stable person identities and 55 named
skills across sixteen professional disciplines. Practical skill, theoretical
foundations and familiarity with **specific procedures on specific machinery**
are separate persistent records. The twelve formative aptitudes are distinct
from the twelve continuous psychological dispositions; neither job titles nor
MBTI-inspired writing presets can grant real technical competence.

Real work via `oxwork` may now provide limited verified practice: successful
P-01 repairs, C-01 restows and A-01 cartridge replacements produce world
receipt-linked evidence for the applicable practical skill and exact procedure.
The same request ID or even a second receipt referencing the same physical
event cannot award another credit. Other operations, including refused
commands, do not grant experience. Routine repair does **not** generate
theoretical-knowledge credit.

G4g adds a separate conceptual-learning activity: a qualified person offers
`mechanical.controlled_comparison.v1` to a consenting learner at the Machine
Shop bench. Both remain there for fifteen game minutes, then the learner
interprets a new training comparison. Correct answers earn bounded
`CharacterKnowledge.study_progress`; incorrect answers earn none. The course
has a mastery ceiling and completed assessments must be spaced by a game day.
Lesson events are participant-private and the normal global work receipts
preserve restart/replay safety. This is an explicitly requested activity;
the autonomous supervisor does not yet schedule lessons. See the
[lesson protocol and acceptance gates](../design/prototypes/g4g-verified-conceptual-learning.md).

G4h additionally develops `investigation.methods` from a real local inquiry:
file a firsthand report and question, predict before probing, perform and
report the actual diagnostic, then complete a delayed evidence-limits and
source-independence reflection. Correct reasoning can earn bounded study
progress even if the forecast was wrong. Grading never consults the hidden
cause or certifies the crew's diagnosis. New learning observations are
investigator-private; physical work and authority are unchanged. See the
[inquiry protocol and limits](../design/prototypes/g4h-investigative-learning.md).

The Task Resolver's routine/unfamiliar/novel comparison still runs only in
world/operator shadow tests. Its provisional performance score neither
changes the success of a physical operation nor authorises access. The
captain's **actual** bridge-instrument qualification is a separate world-owned
`investigation.instrument_analysis >= 40` requirement.

Normal characters and authenticated accounts use **explicit Ox command
allowlists**. Stock MUD `home`, generic pickup/drop/give, builder commands,
character self-creation/deletion and unscoped account communication are not
part of standard Ox gameplay. Evennia authentication, sessions, movement,
locks, commands and ORM are retained underneath these boundaries.

[Authoritative stage index](../design/STATUS.md) |
[character/resolution specification](../design/prototypes/g4d-skill-shadow.md) |
[independent theory and familiarity](../design/prototypes/g4e-independent-knowledge-techniques.md) |
[receipt-verified practice](../design/prototypes/g4f-world-receipt-learning.md) |
[verified conceptual instruction](../design/prototypes/g4g-verified-conceptual-learning.md) |
[firsthand investigative learning](../design/prototypes/g4h-investigative-learning.md)

## G3d optional self-directed maintenance rounds (PR #46, merged)

In a development world, the operator may **once** arm a recurring
game-time inspection window with
`from world.independent_rounds import schedule_rounds; schedule_rounds(period_game_seconds=1800)`
through `evennia shell --command=...` while the server is stopped.
The persistent duty Script will then coalesce late windows and deliver
`crew_round_window` events privately to all five crew. The handler only
responds to those opportunities when separately launched with
`OX_G3D_INDEPENDENT_ROUNDS=1`. Neither merely starting the game nor
running the three-crew handler opts in.

The world tracks a bounded C-01/A-01 wear index. The index is **not**
included in the round invitation; only local inspection supplies evidence.
`oxwork <request-id> round_report ship <station>` requires a first-hand,
current-cycle local inspection. Supported stations are `operations`, `pump`,
`cargo`, and `scrubber`. The bridge receives one verified report per actor
per round. With verified wear over the limit, authorized specialists may
issue `oxwork <request-id> retension cargo` or
`oxwork <request-id> purge scrubber`. The world rejects stale observations,
unauthorized users, unsafe physical states and repeated effects. The
G3d test workflow exercises these rules and a five-client decision path.
[Boundaries and limitations](../design/prototypes/g3d-independent-rounds.md).

## What is in the legacy seven-compartment crew fixture

| Object | Game-owned behavior |
| --- | --- |
| Bridge | Lin Sato, posted roster, real-time pump telemetry and in-world radio |
| Connecting Passage | Junction for Bridge, Engineering, Cargo Hold, Environmental Plant and Crew Mess; posted department duties |
| Engineering | Ari Sen, Iona Vek and physical access to pump P-01 |
| Cargo Hold | Mara Voss and cargo restraint grid C-01; local inspection, restow and certification |
| Environmental Plant | Teo Hale and scrubber A-01; cartridge fault, isolation, replacement, verified restart |
| Crew Mess | Navigable living/galley area, not yet a nutrition or morale simulation |
| Machine Shop | Legacy engineering annex and G4g supervised-training bench; the full G19 ship has separately implemented fabrication and workshop machinery |
| Operations Console | Bridge-only readout of cargo restraint and atmosphere scrubber states |
| Cooling Pump P-01 | `normal → low_pressure → isolated → repaired → normal`; durable event history and physical command receipts |
| Ship roster | Active engineering duty holder, independent safety reviewer and handover state |
| Duty Script | Persistent `world.live_clock.ShipDutyClock` checks an armed world deadline; it never calls a model |
| World-private events | Receiver-specific `ox_event` observations and `oxinbox` replay; no cross-crew memory access |

In this **legacy seven-room fixture**, cargo and atmosphere operations are
limited to local teaching/test procedures. This fixture has no propulsion,
freight commerce, general cargo routing or fabrication workshop; **the
separate accepted G19 full ship does simulate propulsion, cargo mechanisms
and workshop fabrication**. Integrating autonomous crew with the full ship
and adding graded skill-sensitive physical task outcomes remain later work.
Selected authenticated successful work now grants bounded practice in G4f.
The P4e supervisor runs five private cognitive agents; the original P4c three-crew supervisor
remains available but must not be run simultaneously on the same ship.

## Independent PostgreSQL concurrency gate (verified in merged PR #28)

Ox runs on PostgreSQL only, in a cluster the game manages itself
([ADR 0010](../design/decisions/0010-postgresql-only-game-managed.md)).
The G1 concurrency trial uses a disposable `ox_contention_ci` database in
that cluster. Only under `OX_PG_CONCURRENCY_TEST=1` and
`OX_PG_DATABASE=ox_contention_ci` can its
`python -m world.postgres_contention` probe execute.

The probe checks simultaneous duplicate-ID radio submissions,
competing authorized requests for one remaining A-01 cartridge,
a second transaction blocked by an actual ship row lock, and
rollback of both the world event and its authoritative receipt.
The [PostgreSQL CI gate](../.github/workflows/ox-g1-postgres-contention.yml)
does not change how the ordinary game launches, and should never be
run against a populated ship database.

## P4j shared world-work receipts for cargo and environmental tasks

New AI-initiated C-01/A-01 work now uses the same globally unique,
world-owned `WorkReceipt` records as pump and ship coordination work.
Each specialist's handler checkpoint contains a per-step intent,
and the world separately validates actual location, duty and equipment
state before recording the result. A dropped cartridge-replacement ACK
cannot spend another cartridge. Existing P4e checkpoints that store
a `pending` fixture-specific ID still reconcile through `oxreceipt`
using that original ID; subsequent work uses the global protocol.

The [specialist recovery workflow](../.github/workflows/ox-p4j-specialist-recovery.yml)
checks both independent departments and an older saved-checkpoint
upgrade case. No transferrable inventory or skill-by-use implementation
is claimed here.

## P4h pump-work recovery across handler restarts (merged PR #24)

A separately running three- or five-crew handler can restart after a
world-confirmed pump repair, safety request, independent review,
commissioning or incident resolution. The handler preserves each work
request ID before sending it; after restart, it reconciles against the
world's actor-bound receipt rather than inventing a second attempt.

The [P4h Actions gate](../.github/workflows/ox-p4h-pump-recovery.yml)
tests eight independent process launches across seven restarts, including an interrupted prepared
request that is retried using its **original ID**, and verifies exact
physical and private social event counts on the authoritative database.
The first isolation still uses the legacy P4b receipt.

This coverage does not yet extend to all autonomous handovers, hails,
or specialist task bookkeeping.

## P4g typed shipboard work receipts (first stage)

`oxwork <32-hex-id> <operation> <target> [hail-id response]`
submits one validated physical or social action through the common global
work ledger. Targets are `pump`, `cargo`, `scrubber`, or `ship`.
Equipment operations retain their existing names (`isolate`, `repair`,
`commission`, `restow`, `certify`, `replace`, `restart`). Shipboard
social verbs are `radio`, `request`, `approve`, `resolve`,
`offer`, `accept`, and `answer`; only `answer` accepts a hail ID
and bounded `status`/`ack`/`decline` response.

`oxworkreceipt <32-hex-id>` returns an actor-private world result without
repeating the command. The request ID is global across all three equipment
systems and shipboard coordination. Repeating a rejected request produces
the original refusal even after circumstances change; use a newly authorized
request for a genuinely new attempt. The legacy commands are unchanged.

This first stage does **not** implement automatic resumption of every
interrupted supervisor procedure.

## P4f durable world events (PR #22)

Private ship observations are now persisted in an indexed Django
`world.CrewEvent` table rather than as one growing list on P-01.
`evennia migrate --noinput` installs the table. On a preexisting P4e
world, the first event read/write idempotently imports and preserves
the original P-01 history; it does not delete that rollback source.

The **authenticated** character command `oxinbox <sequence>` returns
at most 128 OOB `ox_event` frames, followed by `ox_inbox_done` with
`version=2`, `count`, `next_cursor` and `has_more`. When `has_more`
is true, issue another `oxinbox <next_cursor>`. The sequence is a
journal ordering token, not a permission to read another character's events.
Live packet delivery is advisory; committed history is replayable.

`oxjournal <32-lowercase-hex-nonce> <recipient-sequence>` provides a
read-only, actor-specific continuity certificate for an exact old cursor.
The world persists one journal generation and a cumulative per-recipient
SHA-256 digest on every committed `CrewEvent`. No other character's
event details are exposed. The upgrade includes a one-time indexed-history
seal migration and the destructive test fixture rotates the generation.
This does **not** compact or delete historical events. See the
[journal continuity contract](../design/prototypes/p4f-journal-continuity.md).

`oxevent <32-lowercase-hex-nonce> <event-id>` now retrieves one **exact**
world-owned event through the ordinary authenticated character session,
without full inbox pagination. The command reads only records whose
`recipient_dbref` equals its real caller. Unknown and foreign events both
reply `missing`; `found` returns the complete original source through
typed `ox_event_lookup`, while `oversized` explicitly refuses responses
over the wire safety bound. Legacy `oxevt-N` IDs remain queryable.
This is read-only past evidence, not an operation, permission or journal
compaction. [Protocol and limits](../design/prototypes/p4f-world-exact-evidence.md).

Only the disposable `fixture_setup()` acceptance-test setup clears the
journal. **Never run it against a populated ship.** There is no automatic
retention or history compaction yet, and a supported live upgrade requires
backing up the Evennia database before migrations.

## P4e specialist autonomy (merged PR #19)

The independent five-person handler gives Mara and Teo real Concordia
agents. It reuses ordinary character commands and recipient-private world
events while adding typed durable work requests:

~~~text
oxaction <32-hex-id> restow cargo
oxaction <32-hex-id> certify cargo
oxaction <32-hex-id> isolate scrubber
oxaction <32-hex-id> replace scrubber
oxaction <32-hex-id> restart scrubber
oxreceipt <32-hex-id> cargo
oxreceipt <32-hex-id> scrubber
oxhail mara = Are the restraints secured?
oxhail teo = Is the scrubber working?
~~~

All transitions require the proper character, physical access and stage-
specific inspections. Replaying the same ID returns the original receipt,
including a failed attempt, rather than applying an action twice. The
historical two-argument `oxaction`/`oxreceipt` forms still target P-01.
**PR #19 passed all 13 focused Ox CI workflows and is merged.** A real
five-client test showed safe recovery from a lost cartridge-replacement
acknowledgment alongside coolant, cargo, hails and world-owned handover.

## Accepted full-ship operation and autonomous-crew boundary

The full 950 m vessel model under [`design/ship/`](../design/ship/README.md) is materialised in Evennia as persistent canonical rooms and exits. Since G19, ordinary characters traverse those exits through world-owned pressure, interlock, suit and indexed-transfer gates (`world/ship_crew_access.py`), and operate full-ship machinery with the receipted `oxplantread` / `oxplant` commands. The `board ox` development entry remains Developer-only. The autonomous crew and the proving-ground commands documented below still use the seven-compartment ship. See [integration scope](../design/ship/EVENNIA_INTEGRATION.md) and the [G19 acceptance record](../design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md).

## Start the game

With Python 3.12+ and a virtual environment, run from the repository root:

~~~sh
python -m pip install -e .
cd game
evennia migrate
evennia start
~~~

Default settings bind **only to localhost**: Telnet `127.0.0.1:4000`,
web client `http://127.0.0.1:4001` and AI-character WebSocket
`127.0.0.1:4002`. Registration is disabled by the Ox development
settings; use an existing developer/test account or the one-time
Evennia initial owner setup. The first-start hook `at_initial_setup`
builds the ship. If the database predates it, from `game/` run:

~~~sh
evennia shell --command="from world.bootstrap import build_ship; build_ship()"
~~~

`build_ship()` is idempotent: it will not duplicate rooms or reset a
faulted pump, cargo status, cartridge stock, existing events or crew positions.
Stop the local server
using `evennia stop` from `game/`. The private signing key lives in an
ignored `game/server/conf/.local-secret` unless supplied as `OX_SECRET_KEY`.
These settings are **not suitable for a public deployment**.

## Ordinary in-world exploration

From Limbo, the `board` exit leads to the Bridge:

~~~text
board
look
look console
look roster
aft
engineering
look pump
inspect pump
~~~

The original route is preserved, with new branches:

~~~text
Bridge <--fore/aft--> Connecting Passage <--out/engineering--> Engineering
                           |     |       |                       |
                      Cargo    Environmental  Crew Mess      Machine Shop
                    (starboard)   (port)       (mess)         (workshop)
~~~

From the Bridge use `inspect operations` to see world-authoritative cargo and
environmental status. In the passage use `inspect duties` to read the
posted responsibilities. Branches have explicit reverse exits:
Cargo `port`, Environmental `starboard`, Mess `out`, Shop `out`.

A **Developer-authorized** character may enter Engineering and use
`shipengineer` to acquire a test engineering role, then use
`shipfault pump` to introduce a synthetic failure. Only a character
physically present and authorized by the current world rules can
operate the pump:

~~~text
shipengineer
shipfault pump
inspect pump
isolate pump
repair pump
commission pump
inspect pump
~~~

These are actual game commands, not instructions to change `.db` fields.
The Bridge console permits **remote observation**, not remote repair.
When the P4 safety gate is enabled, the engineer must also obtain a
fresh independent safety release after repair, before commissioning.
The chief cannot self-approve during her own engineering watch.

## Additional specialist duties (P4d)

**Cargo officer Mara Voss**, physically in Cargo Hold, uses:

~~~text
inspect cargo
restow cargo
inspect cargo
certify cargo
~~~

These become necessary after an operator injects a **synthetic**
`shipfault cargo` while standing in the hold. C-01 begins with eight
sealed containers and twelve possible positions; a simulated load shift
loosens two restraints. Restow requires the officer's own fresh local
inspection; certification requires another inspection *after* restow.
Being in the wrong compartment or holding the wrong role is refused.

**Environmental technician Teo Hale**, in the Environmental Plant, uses:

~~~text
inspect scrubber
isolate scrubber
replace scrubber
inspect scrubber
restart scrubber
~~~

An operator can introduce a saturated cartridge with
`shipfault scrubber` in that room. A-01 consumes one of two initially
stocked spares per replacement. Without a spare, the fixture remains
isolated rather than creating an imaginary cartridge. Atmospheric and
cargo fault events are individually addressed to their specialist and
to Lin; other characters cannot read them from their own inbox.

For local hands-on tests, a **Developer** can switch their own ordinary
character to a disposable specialty with `shiprole cargo` or
`shiprole environment`. They must still walk into the appropriate
compartment and inspect the equipment; the assignment does not authorize
work remotely. Normal players cannot assign themselves a role this way.

Developer-only synthetic faults and specialist work verbs are
available through ordinary game commands. This P4d world-physics section
predates the P4e autonomous-specialist milestone: **Mara and Teo now have
their own separate Concordia agents**, and C-01/A-01 have durable
actor-bound receipts. P4g additionally offers a common typed work
namespace; the existing five-crew supervisor still uses the compatible
fixture-specific recovery path. Those original P4d competence tags were later superseded by the G4
world-owned skill/knowledge/technique ledgers and G4f practical progression;
this paragraph otherwise describes historical P4d/P4g sequencing. See
[the P4d implementation history](../design/prototypes/p4d-ship-departments.md).

## Authenticated three-crew protocol (P3)

The external AI handler connects through Evennia's ordinary JSON
WebSocket sessions. The game binds a nonprivileged account to one
specific character via an identity/nonce challenge.

- `oxidentity` verifies the caller's own character identity.
- `oxinbox <cursor>` replays private world events addressed to that
  character, with stable IDs, sender, time and scalar details.
- `oxradio` transmits a bridge alarm to the **currently assigned**
  engineer (Ari or Iona).
- `oxaction <request-id> <isolate|repair|commission>` issues a
  physical operation. The game returns an actor-bound, durable
  `ox_receipt`. `oxreceipt <request-id>` reconciles it if the response
  was lost; retrying with a new request ID would be unsafe.
- `oxrequest` requests independent safety review; `oxapprove`
  records a world-validated local inspection and signoff.
- `oxresolve` reports independently verified normal pressure.
- `oxhandover` and `oxaccept` transfer an in-world watch only after
  the correct due event, briefing and authorization.

See [wire and authority contracts](../contracts/README.md),
[`game/commands/crew.py`](commands/crew.py),
[`game/commands/ship.py`](commands/ship.py) and
[`game/world/live_crew.py`](world/live_crew.py).

## The genuine watch clock (P4b)

Earlier P3 acceptance fixtures used an artificial jump to 07:55
after closing the incident. P4b adds an **Evennia-owned persistent
`ShipDutyClock` Script**, which fires a due event according to a
world-stored time deadline. The fixture's `scheduled_clock=True` mode
arms a short experimental deadline; it is **not** a complete shipboard
calendar or realistic eight-hour schedule.

On the test handover, active engineering duty transfers from Ari to Iona.
Ari is separately assigned independent safety-review authority; Iona
cannot operate P-01 **and** approve her own commissioning. The second
coolant incident is therefore repaired by Iona and reviewed by Ari.

For executable evidence, use [P4b world tests](world/tests/test_autonomy.py)
and the [full P4b Actions workflow](../.github/workflows/ox-p4b-autonomy.yml).

## Automated game tests

From a repository-root environment with Evennia installed:

~~~sh
cd game
python -m world.test_runner world.tests.test_ship --verbosity=2
python -m world.test_runner world.tests.test_live_cooperation --verbosity=2
python -m world.test_runner world.tests.test_autonomy --verbosity=2
python -m world.test_runner world.tests.test_departments --verbosity=2
~~~

Use `--verbosity=2`, not `-v 2` (Evennia reserves `-v` for version
information). These tests use Django's test database. The independent
full-server workflows validate session behavior and persisted PostgreSQL
state separately. Focused CI is intentionally distinct from the large
inherited Evennia matrix.

## Live P4 demonstrations in GitHub

The most useful earlier three-AI demonstration is **Actions → Ox P4b autonomous
two-incident ship → Run workflow** on `main`:

1. CI builds a disposable game with three ordinary bot accounts.
2. Three native Concordia entities perform finite choices during an
   initial P-01 fault; GOAP performs ordinary physics through receipts.
3. A game-owned watch event lets Ari offer and Iona accept the handover.
4. The world then develops a second fault; Iona is the active repairer
   and Ari must independently inspect/approve the release.
5. CI terminates/restarts the independent handler after a deliberately
   lost isolation ACK. It reconciles the same action ID and verifies
   the game's eight physical transitions—exactly two complete cycles.

`ox-p4a-concordia-crew.yml` tests a single live incident with three
native Concordia entities. `ox-p3-three-crew.yml` retains the earlier
purely deterministic three-client regression. All three use **synthetic
test data and a deterministic model**; they do not demonstrate unscripted
conversation among three hosted models. No Gemini secret is needed.

## Earlier single-engineer experiments (retained)

The in-process developer harness `game/world/ai_repair.py` predates the
external transport. It uses normal Evennia character commands, but
executes a local trial **inside the game process**. This remains useful
as a control experiment, not the current handler architecture.

After installing `./services/ai-handler[concordia]`, from `game/`:

~~~sh
python -m world.test_runner world.tests.test_agent_repair --verbosity=2
evennia shell --command="from world.ai_repair import live_trial; live_trial()"
~~~

`live_trial()` is **state-changing**: it faults the real local P-01,
may move Ari, and validates the final world event history. Use a
throwaway database. For local OpenAI-compatible models, set
`OX_LLM_BASE_URL`, `OX_LLM_MODEL` and the necessary API placeholder/key.
For the older Gemini choice experiment, `OX_TRIAL_PROVIDER=gemini`,
`GEMINI_API_KEY` and `OX_LLM_MODEL` configure that in-process harness.
This older `OX_TRIAL_PROVIDER` setting is different from the P4 external
handler's `OX_COGNITION_PROVIDER`.

The manual **Ox live Gemini pump repair** GitHub workflow is available
with a repository Actions secret named `GEMINI_API_KEY`. It runs the
single-engineer test on synthetic ship data; it is neither an
always-on inference service nor a three-crew LLM benchmark.
Provider availability, free-tier terms and quotas are external and may
change. Do not commit credentials or real private player data.

The **Ox GOAP pump repair (zero LLM)** workflow tests the deterministic
engineer without a model, including a repeat-fault/replanning case.
Its reuse in P3/P4 does not mean GOAP can diagnose unknown machinery
or perform general language tasks.

## Boundaries and future work

P4b supplies a **runnable** independent `serve` supervisor, but it is
not automatically deployed by `evennia start`. Test provisioning in
`world/transport_probe.py` creates disposable accounts sharing one
CI password and refuses to overwrite existing accounts. Do not use it
as a production account registrar.

All three major equipment systems have actor-bound durable world
receipts. The shared `oxwork` command additionally supports typed social
and equipment work requests, and the P4h supervisor persists original IDs
across five consequential pump stages. The eight-process trial (seven restarts)
proves those specific recovery paths, not every hail, handover, or specialist
work interruption. The browser observatory remains deferred.

See [setup](../INSTALL.md), [handler operations](../services/ai-handler/README.md),
[P4 status](../design/STATUS.md) and [original P2 scenario](../scenarios/coolant_fault/README.md).


## G3e uncertain case and follow-up (opt-in)

G3e-1 merged PR #47. The operator may arm one intermittent analyzer anomaly
using `world.investigation.arm_anomaly()`; five crew independently sample
existing station instruments with `oxsample <case-id>`. The latent cause is
never in the initial addressed notice; authenticated world WorkReceipts
gate each report and Lin's unconfirmed first assessment.

G3e-2 (merged PR #48; 46/46 final-head checks) adds `oxprobe <case-id>` for role-specific
second-stage diagnostics after a specialist has challenged Lin's first
explanation. Global `oxwork` operations `anomaly_challenge`,
`anomaly_probe_report`, `anomaly_reconsider` and `anomaly_reassess`
require the actual local sample and appropriate evidence/role.
These are testimony and tentative hypotheses, never physical repairs
or oracle lookups. Existing emergency and safety procedures take priority.
[Detailed contract](../design/prototypes/g3e-contradictory-evidence.md).


## G3e-3: independent known-unknown investigation

Existing Ari, Iona, Mara and Teo may initiate `anomaly_question` as a
world-receipted `oxwork` with a legitimate firsthand original case report
and their own local station access. The handler can then use `oxprobe`
and `anomaly_probe_report` without requiring `anomaly_challenge` or
a previous Lin theory. One question/sample per specialist per open case;
instrument readings, private opinions and bridge reassessments never
reveal or modify the world-secret cause. The original G3e-2 protocol is
still available for comparison.

[Verification, operation flags and trial evidence](../design/prototypes/g3e-independent-questions.md).
