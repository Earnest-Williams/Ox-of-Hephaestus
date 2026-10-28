# G19 finite HAB-04 medical care

This G19 construction adds a physically located pharmacy-to-treatment flow in the original HAB-04-MED-PHARM and HAB-04-MED-TREAT rooms. Operator-attested pharmacy stock defaults to zero and is capped at 24 dressings / 12 kg fluid within existing mission supplies. Qualified medical/environmental staff must pick up at the pharmacy, physically transport and deliver a kit at treatment. A real, individually registered injured patient and worker must attend the treatment room. Each 300-second course consumes one dressing and 0.5 kg fluid, reduces persistent injury by a bounded small amount, and pauses for absence, power outage or unsafe breathing air. Dead crew cannot be revived, hypoxia history is retained, and treatment does not add oxygen or voyage mass.

Commands: oxplant <id> medical kit pickup:2; oxplant <id> medical kit deliver; oxplant <id> medical care <patient_dbref>; oxplantread medical.

Commissioning: commission_g19_medical(operator_approved=True, dressings=4, fluid_kg=2). No automatic refill on repeated commissioning.

Dedicated two-job CI: ox-g19-medical.yml. This is bounded care, not full medical evacuation or the deferred 40-crew voyage.


## Follow-on — attended 2-hour observation and clinical recovery (28 October)

The original HAB-04 treatment room now supports **two concurrent** attended convalescence courses after or independently of finite initial stabilisation. An individual medical officer physically co-located with a living, registered injured patient initiates `oxplant <id> medical observe <patient_dbref>`. Each new course consumes one additional real dressing and 0.5 kg of fluid already transferred from the separately located pharmacy. The observer is reserved for that patient and cannot work another case simultaneously. A 7,200-second course runs on the same bounded world clock, with modest injury reduction of 0.000003 per elapsed second, **only** while the caregiver and patient both remain physically present and the actual clinic electrical feeder, local panel and pressure cell are safe. The course pauses, rather than finishing automatically, during outage, unsafe air, personnel absence or incapacitation. Injury is persisted into the actual individual `crew_health` row throughout the course; historical hypoxia, smoke/CO2/temperature exposure and water deficits are never reset by treatment. Dead patients cannot recover.

A medical worker can issue `oxplant <id> medical discharge <patient_dbref>` to terminate their own ongoing observation without refunding consumed kit supplies. `oxplantread medical` displays the local observation ledger and completion count. All actions use the existing globally deduplicated signed work receipts. Existing medical ledgers migrate during the next accepted physics tick without replacing their old stock/case state.

**Acceptance boundary:** pure and installed tests added for initial provisioning, physical attendance, outages, persisted injury, overlapping staff lockouts and discharge; the new commit still requires its same-head medical and compatibility workflow passes before this follow-on may be called accepted. This remains gameplay medical recovery, not a diagnosis/procedure system or an all-crew voyage acceptance.
