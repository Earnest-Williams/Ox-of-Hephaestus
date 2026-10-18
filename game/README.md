# Ox playable ship — authoritative Evennia game

**Status (18 October 2026):** Seven connected compartments, three physical
equipment systems and **five separately authenticated native Concordia
crewmembers**. Lin, Ari and Iona work the cooling/watch chain; Mara and
Teo autonomously handle bounded cargo and atmosphere procedures. It is
still a proving ground, not a complete cargo freighter.
[Current milestone status](../design/STATUS.md).

All Ox ship content is under `game/`; the inherited `evennia/` engine has
not been converted into a different distribution.

## What is in the world

| Object | Game-owned behavior |
| --- | --- |
| Bridge | Lin Sato, posted roster, real-time pump telemetry and in-world radio |
| Connecting Passage | Junction for Bridge, Engineering, Cargo Hold, Environmental Plant and Crew Mess; posted department duties |
| Engineering | Ari Sen, Iona Vek and physical access to pump P-01 |
| Cargo Hold | Mara Voss and cargo restraint grid C-01; local inspection, restow and certification |
| Environmental Plant | Teo Hale and scrubber A-01; cartridge fault, isolation, replacement, verified restart |
| Crew Mess | Navigable living/galley area, not yet a nutrition or morale simulation |
| Machine Shop | Navigable engineering annex, reserved for later fabrication and tools |
| Operations Console | Bridge-only readout of cargo restraint and atmosphere scrubber states |
| Cooling Pump P-01 | `normal → low_pressure → isolated → repaired → normal`; durable event history and physical command receipts |
| Ship roster | Active engineering duty holder, independent safety reviewer and handover state |
| Duty Script | Persistent `world.live_clock.ShipDutyClock` checks an armed world deadline; it never calls a model |
| World-private events | Receiver-specific `ox_event` observations and `oxinbox` replay; no cross-crew memory access |

The ship now has separate bounded physical cargo and atmosphere procedures.
There is still **no propulsion, trading economy, general cargo routing,
manufacturing, or skill-by-use progression**. The P4e supervisor runs
five private cognitive agents; the original P4c three-crew supervisor
remains available but must not be run simultaneously on the same ship.

## P4h pump-work recovery across handler restarts (merged PR #24)

A separately running three- or five-crew handler can restart after a
world-confirmed pump repair, safety request, independent review,
commissioning or incident resolution. The handler preserves each work
request ID before sending it; after restart, it reconciles against the
world's actor-bound receipt rather than inventing a second attempt.

The [P4h Actions gate](../.github/workflows/ox-p4h-pump-recovery.yml)
tests seven independent process starts, including an interrupted prepared
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
fixture-specific recovery path. Competence tags are future skill hooks,
not a live skill progression mechanism. See
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
full-server workflows validate session behavior and persisted SQLite
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
across five consequential pump stages. The seven-process restart trial
proves those specific recovery paths, not every hail, handover, or specialist
work interruption. The browser observatory remains deferred.

See [setup](../INSTALL.md), [handler operations](../services/ai-handler/README.md),
[P4 status](../design/STATUS.md) and [original P2 scenario](../scenarios/coolant_fault/README.md).
