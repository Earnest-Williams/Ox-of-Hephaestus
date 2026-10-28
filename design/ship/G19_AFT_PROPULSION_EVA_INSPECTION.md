# G19: original aft propulsion nozzle EVA inspection

**Scope:** Draft G19, no synthetic nozzle or manufactured extra repair gear.

The installed v0.5 ship already contains the exterior service workface EXT-PROP-AFT, its EXT-AFT exterior rail and the original ACC-EXT-AFT-EXT-PROP-AFT 120-second EVA platform. The internal PROP-SVC room remains pressure-unknown. It is NOT made habitable by this extension.

The world operator must explicitly commission the fitted workface via commission_g19_propulsion_exterior(operator_approved=True). A later survey_g19_propulsion_exhaust(operator_approved=True, temperature_k=..., plume_clear=True) records a positive plume clearance, finite measured nozzle skin temperature, and an unchanged lifetime propellant/FTL fuel-consumption signature. Unmeasured, hot, stale-after-firing or negative clearance does not permit entry.

**Local work order:** A qualified engineer at the original PROP-CTRL station must command both drive MAIN inhibit and drive RCS inhibit. The vessel must be coasting, holding attitude, without a live FTL leg, significant angular speed or excessive residual drive heat. The original LP-PROP-CTRL, LCS-PROP and EVA-WORK-PLATFORM hardware must be sound. Then the worker issues:
- oxplant <request32> propulsion_service EXT-PROP-AFT secure
- oxplant <request32> eva ACC-EXT-AFT-EXT-PROP-AFT deploy (from the real EXT-AFT rail)
- Traverse the original forward EVA passage, timed 120 seconds
- oxplant <request32> propulsion_service EXT-PROP-AFT inspect (from the actual workface in a genuinely issued oxygen suit)
- Traverse the original reverse EVA passage back to EXT-AFT
- oxplant <request32> propulsion_service EXT-PROP-AFT release (back at PROP-CTRL, once no workers or timed suits remain on the face)

The permit is global, durable, owner-specific, and replay-safe. It inhibits main thrust, attitude thrust, MAIN/RCS re-arm, and FTL engagement without preventing emergency coast, hold or inhibit. A failed propulsion panel, changed propellant/FTL signature, renewed heat or loss of clearance pauses inbound EVA transit. The return trip remains possible through the real original EVA link, even after hazardous work conditions reappear. A live crew body on the face or an in-progress transit blocks permit release; decorative exit objects do not count as workers.

No new spacecraft interior, breathable vacuum, spare parts, thrust model, engine nozzle or production fabrication tolerances were added. This station is an inspected hazard-exclusion interface only. Detailed engine component repair awaits a named, physically fitted service item in a later build.

Dedicated CI: .github/workflows/ox-g19-propulsion-exterior.yml runs pure physical contracts and four installed Evennia scenarios. No 40-crew voyage.


## Additional main-drive measured-output witness (28 October 2026)

At the original staffed `PROP-CTRL` console an authorised crew member may now open a signed main-drive proof with `oxplant <request32> drive MAIN prove_start`. This captures the original authoritative game time, accumulated spent propellant and inertial velocity while the drive is healthy, released and coasting. The ordinary helm operator then commands an actual finite drive burn and returns to coast. The same witness must attend `PROP-CTRL` again and issue `oxplant <request32> drive MAIN prove_verify`. The verifier demands new elapsed physics time (within one hour), strictly positive new original propellant expenditure, a measurable three-dimensional inertial delta-v, a non-firing coasting drive and healthy physical original LCS-PROP / LP-PROP-CTRL controllers. Fuel-only changes, coasting drift, altered velocities without spent propellant, RCS-only action, active firing, second verification of one receipt and an unrelated witness do not pass. No propulsion test command generates a burn or extra impulse by itself. `oxplantread drive_proof` displays the locally attended witness history. The state survives restart in the original physics clock, and the existing global work receipt gives deterministic command replay.

Focused unit regressions are in `test_ship_propulsion_proof.py` and the existing aft nozzle workflow includes them; latest same-head CI is needed before this slice is accepted. This is operational testing of the actual fictional main drive, **not** independently serviced hot thrust hardware. The unsurveyed original interior `PROP-SVC` machinery compartment still requires a rated access/repair procedure.
