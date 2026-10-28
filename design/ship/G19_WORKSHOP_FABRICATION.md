# G19 — original workshop fabrication and material custody

**Branch:** `g19-complete-ship-systems`; PR #138 remains draft. This is operational game-world engineering, not a spacecraft manufacturing qualification. No 40-person voyage is part of this acceptance.

## As-fitted equipment

- The physical manufacturing workspace is the **existing** `SHOP-MECH`. Its fitted machine tools are `SHOP-CNC-MILL`, `SHOP-CNC-LATHE`, and `SHOP-MANUAL-LATHE`; the mill is the first installed-world end-to-end proving case. These are three of the six existing rotating/press machines and share no invented global power bus.
- Each tool has its **real** `ISO-G19-SVC-<machine>` refit breaker, original local distribution panel, existing plant start/stop control, service wear/fault history and `physics_workshop_gauge` physical shaft output. A closed breaker does not equal productive spindle work. The workshop retains the existing all-machines shutdown/coastdown and finite-spares repair interlocks.
- Existing `INV-SPARES` holds finite pre-existing generic metal/bar blanks, subject to an explicit operator classification at a **previously surveyed original inventory room**. The source material is not created by workshop commissioning, test setup or an AI. An original `INV-INDUSTRIAL-SCRAP` sealed cassette receives offcuts only after physical transfer.
- Original `SHOP-WELD` fitted welding cells are *not* counted as producing arcs or repaired parts by this machining implementation. Their separate electrode/arc/workpiece path remains open.

## Real crew work chain

A ship operator first commissions the existing electrical, water/material survey and shared repair ledgers, then calls `commission_g19_fabrication(operator_approved=True)`. Idempotent re-commissioning preserves all prior work and material. After `survey_g19_water_material(source="INV-SPARES", room_id="SPARES-CENTRAL", verified_kg=...)`, the operator separately classifies an actual portion as machinable bars with `survey_g19_fabrication_blanks(room_id="SPARES-CENTRAL", verified_kg=..., operator_approved=True)`. The same room cannot be certified twice. Certification does not subtract or duplicate material.

1. A qualified physically present engineer obtains, for example, **4 kg** of previously certified stock at its original storage room with `oxplant <uuid> fabricate blank pickup:4`. This debits the real `INV-SPARES` inventory and the prior water/material location survey in one world-authoritative transaction. The blank is tagged to that worker; it does not teleport into the workshop.
2. That worker traverses actual ship exits to `SHOP-MECH`. An engineer commands the real powered `SHOP-CNC-MILL` **on**, with true source path, live individual feeder, healthy hardware and separate startup completion. A locally signed `oxplant <uuid> fabricate SHOP-CNC-MILL start:4` reserves the worker, the finite blank and the physical spindle. The worker cannot begin another job simultaneously; another worker cannot silently take over the same occupied tool.
3. On each advancing, bounded 10-second ship physics interval, the real machine must have *fresh current* measured shaft output, adequate powered operation and the qualified worker physically in safe shop atmosphere. Each 1 kg of stock takes **90 seconds** of tool engagement; a 4 kg example therefore takes **360 seconds**. A dark panel, disconnected feeder, latched restart, defective machine, off-site or incapacitated worker stops work without completing material. Replays and old cumulative shaft revolutions do not count as fresh manufacturing epochs.
4. On completion, the existing repair worker personally receives **75%** of the blank's mass as mechanically produced compatible replacement stock (**3 kg** in the example). The remaining **25%** is actual shop offcuts (**1 kg**), retained in the finite original workshop chip-tray ledger. The physical repair carried-parts validator and original 12 kg hand-carry limit apply to the finished part; if the worker's hands cannot accept it, completion waits without double-counting output. A bounded finish receipt records the original work request, machine, worker, source mass, yielded part mass and retained offcuts. The resulting part may enter the existing timed and safety-gated `repair` action, without restarting or clearing a fault by itself.
5. A worker separately collects the chip tray with `oxplant <uuid> fabricate offcuts pickup:1`, hand-carries it from the original workshop to an installed `IND-SCRAP-HOLD-A/B` location and issues `oxplant <uuid> fabricate IND-SCRAP-HOLD-A deposit:1`. An intact, correctly located, sealed, unreserved receiver with finite capacity is required. The *already debited* source blank is **not charged twice**. Its material merely changes custody from hand-held workpiece to finished replacement and original, physically sealed industrial waste. This waste then uses the previously accepted cassette/port-offloading system.

For direct local review: `oxplantread fabrication` is available only at the actual workshop or relevant material storage site. Unvisited regions do not provide remote access to private machine condition.

## Conservation and persistence

For the new manufacturing ledger, the invariant is:

`total certified stock already issued = raw personally carried + active workpieces + cumulative finished parts + offcuts at shop + personally carried offcuts + offcuts deposited to real industrial cassettes`.

The cumulative finished amount is intentionally counted once in the existing shared repair spare custody after completion (it may then be carried, staged and installed). The offcuts deposited are matched by real increases in the pre-existing `INV-INDUSTRIAL-SCRAP` and sealed receiver records, not duplicated fabricated cargo. Source `INV-SPARES` shrinks once on pickup. Ordinary component repairs still need qualified real workers, toolkit, compatible spare mass, safe isolation, and time.

The world clock, machine gauges, stock locations, waste receiver and repair inventory remain canonical Evennia records. Reusing an existing `WorkReceipt` request ID returns the original result or rejects a different operation.

## Acceptance

- Pure: `world.tests.test_ship_workshop_fabrication` plus prior spindle and shared-repair conservation tests. A damaged or unmeasured source, absent worker, stale shaft output, full hands, material overissue, no cassette or replay cannot create replacement parts.
- Installed: `world.tests.test_installed_ship_workshop_fabrication` executes live original room/material surveys, correct generator route, CNC startup/360-second machining, offcut transport, real receiver deposit and a real failed water processor repaired with the produced finite 3 kg replacement.
- Workflow: `.github/workflows/ox-g19-workshop-fabrication.yml` (two independent jobs; branch-push, not skipped by the draft PR policy). **Both jobs must pass at the same exact runtime commit before this workshop manufacturing slice is marked accepted.**

Further machine-shop closure requires genuine welding arcs/electrode/workpiece accounting, fuller work-order material typing/compatibility and wider G19 cross-system casualty campaigns. These are not silently treated as fabricated or complete.
