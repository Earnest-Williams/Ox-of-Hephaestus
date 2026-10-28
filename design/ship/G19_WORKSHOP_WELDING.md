# G19 — original twin welding cells: finite joined parts and arc verification

**Integrated:** `g19-complete-ship-systems`, draft PR #138. No 40-person voyage. The working ship is a historically repaired freighter; the aim is an authoritative causal Evennia work chain, not certification of a real weldment.

## As-installed machinery and materials

The original `SHOP-WELD` is a separate original room on the adjustable engineering rotor, in physical pressure cell `PZ-WR-SHOP`, connected to `SHOP-MECH` by its actual `ACC-WR-SHOP-WELD` fire door. Its two original distinct welding appliances, `WELD-CELL-A` and `WELD-CELL-B`, have individually installed and breakered G19 service feeders `ISO-G19-SVC-WELD-CELL-A/B`. Neither receives a fake bridge-only load path. Their shop supply is the real `NODE-LP-SHOP-WELD`, originally connected through `NODE-WR-PWR-IF` and `ISO-LP-SHOP-WELD`.

The two cells have separate real `plant` startup/shutdown, measured service hours and wear failures. The new welding ledger may be commissioned only after electrical, water/material and shared finite-repair systems are commissioned, and after both original cell/room/breaker identities are physically audited.

The source of weld wire/electrode is a **positively surveyed, physically present allocation of original `INV-SPARES`**, not infinite filler. The world operator uses `survey_g19_water_material` for actual located source stock then `survey_g19_welding_filler(operator_approved=True, room_id=..., verified_kg=...)` exactly once per store. The latter classifies existing stock without creating or debiting it. A real engineer at that storage room uses `oxplant <request32> weld filler pickup:<kg>` to transfer up to 3 kg personally; the original inventory row and location survey are debited together. The worker also needs a separately carried, genuinely existing base workpiece in their **existing shared repair part custody**; this can be obtained from original spares or the separately implemented physically machined CNC output.

## Work, output and recovery

- A qualified engineer physically in `SHOP-WELD`, with a sound cell under individually measured live power and completed startup, issues `oxplant <request32> weld WELD-CELL-A start:<base-kg>:<filler-kg>`. The loaded workpiece is removed from the worker's existing repair-spare tally and retained in the physically booked work order. Filler is staged from their separate carried spool. One real individual cannot operate both cells simultaneously.
- Work advances only through the original shared ship's bounded 10-second monotonic time, with the qualified worker personally present, breathable surveyed pressure-zone air, nonfailed equipment and genuine source-to-cell dispatch. For the chosen gameplay envelope a 3 kg base with 1 kg filler requires **300 seconds**. A live observed arc contributes **15 kW of heat** against the real `PZ-WR-SHOP` thermal inventory; it is not a fictional power source or remote temperature claim.
- Successful elapsed arc creates exactly **3.85 kg of joined repair material** (original 3 kg base plus 0.85 kg retained filler) and **0.15 kg of industrial slag** in the physical workshop holding ledger. The usable 3.85 kg is credited back to the existing single shared repair material account in the worker's hands. It is not an automatic machinery repair; the established toolkit, diagnosis, feeder isolation, parts compatibility and timed local repair remain required.
- Work pauses under lost electrical dispatch, failed local breaker, failed cell, crew absence/incapacity, no trustworthy air or an occupied worker. The work and staged inputs remain persistent. Genuine output cannot be credited twice on replay or after a finished job. An intact cell with no loaded work order produces **zero** positive welding output.
- Each welded arc's local existing equipment row gains a `physics_weld_arc_gauge` with **last 10-second kJ**, persistent cumulative kJ and measured game time. `oxplantread WELD-CELL-A/B` reports this with the original circuit; `output_proven_at_site` requires the actual fresh arc, healthy machine, operating state and conducting supply. The source-specific `fault` repair/restart verifier for both cells also requires two actual subsequent positive-output physics epochs, not merely energisation of a repaired breaker.
- `oxplant <request32> weld slag pickup:<kg>` at `SHOP-WELD` moves up to 5 kg personally, only from actual retained slag. `oxplant <request32> weld IND-SCRAP-HOLD-A deposit:<kg>` at an original sound, sealed, nonreserved industrial receiver transfers it to the existing bounded waste cassette plus `INV-INDUSTRIAL-SCRAP`. It then uses the already functioning port-side waste offload system. Neither deposited slag nor consumed filler reappears as newly available `INV-SPARES`.

## Conservation and limits

The invariant for this physically staged welding process is:

`cumulative original electrode mass issued + cumulative original base repair mass borrowed = filler carried + (base + filler) retained in active weld jobs + completed joined part mass returned to repairs + slag remaining at shop + slag in hand + slag deposited into existing sealed cassettes`.

Material is always debited only once at its source; full-ship mass never increases from welding. Finished welded material and industrial waste are custody transitions of prior shipboard stock, not new ship supplies.

This is a coarse game-world welding process. It does not model metallurgy, joint geometry, shielding gas, filler compatibility by alloy, non-destructive test radiography or qualified load-bearing part classification. Those can be introduced as distinct bounded controls, but cannot be silently inferred from an arc gauge.

## Acceptance gate

`.github/workflows/ox-g19-workshop-fabrication.yml` now runs both CNC and welding campaigns. Its pure job includes `test_ship_workshop_welding.py` plus the existing spindle, real repair and fabrication tests. The installed Evennia job includes `test_installed_ship_workshop_welding.py`, physically proving source stock issue, local cell startup, actual arc and heat, new usable repair material, produced slag, powered and attended interruption, local fresh gauge, material receipt replay and real industrial receiver delivery. **The welding slice is accepted only after both jobs pass on the same commit that contains the new tests and instrumentation.** Wider cross-system G19 acceptance remains separate.
