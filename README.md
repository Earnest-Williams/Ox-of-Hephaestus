# Ox of Hephaestus

**A shipboard systems and autonomous-crew MUD/simulation built on [Evennia](https://www.evennia.com/).**

**Full-ship integration (G19, [PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138)):** the canonical 421-room / 517-link topology and all 808 v0.5 equipment units run under one persistent Evennia physics clock. Characters traverse authored exits through world-owned pressure, interlock, suit and transfer gates, and operate machinery through receipted local commands. The autonomous Concordia/GOAP crew still runs on the seven-compartment proving ground; migrating it to the full ship is the next stage. See the [G19 acceptance record](design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md) for verified scope and open items.


**Start here:** [verified implementation and limitations](design/STATUS.md) ·
[prepared full-ship physical model](design/ship/README.md) ·
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

The accepted G19 full ship is the installed physical simulation; the autonomous-crew proving ground remains a smaller, separate fixture for integration tests. A character **knows**
only observations legitimately received; their beliefs may be wrong; and
world facts unknown even to be missing remain unknown unknowns from that
character's perspective. An AI's statement or diagnosis cannot change
equipment, authorize itself, invent evidence or settle a case.

## Current implemented systems

| Area | Verified capability |
| --- | --- |
| Ship | Canonical 421-room/517-link topology with gated crew traversal and 808 v0.5 equipment units under one physics clock (G19): finite power, gas, water, waste, heat, fire, cargo, propulsion, repair and crew exposure. Separate seven-room proving ground with coolant pump P-01, cargo grid C-01 and atmospheric scrubber A-01 still hosts the autonomous crew |
| Crew | Lin, Ari, Iona, Mara and Teo have separate character identities, authenticated sessions, native Concordia state and private observations; the sixth captain is opt-in |
| Responsibilities | World-owned roster, inspection and safety gates, specialist work, addressed hails, watch changes and captain-owned open obligations with assignment/review |
| Decisions | Event-driven external supervisor; bounded Concordia choices; model-free GOAP for familiar procedures and locally discovered travel; optional independent maintenance rounds and uncertain investigations |
| Authority and recovery | Evennia owns world truth, equipment, private event journal, global actor-bound work receipts and restart/replay reconciliation for supported stages |
| Character system | Twelve formative aptitudes, twelve psychological dimensions, 55 world-owned practical skills in 16 disciplines, independent theoretical foundations and exact procedure familiarity |
| Learning | Receipt-backed, rate-limited practice from successful selected P-01/C-01/A-01 work; G4g supervised transfer assessment; G4h firsthand investigation and evidence-limits reflection |
| Opt-in crisis | G6/G6b: six authenticated crew confront a world-owned terminal atmospheric failure with finite resources, mortality and bounded decision budgets |
| Social authority | G7/G7b: separate two-person apartment GOAP fixture, reusable typed social choices, and Evennia-owned bilateral commitments with authenticated receipts |
| Private cognition | G8–G10b: seeded temporal episodes, subjective reinterpretation, owner-revisioned memory, native read-only Concordia context and simulated-time aging |
| Experimental evidence | Six-client, 500-decision G8 model-free ship/social trial; G11 matched-evidence hosted-model A/B harness; G12 local native profiling at 6/20/40 brains |
| Transport and concurrency | Buffered authenticated WebSocket matching; PostgreSQL commit-ordered journal and exact receipt provenance (PRs #82–83); cursor-based inbox reads (PR #85) with actor-scoped disposable SQLite evidence indexes and bounded Python history retention (PR #86) |
| Observation | Operator/test journals, CI evidence and a Developer-only read-only canonical-space terminal; no public world/handler combined observatory |

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
   separately permissioned world and cognitive read models. A limited authenticated
   Developer-only **spatial terminal** is implemented; it exposes neither
   private AI memory nor a combined handler/world observatory or operator control API.

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
The G4h milestone ([PR #63](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/63))
historically reported **194 passing world tests, 150 handler tests and
36/36 workflows**; those are *G4h-era counts*, not today's full inventory.
The later G8 experiment completed 500 model-free decisions with six real
authenticated clients, five resolved ship faults and private memory revisions.
PR #83 passed 50/50 final-head checks, including real PostgreSQL ordering
and captain-obligation contention. G11's opt-in hosted-model harness and
G12's native dispatch profiler answer **different** questions from this
integration testing. See [status and limits](design/STATUS.md).

P5 (joined handler/world observatory) is postponed. The [full ship](design/ship/README.md) **is materialised in Evennia** with G19 operational mechanics and an authenticated Developer-only read-only [wire terminal](design/ship/LIVE_TERMINAL.md). The seven-compartment proving ground still hosts the autonomous crew. Still unimplemented are autonomous crew operation of the full ship,
freight trading/economics, graded real physical task attempts,
an acquired-attribute engine, autonomous education agendas and comprehensive
production operations. See [status](design/STATUS.md) and
[active development priorities](design/ROADMAP.md) rather than inferring features
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
