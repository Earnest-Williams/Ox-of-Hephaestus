# G19 — installed hull breach and finite restoration

**Status: implemented on draft G19 PR #138; acceptance is pending installed-world CI.** The whole-ship PR is not merged. This is causal gameplay for an extensively refitted freighter, not spacecraft certification, FEA or fabrication detail. No 40-crew voyage is included in this work.

## Authoritative pressure-shell damage

A hull breach is **not** another mutable air simulator or a free-floating gameplay effect. The installed pressure-cell row continues to own actual atmosphere, gas species, leak rate and vented mass. The existing continuous physics clock measures every kilogram of gas vented, including oxygen and smoke. The additional bounded `clock.details["hull"]` registry records only the survey of the physical repair face, original leak rate, temporary/restored phase and amount of real spares permanently installed.

The world operator explicitly commissions `commission_g19_hull(operator_approved=True)` **after** commissioning the existing finite shared repair system. `register_g19_hull_breach(operator_approved=True, zone_id=..., site_room_id=..., leak_kg_s=...)` identifies **one real installed room in that exact pressure cell** and introduces a single initially unvalved hull breach there. A previously commissioned service-line leak cannot be renamed to obtain the repair mechanic. No unknown room, vacuum zone or second breach in the same cell is inferred; unregistered casualty modes remain under the G18 test/operator interface.

`ship_hull_restoration.py` is a deterministic state-transition library. The real clock, original pressure row, actual character, spares ledger, work receipts and canonical events remain authoritative. Every tick cross-checks registered hull effective leak against pressure-cell leak. Tampering or inconsistent rates fail the transaction rather than silently changing the physical source.

## On-site, two-stage maintenance

A qualified engineer obtains a **reusable** toolkit from the existing TOOL-CRIB and personally carries spare parts obtained by physically surveying the original INV-SPARES store. The same pre-existing material ledger and `repair` work-order service are used for hull restoration; there is no separate, invented hull-repair inventory. Parts move from the worker to an active work order, then into the installed replacement. No source of gas is generated and no missing atmosphere is automatically replenished.

| Stage | Crew command at the operator-surveyed room | Spares installed | One-worker time | Result |
| --- | --- | ---: | ---: | --- |
| Emergency temporary patch | `oxplant <id> hull <PZ-cell> patch` | 2 kg | 600 s | Live original leak reduced to 10% |
| Permanent repair after patch | `oxplant <id> hull <PZ-cell> restore` | 4 kg | 900 s | Residual leak closed; structural repair recorded |
| Additional qualified worker | `oxplant <id> hull <PZ-cell> join` | Own reusable toolkit | Accelerates active work | No unearned replacement material |

Every step is issued through an authenticated, idempotent 32-hex request and persists in the authoritative world. Work proceeds only if a qualified, physically present, non-incapacitated worker remains on site; losing the worker or the safe environment **pauses** rather than completes repair. The temporary patch is a distinct persistent condition. A completed repair does not re-pressurise the compartment or restore depleted oxygen. It leaves the original gas-loss ledger unchanged.

## Safe access constraints

General pressure-hatch opening and ordinary machinery repair still reject any active leak. The special inside-hull repair face is accessible only with a verified **small** loss at or below **0.05 kg/s (50 g/s)** and otherwise fully healthy pressure, gas fractions, smoke, fire and temperature. This is a bounded *gameplay* approach for a local gasket/small plating repair, not permission to work in hard vacuum. A larger rupture, dangerous thermal state, smoke, pressure loss or missing room mapping requires separate isolation/suited operations and cannot be repaired by this unsuited crew action. Suit-enabled larger-breach work and exterior worksite traversal are **not claimed implemented** here.

The operator-surveyed site is an attestation to a reachable inner repair face on the installed shell. This is not a new room, a simulated hull mesh or proof of physical exterior accessibility.

## Verification and limits

- Pure tests: finite rate, immutable state transitions, material quantities, phase ordering, corruption rejection and independent pressure cells.
- Installed Evennia tests: actual room and account, spares pickup/toolkit, original gas-loss physics, 600 s temporary patch, 900 s permanent restore, no instantaneous refill, event/receipt replay, wrong-room denial, worker departure pauses, large rupture refusal and operator leak protection.
- Workflow: `.github/workflows/ox-g19-hull.yml`, with draft-PR expensive-job gating and branch push regression execution.

This scope is an additional *ship structure and damage-control implementation slice*. It does **not** close exterior suit work, major hull replacement, all compartment traversal, the full equipment-family matrix, or whole-ship acceptance. As requested, the 40-crew voyage is explicitly deferred.
