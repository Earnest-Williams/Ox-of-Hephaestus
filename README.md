# Ox of Hephaestus

**A prototype autonomous spaceship MUD built on [Evennia](https://www.evennia.com/).**

> **Status — 18 October 2026:** P4a and P4b are merged. Three authentic
> Evennia crew sessions now have independent native Concordia cognition,
> bounded decisions and a separately runnable, event-driven watch supervisor.
> The real-world P-01 test has completed **two incidents across a watch
> handover and handler restart**, with world-validated repair operations.
> This is a narrow, tested prototype—not a deployed production simulation
> or proof of open-ended three-model intelligence.

**Start here:** [Current implementation and limitations](design/STATUS.md) ·
[Install and test](INSTALL.md) · [Playable ship](game/README.md) ·
[AI handler](services/ai-handler/README.md) · [Architecture](ARCHITECTURE.md).

## The project

*Ox of Hephaestus* is envisioned as a bulk-freight starship whose working
compartments form the MUD. Crewmembers keep watches, maintain machinery,
exchange reports, carry imperfect memories and respond to shipboard events.
Humans can participate as ordinary players. Eventually, an operator should
also be able to inspect the whole ship and drill into individual crew cognition.

The longer-term design includes departments, cargo and propulsion,
skill-by-use development instead of levels or classes, and background
simulation advanced by consequential events or coarse ticks. **These larger
ship systems, skills and observer UI have not been implemented.**

## What's actually runnable

| Part | Present implementation |
| --- | --- |
| Ship | Bridge, Connecting Passage, Engineering, real Evennia pump P-01, bridge telemetry, roster and three persistent crew bodies |
| Game rules | Four-state pump lifecycle, presence/role checks, chief/reviewer release, private alarms and world-owned watch handover |
| Transport | Three ordinary authenticated WebSocket client sessions with character identity checks |
| Cognition | Three separate Concordia entities with per-character observations, memory and snapshots; bounded choice menus |
| Routine engineering | Model-free GOAP plans actions; Evennia validates physical effects and durable request-ID receipts |
| Autonomous runtime | External `ox_ai.runtime.watch_service serve` entry; event-triggered work, a persistent Evennia duty Script and tested isolation-ACK recovery |
| Observability | JSON journals and focused CI artifacts; **no browser dashboard or published handler API** |

A completed CI test is not equivalent to general intelligence. CI uses
Concordia's deterministic test model, while single-engineer hosted Gemini
inference remains an explicitly opt-in experiment. The handler does not
continuously call a language model when no character event needs attention.

### Architecture in brief

1. **Evennia** is the authoritative game world: equipment, roles, duty
   deadlines, character locations, visibility and physical outcomes.
2. **Ox AI handler** owns individual cognition and action proposals. Its
   ordinary character clients can only see and do what the world permits.
3. **Human interface** will join world facts with handler beliefs through
   two separately permissioned APIs. **It is deferred, not running.**

A model's claim that something is repaired does not repair it. The world
returns an authenticated result or an explicit unknown outcome; unknown
physical actions must be reconciled, not blindly retried. The game and
handler remain operational without a dashboard.

## Try the prototype

For an ordinary human client and the three-room game, follow
[`game/README.md`](game/README.md) or [`INSTALL.md`](INSTALL.md). Local ports
are Telnet `127.0.0.1:4000`, web `127.0.0.1:4001` and Evennia's
character WebSocket `127.0.0.1:4002`.

To exercise the current autonomous behavior **without installing the game**,
use GitHub **Actions → Ox P4b autonomous two-incident ship → Run workflow**.
That focused job provisions disposable accounts and a game database,
runs both cooling incidents with an independent reviewer, drops a physical
ACK between separate handler processes, and checks the authoritative
event ledger afterward.

For local AI development:

~~~sh
python -m pip install -e .
python -m pip install -e './services/ai-handler[concordia,transport]'
python -m unittest discover -s services/ai-handler/tests -p 'test_p4b_watch_runtime.py' -v
~~~

The persistent `serve` mode also requires a running Evennia ship,
non-privileged crew accounts, the private development credential and
the stored character-to-agent mapping. See [handler setup](services/ai-handler/README.md).
Do not run test account provisioning against an existing production world.

## Milestones and evidence

- **P0–P2:** package boundaries, one Concordia agent and two deterministic
  three-crew mock scenarios.
- **P3a–P3c:** authenticated external clients, durable world receipts and
  a three-character real-Evennia coolant incident
  ([PR #10](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/10),
  [#11](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/11),
  [#12](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/12)).
- **P4a:** individual native Concordia decisions in the actual three-client
  incident ([PR #13](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/13)).
- **P4b:** world-clock handover, changed active engineer, second incident
  and independent process restart/reconciliation
  ([PR #14](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/14)).
- **P5:** joined world/agent browser observatory—**deferred**.

See the [verification matrix](design/STATUS.md) for precise scope and gaps.

## Repository map

| Path | Purpose |
| --- | --- |
| [`game/`](game/README.md) | Ox Evennia game template, ordinary in-world commands, clock and authoritative fixtures |
| [`services/ai-handler/`](services/ai-handler/README.md) | External runtime, Concordia entities, GOAP, transport, mock and live scenarios |
| [`services/interface/`](services/interface/README.md) | Interface package scaffold; no UI or API server |
| [`contracts/`](contracts/README.md) | World/handler interface boundaries and existing wire conventions |
| [`design/`](design/README.md) | Status, decisions and prototype-stage evidence |
| [`scenarios/`](scenarios/shift_handover/README.md) | Earlier deterministic P2 fixtures retained as regressions |
| `evennia/` and `docs/` | Inherited Evennia framework and manual, not Ox product documentation |

## Attribution

This repository is a fork of [evennia/evennia](https://github.com/evennia/evennia).
The inherited source and manual retain their upstream attribution and the
applicable [BSD 3-Clause license](LICENSE.txt). Ox of Hephaestus is not an
official Evennia release or a product endorsed by its maintainers.
