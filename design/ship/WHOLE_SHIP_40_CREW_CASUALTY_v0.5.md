# 40 distinct crew, whole-ship coupled casualty — v0.5 candidate

**Design-side operational exercise, 23 October 2026.** Governed by
[Ship Engineering Design Standard](SHIP_ENGINEERING_DESIGN_STANDARD.md):
the target is verisimilitude, coherent operations and playable consequences,
**not NASA approval or construction-ready spacecraft qualification**.

This test completes a bounded design-side 40-person exercise spanning
habitation, pressure bridges, command, stores, workshop and axial trunks.
It does **not** instantiate 40 authenticated Evennia agents, run 40
Concordia/Decider language-model brains, or install these sample injuries,
jobs, personalities or faults as canonical crew history.

## World source and individualized personnel

`whole_ship_crew_casualty_v05.py` extends the existing
`electrical_evacuation_v05.py` and its coupled smoke, thermal,
pressure and gas ledgers. It uses the immutable selected physical identifiers
from the **421-room / 517-access** ship candidate, **133 pressure cells /
339 pressure gates**, **438 power nodes / 450 power links**, and existing
ventilation, suppression, coolant and reserve networks.

The deterministic crew manifest has **40 different IDs and 40 different
authored starting rooms**:
The Ox's four residential arcs are interleaved with distinct galley,
medical, ECLSS and workshop service arcs; **HAB-02/04/06/08 do not
contain cabin numbers**. This exercise deliberately uses their actual
specialist spaces rather than fabricating crew cabins.


| Assignment | Individuals | Real starting rooms |
| --- | ---: | --- |
| Cabin occupants in residential arcs | 8 | CAB-01/CAB-02 of HAB-01, HAB-03, HAB-05 and HAB-07 |
| Specialist arc-duty crew | 8 | HAB-02 GALLEY/MESS; HAB-04 MED-TREAT/MED-OBS; HAB-06 ECLSS-A/WORKSHOP; HAB-08 ECLSS-B/GROW |
| Habitation sector watches | 8 | HAB-01..08 main corridors |
| Ring pressure/transfer technicians | 8 | BR-01..BR-08 physical pressure bridges |
| Command, engineering, stores and trunk posts | 8 | CMD-PRIMARY, CMD-EMERG, SHOP-MECH, SPARES-CENTRAL, TRUNK-A-BOW, TRUNK-A-DR-01, TRUNK-A-AFT, TRUNK-B-AFT |
| **Total** | **40** | **40 distinct authored rooms** |

Each slot retains its own ID, specialty, initial/final location,
individual local startup observation, later disposition or task orders,
gear ownership, and cumulative unsafe person-seconds. Physical room
occupancy and pressure-cell occupancy must *both* sum to forty at every
final check, with no phantom separate maintenance-worker population.

Crew are **individually tracked physical actors** in a deterministic
engineering exercise, **not** artificial general intelligences. Test
policies are deliberately authored rather than attributed to learned
personalities or autonomous decision-making.

## Common incident and imperfect knowledge

All compared runs start with the *same* selected 40-person manifest,
nominal measured-at-startup reference gas, available original utility
distribution and a normal shift in which the two **actual** BR-03
pressure hatches have been explicitly opened (not assumed open by the
baseline model). The shared incident is a real refit-era
**HAB-03 cabin 07 fan-coil electrical fire**. The coil is fed from
**SG2 corridor board**, not its apparent cabin panel; the B-distribution
source must actually be de-energized before water mist is permitted.

The installed HAB-03 fire detector is deliberately stuck silent. The
captain at CMD-PRIMARY receives that **false-silent reading**, not
private fire-object truth. An HAB-03 sector watch at its real corridor
position provides a competing local odor/visible-smoke observation
after a fixed detection threshold. The captain may receive that
report only while the real HAB-03 communications circuit, protected
power and command transport are available. Disabling that route stops
the report. No controller gets an omniscient fuel/oxygen/valve map.

The following selected **reference assumptions** are explicit:
28 kg initial combustible carbon-equivalent fuel; 0.07 kg/s nominal
burning; 30% tagged smoke yield; an incident horizon of 240 s;
two preassigned masks and two portable lights as finite allocations
from existing damage-control resources; 180 seconds nominal protective
mask endurance; and test-selected response/valve delays. These are
**not** surveyed ship performance, actual mask stocks/endurance, or
new permanent inventory/equipment objects. Preissued personal gear is
stated explicitly so it is not teleported from the service locker
during a smoky casualty.

## Competing courses of action

**Containment-first:** The bridge operator orders closure of both
rated BR-03 hatches; the captain queues real remote closures for both
HAB-03 ventilation-ring isolation dampers; the engineer at CMD-EMERG
isolates generator B, proving the refitted coil is no longer energized;
then compatible water mist may flow through the actual fire main using
finite existing water. The two HAB-03 cabin occupants remain in their
arc with finite-duration protective equipment: surrounding atmosphere
is protected sooner, but the two people stay exposed to local smoke
when protection is exhausted.

**Rescue-first:** The same hatches remain physically open while two
identified cabin occupants (CREW-007/CREW-008) move **one by one**
from separate real cabins through their corridor, vestibule,
BR-03 and the HAB-04 vestibule into HAB-04's real corridor. Each
access leg advances ship casualty time and is invalidated by changed
access or receiving atmosphere. A mask must also have **enough remaining
reference duration for the entire next leg**; entering a passage just
before its equipment expires does not count as a verified traversal. Each person carries one of the two
separately debited breathing/light allocations. Only *after* these
movements does the operator shut the hatches, isolate the ventilation
dampers and B electrical source, and admit mist. This can save
the two individuals while allowing more smoke and heat to spread
toward occupied HAB-04, and burning more fuel before suppression.

**Containment with a jam:** The HAB-03/BR-03 hatch is explicitly
jammed open; the close command fails and is recorded as such.
The independently functioning far BR-03/HAB-04 hatch may still
protect HAB-04 even while BR-03 itself becomes a worse exposure.
No one is credited with a positive pressure seal that never existed.

These are **counterfactual choices** for engineering testing, not a
claim that one is universally the 'correct' behavior in every fire.

## Physical execution and acceptance

Run `python design/ship/check_whole_ship_crew_casualty.py`.

The checker requires all three cases to share one 240-second
evaluation horizon and initial forty-person roster. It checks
different propagation/suppression outcomes, the actual two named
evacuations, pressure-door and ventilation-isolator receipts, scarce
gear, per-person risk, generator B isolation, finite suppressant water,
gas/fuel mass accounting, unique actor event authors, 40 tracked people
in 40 valid original starting spaces, individually recorded orders and
observations, and distinct outcomes under the jam fault.

It also rejects **ten intentional bad configurations or manipulations**:
unknown policy (two variants), false jam setting, nonexistent crew actor,
remote observation with disconnected command transport, false local
observation from a different room, manufactured crew movement,
expired breathing gear, passage through a closed rated hatch, and
a fabricated 41st physical crew member.

The common test never creates replacement gas, infinite mask supplies,
third-party medical rescues, vacuum-safe breathing masks or extra
physical rooms. If an entrance or escape path is actually closed,
its apparent topology alone is not enough to credit a crossing.

**Review interpretation:** This verifies that the established fictional
ship engineering can produce contrasting, concrete consequences for
40 distinct workers and passengers. It is *not* a new real-time
scheduler for forty world-authoritative Evennia actors. A subsequent
integration increment can feed these same physical IDs and bounded
failure consequences into individual crew GOAP/Decider/Concordia cognition
while letting Evennia remain the sole owner of movement, repairs,
equipment, timing, injuries, inventories and receipts.

## Verified result from the 23 October 2026 reference run

The [v0.5 ship-design integrity workflow](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39997482622)
passed the 40-person matched-policy suite at commit
[`029826f`](https://github.com/Earnest-Williams/Ox-of-Hephaestus/commit/029826f78dab48db818e365253f77316e5358e2f).
The other three focused workflows also passed. **40 separate people occupied
40 original authored rooms in 24 different nominal pressure cells**;
all received individual locally bounded startup evidence and shift
orders, with identity/location and total occupancy conserved to the
end. **Ten invalid cases were rejected.**

| 240-second metric | Containment-first | Rescue-first | Containment with HAB03 hatch jammed open |
| --- | ---: | ---: | ---: |
| Individually identified people moved into HAB-04 | 0 | 2 | 0 |
| Time suppression actually started | 23 s | 140 s | 23 s |
| Carbon-equivalent scenario fuel burned | 2.2176 kg | 10.0800 kg | 2.2176 kg |
| Smoke tracer in HAB-04 | 0.001818 kg | 0.097332 kg | 0.001819 kg |
| Smoke tracer in BR-03 | 0.000131 kg | 0.007483 kg | 0.004576 kg |
| Allocated firefighting water used | 130.2 kg | 60.0 kg | 130.2 kg |
| Total individual unsafe person-seconds | 357.0 | 1,576.5 | 576.0 |
| Individual and operational event records | 132 | 146 | 133 |

The tests passed exact manifest reconciliation, real passage-link receipts
for CREW-007 and CREW-008, fuel/water/material balances, finite mask/light
allocations, separately tested duct and pressure-hatch closures, actual
B-source de-energizing for a refitted fan-coil, and failure of the
jammed pressure seal. The 240-second endpoint is shared; the difference
in water spent results from different durations of suppression in that
fixed window, **not** new water creation or better liquid efficiency.

**Interpretation:** rescue-first protects two identifiable cabin occupants
by moving them, but waiting to seal the open pressure bridge and isolate
the electrical fault exposes HAB-04 to much more smoke, lengthens
combustion and increases person-time in unsafe atmospheres. A failed-open
first bridge hatch increases contamination/exposure in BR-03; the
independently functioning second hatch still protects HAB-04. These
are meaningful **fictional operational choices**. Unsafe person-seconds
are modeled exposure indicators, **not assigned injuries, deaths or
measured physiological dose**, and figures are neither NASA-certifiable
performance claims nor actual ship measurements.

## Deliberate next-stage refinements

The reference scenario still uses deterministic command policies and
a fixed detection threshold; it has not yet measured the stochastic
effects of individual experience, mixed priorities, limited communications,
multiple concurrent repair teams, exhausted apparatus or genuine
crew-task arbitration. Those belong in future *playable operations*
refinements, not in an aerospace-certification programme.
