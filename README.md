# Ox of Hephaestus

**An autonomous spaceship MUD/simulation prototype built on [Evennia](https://www.evennia.com/).**

> **Current state — 19 October 2026 (through merged G4h / PR #63).**
> A seven-compartment ship contains three simulated physical systems,
> five independently authenticated specialist crewmembers and an **optional
> sixth captain**. The world enforces physical outcomes, individual
> knowledge boundaries, crew duties and receipts. It now persists distinct
> formative aptitudes, psychology, professional skills, conceptual knowledge
> and exact-equipment familiarity. Verified physical work can earn practical
> experience; two narrow assessed activities can earn conceptual progress.
> This is a **bounded and tested prototype**, not a complete commercial
> freighter, a production deployment or generally intelligent crew.

**Start here:** [verified implementation and limitations](design/STATUS.md) ·
[install and tests](INSTALL.md) · [in-world ship guide](game/README.md) ·
[external AI handler](services/ai-handler/README.md) ·
[architecture and authority](ARCHITECTURE.md) · [roadmap](design/ROADMAP.md).

## What the project is

The intended game is a working bulk-freight spacecraft, not a backdrop for
a conversation. Humans and autonomous characters share a material world:
equipment can fail, supplies run out, crews work under incomplete information,
and unresolved incidents need follow-through. The ship's eventual economics,
cargo arrangements, propulsion, staffing constraints and skills should make
operational tradeoffs consequential.

The current ship is a proving ground for that design. A character **knows**
only observations legitimately received; their beliefs may be wrong; and
world facts unknown even to be missing remain unknown unknowns from that
character's perspective. An AI's statement or diagnosis cannot change
equipment, authorize itself, invent evidence or settle a case.

## Current implemented systems

| Area | Verified capability |
| --- | --- |
| Ship | Seven connected compartments; coolant pump P-01, cargo restraint grid C-01 and atmospheric scrubber A-01, each with bounded physical states |
| Crew | Lin, Ari, Iona, Mara and Teo have separate character identities, authenticated sessions, native Concordia state and private observations; the sixth captain is opt-in |
| Responsibilities | World-owned roster, inspection and safety gates, specialist work, addressed hails, watch changes and captain-owned open obligations with assignment/review |
| Decisions | Event-driven external supervisor; bounded Concordia choices; model-free GOAP for familiar procedures and locally discovered travel; optional independent maintenance rounds and uncertain investigations |
| Authority and recovery | Evennia owns world truth, equipment, private event journal, global actor-bound work receipts and restart/replay reconciliation for supported stages |
| Character system | Twelve formative aptitudes, twelve psychological dimensions, 55 world-owned practical skills in 16 disciplines, independent theoretical foundations and exact procedure familiarity |
| Learning | Receipt-backed, rate-limited practice from successful selected P-01/C-01/A-01 work; G4g supervised transfer assessment; G4h firsthand investigation and evidence-limits reflection |
| Observation | Operator/test journals and focused CI evidence; no published world/handler inspection APIs and no browser observatory |

**Current learning is narrower than the character design.** The operator-only
routine/unfamiliar/novel *shadow* resolver compares capabilities, but it does
not set live repair success or damage. Practical credit follows already
successful, world-authorized work. G4g teaches one controlled-comparison
curriculum, and G4h assesses one investigative-method reflection. Neither
activity demonstrates unrestricted teaching, general science or autonomous
study scheduling.

The original five-specialist supervisor remains the standard configuration.
The captain adds separately authenticated command follow-through when enabled;
rank does not grant technical skill or cause problems to resolve magically.
The historical three-person supervisor remains a separate regression/runtime
mode and **must not run simultaneously against the same ship**.

## Authority boundaries

1. **Evennia game:** character identity, location, equipment, inventory,
   access and safety checks, real world-time deadlines, verified receipts,
   personal capability ledgers and physical results.
2. **External Ox handler:** each AI's private observations, memories, hypotheses,
   decisions, GOAP proposals, pending request IDs and checkpoints. It accesses
   the world as ordinary individually authenticated characters.
3. **Human observatory (deferred):** a future presentation layer joining
   separately permissioned world and cognitive read models. No running
   frontend, combined API or operator-control service exists.

Unknown physical-action outcomes are reconciled using the **original
request ID**. A timeout is not proof of failure and never justifies blindly
repeating a consumable operation.

## Try it and verify it

The [installation guide](INSTALL.md) explains local development setup.
The [game guide](game/README.md) lists real ship commands and simulated
systems; the [handler guide](services/ai-handler/README.md) covers separate
authenticated supervisor processes and their optional modes.

Focused GitHub Actions workflows test the real Evennia server, world
transactions, PostgreSQL contention, persistent crew, restarts, uncertain
evidence, character records and learning. The
[G4g conceptual-learning workflow](.github/workflows/ox-g4g-concept-learning.yml)
and [G4h investigative-learning workflow](.github/workflows/ox-g4h-inquiry-learning.yml)
include authenticated real-client restart and lost-acknowledgment checks.
The final merged G4h implementation ([PR #63](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/63))
reported **194 passing world tests, 150 handler tests, and 36/36 applicable
focused workflows** on its final head. These are scoped acceptance tests,
not proof of general autonomous performance.

P5 (operator observatory) is postponed. Still unimplemented are a full ship,
propulsion, freight trading/economics, graded real physical task attempts,
an acquired-attribute engine, autonomous education agendas and comprehensive
production operations. See [status](design/STATUS.md) and
[next acceptance gates](design/ROADMAP.md) rather than inferring features
from the long-term design or historical prototype documents.

## Repository map

| Path | Purpose |
| --- | --- |
| [`game/`](game/README.md) | Authoritative Evennia ship, world mechanics and commands |
| [`services/ai-handler/`](services/ai-handler/README.md) | External Concordia characters, GOAP, client transport, supervisor and replay |
| [`services/interface/`](services/interface/README.md) | Deferred UI/API scaffold, not a running observatory |
| [`contracts/`](contracts/README.md) | Implemented wire conventions and future service boundaries |
| [`design/`](design/README.md) | Current status, historical decisions, milestones and evidence |
| [`scenarios/`](scenarios/shift_handover/README.md) | Retained early deterministic regression fixtures |
| `evennia/` and `docs/` | Inherited engine and upstream manual, **not** Ox product documentation |

## Attribution

This repository forks [evennia/evennia](https://github.com/evennia/evennia).
The inherited code/manual retain their original attribution and applicable
[BSD 3-Clause license](LICENSE.txt). Ox is not an official Evennia release
or endorsed by its maintainers.
