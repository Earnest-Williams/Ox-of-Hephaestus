# G19 finite HAB-04 medical care

This G19 construction adds a physically located pharmacy-to-treatment flow in the original HAB-04-MED-PHARM and HAB-04-MED-TREAT rooms. Operator-attested pharmacy stock defaults to zero and is capped at 24 dressings / 12 kg fluid within existing mission supplies. Qualified medical/environmental staff must pick up at the pharmacy, physically transport and deliver a kit at treatment. A real, individually registered injured patient and worker must attend the treatment room. Each 300-second course consumes one dressing and 0.5 kg fluid, reduces persistent injury by a bounded small amount, and pauses for absence, power outage or unsafe breathing air. Dead crew cannot be revived, hypoxia history is retained, and treatment does not add oxygen or voyage mass.

Commands: oxplant <id> medical kit pickup:2; oxplant <id> medical kit deliver; oxplant <id> medical care <patient_dbref>; oxplantread medical.

Commissioning: commission_g19_medical(operator_approved=True, dressings=4, fluid_kg=2). No automatic refill on repeated commissioning.

Dedicated two-job CI: ox-g19-medical.yml. This is bounded care, not full medical evacuation or the deferred 40-crew voyage.
