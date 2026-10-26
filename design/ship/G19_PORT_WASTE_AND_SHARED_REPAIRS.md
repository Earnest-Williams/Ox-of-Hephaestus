# G19 — sealed waste port offload and shared equipment repairs

**Status: SUBSYSTEM ACCEPTED — 26 October 2026.** Port-side sealed solid-waste offloading and shared finite equipment repairs passed the dedicated real-world and conservation suites. The single G19 PR #138 remains **draft and unmerged**. This is game-world verisimilitude for an old refitted working freighter, not fabrication or NASA certification.

## Verified acceptance

**Tested runtime revision:** `5eb76e257f30ac8a3b6aa6b8109c980eb304306d`. The [dedicated Actions run #40250285584](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40250285584) completed successfully with **all five jobs green, 74 tests passing**:

| Acceptance job | Tests | Result |
| --- | ---: | --- |
| Standalone waste custody, spare/toolkit conservation, water endurance and fuzz | 29 | PASS |
| Installed Evennia solid-waste haul, real port receipt, generator/door/water repairs and crew incapacity | 6 | PASS |
| Existing installed water and recycling regressions | 12 | PASS |
| Existing installed cargo, freight, rotor and movement regressions | 13 | PASS |
| G18 air/pressure, thermal, fire and seeded 80-tick casualty compatibility | 14 | PASS |
| **Total** | **74** | **PASS** |

The same tested revision also passed [fast PR source checks](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40250289804) and [documentation/CI-scope checks](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40250289769). The original physical waste/design validators passed inside the standalone job. [Machine-readable acceptance record](G19_WASTE_REPAIR_ACCEPTANCE_2026-10-26.json) retains the exact test revision, run and scope; documentation-only commits do not change the validated runtime.

**Acceptance scope:** actual berth-bound cassette offload, sealed waste class custody, finite powered transit, return/reversal, port quota and ship-mass reconciliation; reusable toolkit and carried spares, locally verified repair conditions, timed assisted work, physical crew health and safe restart. Crew traversal across every ship compartment, suit physiology/long-term exposure, hull replacement and the final 40-crew autonomous voyage remain separate full-G19 acceptance obligations.

## Scope

These features share the **existing canonical Evennia world clock**, original 421-room geometry, existing equipment, the finite water/waste receiver inventory accounts, the original cargo drum port handlers, and the existing 25-tonne maintenance spares account. They do **not** introduce an invented disposal hatch, invisible replacement inventory, global instant-repair action, or a parallel physics database.

The two modules implementing bounded pure physical transitions are `game/world/ship_waste_offload.py` and `game/world/ship_equipment_repair.py`. `ship_waste_repair_world.py` validates original installed access, safe atmosphere and machine isolation. Existing continuous physics owns game-time progression, external mass, individual equipment conditions and receipted crew actions.

## A. Offloading the existing sealed waste cassettes

The actual installed receiver locations remain authoritative:

| Class | Physical receivers | Capacity | Installed source rooms |
| --- | --- | --- | --- |
| Stabilised sanitary solids | WASTE-RESIDUE-HOLD-A/B | 8 t each | STORE-FLUID-AFT |
| Sorted industrial scrap | IND-SCRAP-HOLD-A/B | 4 t each | SPARES-CENTRAL / MATERIAL-STOCK |
| Compatible isolated hazardous solids | HAZ-ISO-HOLD-A/B | 1 t each | PARTS-WASH / STORE-CRIT-SPARES |

Neither the 16 t sanitary capacity nor the independently segregated 8 t industrial and 2 t hazardous capacities are merged into a general-purpose sink.

An external disposal facility is not inferred from a random dock. An **operator** first records a stable acceptance identity, actual berth identity, appropriate waste class, installed DR-01–DR-06 cargo portal and **finite kilogram acceptance limit** via `commission_waste_acceptance`. An operator then surveys the actual sequence of installed, internally rated access links from the receiver's real store to the selected drum's **DR-xx-FREIGHT-LOCK** using `survey_waste_freight_route`. The survey is archived as actual access-link IDs; it creates no bypass and validates the installed map. Without those two external/route attestations, the crew cannot begin a shipment.

Crew operations are separated into real stages:

1. A qualified environmental or engineering crewmember at the **loaded, sound, sealed receiver** issues a receipted `waste <receiver> stage:<acceptance-id>`. That claims its actual contents and immobilises that receiver, but neither clears its inventory nor moves a gram of material.
2. At the destination **DR-xx-FREIGHT-LOCK**, a qualified cargo or engineering crewmember parks the drum, extends its separately fitted freight collar, verifies rated pressure conditions, opens `ACC-DR-xx-FREIGHT-CAPTURE` using `wasteport <receiver> capture_open`, and issues `wasteport <receiver> haul`. The finite internal haul takes **240 seconds** of powered, safe, sound freight work. Every segment remains bound to the surveyed route. Its original filled mass moves from the store receiver into separately accountable **aboard freight custody**, not off the ship. The source receiver remains unavailable for new waste until the empty cassette returns.
3. The freight capture closes and retracts before a separate, stopped and hardlocked **commercial P1/P2 berth** can dock. A qualified cargo operator at **CARGO-CTRL-FWD** issues `wasteport <receiver> offload`. After **60 seconds startup**, a functioning external handler moves at **80 kg/s**, charged against the berth's accepted capacity. **Only this physical transfer** reduces the real waste inventory and the vessel's inertial mass and increases the destination's delivered custody quantity. Sanitised solids originating in water/food processing debit the **mission-fluid mass family**; equipment scrap and isolated cartridges debit **dry onboard material mass**. Total mass reduction equals exported kilograms, not a fictitious structural-hull loss. Port electrical shortfall, lost docking, blocked gallery seal or damaged handler stops transfer. Ordinary commercial cargo on the same drum shares the actual handler and cannot run concurrently.
4. On successful delivery, the port may undock while the now-empty cassette remains held in the drum. Crew extend and positively capture the freight route again, then issue `wasteport <receiver> return`. Its finite **240-second** return restores receiver availability. A prematurely opened or unsecured replacement receiver is not free waste capacity.

A crew command can **pause** or **resume** the handling process. An aborted outbound haul that has not exported material returns the exact original contents to its source after real handling time. Once any mass has actually crossed to the outside facility, abort cannot conjure it back: the remaining approved transfer must finish before return. All intermediate states are journalled and persist across clock advances, disconnections and duplicate request IDs.

The original spacecraft mass total is changed only for **actually exported kilograms**. The water/waste conservation validator counts sealed source cassettes *plus* material carried in the inboard freight carrier against the same installed `INV-WASTE-RESIDUE`, `INV-INDUSTRIAL-SCRAP` and `INV-HAZARDOUS-RESIDUE` accounts. No empty bin is generated by deleting a quantity or resetting an equipment condition.

## B. Shared, finite machinery repair

Shared maintenance is separately and explicitly commissioned by `commission_g19_repairs(operator_approved=True)` after the existing G19 material-custody model. One durable work-order system covers **installed equipment, isolators and access units**. It does not silently erase the consequences of a fire, pressure casualty, jammed actuator or missing mechanical component.

An operator first physically surveys **existing** `INV-SPARES` material at one of its actual stores using `survey_g19_water_material`. A qualified engineer physically visits that store and obtains up to **12 kg** of verified spares with `repair INV-SPARES pickup:<kg>`. Those kilograms are debited from the original stock once and held under the worker's actual character ID. They are **not available at other rooms** until personally carried there.

A fitted TOOL-CRIB now contains **six individually assigned, reusable maintenance toolkits** already accounted for within the ship's existing stores. An eligible engineer visits that actual crib to `repair TOOL-CRIB pickup_toolkit`, and may `return_toolkit` there when not committed to an active job. A work order cannot begin without a personally held toolkit; helpers likewise bring their own. Toolkit count plus personally carried units is always six. They are not disposable spares or newly added departure mass.

At the actual failed machine, a qualified engineer may `repair <category:id> start` only if the fault is repairable, required parts are physically carried, and the relevant installed energy/pressure/motion interlocks are satisfied. The worksite must have verified safe breathable atmosphere **or** be an operator-surveyed, explicitly suited generator-service compartment with genuinely verified crew protection; a blank pressure classification is never treated as air. Generators must be off and their own breakers isolated; water and sanitation processors must be stopped; freight and rotary machinery must be parked and hardlocked; access doors and valved isolators need safe physical positions. A thermal protection trip still requires its separate cooldown/isolation reset. Destroyed hardware is not restored through this service. A second or third engineer can `join` the same on-site work order and modestly accelerate it.

| Original physical condition | Parts fitted | One-worker duration |
| --- | ---: | ---: |
| Degraded | 0.5 kg | 120 s |
| Faulted, without unresolved protection trip | 1 kg | 300 s |
| Failed | 3 kg | 600 s |
| Jammed | 2 kg | 600 s |
| Severed | 4 kg | 900 s |

Every bounded simulation advance verifies that an authenticated, qualified worker remains at the **same installed machine site** and that the original isolation and environment conditions still hold. Installed access doors are links, with no fictitious central `space_id`; a qualified worker may repair such a door only from one of its **actual authored endpoints** in a verified safe compartment. A naturally unpressurised generator bay, such as `GEN-B-ROOM`, is not assigned an invented gas cell. Its original `ACC-GEN-B-ROOM` pressure boundary stays rated and closed by default. The operator may record `survey_g19_repair_site(..., room_id="GEN-B-ROOM", work_class="suited_service")`, but that is **not** passage authorization. The crew must genuinely reach that site through the separately gated G19 suited-transfer system before it can begin and continue local repair. A missing or revoked suit verification immediately halts repair progression. Removing all workers, losing safe conditions or worsening the condition **pauses** physical repair progress instead of silently finishing. A completed work order installs already debited replacement parts, updates the physical component's persistent condition and maintenance history, and leaves the machine **off**. A normal local restart or approved reset is a separate operation; repaired power, rotor and water hardware do not auto-restart.

The repair mass budget is explicitly `issued spares = carried parts + staged work order parts + installed replacements`. Original broken equipment mass remains in the vessel's existing dry-mass envelope until an independently recorded, classified removal; no imaginary new scrap or offship disposal arises automatically from a repaired condition.

## C. Crew command and authority

`oxplant <32hex-id> ...` is the existing global work-request namespace. A duplicate request returns its original outcome without repeating stock transfer, work, repair or waste export. `oxplantread repairs` shows only personally carried spares and work orders in the actor's present room. `oxplantread wasteport` reveals waste shipment state only from its source receiver, local drum freight-lock or cargo control station. The operator's route and acceptance attestation are **not** available as player or model-written world-state commands.

All interaction is causal gameplay: a broken handler, wrong berth, missing approved hazardous classification, blocked service corridor, unusable pressure gate, missing spares, departed crew member or failed generator can constrain actual work over successive game ticks.

## D. Acceptance and boundaries

Dedicated workflow: `.github/workflows/ox-g19-waste-repair.yml`, containing standalone conservation/casualty tests, compiled installed design, and a real Evennia world campaign. The existing water/waste and G18 compatibility suites remain required regression gates.

**This document's scope is the port-side offload and shared repair features only**. It does not claim final closure of G19's crew physiology, complete ship equipment-family coverage, autonomous-voyage acceptance or the full-ship merge gate. The fictionally credible rates, work-order parts and time budgets are scenario parameters, not engineering-grade physical qualification.
