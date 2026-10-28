# G19 — physically attributable machinery output

The G19 ship does not equate live electrical contacts, a commanded ON flag,
or a functioning switchboard panel with actual work. Each local source must
demonstrate a current effect on its **original connected medium**.

## Source inventory (42 original individually fitted motor identities)

| Families | Count | Positive-output proof | A missing measurement means |
| --- | ---: | --- | --- |
| ECLSS A/B | 2 | Actual kg CO2 captured from each **original bounded intake cell** and credited against finite ship sorbent capacity | An idle/saturated train has no new capture proof |
| HAB-01–08 AHUs and fore/aft spine fans | 10 | Actual gas-mass parcel crossing an *existing* powered local duct endpoint (not passive pressure exchange) | Energized motor and intact duct alone are insufficient |
| WATER-PROC A/B and WASTE-PROC A/B | 4 | Per-side physically processed kg from the existing conservative finite wastewater solver; both skids are required for each side | One stopped skid extinguishes both skids' treatment proof |
| FIRE-PUMP-FWD/AFT | 2 | Existing finite suppression-water inventory debit at an actually supplied HAB mist terminal | If both pumps are active on a shared header, **neither** gets individual source credit; isolate one for a flow test |
| BE-01…12 LUBE N/S | 24 | Independently powered local captive-oil skid, finite differential pressure rise, and recirculated kg through that skid | Pressure must build; a live breaker alone cannot prove it; pressure decays on source loss |

**No additional ship spaces, supply trunks, motors, free source inventories,
or remote cameras are introduced.** The 24 existing bearing skids are modelled
as sealed hydraulic recirculation loops: recirculated mass is a throughput
meter, **not** fresh or consumed oil mass, and never changes ship total mass.

The local receipt on the existing original equipment object records its
measurement type, current 10-s interval amount, cumulative amount, physics
sample time and (for bearing skids) retained pressure. Old cumulative output
cannot establish new function. At each physics epoch, physical media
transactions produce receipts. A blackout, bypass, failed machine, dark
process, or lacking downstream demand yields **zero** new proof.

## Operational diagnostics and restart

A physically attending engineer uses
`oxplantread fault:<original-machine-id>` to see fitted breaker
identities, the local panel, local condition, and the
`observed_process_output`/ `process_output_recent` values. No remote
character can inspect another worksite's hidden casualty.

The existing signed maintenance sequence (inspect → isolate → finite repair
→ inspect again → manually restore each actual feeder → authorize →
verify) remains in force. Two **consecutive genuine physics epochs** must
show positive process output for the 42 process machines, plus healthy
body, restored supply, fresh local panel and no relevant trip or alarm.
Workshop spindles keep their own measured-rpm path. Water/bearing skids
operate as automatic processes when their original physical supply and
medium permit it; they do not invent operator ON controls absent from the
original ship.

Bearing skid service additionally waits for its *real remaining hydraulic
pressure* to bleed down, including older legacy repair jobs. A closed
breaker, stopped motor contactor or logged repair does not mean the sealed
skid is depressurized.

## Conservation and attribution boundaries

* Water: `processed_A_kg + processed_B_kg == processed_kg`, checked inside
  the water mass solver. The same positive side-flow is evidence of the
  **coupled** waste and water skids in that train, not an independent
  flowmeter in every pump body. Backlog/effluent is finite.
* Air: only forced parcel movement on conducting atmosphere edges
  qualifies for an AHU/spine fan, whereas each ECLSS train must capture
  actual CO2 from its own pressure cell. Passive pressure difference
  cannot be credited as fan movement.
* Fire: water is credited solely when mist physically leaves the finite
  normal-water source. One available pump gets source-specific credit;
  two available pumps get **no per-unit** proof because a shared header
  has no flow meter resolving their separate contributions.
* Bearings: modeled differential pressure and seal-loop circulation provide
  machine-specific positive output, but this is **not** yet a complete
  simulation of each lubrication journal's film thickness, oil temperature,
  particle loading or leakage. A future bearing-film extension should
  depend on this pressure/flow, never the inverse.

No normal/essential power dispatch, finite water reserve, hazardous-bay suit
rule, existing physical tool/spare custody, or previous retrofit topology
is relaxed by this phase.

## Acceptance tests

`.github/workflows/ox-g19-process-output.yml` runs pure invariants
(including seeded changes, source isolation, A/B mass reconciliation and
shared fire-header ambiguity) and independent installed-world scenarios
for ECLSS CO2, HAB fan airflow, A/B wastewater, bearing pressure and
single-source fire delivery. The existing large G19 instrumentation workflow
also includes the new pure tests. Neither runs the 40-person voyage.

### Focused acceptance — 28 October 2026

[Run #40764736704](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40764736704)
passed **38/38 pure tests** and **5/5 installed Evennia scenarios** at
runtime commit `8d2899f4`. The five installed cases directly demonstrated:
ECLSS-A/B capture debited from real gas, independent A/B water treatment
and A-source loss with B failover, physical HAB-08 air movement ending at
its breaker, fire pump FWD discharge accounted against actual finite water,
and separate BE-01 N/S pressure and flow with actual one-fuse loss.

The first version of the pure tests caught and corrected a serious
attribution error: a single active fire pump's discharge was mistakenly
also credited to the *inactive* partner. The fixed source credits **only
the actual lone active source**. A separate false expectation that both
water trains always work equally was replaced by the real A-preferred
scheduler: B is correctly idle while A carries demand and begins producing
measurable flow when A is isolated.

The larger 14-job G19 instrumentation and subsystem regression matrix
runs separately, and its acceptance is not implied by this focused result.

