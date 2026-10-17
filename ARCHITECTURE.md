# Ox of Hephaestus — preliminary architecture

> **Status:** Design sketch, October 2026. This document describes intended boundaries and experiments, **not an existing implementation**. Decisions remain revisable.

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

## 2. Transport: start conventional, then specialise

### Phase A — normal client connections

The external handler connects AI characters to an unmodified or minimally configured Evennia game as ordinary clients. Each controlled character has an appropriate game identity/session and uses commands and observations exposed by the game.

This allows the handler, agents, and initial scenario to be developed and evaluated without first changing Evennia's server internals.

The handler should depend on a small transport contract—roughly **connect, observe, act, receive outcome, disconnect**—rather than on the incidental details of a particular MUD protocol.

### Phase B — a dedicated AI-service endpoint

If the conventional-client prototype works, introduce a purpose-built authenticated endpoint. A single service connection could act on behalf of several separately identified NPCs and receive structured observations or event notifications.

That endpoint must resolve the acting character, apply the normal authorization and world rules, and return the same kinds of outcomes the character would encounter through ordinary play. **A service credential must not automatically become omniscience or a bypass around the game.**

The endpoint is an intended optimization and integration improvement, not a prerequisite for the first prototype.

## 3. Interface and API contracts

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

## 4. Agent identity and knowledge

Every significant NPC should have distinct persistent identity and continuity. Their own goals, assigned duties, skills, remembered experiences, and imperfect understanding of events may differ from the canonical ship state.

In particular:

- An agent may act only on information it can legitimately obtain, directly or from other characters or systems.
- The game resolves what an action physically changes; the handler decides what an agent attempts.
- Skills are intended to advance from practice, training, and use, not fixed classes or character levels.
- A duty roster creates obligations and opportunities, but it should not dictate every decision by script.

Whether memories and plans use files, a database, or another persistence layer remains open.

## 5. Time and workload

The ship should be able to progress without a human connected. That does **not** imply one high-frequency LLM call per NPC or a fully detailed real-time simulation of every compartment at every instant.

An initial implementation can combine scheduled duties, meaningful events, asynchronous decision queues, coarse background ticks, and deferred catch-up. Work should remain causally consistent with Evennia's authoritative state and become detailed when consequences require it.

## 6. First proving-ground scenario

Start with a handful of rooms and crew rather than the full freighter:

1. An engineering space, a control room, and a connecting passage.
2. Three individually managed crew members with distinct responsibilities and duty assignments.
3. A routine maintenance or watchkeeping schedule.
4. A failure such as a cooling pump fault, observable by appropriate crew or instruments.
5. Logs that show who noticed what, what they believed, whom they contacted, and what they tried.
6. A minimal read-only interface combining a pump/room status view from Evennia with each engineer's status and recorded decisions from the AI handler.

Success means meaningful autonomous coordination, valid in-world actions, and correctly attributed observations—not merely convincing dialogue.

## 7. Deliberately undecided

The AI model, inference backend, message/event schema, storage engine for agent cognition, final dedicated API shape, interface/backend technology, ship-system fidelity, and dashboard technology have **not** been chosen here.

The early priority is a testable separation of concerns: **the game determines what is true and possible; the agents decide what to try; the interface exposes both without silently changing either; the transport lets us change how they communicate.**
