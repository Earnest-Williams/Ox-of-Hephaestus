# G17 — full-ship operating-state foundation

## Scope and authority

The 0.5 candidate is an explicitly approved *reference model*, not a set of live readings. `world.full_ship_operations.install_candidate(operator_approved=True)` is an **operator-only installation function**. It requires the canonical 421-room world to exist, creates one persistent operational record for every authored equipment unit, access link, service node, service edge, isolator and inventory account, and never overwrites those records on a repeated call. An interrupted installation rolls back atomically.

The v0.4 room topology stays installed. The 0.5 candidate has the same 421 room IDs and 517 connection IDs, so this first step attaches operating state without silently replacing the deployed topology. It does not activate NPC traversal. Evennia remains the only owner of physical truth.

## Coverage

| Component class | Authored IDs imported | Live dimensions |
|---|---:|---|
| Equipment | 808 | condition, revision |
| Access links | 517 | condition, setting, revision |
| Service nodes | 1,186 | identity, owner and network reference |
| Service edges | 1,181 | condition, availability setting, isolators |
| Isolation points | 1,256 | condition, open/closed setting |
| Inventory accounts | 15 | finite total stock in tonnes |
| Pressure cells (separate explicit scenario) | 133 | bounded gas volume, temperature, finite air mass, pressure |\n| Installation anchor | 1 | version and category counts |

Runtime changes append database-backed physical events with the before/after state and game time. Reference records are retained separately; old refit documentation cannot become measurements. The separate actor-addressed journal stays private and does not receive an indiscriminate ship-state broadcast.

A directed graph query can determine whether authored service nodes are *reachable* through currently available edges and correctly actuated switches/valves. This is **not** yet delivered power, pressure, capacity, heat transfer or fluid flow. A breaker conducts when **closed**; a valve passes when **open**. Damaged components do not conduct. Standby branches cannot conduct merely because a graph edge exists.

Inventory uses finite account totals; location allocations do not mint additional stock. The world refuses negative, nonfinite or overdrawn consumption, and rolls stock changes and physical events back together.

## Pressure-casualty simulation slice

A separate explicit `install_pressure_cells(operator_approved=True)` imports all **133 bounded elementary gas cells**. Initial air quantities remain **unknown**, not fabricated from CAD. `initialize_nominal_atmosphere(operator_approved=True)` establishes a *scenario* with per-cell gas volume taken from the midpoint of the audited v0.5 planning interval, finite ideal-gas mass at 101,325 Pa and 293.15 K, and an explicit `reference_midpoint_not_measured` provenance marker. That initialisation cannot be repeated to erase a casualty. The 83 unclassified rooms and 26 explicitly vacuum spaces do not inherit breathable status.

The operator-only `vent_pressure_cell` permits a simulated hull-gas loss which lowers pressure without creating refill inventory. `equalize_cells` conserves total mass between two finite pressurised cells at a compatible temperature. These are world-engine test operations, **not** character commands; no pressure-hatch movement or air route is authorised by calling them. Real seal actuation, flow rates, breach area, oxygen and carbon-dioxide fractions, temperature gradients and species-specific flow remain subsequent work.

## Restrictions deliberately retained

- No character-facing command for changing arbitrary state, bypassing pressure boundaries, granting unrestricted repair or injecting faults. The operator-only fault and inventory methods are not wired into the AI supervisor or player cmdset.
- No ordinary traversal of the 517 access connections. The old developer-only exit locks remain active. A conservative access evaluator fails closed on shut/damaged doors, unverified air and unequal pressure zones. It cannot substitute for actual seal, equalisation, suit and rotary-index checks.
- No generalised maintenance workflow yet. The 42 task definitions are present in the reference design but are not evidence that a character has parts, tools, safe isolation or skill.
- No populated 40-crew lived-in state, atmospheric tick, combustion/smoke/heat, refrigeration/food, orbital operations or propulsion physics yet. No claim that the full ship is simulated merely because its register is installed.

## Gate and next work

`.github/workflows/ox-departments.yml` runs a database-backed regression suite, performs an explicit 0.5 register installation after the existing 0.4 topology bootstrap, then verifies the stock persists across a second independent Evennia process. This gate must pass before merge.

Next: implement server-owned pressure-cell state with finite gas mass and temperature, leak/equalisation operations, and seal interlocks; then local equipment interaction with global idempotent receipts and real 42-task maintenance; finally network-specific flow/power/load consequences and incident ticks. Run the 40-person HAB-03 casualty as an **actual world event** only after those dependencies can be observed and changed through authorised character actions.

**Design standard:** verisimilitude and causal consistency for a heavily refitted fictional working freighter, *not* aerospace qualification or NASA approval.
