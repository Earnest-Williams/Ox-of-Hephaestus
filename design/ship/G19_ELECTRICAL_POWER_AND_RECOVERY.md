# G19 — installed electrical plant, distribution, protection and recovery

**Implementation:** G19 draft PR #138, unmerged. This is the electrical subsystem's operating contract for the canonical Evennia ship, not a second electrical simulator or a construction-ready switchgear qualification. The 40-crew voyage is expressly excluded from this development round.

## Acceptance evidence (27 October 2026)

**Bounded G19 electrical subsystem accepted, not full G19 or merge approval.** [CI run #40435001116](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40435001116) passed **77/77 in four jobs** against actual runtime `c586378e897fe284418456331e860ead50211596`: 22 pure energy/network/conservation tests, 16 installed Evennia electrical operation tests, 14 existing G18 gas/fire/thermal regression tests, and 25 G19 installed water/cargo/movement compatibility tests. See [archived acceptance record](G19_ELECTRICAL_ACCEPTANCE_2026-10-27.json). Subsequent documentation-only commits are **not** new tested runtime revisions.

The required bounded electrical installation, physical source paths, conductor/isolator state, finite energy, cartridge fuel, local control receipts, protective trips, recovery and existing-ship subsystem compatibility have passed. The remaining exceptions below refer to explicit as-installed hardware wiring gaps and the intentionally unperformed long-duration/40-crew integrated ship acceptance. No 40-crew voyage was run.

## Fitted network and commissioning

The installed v0.5 ship contains **438 power nodes, 450 power edges and 466 actual breaker/isolation points**, plus the separate thermal, gas and fire-main networks. `commission_g19_electrical(operator_approved=True)` audits the **authoritative installed** rows, checks every power edge endpoint and fitted breaker, and creates one persistent ledger on the existing `meta:continuous-physics` clock. An existing ledger is never reset. No new nodes, remote shortcuts or simulated extra generator are created.

The real installed power source gates remain `GEN-M`, `GEN-A` and `GEN-B`, with selected deliverable schedules of 3.0, 0.65 and 0.65 MW. Total output is capped at **3.3 MW**, including the combined 3.3 MW envelope rather than summing nameplate to claim 4.3 MW. The scheduled base loads are essential 0.65, protected 0.75, normal 1.35, and demanding 2.60 MW. All are **selected fictional game-engineering parameters**. Actual generation must be commanded online, physically healthy, and connected through its installed source edge and breaker. A tripped generator or open feeder reduces capacity. The source-reachability graph is directed except real `bridge_feeder` and `cross_tie` connections. Protected loads cannot reverse-feed the main switchboards.

**No automatic load shed.** When GEN-M fails during a normal 1.35 MW schedule, its remaining single 0.65 MW auxiliary cannot supply the normal schedule. Crew must explicitly select a smaller verified schedule, restore generation, or bring rated external service online. ECLSS and EVA station power still require a verified local conducting node. Protected service additionally requires its actual protected distribution node; the presence of an online generator alone is not sufficient to power every panel.

## Switchgear, bus tie and protected transfers

Local authorised engineers use the existing `oxplant <32hex-id> power <target> <value>` receipted interface. Ordinary breakers remain crew-reachable only at the real switch's authored room. Installed-source selection is a separate operation from `plant GEN-X on` and from generator thermal-trip reset.

- `power EDGE-MSB-XTIE sync` begins a **15-game-second**, site-attended main bus synchronisation witness. A source/bus signature is captured and expires after 90 game seconds. `power EDGE-MSB-XTIE close` then requires matching live source/bus conditions and healthy closed real tie isolators; `open` releases the tie and invalidates the witness. A dead bus, changed source state, elapsed witness, failed breaker or physically tripped contact cannot be bypassed with a paperwork flag. The manual `switch` command cannot secretly restore contacts beneath a closed tie.
- `power PWR-PROT select:A|select:B` selects the central protected feeder. `power HAB-03-PROT select:A|select:B` does the analogous HAB protected-feed selector for a real HAB arc. The twin real edges switch **break-before-make**.
- When the two real feeder switches require separate local attendance, `power <existing-EDGE-PWR-MSB-A-PROT|EDGE-HAB-03-PROT-A|...> isolate|enable` provides individual local staged transfer; the opposite feeder must already be disengaged before enable. No remote magic closure across two separated local stations is assumed.
- `oxplantread power` exposes the currently persisted generation, battery, shore and trip meters at physically installed engineering boards. Local node readout is permitted only beside its actual installed equipment or distribution position. It reports current route energisation and selected schedule support, not unvisited private damage.

## Actual fault consequences

An operator may record a **measured circuit overcurrent** with `configure_g19_electrical_fault(operator_approved=True, breaker_id=..., rating_mw=..., measured_mw=...)`. The normal ship clock accumulates real elapsed time and, after 10 seconds of continuing overload, **physically opens the installed breaker**, records a persistent protective latch, and immediately removes the branch from the reachable power graph. Fault observations can change, but changing the observed fault does **not** clear a latched contact. Qualified crew must attend its safe real room and issue a receipted `power ISO-... reset` once the fault is gone. The switch remains open: ordinary `switch ... closed` is a separate, independently authorised action. Repeated/replayed receipts cannot close the same switch twice or fabricate energy.

Generator local thermal protection, start-up delays and equipment damage still use the established G18 machinery and share its clock. Power trips can stop actual ECLSS processing, cooling, pumps, rotary operations, port handling, EVA pumpdown, propulsion auxiliaries and habitation services; physically open gas ducts do not automatically close when electric fans fail.

## Battery, shore and conservation

The original vessel has two authored battery source identities (`BAT-COMMON-OPS` and `BAT-COMMON-PROT`) and shore power (`SHORE-PWR`). **Their operating ratings and state of charge are not inferred from the mere existence of equipment**, and they begin with **zero credited dispatch**, not an invented infinite UPS. A world operator can separately measure each real source and its installed node/feeder using `survey_g19_electrical_source` with finite capacity/initial energy and independent charge/discharge power ratings, or shore MW rating. The source cannot be surveyed twice to magically recharge a bank.

- A commissioned battery can be placed in `standby`, `charge` or `discharge` at its actual equipment station. Finite protected-bus discharge is constrained simultaneously by the fitted cable path, the maximum recorded kW, elapsed time and measured remaining kWh. A battery path that would backfeed a main bus is rejected. Batteries do **not** subsidise general cargo motors, main propulsion or main-board loading.
- Charging is credited **only** from spare real generator/shore MW with a conducting source-to-bank route. State of charge plus cumulative discharge must equal surveyed initial charge plus cumulatively metered recharge. No infinite regeneration; no rated circuit means no credited energy.
- A physically surveyed shore connector may be connected by a local operator only while a commissioned commercial berth is actually moored, the real shore line is selected and ship generators are isolated. Generator restart is blocked while shore remains physically connected. Losing the mooring stops shore dispatch and clears the connection rather than inventing an external port.
- The world clock records generated kWh, metered shore imports, battery charge/discharge, load delivered and load not served. A repeated tick changes none of them. All stores and receipts survive the existing database restart without an invented energy reset.

## Power-system constraints and remaining integration gate

The installed graph supports the particular HAB-03 cabin 07 refit: the fan-coil's real SG2 branch is **not** the cabin's labelled panel branch. A true panel status must come from its own source path; no central scheduler can silently substitute generic panel wiring.

The **original** v0.5 design reference had no separately authored motor feeds for the two fire pumps or LT plant. G19 now constructs persistent, separately identifiable **refit** feeder and breaker objects at their verified machinery rooms, as described below; it does not pretend those circuits belonged to the original wiring diagram. Before G19's optional refit is commissioned, thermal/fire operations continue to require the previous conservative power and equipment witnesses. Per-circuit transients and short-circuit current calculations remain abstracted into bounded protection and actual isolator state.

**Acceptance required before declaring this G19 electrical gate fully closed:** pass the pure electrical graph/energy/protection tests, installed 438/450/466 topology and actual character/receipt tests, original G18 thermal/fire/atmosphere/locally operated switch regressions, installed water/cargo/movement compatibility, battery and shore surveys using the fitted hardware when available, and simultaneous restoration fault scenarios. Use `.github/workflows/ox-g19-electrical.yml`. Do **not** interpret a passing pure suite as completion of the installed power system, and do not merge PR #138 before all G19 gates close.


## Additional fitted energy hardware and reserve hierarchy (27 October)

The candidate electrical design carries **18 distinct installed battery units**, of which only two have **actual grid source nodes and dedicated power feeders**. These are not interchangeable generic UPS accounts:

- **BAT-COMMON-OPS**: 8 MWh design nameplate, actual independent feeder to **PWR-MSB-B**. After a bounded individual capacity/state-of-charge/power survey, it may supply the genuine B main board and its independently closed load branches. It cannot energise MSB-A through a protected branch or create source power merely by being on a drawing.
- **BAT-COMMON-PROT**: 12 MWh design nameplate, direct protected-bus feeder to **PWR-PROT**. Surveyed finite discharge may cover *selected essential/protected loads* in shortfall; it never supplies ordinary general freight, rotary plant or engine auxiliary demand through a falsely reversible protected feeder.
- **BE-01..12-BAT, IX-A/B-LOCAL-BAT and HAB-04/08-REFUGE-BAT**: sixteen named local battery units, some with finite nominal design ratings. They have **no independent grid nodes or generator/feeder endpoints in the 438/450 authored power graph**. They therefore receive *no whole-ship dispatch credit*. Their local emergency equipment autonomy must be claimed by the specific fitted family only when that subsystem establishes a real local energy path and measured current charge.

The installed vessel also carries **64 separate F1/F2 kinetic storage modules**, `F1-FW-01..32` and `F2-FW-01..32`, with 3.90625 MWh *nominal deliverable design capacity each* — **250 MWh total nominal**, not an automatically full or credited 250-MWh store. Each module has its own bidirectional storage node, actual `EDGE-PWR-Fx-FW-yy` feeder and isolator. F1 and F2 each have a real, individually selected main-board infeed and one grid-connected bank bus.

G19 ledger **version 2** registers each flywheel by independently witnessed actual capacity, initial stored energy and maximum charge/discharge MW. No module begins charged just because its catalogue says 3.90625 MWh. The main bus feeder, the module feeder, actual equipment condition and the current bank-source selection are checked on every tick. A commissioned module may **charge from unused fitted generator/shore production** through the real selected infeed. It may **discharge in an electrically islanded state** onto the selected actual main board with finite energy and a maximum 3.3 MW total ship dispatch envelope; there is no invisible cross-tie or automatic unsynchronised paralleling of module inverters with live generators or an operational main-board battery. A physically opened module breaker, severed module, missing bank infeed, module fault or empty measured charge stops it without resetting its held energy. Two simultaneously selected, non-synchronised F1 (or F2) bank inputs are rejected rather than creating a hidden A/B tie. Only a qualified worker physically **inside the surveyed F1-BAY or F2-BAY with verified suit protection** can select the module's operating mode.

`survey_g19_electrical_source(...source="F1-FW-01",capacity_kwh=...,initial_kwh=...,max_charge_mw=...,max_discharge_mw=...)` is operator-only, limited to the actual module's 3,906.25 kWh nameplate. `power F1-FW-01 standby|charge|discharge` is a local crew operation with an immutable physical work receipt. `survey_g19_electrical_worksite` accepts actual vacuum-exposed flywheel bays, but never makes their atmosphere safe. Existing typewritten, non-commissioned module energy does not count as a backup.

**Migration:** a previously commissioned G19 v1 electrical ledger is upgraded by operator re-commissioning, adding *empty* flywheel accounts and zeroed flywheel meters while preserving all earlier generation, protected-battery, delivered-energy, tripped-breaker, worksite and shore custody. Recommissioning an already v2 store makes no state change.

**Electrical modelling boundary:** detailed AC transients, control-voltage phase angles, contact arcing, exact module friction losses and fully per-load kW allocation are intentionally abstracted. Selected load profiles are authorial ship operating schedules, not mathematical sums obtained by fabricating an unknown amperage for every one of 438 electrical nodes. When **all actual consumers are physically disconnected**, a live generator board does not count as delivering the selected schedule, and the ledger records unmet demand rather than fictitious delivered kWh. This is the game-world engineering contract; full-G19 acceptance still requires installed/compatibility CI.

## Finite generator cartridges and corrected energy units

The actual installed `INV-GEN-CART` magazine contains **125 tonnes** at the selected reference initial condition. G19 commissioning creates a non-resettable **magazine plus spent-housing** custody baseline on the same ship clock. Generators draw cartridge stock only for **actually metered electrical output**; the selected fictional consumption parameter is **2 kg per MWh**. Each ten-second step checks actual remaining stock, caps available generation by the quantity it can consume during that step, debits the original installed magazine, and credits the same mass to retained spent housings. Exhausted stock cannot energise a switchboard even when a generator retains an old ON_LOAD indication. No cartridge or spacecraft mass disappears at a generator switch; the magazine plus retained spent-housing kilograms must equal its original commissioned baseline. A duplicate or replayed ship-time tick produces no second fuel or electricity debit. Tampered inventory causes the entire transaction to fail before producing energy.

**Units:** `1 MW × 3.6 seconds = 1 kWh`, or `1 MW × 3,600 seconds = 1 MWh`. Every finite battery/flywheel charge, discharge and lifetime calculation uses the **3.6 MW·seconds/kWh** conversion. The initial intermediate G19 power draft had mistakenly divided MW·seconds by 3,600 to obtain *kWh*, undercounting real energy consumption by 1,000. That implementation was superseded before electrical acceptance and now has explicit pure/installed regression coverage for accurate physical units.

**Important remaining model limitation:** Device-level electrical nameplate loads are not completely enumerated in the as-installed graph. G19 uses bounded ship-wide operating schedules rather than inventing per-device kW ratings. Equipment operation requires authentic original distribution and, for 72 priority machinery units, the newly fitted and individually isolatable G19 refit feeders. The 16 local batteries have **separate physical emergency outputs and generator/shore-fed chargers**, but none is a main-bus generator or unlimited reserve. Source dispatch, demand and shortfall remain lumped by operating schedule; detailed per-circuit current-flow and fault-current studies are deliberately outside this game-world contract. The 808-equipment audit below distinguishes further powered-device modelling gaps from passive equipment, rather than silently declaring every outstanding component electrically complete.



## Source-to-storage energy reconciliation

Generator cartridges now pay for **all actual metered production**, including kWh delivered into a physically connected battery or flywheel charger. A generator is not allowed to recharge the ship's storage for free while debit accounting sees only ordinary ship service. The power ledger checks each bounded tick independently: generator output, shore imports and finite-storage discharge must equal delivered ship-load energy plus the energy newly stored in batteries/flywheels. This permits retention of historical v1 meter values without rewriting prior receipts.

The fitted 125-tonne generator cartridge magazine remains authoritative; spent cartridges retain the corresponding mass aboard. Pure and installed tests now include charging from real generation, fuel-limited replenishment, metered energy balance, and replay-safe inventory custody. These revisions follow the previously accepted four-job baseline at `c586378e` and require their own CI pass before the updated electrical runtime can be accepted.


## Fitted shore connector and commercial berth safety

At an actually moored berth, a separately rated `SHORE-PWR` connector must conduct through its original `EDGE-SHORE-PWR` and `ISO-SHORE-PWR` before imported electricity can energise MSB-B. The external source is not a ship generator: charging and delivered load are separately metered as imports, and do not consume generator cartridges. The **local dockside crew command** receives an idempotent work receipt.

Shore supply and any physically live ship generator feed are **not authorised to parallel without synchronisation hardware**. An attempted manual closure of a generator source breaker while shore remains connected is rejected, and the authoritative dispatch kernel independently rejects any forced simultaneous source state. A commercial berth cannot be released while the ship's external power cable remains connected: the operator must first use the physical dockside disconnect. The enclosed G19 installed tests explicitly exercise docking, source selection, real B-board service load, protected generator switchgear, disconnect, and undocking.

This remains a game-world engineering interlock, not a certified electrical-transfer switch or arc-flash calculation. The design provides no arbitrarily invented shore connector or remote cable.


## G19 fitted machinery feeders and finite local emergency electrical cycle — pending CI

The established generator/shore revision at `d375bc51` passed all four jobs in [run #40437404966](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40437404966). The much wider auxiliary circuit implementation below follows that tested baseline and **does not inherit its acceptance status**. The previous auxiliary run [#40488825757](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40488825757) passed three of four jobs; the installed test failure was a mistaken A-generator path to the B-fed forward-pump room and was corrected. Subsequent expanded runtime and charging tests require their own full CI evidence.

### 72 independently fused machinery feeders

The 72nd protected operation is the independently breakered **FTL translation-field control/auxiliary feed** in `FTL-SVC`, supplied from the real B-side `NODE-LP-FTL-SVC` panel. Its fitted cable and contact must conduct before an electrical-commissioned crew member can engage a planned FTL leg. If the conductor subsequently opens, the active FTL leg aborts through the existing navigation state machine rather than continuing through a virtual power source; the previous motion/fuel custody rules still apply. This is the field's *shipboard control and ancillary demand* inside the bounded MW schedule, not a false assertion that the fictional translation drive draws its full energy from a conventional 3.3 MW electrical feeder.



G19 initially added 49 explicit `g19_motor` branches from individually verified **co-located as-installed power panels**. The list comprises the forward/aft fire pumps, LT thermal plant, **24 independently serviceable drum bearing lubrication skids**, both ECLSS processors, both water processors, both waste processors, two HAB ring drives, two HAB indexer drives, six drum indexed personnel carriers and six radial freight handlers. Each added terminal, cable/edge and local breaker is a uniquely identified persistent Evennia world object. Breaker trips and local inspection expose the one actual motor path; sound room wiring cannot override a failed motor fuse. Redundant devices remain independently serviceable, and the relevant existing environment/water/cargo/HAB operations now test their fitted feeder condition rather than treating their room panel as a blanket permission. Crew repair and restart remain separate operations.

**Protected fire-pump alternate:** The two installed emergency/fire pumps now have a second, separately breakered cable from the original `PWR-PROT` protected bus at `PWR-AFT`. The forward cable is explicitly routed down the authentic A-side fixed-spine service trunk to `WATER-FWD`; the aft cable runs through its actual aft spine section to `ENV-AFT`. Each uses its existing motor terminal but its own `g19_motor_protected` source edge/isolator, initially isolated. Qualified crew physically attending the actual pump use `power FIRE-PUMP-FWD|FIRE-PUMP-AFT select:normal|select:protected`; transfer persistently opens the old source selection **before** closing the other. Neither source may remain physically paralleled, and breaker failure/trip prevents selecting that source. Without an energised protected bus, the alternate feeder provides zero current; with the protected bus live it does not reverse-feed the B-side main distribution or other equipment. The source change is a manual emergency action, not an invisible failover. Pure and installed regressions check live protected takeover from an A-side generator while the B-side pump room panel remains without power, fuse isolation, return to normal and non-backfeed. **This is added modelled refit hardware**, not undisclosed original candidate wiring. Its acceptance is pending new full CI evidence.

These are **versioned additions** to the modelled in-world refit, not a claim that the v0.5 candidate reference already contains motor endpoints. The original **438/450/466** power graph retains its identities and counts. G19 auxiliary rows are additional, intentionally segregated `g19_motor`, `g19_motor_protected`, `g19_local_dc` and `g19_local_charger` networks, so the main-source audit and its pre-existing equipment data cannot silently change or create another generator. No loads receive invented per-device electrical nameplate MW; the selected ship-level load schedules continue to bound total dispatch.


**Additional 22 individually isolated motor circuits:** Four independent workshop-rotor motors (two WR drives and two carriage extenders), separate oxygen-generation and CO2-regeneration skids on both ECLSS trains, four dehumidifiers, eight HAB arc air-handler fans, and two fixed-spine air handlers. Their parent panels are verified against real installed equipment in the same compartment, including the physically distinct HAB-06 B-side and HAB-08 A-side environmental supplies. The workshop rotor's new feeds originate at its existing rotary power interface, not an imaginary line from a fixed control room.

**Consequences now coupled to ship physics:** Loss of the selected workshop drive branch removes that drive's motoring ability; an independently live counterpart still permits rotation, while carriage extension requires both fitted extender paths. An oxygen generator's own breaker can interrupt electrolysis without necessarily disabling the rest of its ECLSS circulation train. A HAB air-handler breaker removes motor-driven air exchange through that manifold while leaving ducts physically open for pressure-driven leakage, and fixed-spine circulation can run from separately supplied handlers if commissioned, powered and started. The existing central ECLSS CO2 sorbent has finite remaining capacity; simply energising the new regeneration motor **does not** create a CO2 disposal receiver or replenish sorbent. The four dehumidifier circuits are individually isolated and inspectable, but fine-grained airborne-water condensation remains a later environmental modelling task. These changes add failure consequences without inventing comprehensive instantaneous new crew environment services.

**Headroom correction:** Distributed local battery charging is constrained by both authentic generator/shore production and the ship's **3.3 MW deliverable main-bus envelope**; combining generators with greater nominal output cannot create a fictitious recharging surplus. The new pure and installed tests check independent circuit identities, redundant drive isolation and AHU failure/recovery. Pending CI must pass for these **72** circuits, not the previous 49-circuit set.

### 16 finite emergency DC sources and their dedicated chargers

Each original BE-01..12 local rescue battery supports one local bearing emergency/control station, IX-A/B local batteries support their *fixed-collar recovery* appliance (not HAB phase matching), and HAB-04/08 refuge batteries support their own emergency-air appliance (not general rotary, cargo, or the main distribution bus). Each local battery owns two independently breakered short paths: a **one-way DC emergency output** to its nearby fitted appliance and a **separate grid-fed charger input** from the actual parent panel. The charger has to conduct through its individual breaker, sound installed cable, and a real energised generator/shore producer path to the panel. A main-board battery or flywheel cannot refill local emergency reserves by mere indirect backfeed.

Operators must first attest real initial state of charge and capacity; missing measurements confer zero dispatch or refill. Local qualified crew select `power <battery-id> standby|reserve|charge` at the physically installed worksite, with durable shared request receipts. The twelve depressurised BE service rooms additionally require an individually surveyed hazardous electrical worksite and verified suit protection; presence of a battery does not render vacuum breathable. A `reserve` bank only spends energy after its actual normal appliance endpoint loses grid supply; the HAB refuge emergency-air load has its own independently breakered normal circuit, not merely the state of its room panel. Damaged/failed battery, appliance, emergency fuse or conductor refuse backup, and exhausted charge cannot self-recover. `charge` requires genuine **unused generation or shore MW** and a fitted charging path. The selected finite local battery draw/charge rates are bounded fictional parameters, **not measured nameplate ratings of real hardware**.

The local ledger v2 preserves `initial_kwh + charged_kwh − delivered_kwh = held_kwh` per battery and reconciles local aggregate charging/discharge meters. `step_energy` independently proves on every bounded ship tick that newly charged local kWh appears as a dedicated source-energy sink **instead of also being counted as ordinary delivered load**. Generator cartridges pay for local charging; shore imports meter it as actual external energy without consuming cartridges. Adding simultaneous central battery/flywheel storage charges does not grant a second energy allowance. A repeated ship tick or receipted local command has no further effect. Migration from the preceding local-v1 state preserves original meter, charge and damage history instead of silently resetting batteries.

Local character readouts report **only an attended battery's measured charge, selected mode, actual fuse, charger fuse and current local condition**, not hidden charge at remote stations. The bridge engineering readout does not reveal private reserve stock in inaccessible lockers. The 16 local DC circuits do not perform general grid dispatch, nor does their energised status alone certify all related environmental or HAB recovery behaviour.

### Machine-readable installation coverage check

Run `python design/ship/check_g19_electrical_inventory.py` from the repository root. The pure audit reconciles all **808** selected installed equipment records with the untouched **438/450/466** original power graph, the **72 priority powered machines** in 17 equipment families, **16 independently charged local DC reserves**, and two alternate protected fire-pump feeds. The test checks terminal, conductor, breaker, parent panel, physical room, nameplate-bound local battery and source-route identities, and rejects collisions with original wiring. It is now part of the focused electrical CI job.

The result **does not** pronounce all 808 equipment electrically commissioned. Passive hardware, structures, unpowered emergency tools, cargo climate equipment, crop-processing machinery and specialised tools remain explicitly identifiable in its outstanding-by-kind report. This prevents an undifferentiated "missing circuit" count from disguising the difference between passive apparatus and an operating machine that actually requires a supply. Equipment-level energy budgeting and further cargo/agricultural machinery effects remain open.

### Coupled fire-main and low-temperature heat rejection — pending focused CI

A post-fault-sweep integration review found two real operating inconsistencies,
corrected on the same G19 branch:

- **Fire-main source selection:** an installed fire-pump motor may draw
  through its verified normal feeder with a sound main operating schedule,
  even when the protected bus is unavailable. On manually selecting the
  protected alternate, the original normal room feed is no longer credited:
  the protected source must independently provide sufficient energy through
  its dedicated, closed, serviceable breaker. A powered protected bus cannot
  excuse a normal-source brownout or a failed pump, and the two source
  contacts cannot be paralleled. This is enforced in the authoritative fire
  suppression tick, where finite water is expended only when the fitted
  fire-main path actually conducts.
- **Shared LT cooling:** propulsion formerly could reduce its stored heat
  while bypassing the newly installed LT motor fuse; its independent
  1.8-MW-equivalent heat-rejection allowance also could exceed the
  surviving radiator capacity. The tick now shares **one** capacity limit
  (four 937.5-kW equivalent radiator units, 3,750 kW maximum). Drive heat
  is rejected first, subject to both stored heat and an 1,800-kW ceiling;
  the remainder alone cools the pressure-zone thermal network. Lost LT
  feeder, coolant path, machinery state, radiator units or live service
  inhibits that corresponding capacity. These are fictional game-calibrated
  thermal rates, not a new thermal plant.

Focused pure tests cover every selected fire-pump supply, fault and transfer
isolation, all zero-to-four-radiator allocations, invalid integration inputs,
the finite 72-motor isolation sweep and seeded 16-bank charge conservation.
Additional **installed Evennia** regressions use original room panels,
real fire-main valves, actual finite suppression-water custody, an LT fuse
casualty, thermal storage persistence, and safe restoration without falsely
declaring a full-ship blackout.

**Status:** these are committed implementation changes following the
previously verified electrical base. They are *not* accepted by borrowing
evidence from the earlier 77-test or 25-test runs. Require the new focused
branch-push CI plus installed and compatibility results on the same runtime
revision. Neither the full-ship acceptance nor 40-crew voyage has been run.

### Independent HAB refuge sorbent and local DC failover — pending CI

The original **HAB-04-REFUGE-AIR** and **HAB-08-REFUGE-AIR** packs are
explicitly installed life-support equipment, each with a normal powered
appliance branch and a nearby independently charged local emergency battery.
G19 previously consumed reserve electricity without providing any atmospheric
service. The new bounded `ship_refuge_life_support.py` operation makes the
causal link explicit:

- An operator must attest **remaining CO2 scrubber capacity** in the
  existing original pack, no more than the derived nominal envelope of
  40 occupants for 72 hours at the crew physiology model's 10 mg/s
  per-person oxygen/CO2 mass proxy (**103.68 kg per fitted pack**).
  **Zero surveyed medium means zero credit**, and re-commissioning does not
  replenish a used filter.
- A working package may scrub only its **actual local pressure cell**, when
  powered through the original `NODE-PWR-HAB-xx-REFUGE-AIR` normal branch
  or the **fully supplied, locally fused, finite reserve battery**. Merely
  having a healthy ship bus, an unmeasured battery, or another pack's
  electricity is insufficient. Each package is limited to a 40-person
  respiratory-mass-proxy capture rate; failed hardware and a depressurised
  room refuse operation.
- Each increment of CO2 removed from the original air inventory is retained
  as an **explicit onboard finite captured mass**, with per-tick aggregate
  conservation. Temperature and gas energy are updated with the same
  existing coarse atmosphere model. The package **does not generate
  oxygen, repressurise hulls, remove smoke, make unventilated surrounding
  rooms safe, or give an unlimited 72-hour guarantee**.
- Both battery draw and independent scrubber medium are consumed
  idempotently by the authoritative ship physics clock. The pack has no
  automatic cartridge change or after-the-fact reset. Existing crew
  physiology measures the changed gas state in the **actual refuge zone**.

The dedicated pure tests exercise unsurveyed/failed/unpowered/refuge-at-
vacuum conditions, finite capture capacity, exact gas + captured-mass
conservation, and nonresetting surveys. The installed-world tests reproduce
an original-source blackout with active emergency DC, fuse isolation,
refuge gas transformation, sorbent exhaustion, replay and commissioning
without reset. The focused electrical CI workflow now includes the new
kernel and pure/installed checks.

**Boundary:** this is one bounded refuge-atmosphere service at each actual
source location, not a full 40-person enclosed living-area recirculation
network; the original refuge's adjacent-room duct coverage, consumable
replacement, full crew habitability and whole-ship acceptance remain open.
The new revision is **unverified until its code-head CI evidence passes**.

### Remaining verification and modelling boundaries

`ox-g19-electrical.yml` gates pure electrical source/charge conservation and faults, installed character/circuit/replay coverage, G18 gas/fire/cooling regressions, and G19 water/cargo/movement compatibility. Installed outcomes must be evaluated against the **exact tested commit**, not a prior acceptance. If the draft fast CI scope gate requires deferral of expensive PR-triggered jobs, focused tests still execute on branch **push**; do not bypass the repository's accepted scope policy.

The electrical model deliberately abstracts detailed conductor impedances, breaker fault-current magnitude, voltage/frequency transient waveforms, converters' efficiency loss, per-motor ampere envelopes, and absolute NASA flight standards. The 72 explicit motor breakers represent modelled priority machinery and locally verified motor circuits; cargo environmental packs, agricultural skids, machine tools and other powered loads are not yet all individually operational in G19. Detailed equipment-by-equipment operating contracts remain under audit. **Full G19 ship acceptance is not granted** without remaining crew/environmental/maintenance/operating scenarios. PR #138 stays draft and unmerged. No 40-crew voyage is authorised in this development round.
