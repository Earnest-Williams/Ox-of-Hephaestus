# Ox of Hephaestus — preliminary architecture

> **Status:** Agreed prototype architecture, first native Concordia entity integration candidate and a small playable Evennia test ship, October 2026. The agent has **not** been connected to the ship; the AI supervisor, game adapters and UI remain unimplemented.

## 1. System boundaries

**Evennia (the authoritative game server)**

- Owns the game-world state: characters, locations, items, machinery, ship systems, and consequential actions.
- Applies normal game permissions, rules, time advances, and action outcomes.
- Delivers observations and events to characters through the available game interfaces.
- Remains usable by ordinary human clients.

**External AI handler (a separate service)**

- Manages many distinct, persistent AI-controlled characters.
- Maintains or coordinates each agent's memory, beliefs, goals, interpretation of duties, plans, and decision state; official in-world duty assignments remain game state.
- Schedules cognition and shares model/inference resources among agents; one NPC is not one AI server process.
- Converts perceptions into proposed actions and receives the results through a transport adapter.
- Does not own or silently override authoritative ship or character state.

**Human interface (a distinct, separately operable component)**

- Presents traditional gameplay where useful, ship-wide views, departments, cargo, machinery, crew, incidents, and historical charts.
- Obtains **authoritative world data and game actions from Evennia's interfaces**, using narrowly scoped Ox-specific endpoints when the existing Evennia facilities are insufficient.
- Obtains **agent-owned information through an API exposed by the external AI handler**: agent status, beliefs, goals, intended actions, recorded decisions, and execution history, subject to permissions.
- Combines those sources for human inspection without becoming a third authoritative store for physical or cognitive state.
- May include a lightweight backend-for-frontend for authenticated requests, event aggregation, and access control. Its deployment shape and screen design remain open.
- Is optional to the autonomous operation of the ship; closing all dashboards must not halt the game or its crew.

## 2. Concordia cognitive foundation and minimal Game Master

**Decision:** Adopt [Concordia](https://github.com/google-deepmind/concordia) (Apache-2.0, distribution `gdm-concordia`) for Prototype 1. Each full NPC is represented by a Concordia `EntityAgentWithLogging`. An independent Ox handler supervises entities, inference budgets, memory persistence, scheduling and game transport.

Start with observation, memory and acting components, adding Ox-specific duties, commitments and procedures. Use rich deliberative components selectively rather than running several expensive model requests for every routine action.

A Concordia Game Master **can be deterministic**. In the mock-world experiment, explore its interrupt-driven event masks and timers, but the **mock world**, not a generative GM, resolves physical actions. In the live Evennia mode, the handler may invoke `observe()` and `act()` directly without adopting Concordia's world-driving simulation loop or clock. The Evennia world remains authoritative.

Concordia's published v2.4.0 release lacks the newer interrupt-driven scheduler. The handler's optional dependency is pinned to a [reviewed upstream revision](https://github.com/google-deepmind/concordia/tree/4b7e02a94b719e56f10989046af32d79bbbc3b9c), as described in [ADR 0001](design/decisions/0001-concordia-first.md). See [ADR 0002](design/decisions/0002-game-master-world-authority.md) for GM boundaries and [Prototype 1](design/prototypes/01-autonomous-crew.md) for build gates.

## 3. Transport: start conventional, then specialise

### Phase A — normal client connections

The external handler connects AI characters to an unmodified or minimally configured Evennia game as ordinary clients. Each controlled character has an appropriate game identity/session and uses commands and observations exposed by the game.

This allows the handler, agents, and initial scenario to be developed and evaluated without first changing Evennia's server internals.

The handler should depend on a small transport contract—roughly **connect, observe, act, receive outcome, disconnect**—rather than on the incidental details of a particular MUD protocol.

### Phase B — a dedicated AI-service endpoint

If the conventional-client prototype works, introduce a purpose-built authenticated endpoint. A single service connection could act on behalf of several separately identified NPCs and receive structured observations or event notifications.

That endpoint must resolve the acting character, apply the normal authorization and world rules, and return the same kinds of outcomes the character would encounter through ordinary play. **A service credential must not automatically become omniscience or a bypass around the game.**

The endpoint is an intended optimization and integration improvement, not a prerequisite for the first prototype.

## 4. Interface and API contracts

**The interface must consume both backends, through clearly separate interfaces.** This is a planned architectural requirement, not a claim that the needed endpoints already exist.

```text
      Human players / observers / operators
                        |
                Interface component
                  /           \
     Evennia-facing API     AI-handler API
            |                    |
      Evennia server <------> AI handler
        world truth       agent transport and cognition
```

The interface may make both requests itself or use an interface-owned backend-for-frontend to consolidate auth, events, and presentation-friendly responses. That backend is a gateway/read-model layer, not a fourth simulation authority.

### Evennia-facing data and actions

- Read ship and game facts: rooms, equipment, cargo, crew positions, in-world duty assignments, events, and operational measurements when available to the requesting identity.
- Perform normal in-world commands or appropriately authorised ship operations through Evennia. Game rules remain authoritative regardless of whether a human used a text client or dashboard.
- Reuse supported Evennia networking and API mechanisms. Where stock Evennia lacks ship-specific read models, add explicit extensions rather than reach into its database from the UI. No claim is made that the complete dashboard API currently exists.

### AI-handler-facing data and controls

The independent handler should offer its **own versioned, authenticated API**, ideally separate from its transport to the game server. Candidate capabilities include:

- List managed agents and expose their online/offline status, current decision activity, goals, intended next actions, and handler-side schedules.
- Inspect recorded observations, beliefs, memory summaries, decisions, attempted game commands, and the outcomes agents received—subject to viewing permissions.
- Expose operational diagnostics such as action queues, inference workload, errors, and event histories.
- Support explicitly authorised **operator controls** such as pausing/resuming an agent or changing an administrative execution setting; these are not ordinary in-world character actions.

These describe information and action categories rather than fixed REST paths or a selected protocol. Preserve an explicit distinction between an agent's **belief** and an authoritative fact, and between a decision explanation logged by the handler and any unrecorded internal model reasoning.

### Joining both sides without losing provenance

A stable mapping between an Evennia character ID and a handler agent ID will let the UI assemble a crew profile from both sources. Correlatable event IDs, game-time and wall-time timestamps, and distinguishable observed / attempted / succeeded / failed states are useful targets for the eventual API schemas.

- A pump's actual condition comes from **Evennia**; an engineer's belief that it is broken comes from **the AI handler**.
- An issued duty assignment comes from **Evennia**; how the agent plans to fulfil it comes from **the AI handler**.
- A human's command to operate a pump routes to **Evennia**; an administrator's command to pause an AI agent routes to **the handler**.
- Displaying or exporting diagnostic cognition must not leak private agent information to ordinary players or grant them omniscience.

For an initial prototype, polling suitable endpoints is acceptable. Streaming updates (for example via WebSockets or server-sent events) can be introduced where supported or deliberately implemented; it is not a prerequisite to begin. The handler and game continue without any interface connection.

## 5. Agent identity and knowledge

Every significant NPC should have distinct persistent identity and continuity. Their own goals, assigned duties, skills, remembered experiences, and imperfect understanding of events may differ from the canonical ship state.

In particular:

- An agent may act only on information it can legitimately obtain, directly or from other characters or systems.
- The game resolves what an action physically changes; the handler decides what an agent attempts.
- Skills are intended to advance from practice, training, and use, not fixed classes or character levels.
- A duty roster creates obligations and opportunities, but it should not dictate every decision by script.

Prototype 1 will begin with Concordia component snapshots and an append-only decision/event journal; the durable storage backend and retrieval approach remain to be implemented. The skeleton `WorldPort` contract in `services/ai-handler/` is not a finished transport implementation.

## 6. Time and workload

The ship should be able to progress without a human connected. That does **not** imply one high-frequency LLM call per NPC or a fully detailed real-time simulation of every compartment at every instant.

An initial implementation can combine scheduled duties, meaningful events, asynchronous decision queues, coarse background ticks, and deferred catch-up. Work should remain causally consistent with Evennia's authoritative state and become detailed when consequences require it.

## 7. First proving-ground scenario

Start with a handful of rooms and crew rather than the full freighter:

1. An engineering space, a control room, and a connecting passage.
2. Three individually managed crew members with distinct responsibilities and duty assignments.
3. A routine maintenance or watchkeeping schedule.
4. A failure such as a cooling pump fault, observable by appropriate crew or instruments.
5. Logs that show who noticed what, what they believed, whom they contacted, and what they tried.
6. A minimal read-only interface combining a pump/room status view from Evennia with each engineer's status and recorded decisions from the AI handler.

Success means meaningful autonomous coordination, valid in-world actions, and correctly attributed observations—not merely convincing dialogue.

## 8. Deliberately undecided

The Concordia framework and deterministic GM authority boundary are chosen for Prototype 1. The specific model, inference server, durable storage, event/wire schema, dedicated Evennia API, UI framework and ship-system fidelity remain open.

The early priority is a testable separation of concerns: **the game determines what is true and possible; the agents decide what to try; the interface exposes both without silently changing either; the transport lets us change how they communicate.**

## 9. First concrete Evennia game directory

The standalone [`game/`](game/README.md) directory is now a **playable fixture**, not an invented model observation. Its idempotent builder (`game/world/bootstrap.py`) creates a bridge, connecting passage, engineering compartment, four physical exits, three initially idle crew bodies, a pump, status console and posted roster. If Evennia has generated Limbo, an additional boarding exit makes the ship accessible from the default entry room. The pump's `normal -> low_pressure -> isolated -> repaired -> normal` transitions and event history persist as game-owned state. The read-only bridge telemetry reads its actual state; physical commands require presence and an authorised character role.

This does **not** mark P2, P3 or P4 complete: there is no multi-agent mock scenario or external agent-to-Evennia transport. A local in-process repair experiment now lets one Concordia entity attempt normal Evennia commands, but it does not exercise a remote session or establish unscripted model competence. The dedicated `ox-ship-world.yml` workflow exercises game mechanics on an isolated Django test database. The existing P1 Concordia agent operates separately until an ordinary client transport is implemented.

## 10. Single-character in-process command experiment

`game/world/ai_repair.py` is a deliberately limited **developer harness**:
a Concordia entity is paired with the actual Evennia engineer object. An
operator places the engineer on the bridge and injects a pump fault. The
entity receives only in-game text returned by ordinary commands and a list
of locally visible command options. Each selected action goes through
`DefaultCharacter.execute_cmd`, not a new privileged endpoint or direct
Attribute mutation. Evennia determines movement, permissions and pump state.
An external evaluator inspects the game-owned event log only **after** the
agent has stopped, requiring a real pump recovery attributed to the
engineer's character ID.

Scripted-choice CI proves command-dispatch wiring, not planning. The opt-in
`live_trial` permits an actual LLM to choose actions; users must supply an
inference endpoint and inspect whether it succeeds. This exception to our
planned three-service topology is temporary: normal network character
sessions and a genuine independently running handler remain required.


## 11. GOAP without a language model

An additional policy is being developed for the same P-01 Evennia
command harness: a model-independent GOAP planner with known preconditions,
effects, costs, and ship layout. It uses character-authorised text
observations to learn current equipment state, and retains its planned
action sequence until the world contradicts its predictions. Each command
still passes the existing Evennia access and physical-state checks.

This does not change Concordia's status as an experimental cognitive host:
routine deterministic planners must work without it. The GOAP fixture is
not proof of general shipwide autonomous behavior. For limitations, tests
and interface decisions see ADR 0006.


## 12. Event-driven three-crew mock world

A new P2 fixture extends the single-engineer experiment to three distinct,
role-specific policies and an event-driven handler. A deterministic mock
world owns a simulated game clock, active-watch roster, authorised readings,
co-located message delivery and world receipt IDs. The handler supervises
Ari, Iona and Lin with individual memories and scheduled obligations.
No model or Concordia dependency is required for this mock duty scenario.

Ari can relay a previously observed, unverified concern to Iona at watch
handover; Lin does not gain access to its content. Iona's acknowledged
acceptance causes the world to transfer engineering duty. Quiet intervals
produce no agent wakeups, and unknown command receipts are reconciled
without replaying the command.

This is deliberately **not** an external service linked to persistent
Evennia sessions. The rest of P2 (mock coordinated cooling fault), P3
(live transport), and P5 (observatory) remain open. See
[ADR 0007](design/decisions/0007-three-crew-watch-supervision.md).
