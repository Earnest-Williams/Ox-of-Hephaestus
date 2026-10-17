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
- Maintains or coordinates each agent's memory, beliefs, goals, duties, plans, and decision state.
- Schedules cognition and shares model/inference resources among agents; one NPC is not one AI server process.
- Converts perceptions into proposed actions and receives the results through a transport adapter.
- Does not own or silently override authoritative ship or character state.

**Operational interface (planned)**

- Exposes ship-wide overviews and drill-downs for crew, departments, cargo, machinery, incidents, and time-series data.
- Makes decisions and outcomes inspectable without treating the UI as a source of game truth.
- May coexist with traditional MUD clients; the display and interaction design is not yet settled.

## 2. Transport: start conventional, then specialise

### Phase A — normal client connections

The external handler connects AI characters to an unmodified or minimally configured Evennia game as ordinary clients. Each controlled character has an appropriate game identity/session and uses commands and observations exposed by the game.

This allows the handler, agents, and initial scenario to be developed and evaluated without first changing Evennia's server internals.

The handler should depend on a small transport contract—roughly **connect, observe, act, receive outcome, disconnect**—rather than on the incidental details of a particular MUD protocol.

### Phase B — a dedicated AI-service endpoint

If the conventional-client prototype works, introduce a purpose-built authenticated endpoint. A single service connection could act on behalf of several separately identified NPCs and receive structured observations or event notifications.

That endpoint must resolve the acting character, apply the normal authorization and world rules, and return the same kinds of outcomes the character would encounter through ordinary play. **A service credential must not automatically become omniscience or a bypass around the game.**

The endpoint is an intended optimization and integration improvement, not a prerequisite for the first prototype.

## 3. Agent identity and knowledge

Every significant NPC should have distinct persistent identity and continuity. Their own goals, assigned duties, skills, remembered experiences, and imperfect understanding of events may differ from the canonical ship state.

In particular:

- An agent may act only on information it can legitimately obtain, directly or from other characters or systems.
- The game resolves what an action physically changes; the handler decides what an agent attempts.
- Skills are intended to advance from practice, training, and use, not fixed classes or character levels.
- A duty roster creates obligations and opportunities, but it should not dictate every decision by script.

Whether memories and plans use files, a database, or another persistence layer remains open.

## 4. Time and workload

The ship should be able to progress without a human connected. That does **not** imply one high-frequency LLM call per NPC or a fully detailed real-time simulation of every compartment at every instant.

An initial implementation can combine scheduled duties, meaningful events, asynchronous decision queues, coarse background ticks, and deferred catch-up. Work should remain causally consistent with Evennia's authoritative state and become detailed when consequences require it.

## 5. First proving-ground scenario

Start with a handful of rooms and crew rather than the full freighter:

1. An engineering space, a control room, and a connecting passage.
2. Three individually managed crew members with distinct responsibilities and duty assignments.
3. A routine maintenance or watchkeeping schedule.
4. A failure such as a cooling pump fault, observable by appropriate crew or instruments.
5. Logs that show who noticed what, what they believed, whom they contacted, and what they tried.

Success means meaningful autonomous coordination and valid in-world actions, not merely convincing dialogue.

## 6. Deliberately undecided

The AI model, inference backend, message/event schema, storage engine for agent cognition, final dedicated API shape, ship-system fidelity, and dashboard technology have **not** been chosen here.

The early priority is a testable separation of concerns: **the game determines what is true and possible; the agents decide what to try; the transport lets us change how they communicate.**
