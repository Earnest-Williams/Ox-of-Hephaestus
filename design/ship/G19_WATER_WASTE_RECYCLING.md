# G19: finite potable water, wastewater and sealed waste operation

**Status: WATER/WASTE/RECYCLING SUBSYSTEM ACCEPTED (25 October 2026).** Its finite-resource model, installed-world operations and G18 compatibility regressions passed on the G19 branch. **PR #138 remains draft and unmerged** until the *other* ship systems complete their own integration gates.

## Scope and source of truth

The physical design is the selected v0.5 candidate, particularly
[BYPRODUCT_AND_WASTE_CLOSURE_v0.5.md](BYPRODUCT_AND_WASTE_CLOSURE_v0.5.md),
[ENDURANCE_LEDGER_v0.5.md](ENDURANCE_LEDGER_v0.5.md), and
[MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md](MACHINERY_AND_FINITE_DISPOSAL_CLOSURE_v0.5.md).
This is causal game-ship engineering, not construction or NASA certification.

The **canonical installed Evennia database** owns actual valve settings,
device conditions, inventory quantities, clock, faults, local worker positions
and receipts. `game/world/ship_water_recycling.py` is a deterministic
transition library; it has no independent persistent database or unlimited
resource source. The G19 water state is a component of the existing
`meta:continuous-physics` world-clock JSON. The runtime reads installed
network edges and actuators for every treatment step, not the design's
static "available" reference. Recommissioning never resets a running cycle.

Existing G18 scenarios retain their previous behaviour until the world
operator explicitly calls `commission_g19_water(operator_approved=True)`.
There is no implicit retrofit when a model, handler or server restarts.
The working-potable reference begins at **39,000 kg** within the original
ship mass, not from a newly invented inventory. The existing authoritative
inventories are **162 t** normal makeup and **70 t** separate protected
reserve. The remaining existing inventory categories retain their separately
owned source quantities and identities.

## Finite physical circuit

- Two independently conditionable water processors, `WATER-PROC-A/B`, and
  sanitation processors, `WASTE-PROC-A/B`, live in their existing HAB-06
  and HAB-08 ECLSS compartments. A treatment train cannot run solely
  because a GUI says it is ready: installed equipment must be sound,
  authorised local controls must permit operation, electrical distribution
  must be assured, and the current service graph must connect source and
  receiver. Each can treat a 40-person wastewater load when healthy.
- At the 40-person reference, **1,000 kg/day domestic circulation** is
  split into separately held grey and black streams. Each processor is
  limited to **1,100 kg/day grey** and **120 kg/day black**; independent
  local buffer capacities are **500 kg grey** and **250 kg black**.
  The separate fixed receivers at WATER-FWD retain their actual
  **10,000 kg grey** and **2,000 kg black** capacities.
- Fixed receiver access requires a live rated rotary fluid crossing,
  including real open local isolators on both sides. Either A or B can
  provide the authorised redundant path. With both disabled or isolated,
  local treatment/buffering remains available but the fixed tank is not
  magically reachable. An isolated fixed receiver continues holding
  its existing mass and does not drain itself.
- Nominal **90%** treatment is returned to the working potable circuit
  *only after successful processing*. **1%** becomes sealed stabilized
  sanitary residue, **9%** leaves the potable-resource cycle as an
  explicitly counted nonrecovered mission-process/reject output.
  This coarse nonpotable output is counted as an operational budget,
  **not** a fictional second potable stock or an unbounded reusable tank.
  A damaged-but-running water or sanitation processor derates to **60%**
  throughput and **80%** recovery, with the extra reject charged to the
  same finite water allowance. At forty crew, a whole-leg change from
  90% to 80% adds **73 tonnes** of makeup demand over 730 days.
  Normal supplies may therefore run out and actual crew demand is rationed;
  no automatic debit from the protected reserve disguises that casualty.
  More detailed water chemistry and receivers are deliberately outside
  the coarse simulator's verisimilitude requirements.
- Ordinary demand and makeup are metered over simulation time; buffer
  exhaustion and treatment shortfall reduce **actual served demand**.
  Normal makeup goes to the 39 t working tank at a finite transfer rate.
  The protected 70 t reserve is never used without a qualified crew
  member at the actual WATER-FWD controls explicitly releasing it.
  While that reserve is released, ordinary cultivation irrigation and
  routine servicing are automatically deferred, but domestic consumption,
  food rehydration and verified oxygen-electrolysis feed can continue.
  The curtailed discretionary demand is metered explicitly.
- The independent dry sanitary `INV-WASTE-RESIDUE` account reconciles
  its two **8 t** sealed physical cassettes after every transition. The
  independent **4 + 4 t industrial** and **1 + 1 t hazardous** receivers
  cannot borrow sanitary capacity. The transition library for segregated
  discarded material debits already-owned compatible stock first.
  Purifier filters require a location-surveyed source at an actual stores
  compartment. An authenticated qualified crewmember takes a finite portable
  batch, carries it in the world-owned cargo/custody ledger to the real ECLSS
  purifier, and physically loads its bounded cartridge rack before the plant
  can consume filter media. The spent filter goes into a sound, sealed
  hazardous receiver; simply having 8 t of shipwide consumables does not
  provide magically delivered chemistry at an isolated processor.
- A contamination casualty quarantines potable circulation. Locally
  ordered purification uses actual water processing service and finite
  replacement filter stock; a qualified local technician must obtain a
  passing sample before clearing a quarantine. Turning a pump back on
  does not remove contamination. Failed or unsealed cassettes are not
  legitimate receivers. Waste, water and sealed-cassette intervention is
  subject to durable shared request-ID receipts. Actual local industrial
  or hazardous waste deposits must additionally come from an existing,
  operator-surveyed compatible source *in the same room*, consume that
  source inventory and occupy finite sealed receiver capacity. Unlocated
  manifest stock cannot be discarded by name alone.

## Couplings and limits

- Water distribution remains on the essential electrical service tier;
  normal wastewater reclamation requires the selected normal bus capacity.
  A normal-load brownout can preserve essential drinking water while
  wastewater accumulates in finite local/fixed receivers. Complete loss of
  essential power stops potable pumping and sanitation. Recovered or
  quarantined contents do not teleport between zones or bypass a closed
  isolator.
- Fire mist still draws the **same** existing normal-water inventory;
  a water processor does not give the fire service independent, infinite
  water. Canonical transaction locking ensures mist and water demand
  cannot both spend the same stock.
- When an explicitly verified ECLSS/H2 outlet and live electrolysis train
  support oxygen generation, water electrolysis consumes real treated
  water and returns its oxygen product to the actual bounded gas cell.
  Only physically vented hydrogen decreases ship inertial mass.
  The operator-only `verify_g19_hydrogen_outlet` records an actual
  as-installed clearance survey before either H2 port can be used; both
  separate source and hull valves, the exhaust edge and sound equipment
  must still conduct on every physics step. No closed or unverified nozzle
  gets credited as safe exterior discharge merely because the design
  contains an outlet.
  Normal life-support respiration and CO2 regeneration remain the
  separate atmosphere/crew-exposure G19 closure work, not a duplicate
  sanitary network here.
- Nonpotable outputs and ordinary food/cultivation allocations are
  mission-process ledger sinks in this intentionally coarse simulation;
  there is no mass minting or false oxygen regeneration. Detailed
  biological process inventories and specific exterior reject lines are
  not claimed to be independently commissioned from absent geometry.

## Crew controls and work receipts

`oxplantread water` is available only at the actual water, ECLSS or
sealed-receiver stations. `oxplant <uuid> water POTABLE-TANK-MAIN
reserve_open|reserve_close|quarantine|sample|clear` performs local
water-control work. `water WATER-PROC-A/B
on|off|quarantine|decontaminate|decontaminate_off` commands the separate
purification machinery. `waste WASTE-PROC-A/B on|off|quarantine`
controls each sanitation train; compatible sealed cassettes can be
positively `seal`ed or `unseal`ed only within their local safe
work restrictions. Both the clock and WorkReceipt rows survive
restart and duplicate commands cannot repeat work.

## Verified subsystem acceptance — 25 October 2026

**Code revision validated:** `d3d2f9c537a7e03dbe9366821c5af241376f30a6`. Subsequent documentation-only commits do not modify that tested runtime. The dedicated [GitHub Actions evidence run](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40245103836) completed **both jobs successfully**:

| Gate | Result | Verified coverage |
| --- | --- | --- |
| Pure deterministic water/material engine | **17/17 pass** | 730-day normal leg; 80% degraded recovery and the 73 t extra draw; dual-train failures; fixed/local receiver saturation; guarded 70 t reserve and nonessential rationing; material custody; finite treatment filters; seeded multi-casualty fuzz, corruption rejection and replay determinism |
| Installed Evennia G19 water/waste | **12/12 pass** | Live rotary wet valves, single-union failover, local qualified controls and duplicate receipts, physical filter collection/delivery, water sampling and hazardous capture, industrial scrap, H₂ outlet verification, brownout survival and 60%/80% degradation |
| Existing G18 fire/air/thermal/damage compatibility | **14/14 pass** | Actual-world generator, service valves, pressure boundaries, fires, thermal trips, finite suppression and the independently seeded 80-tick casualty campaign |
| Design waste/physical validators | **Pass** | `check_waste_byproducts.py` and `check_physical_operations.py` through the same workflow |

**Total: 43 tests passing**, plus the physical-design validators. The branch's fast PR and documentation checks also passed. Water/waste/recycling is therefore **subsystem-complete** under the project's *verisimilitude, not NASA certification* requirement. It is not an assertion that every other G19 ship system or the final autonomous voyage has passed. The full-ship completion gate stays closed and the PR stays unmerged.

## Acceptance evidence and failure drills

The new `.github/workflows/ox-g19-water.yml` runs:

1. Standard-library 730-day endurance and conservation through the
   entire normal voyage, with domestic and oxygen-water allocations.
2. Single- and dual-processor failures, damaged-train throughput,
   80% degraded recovery, fixed receiver isolation, finite buffer
   exhaustion, sanitary-cassette saturation, emergency-reserve rationing,
   protection of the reserved 70 t, and negative-input rejection.
3. Seeded multi-casualty/property fuzzing across variable time steps,
   processor failures, isolation, buffer saturation, material corruption
   and double evaluation without authority over persistent world state.
4. Real Evennia initialization, installed water equipment/edges,
   local authenticated receipt replay, actual surveyed material custody,
   cartridge installation, contamination, finite filter consumption,
   segregated hazardous/industrial capture, H2 outlet proof, rotary
   failover, essential-power brownout, and no uncommitted mass transfer.
5. Existing G18 continuous-physics and coupled-casualty suites,
   including smoke, thermal protection, power failures and finite
   fire suppression, to detect accidental regressions.

**Scope boundary:** A full port-side offload manifest for sealed solid waste
requires the separate cargo-port handling and crew traversals to be completed;
no in-flight disappearance of full waste cassettes is permitted. Crew-specific
health consequences from water shortage are consumed by the separate G19
physiology/exposure subsystem; this subsystem reports every unserved kilogram.
Mechanical repairs of failed water machinery are handled by the shared G19
finite-material equipment-recovery package rather than an invented local
instant reset. None of these cross-system dependencies is represented as
already completed.

**This subsystem is accepted; no final whole-ship acceptance or merge has been claimed.** The other G19 systems, their cross-system crew/cargo/repair dependencies and the final integrated voyage gate remain separate obligations within the *same* PR.
