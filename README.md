# Ox of Hephaestus

**An autonomous spaceship MUD and shipboard simulation, built on [Evennia](https://www.evennia.com/).**

> **Project status: first playable test ship and first Concordia entity integration candidate.** The standalone `game/` directory contains real Evennia rooms, a pump, bridge telemetry and idle crew bodies. The `services/ai-handler/` package has a tested single-agent Concordia lifecycle and a short-lived, in-process experiment now drives one engineer through real Evennia commands. **The independent handler transport, autonomous crew orchestration and dashboard do not exist.**

## Try the little ship

A real, playable **three-compartment Ox ship** is now available in [`game/`](game/README.md), without changing Evennia's engine. The game fixture creates a bridge, connecting passage, and engineering space, three idle crew, a live bridge cooling readout, a duty board and a stateful P-01 cooling pump. It can be explored with a normal MUD client, and an authorised test engineer can inject, isolate, repair and commission a pump failure through in-world commands. Its world state persists in Evennia's database. A [bounded Concordia repair experiment](game/README.md#experiment-can-an-ai-engineer-physically-fix-p-01) can now drive Ari through ordinary commands inside the local game process; this is not yet external agent transport.

The game lives outside the `evennia/` library and has its own [targeted database-backed tests](.github/workflows/ox-ship-world.yml). See [quickstart and commands](game/README.md) before trying it locally.

## The premise

*Ox of Hephaestus* is envisioned as a large interstellar bulk-freight vessel: a working ship with cargo, machinery, departments, watch rotations, and people whose jobs matter. The ship is the MUD world, rather than merely the setting for a conventional dungeon.

The ambition is a persistent environment in which autonomous AI crew can operate the ship, pursue their own objectives, learn their jobs, cooperate, misunderstand one another, and respond to emergencies. Human participants should be able to join through the game interface or inspect what is happening from higher-level operational views.

## Design direction

- **Full-fledged autonomous crew.** Significant NPCs have persistent identities, personal knowledge, memories, goals, and duties. They are actors in the same game world as human players, not scripted dialogue endpoints.
- **Work and watchkeeping.** Departments, duty rosters, task assignments, reporting relationships, and handovers shape everyday shipboard life.
- **Skills without classes or levels.** Abilities develop through practice, training, and use, not character levels or fixed class advancement.
- **Consequential ship systems.** Cargo operations, machinery, maintenance, and incidents create things for the crew to do and decisions to make.
- **Inspectable operations.** Alongside a traditional text interface, a planned interface will allow drill-down into crew, ship systems, events, histories, and charts.
- **Persistent, not wastefully continuous.** The world should progress without a human logged in, but background work may advance through events, coarse simulation ticks, and deferred catch-up rather than continuously simulating every detail.

These are design goals, not a declaration of implemented functionality.

## Three cooperating systems

Ox is planned as **three separately operable components**, with different responsibilities and sources of truth:

| Component | Responsibility |
| --- | --- |
| **Evennia game server** | Authoritative ship, characters, equipment, in-world duty assignments, game rules, and action outcomes. |
| **External AI handler** | Concordia-powered NPC cognition, memory, beliefs, goals, decisions, inference and interpretation of duties. |
| **Human interface** | Traditional play where appropriate, ship dashboards, data visualisations, crew and AI inspection, and authorised operational controls. |

The **interface will consume two APIs**: Evennia's game-facing interfaces (with additional ship-specific endpoints if necessary) for world facts and actions, and a planned **AI-handler API** for agent status, goals, decision summaries, and other cognitive or operational information. Neither Evennia nor the handler must depend on the interface being connected.

A lightweight interface backend may later consolidate authentication, event feeds, and data from the two APIs. It would remain part of the interface component, not a second source of game truth. Inspecting private AI state or issuing operator interventions must be permission-gated; ordinary players should only receive information their role legitimately permits.

## How the AI will connect

The first AI implementation will be an **independent handler service**, developed and tested against Evennia with little or no engine modification.

Initially, each AI-controlled character will connect as an ordinary game client, using the same exposed commands and observations available to human players. A shared handler can coordinate many independent characters and their inference workloads; each character does **not** require its own AI server process.

Once that works, we intend to add a dedicated, authenticated integration endpoint so the handler can act for multiple characters without maintaining a separate player-like network session for each. The transport can change without replacing the agents' identities, memory, and decision-making. Server-side authorization and game rules must remain authoritative in either mode.

**Prototype 1 adopts [Concordia](https://github.com/google-deepmind/concordia)** for NPC cognition and a **deterministic Game Master** for mock-world tests. The GM never invents physical outcomes: the mock world or Evennia decides them. The handler's optional Concordia dependency is pinned to a reviewed source revision because the published `gdm-concordia` 2.4.0 package does not contain the newer interrupt-driven scheduler.

See the [architecture](ARCHITECTURE.md), [decision records](design/README.md) and [Prototype 1 plan](design/prototypes/01-autonomous-crew.md).

## Human interface

The UI should be able to show both **what is happening on the ship** (from Evennia) and **what an AI crewmember believes, intends, or is attempting** (from the handler), including historical events and discrepancies between perception and reality.

Normal in-world actions should be executed and authorised through Evennia. Operator-only controls over AI execution, if provided, belong to the handler's separately authenticated control API. The interface must not directly modify either component's data stores. Initial views can poll available endpoints; live feeds and event correlation can be added as the systems mature. Stock Evennia does not imply the existence of ship-specific dashboards or telemetry endpoints.

## Proposed first milestones

1. Prepare three-system boundaries, Concordia decisions, independent package skeletons and provisional world contracts (**scaffolding committed; runtime integrations pending**).
2. Build one Concordia entity with a model adapter, persistence and inspectable decisions.
3. Run three agents in a deterministic mock ship with watch handover and cooling-fault scenarios.
4. Connect them as ordinary Evennia clients, then add one small Ox-specific ship mechanic using the game template.
5. Build a read-only interface joining Evennia facts with handler cognitive state.
6. Evaluate a dedicated Evennia AI-service transport after the client approach works.

The order and design may change as prototypes reveal what works.

## Current repository layout

| Location | What it contains |
| --- | --- |
| `evennia/` | Inherited Evennia framework; untouched by the Ox service scaffold. |
| `game/` | Playable three-room ship and local agent-driven pump-repair experiment. |
| `services/ai-handler/` | Standalone Python skeleton for Concordia NPCs, supervisor and game adapters. |
| `services/interface/` | Standalone interface Python skeleton for dual-API views and a future frontend. |
| `contracts/` | Cross-service boundary principles and future wire schemas. |
| `design/` | Concordia decisions and Prototype 1 implementation plan. |
| `scenarios/` | Mock test specifications: watch handover and cooling fault. |
| `docs/` | Retained upstream Evennia engine manual. |
| `ARCHITECTURE.md` | The three-system architecture and source-of-truth rules. |
| `INSTALL.md` | Stock Evennia setup and optional new service scaffolding setup. |

**A runnable Ox ship and bounded agent-driven repair experiment now exist.** No independent AI service transport, multi-agent simulator or dashboard exists yet.

## Built on Evennia

This repository is a fork of [evennia/evennia](https://github.com/evennia/evennia), the open-source Python framework for text-based multiplayer worlds. Evennia supplies the server, persistence, account/character model, networking, command infrastructure, and other foundational machinery on which Ox is intended to build.

The underlying Evennia code and documentation retain their upstream attribution. The applicable [BSD 3-Clause license and original copyright notice](LICENSE.txt) have been preserved. Ox of Hephaestus is an independent project, **not an official Evennia release or an endorsement by Evennia's maintainers**.

For framework usage and reference documentation, see the [Evennia documentation](https://www.evennia.com/docs/latest/). For this project's development setup, see [INSTALL.md](INSTALL.md).
