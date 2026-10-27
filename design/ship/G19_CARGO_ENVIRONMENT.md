# G19 cargo environmental protection — installed mechanical systems

**Branch:** `g19-complete-ship-systems` · **Integration PR:** #138

## Purpose

The six rotating freight drums already contain two mechanically distinct
cargo-environment devices per drum. Before this continuation, their fitted
individual electrical feeds and live duty counters worked but cargo itself
had no persistent exposure consequence. This slice gives the machinery a
finite job: keep surveyed packaged freight within a sensible storage
temperature, or allow its recorded quality to deteriorate during real
machinery and cooling failures.

This is an intentionally bounded game-world thermal model, calibrated for
the existing working freighter rather than a new spacecraft design.

## Original as-installed mechanical route

| Original hardware | Per drum | World consequence |
| --- | --- | --- |
| `DR-xx-CARGO-HX` | Cargo thermal skid | Local thermal exchange and active heat rejection |
| `DR-xx-CARGO-GAS` | Cargo-atmosphere circulation pack | Required for forced thermal distribution through a contained cargo environment |
| `DR-xx-LT-IF` | Rotary low-temperature interface | Must conduct from the original `NODE-LT-PLANT` through original `EDGE-DR-xx-LT-IF` and `ISO-DR-xx-LT-IF` valve |
| `DR-xx-SVC-DB` | Gallery distribution board | Both cargo devices require individually fused service through original gallery supply |
| `PZ-DR-xx-SVC` | Measured service-gallery pressure cell | Supplies actual ambient temperature, receives the corresponding signed wall heat flow |

This is a **packaged freight microclimate**. The machinery does not assert
that vast bulk cargo hold spaces are pressurised, habitable, filled with
breathable gas or supplied with new consumables.

## Survey and controller workflow

1. Operator commissions G19 electrical/equipment service and explicitly
   instruments `DR-01` through `DR-06` individually, via
   `survey_g19_cargo_environment(operation="drum", drum=..., temperature_k=..., target_k=..., heat_capacity_kj_k=..., conductance_kw_k=..., operator_approved=True)`.
   This is a *measurement* of the actual container store; the reference
   geometry cannot infer the cargo's condition or thermal mass.
2. Physical commercial cargo lots still originate through the existing
   `survey_cargo_lot` and verified global 900,000-tonne manifest.
   Explicitly sensitive, actually stowed freight may be identified with
   `survey_g19_cargo_environment(operation="lot", drum=..., lot_id=..., profile=..., operator_approved=True)`.
3. Supported profiles are `cold_chain`, `cool_sensitive` and
   `heat_sensitive`, with different bounded temperature bands and loss
   rates. Unlocated/unsurveyed freight is never retroactively marked as
   refrigerated or assumed undamaged.
4. The local engineer attends the real `DR-xx-GALLERY` skid panel to
   change a thermal target with the existing receipted
   `service DR-xx-CARGO-HX target:<kelvin>` operation. This checks
   live source, working equipment and safely measurable local conditions.
   Local instruments show measured temperature, target, attributed
   sensitive-lot condition and the running cooling status.

## Ship-clock thermodynamics

Each 10-second physics substep:

- Transfers `U × (T_gallery − T_cargo) × dt` of sensible heat through
  the measured cargo thermal store wall. It **debits or credits that exact
  amount** to the real `PZ-DR-xx-SVC` pressure-cell energy ledger.
- Refrigeration needs both powered, serviceable skids **and** the real
  unisolated rotary LT interface. Each skid can request at most **20 kW
  equivalent** of heat rejection. The six together are bounded to
  **120 kW equivalent** and to at most **10% of the finite LT plant capacity
  remaining after propulsion**, reserving the remainder for inhabited
  spaces. The heat rejected is measured in joules and debited *before*
  the existing compartment cooling stage.
- A dead compressor, isolated local motor breaker, stopped circulation
  pack, closed LT valve, disabled LT-PLANT, failed radiator or insufficient
  generator dispatch removes the corresponding cooling. The sensible
  thermal store persists and slowly follows actual gallery conditions.
- A specifically surveyed sensitive lot outside its declared temperature
  band accumulates excursion duration and permanent fractional quality
  loss. Its physical freight mass and its position in the original
  balancing/manifest system remain unchanged. Splitting a damaged lot
  inherits the recorded damage in both daughter and parent; internal
  movements preserve that history and record unmeasured transfer time.

No commercial price is guessed from a cargo quality fraction. Later game
contracts may use the recorded condition in insurance, delivery acceptance
and negotiations, instead of silently rewriting physical cargo mass.

## Engineering tests

- Pure tests:
  `world.tests.test_ship_cargo_environment` — original unsurveyed
  reference, finite heat transfer, radiator allocation, loss of either
  cargo service, LT-valve isolation, thermal upset, cargo quality
  degradation, split inheritance and invalid surveys.
- Installed tests in `world.tests.test_installed_ship_electrical` —
  real generator-to-drum-panel paths, the original LT rotary valve,
  actual gallery heat accounting, receipted local setpoint changes,
  sensitive-lot impairment and non-resetting split history.
- Source audit:
  `design/ship/check_g19_cargo_climate_inventory.py` verifies all six
  original co-located skids, circulation packs, valves, pressure-cell
  gallery mappings and 12 corresponding electrical endpoints.
- The four-job `ox-g19-electrical.yml` suite runs the new kernel,
  installed regression, pre-existing electricity/ECLSS/water and cargo
  compatibility and source inventory checks.

The bounded thermal model is deliberately calibrated through actual
in-world survey data; refined moisture/chemistry, cargo packaging and
delivery-value calculations can extend the same ledger without
changing its original equipment identities.
