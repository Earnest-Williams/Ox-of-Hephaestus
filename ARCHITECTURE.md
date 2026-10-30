# Ox of Hephaestus — current architecture

**Baseline: 30 October 2026.** The installed full-ship G19 physics was accepted and merged ([PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138)); post-merge heat accounting was corrected by [PR #139](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/139). The external Concordia/GOAP crew **still uses the separate seven-compartment proving ground**. A simulated ship and autonomous characters operating the whole ship are different milestones.

Read [implementation status](design/STATUS.md), [ship index](design/ship/README.md), [G19 acceptance](design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md) and the [full historical architecture](design/archive/ARCHITECTURE_THROUGH_2026-10-21.md).

## Authority boundaries

| Component | Authoritative responsibility |
| --- | --- |
| **Evennia game** (`game/`) | Actual world physics, canonical rooms and exits, actor location, access/permissions, skill and resource ledgers, inventories, clock, conditions, damage and persisted action receipts |
| **Ox handler** (`services/ai-handler/`) | Each authenticated agent's private observations, beliefs, memories, goals, GOAP proposals, inference, pending work IDs and checkpoints |
| **Contracts** (`contracts/`) | Authenticated character command/OOB protocol and explicit service message contracts |
| **Human interface** (`services/interface/`) | Deferred presentation scaffold; no deployed joined world/handler observatory or separate world authority |

An AI request is a proposal; it does not alter physical state. Every crew operation is validated by Evennia for real identity, equipment, permission, worksite and material availability. Unknown outcomes are reconciled under the **original request ID**, not repeated as new work. Agent accounts must not have Developer privileges.

## One installed physical ship, two source layers

- **Topology:** `design/ship/ox_full_ship.json` (published v0.4) establishes **421 canonical rooms and 517 links**, materialised as **1,034 directional exit objects** in persistent Evennia.
- **Operational register:** `design/ship/ox_full_ship_v0.5_candidate.json`, topology-compatible, provides **808 installed equipment identities, 91 families and 133 bounded pressure cells**. The operational register is installed without silently promoting the v0.5 candidate to the published topology file.
- **Authority after installation:** the Evennia database and its monotonic, bounded, replay-safe ship clock; the JSON model and read-only spatial renderer are not second copies of mutable world truth.

G19 couples electricity, atmosphere, temperature, fire, hull damage, water/waste, cargo and rotary mechanisms, propulsion, crew exposure, equipment failure and fault recovery on that installed world. It uses finite stocks, actual conductive and flow paths, persistent damage, physically attended repairs, permit-to-work and material/time costs. Generator repair, drum hull work and local restarts are separately verified under active casualties.

A canonical passage is not automatically a safe corridor. `CanonicalShipAccess.at_traverse` delegates to `world.ship_crew_access.traverse_canonical_exit` for pressure, breathable envelope, protective suit, rotating-HAB alignment, cargo indexer and worksite restrictions. The `board ox` development entry remains Developer-only; ordinary characters can use allowed world-gated exits.

**Evidence and limits:** [G19 audited closure](design/ship/G19_ACCEPTANCE_RECORD_2026-10-29.md) documents twelve functioning subsystem groups, complete equipment-family disposition and 74/74 final integration tests plus independent restarts. [Fuzzing](design/ship/G19_FUZZ_CAMPAIGN_2026-10-30.md) corrected occupied-cell heat loss; invalid actor placement and corrupted persisted stock/interlock validation remain hardening items. Acceptance applies to the tested game-world engineering contract, not exhaustive optional gameplay.

## Autonomous crew remains a separate integration

The normal Concordia/GOAP supervisor still operates on the old seven-room, three-machine proving ground. Its five specialists and optional sixth captain have independent authenticated identities and private states, world-addressed alarms and requests, local GOAP navigation, work receipts, restart reconciliation, skill/knowledge ledgers and bounded learning experiments.

The next step is to bind those agent operations to the 421-room G19 ship, with real stations, restricted routes, instruments, safety permits, tools, finite spares and measured outcomes. The older G3–G16 research experiments demonstrate their own bounded claims; they do not prove full-ship autonomous operation, general human-like intelligence or graded practical task outcomes. Consult the [handler guide](services/ai-handler/README.md) and [historical prototype index](design/prototypes/README.md).

## Invariants and references

1. **Physical truth belongs to Evennia.** Private memory, incomplete evidence and generated speech never become world truth merely by being asserted.
2. **Conservation and persistence:** equipment consumes or transfers finite material and energy; damage lasts until appropriately repaired; state and signed effects survive restarts.
3. **Location and safety:** travel is through actual fitted exits and interlocks; role, site, suit and work permissions are checked by the world.
4. **Replay safety:** duplicate action IDs do not duplicate effects; a failed tick substep rolls back coupled state.
5. **Game-world verisimilitude:** physical consequences should be causal and playable, rather than certification-grade aerospace modeling.

[Current roadmap](design/ROADMAP.md) · [Installation](INSTALL.md) · [Archived architecture](design/archive/ARCHITECTURE_THROUGH_2026-10-21.md).
