# G19 — Unified time authority for pause and watch-until

**Status:** implementation contract, not installed behaviour. Written after
the verified drum-3 watch predicate (#158). Account-session wake notifications
are a separate preceding delivery slice (#159).

## Why a separate clock integration is necessary

The game already has a single *physical authority*:
`meta:continuous-physics` in `CanonicalShipState`.
`tick_continuous_physics` advances no more than 60 game seconds per
transaction, with internal physical integration steps. The existing
`ContinuousShipPhysicsClock` invokes it every ten real seconds.
By default, the clock target is taken from
`evennia.utils.gametime.gametime(absolute=True)`; ordinary world events
also use that clock.

**Additional fitted time consumers (confirmed in the repository):**
`game/world/live_clock.py` defines a separate persistent
`ShipDutyClock` on a two-real-second interval. It invokes
`tick_game_clock`, `independent_rounds.tick_rounds`, and
`captain.tick_captain_obligations`. Its persisted roster handover deadline
also reads `gametime.gametime(absolute=True)`.
`game/commands/clock.py` exposes that same absolute source as the
authenticated `oxclock` character observation; the AI handler's
`WorldClockPort` and `MemoryClockBridge` use it for crew decision time.
Those are **real integration points**, not hypothetical future systems.
They must be moved behind the same pause barrier before a player-controlled
pause is advertised. The current P3c disposable handover fixture can
synthetically complete a scheduled handover; that operator-only path must
not become a player time-control route.

The lead-mind design says that **pause is deliberation, with nothing in
the world moving**, and that **watch-until advances the world only until
a condition the lead mind can really observe fires**.
The first verified watch (#158) already implements one legitimate
event-time condition over a delivered dry-contact observation. It
does **not** run or stop the simulation clock.

Simply stopping the physics `DefaultScript` while Evennia's game time
continues would not implement pause: on resume, the existing bounded tick
would begin processing accumulated elapsed time. It could also leave
crew task scripts, timers and message routes advancing independently.
Changing Evennia's module-level `TIMEFACTOR` at runtime is not a
persistent world transaction and would not solve these problems.

**Decision:** implement one explicitly owned world-time controller, tied
to the existing physical clock and shared by every simulated actor and
timer. Do not introduce an independent lead-mind clock, a client clock,
or a parallel physics engine. Keep the present baseline working until
all relevant producers have been migrated.

## Required invariants

1. **One timeline.** All consequential physical, crew, cargo, communication,
   medical and controller actions refer to the same monotonically
   increasing simulated game time; each completed step owns its effects.
2. **One transaction.** The world authority holds the existing clock
   row lock when committing a time step or changing time mode.
   A step either commits the world and its event evidence, or rolls back.
3. **Pause really freezes world progress.** While paused, simulated
   actors and world timers cannot independently advance or invent events.
   Authentication, read-only examination and out-of-character deliberation
   may continue. Crew commands made in pause are proposed/queued, not
   physically executed until the next authorised step.
4. **No hidden catch-up.** A player pause never accumulates overdue physical
   simulation. Restarting after pause does not replay elapsed wall time
   as if the simulation had been running. Existing downtime behaviour
   for ordinary unpaused operation remains explicit and bounded.
5. **No fake observations.** A watch-until wake requires an event that the
   enrolled account's **actual reachable instrument or delivered message**
   can observe. A fault hidden behind a dead gateway never stops watch
   merely because an omniscient world journal knows it occurred.
6. **No instant teleport in time.** Acceleration executes the same
   authoritative world transitions as ordinary play, with bounded
   integration steps, consumables, crew work and event receipts.
   Speed changes wall-clock pacing, **not** physics formulas or work costs.
7. **Precise stop boundary.** Stop after the atomic step whose evidence
   caused the watch to fire and before any later world step. Record the
   source event, game time, final committed step, and reason for stopping.
   A coarse tick that crosses a condition without an observable event
   cannot synthesize a wake.
8. **Deterministic concurrent changes.** Arm, cancel, pause, wake,
   crew work, and time-step progression serialize through the world
   clock. Request IDs and revisions make retries idempotent.
9. **Fail closed, not frozen forever.** Every accelerated run has bounded
   game-time and computational budgets. On budget exhaustion, uncertainty,
   non-progress or a failed step, the controller stops or yields with an
   explicit reason; it never silently jumps ahead.
10. **No extra privileges.** Time control cannot operate unfitted machinery,
    bypass local possession, reveal private crew belief, or grant an
    instrument an observation it did not produce.

## Proposed world-owned record

Extend the **existing clock row**, versioned as a new nested
`details["time_control"]` record; do not create a second ticking
`CanonicalShipState`.

| Field | Purpose |
|---|---|
| `schema_version` | Version and strict validation |
| `mode` | `paused`, `realtime`, or `watch_until` |
| `revision` | Monotonic authority / command generation |
| `simulation_time` | Same value as the authoritative clock's latest committed game time |
| `external_anchor` | Recorded scheduler reference, never an alternative world time |
| `excluded_pause_seconds` | Elapsed external time that cannot become gameplay catch-up |
| `watch_request_id` | Existing enrolled watch predicate, only for `watch_until` |
| `watch_generation` | The exact armed generation; prevents reuse of an older firing |
| `run_budget_s` | Maximum remaining world-time advance before yielding |
| `last_stop_reason` | `user_pause`, `watch_fired`, `budget`, `failure`, etc. |
| `last_stop_source` | Original delivered-event ID when a watch actually fired |

This schema is a **design**, subject to the strict persistence integrity
checks and migration tests before it becomes writable. Avoid storing
redundant source truth if it can be derived from the clock and event journal.

## Transition contract

| From | Request | Guard | Outcome |
|---|---|---|---|
| Realtime | Pause | Authenticated lead mind; current clock generation | All world progression stops after the current atomic step |
| Paused | Resume | Same owner; clock state valid | Real-time progression resumes from frozen simulated time, without catch-up |
| Paused | Watch until | Valid currently armed reachable predicate; positive bounded budget | Scheduler advances the unified world in bounded steps |
| Watch until | Delivered firing | Firing event matches the armed generation and account | Commit causative step, enter paused mode, record source |
| Watch until | Budget exhausted | No delivered firing | Enter paused mode and report `budget` |
| Watch until | Route becomes unavailable | Cannot establish safe current observation contract | Yield/stop with `unreachable`; do not claim an unseen event |
| Any running | Integrity failure | A world step cannot be committed | Preserve prior state; enter safe stopped mode and report failure |

OOC login and deliberate command composition need not be blocked while
paused; consequential crew/player commands are queued or refused rather
than silently executed. Any emergency automation permitted to run in pause
must be modelled as an explicit exception and reconsidered: ordinarily a
paused world has no passing time in which an emergency can develop.

## Implementation sequence

**T0 — Audit and instrumentation.** Inventory every independently
scheduled world mutator, game-time reader and event writer. Establish
which crew/cargo/communications scripts still use Evennia game time or
wall-clock intervals and add a regression inventory. Instrument the
existing physics clock for deterministic step order without changing
the current game mode.

**T1 — Shared time source.** Add one time-authority accessor backed by
the current `meta:continuous-physics` row. Migrate all world actors,
timers and event writers before accepting a pause command. Keep
operator-controlled test times explicit and isolated from the player
API. All producers must prove they use the same committed time source.

**T2 — Durable pause and resume.** Implement a versioned mode record,
bounded external-time exclusion, account-scoped pause/resume receipts,
restart recovery, and a real progression barrier for all world mutators.
Tests must show a paused live server cannot move crew, air, power,
cargo or world clock.

**T3 — Event-time watch-until.** Bind the accepted #158 predicate
to the existing world stepper. Recheck the authenticated source
after each committed step; pause at the causative event and record
the actual observed source ID. No polling of the private journal
for otherwise hidden faults.

**T4 — Acceleration.** Only after T0–T3: change scheduling cadence
or count of fully committed bounded steps per scheduler opportunity.
Benchmark each subsystem and cap game-time and CPU budgets; never
raise an integrator step or skip simulation work to advertise speed.

## Acceptance demonstrations

- **AT01:** A ten-minute player pause results in zero seconds of
  simulated time, no crew action, no power or gas consumption, and
  no accumulated backlog when resumed.
- **AT02:** The same remains true across restart, reconnect and a
  concurrent pause request; command replay has a single receipt.
- **AT03:** A watch through a hidden fault stays running or yields on
  its budget; it cannot claim knowledge of the fault.
- **AT04:** A drum-3 physical hatch change with a verified A/B delivery
  fires the already armed watch and stops before the next world step.
- **AT05:** The identical action with both backbone routes severed
  cannot fire the watch, including after resurvey and reconnection.
- **AT06:** Local takeover still refuses remote valve actuation while
  the world is running or paused; time mode does not change authority.
- **AT07:** Two command races (pause versus tick, cancel versus delivery)
  commit in a single serial order and never duplicate an action.
- **AT08:** A single simulated minute advanced at several valid pacing
  rates conserves the same mass, energy, work and causal event order
  within the existing deterministic tolerances.
- **AT09:** A bounded watch expires with an explicit `budget` result
  even if no matching source event ever arrives.
- **AT10:** An interrupted/cancelled run survives a process restart
  without lost time or duplicate world work.
- **AT11:** Account logout and reconnect cannot move the world
  independently or leak sensor history; a durable fired watch survives
  a missed best-effort push.
- **AT12:** All existing installed-world, fuzz and long-campaign gates
  remain green.

## Explicit exclusions

This contract does not implement a timeskip, alternate timeline,
chronological rewind, world-independent crew clocks, private-source
subscriptions, automatically generated captain messages, or a
hypothetical ship-wide network fit-out.

A dedicated gate must demonstrate that *all* world mutators observe
the pause barrier before live player time control is enabled. Until
then, #158 watch predicates and #159 account wake notifications
operate under the existing continuous physics schedule only.
