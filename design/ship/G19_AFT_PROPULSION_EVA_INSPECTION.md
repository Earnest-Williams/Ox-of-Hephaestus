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
