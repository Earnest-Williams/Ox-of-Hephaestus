# Ox of Hephaestus — architecture and authority boundaries

**Current implementation:** P4a/P4c have passed focused full-server
integration tests. Three independently authenticated Concordia crew control
real pump work, watched handovers and answered hails. P4d extends the
authoritative Evennia world to **seven rooms, three bounded physical
systems and five crew bodies**; new cargo/environmental personnel are not
yet autonomous. This is not a deployed freighter or general social simulation.
[Verified feature matrix](design/STATUS.md) · [Development setup](INSTALL.md).

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

**Ox AI handler (implemented for three crew)** owns each character's
Concordia entity, memory, proposed actions, pending requests, journals,
snapshots and wake-up policy. It connects as three ordinary, nonprivileged
Evennia client accounts. The handler can be stopped while the world keeps
its own state, alarms and event journal. Production process supervision,
generic concurrency limits and full crash-resume coverage are future work.

**Human interface (deferred)** is a separately packaged skeleton under
`services/interface/`. The intended UI will join authoritative world
readings with handler-owned cognitive records through **two distinct
authenticated read APIs**. Neither the joined API nor the browser app
exists. The interface must never create a second store of ship truth.

## 2. The currently implemented ship

`game/world/bootstrap.py` installs Bridge, Connecting Passage, Engineering,
Cargo Hold, Environmental Plant, Crew Mess and Machine Shop. Existing crew
Lin Sato, Ari Sen and Iona Vek remain, alongside non-autonomous cargo
officer Mara Voss and environmental technician Teo Hale. The Bridge
has both cooling and cargo/environmental status consoles. The original
pump P-01 remains under three-AI control and has the lifecycle:

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
survive game restart. They **do not yet implement generic actor-bound
command receipts**, so crash-safe AI control of these new devices is future
work. Cargo and atmosphere alarms are addressed to their specialist and
the Bridge, never broadcast to all crew. The public duty board lists
responsibilities; it is not a character memory store.

World events (`ox_event`) are stored for a **single recipient** with a
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
persistent game database. This is **not** yet proof of recovery from
every possible mid-scene interruption or of production 24/7 uptime.

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
- Ox wire event IDs, physical request IDs, world event timestamps and
  actor dbrefs support attribution; social commands do **not** all have
  the same durable/transactional receipt guarantees as physical actions.
- Individual cognitive journals are private operator diagnostics, not
  authorized input for other crew or a public dashboard.

## 6. Planned systems and explicit non-goals for P4

The eventual bulk freighter will have cargo, propulsion, maintenance
scheduling, department structures, trained skills without level/class
progression and wider AI crew. These have **not been built** in the
three-compartment fixture. The postponed P5 observatory would join
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
