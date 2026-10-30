# G19 — all six original exterior radiator service pads

G19 extends the accepted EVA / finite-oxygen / local repair machinery to the
**six existing external wing platforms**. No new room, pressure cell, corridor,
radiator or coolant isolation valve is fabricated. In the v0.5 ship, the four
LT wings remain owned by the original \`ROTARY-UTIL-A/B\` machinery rooms and
the two HT wings by the unclassified-atmosphere \`THERM-HT\` room. Each actual
accessible repair face is \`EXT-RAD-LT-1..4\` or \`EXT-RAD-HT-1..2\`, connected
by the original rated 150-second \`eva_work_platform_transfer\` hatch.

## Thermal and moving worksite gates

An operator first commissions \`commission_g19_exterior_radiators\` after
fitted EVA and shared maintenance, then positively attests each wing's
measured surface temperature using \`survey_g19_radiator_skin\`. An UNKNOWN
wing has no invented reading. Hot surfaces reject entry until below
315.15 K (42°C). Once sampled, thermal inertia is modelled as a bounded
1500-second response toward either the original in-service target or a
passive 235 K balance. The main cooling machinery remains the sole owner
of heat rejection; this subsystem only tracks worker surface exposure.

Each HT wing has its own **existing** \`ISO-RAD-HT-n\` coolant valve.
The original HT equipment room is not proven breathable, so its original
remote-operable valves are controlled from the **actual** \`ENG-CONTROL\`
panel (when healthy), not by pretending an engineer walked into unknown gas.

The four LT wings have **no individually fitted isolation valves**. Their
work sites therefore require shutting down the real \`LT-PLANT\` and closing
BOTH existing \`ISO-LT-ROT-A/B\` manifold valves. That is a consequential
whole-LT service shutdown, not fictitious selective wing isolation. At each
work face the ship must coast and hold attitude, no FTL or drive firing,
and the adjacent drums must be parked/braked/hardlocked without indexed
passengers or freight. Thermal permit admission checks these live states.

A qualified engineer at \`ROTARY-UTIL-A/B\` (LT) or the rated remote
\`ENG-CONTROL\` station (HT) may issue a globally receipted
\`radiator_service RAD-LT-1 secure\` or equivalent. These persistent exclusive
permits block reopening original coolant valves or restarting LT machinery.
A work platform may be deployed, entered and crossed **only after** a
physically issued EVA suit and a valid cooled, isolated, parked permit.
A hot/wrong-valve transfer is suspended on each ship tick and cannot
complete into a hazardous work face. Retreat to the exterior spine rail
remains possible even if the machinery becomes unsafe.

The ordinary shared \`repair equipment:RAD-HT-1 start\` may be initiated from
the correct exterior surface with the live permit, original finite personally
carried spare parts, one of the ship's six reusable toolkits and a genuine
sound issued EVA suit. Every work-tick rechecks site geometry, isolation,
crew presence, suit and thermal state. Completing a failed radiator installs
3 kg of carried spare parts over 600 attended seconds but does not invent
coolant, bypass thermal shutdown or automatically restart the wing. The
original permit remains held until its issuer releases it at the control
station, with no crew, transit or unfinished repair remaining at that
exterior pad.

This is game-world engineering and worksite operations, not a full radiator
CFD/contact model or spaceflight certification. It does not open unrelated
unknown-atmosphere generator rooms, propulsion plume worksite or other
unsurveyed exterior hazards. The 40-crew voyage is excluded.

**CI:** \`ox-g19-exterior-radiators.yml\` — pure thermal/valve/rotor/permit
gates plus seven installed-world Evennia cases, including both physically
walked LT and HT exterior routes.

**Accepted evidence (28 October 2026):** [CI run #40662087586](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40662087586), 17/17 pure and 7/7 installed Evennia cases at `58315d7c`. All six original pads, both coolant families, interrupted exterior movement and physical repairs are covered. PR #138 stays draft and unmerged.
