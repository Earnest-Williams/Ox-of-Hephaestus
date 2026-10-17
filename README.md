# Ox of Hephaestus

**An autonomous spaceship MUD and shipboard simulation, built on [Evennia](https://www.evennia.com/).**

> **Project status: early design / engine fork.** This repository currently contains the upstream Evennia framework. The Ox-specific spaceship systems, external AI handler, and operational interface described below are plans, **not implemented features**.

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

## How the AI will connect

The first AI implementation will be an **independent handler service**, developed and tested against Evennia with little or no engine modification.

Initially, each AI-controlled character will connect as an ordinary game client, using the same exposed commands and observations available to human players. A shared handler can coordinate many independent characters and their inference workloads; each character does **not** require its own AI server process.

Once that works, we intend to add a dedicated, authenticated integration endpoint so the handler can act for multiple characters without maintaining a separate player-like network session for each. The transport can change without replacing the agents' identities, memory, and decision-making. Server-side authorization and game rules must remain authoritative in either mode.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the initial boundaries and proposed proof of concept.

## Proposed first milestones

1. Establish project documentation and a development baseline on the Evennia fork.
2. Prototype a separate AI handler controlling a few ordinary Evennia characters via client connections.
3. Test a small shipboard duty-and-incident scenario, including coordination and observable decision traces.
4. Add ship-specific mechanics and operational views iteratively.
5. Evaluate a dedicated AI-service API once the external-client approach is understood.

The order and design may change as prototypes reveal what works.

## Current repository layout

| Location | What it contains |
| --- | --- |
| `evennia/` | The inherited Evennia game-server framework; **not** an implemented Ox spaceship. |
| `docs/` | Evennia's upstream engine documentation, retained as reference material. |
| `ARCHITECTURE.md` | Ox-specific preliminary architecture and integration plan. |
| `INSTALL.md` | How to run a **stock Evennia development game** from this checkout. |
| `CONTRIBUTING.md` | How to propose changes to this fork and distinguish them from upstream engine work. |

There is **no production-ready Ox game or AI handler to start yet**.

## Built on Evennia

This repository is a fork of [evennia/evennia](https://github.com/evennia/evennia), the open-source Python framework for text-based multiplayer worlds. Evennia supplies the server, persistence, account/character model, networking, command infrastructure, and other foundational machinery on which Ox is intended to build.

The underlying Evennia code and documentation retain their upstream attribution. The applicable [BSD 3-Clause license and original copyright notice](LICENSE.txt) have been preserved. Ox of Hephaestus is an independent project, **not an official Evennia release or an endorsement by Evennia's maintainers**.

For framework usage and reference documentation, see the [Evennia documentation](https://www.evennia.com/docs/latest/). For this project's development setup, see [INSTALL.md](INSTALL.md).
