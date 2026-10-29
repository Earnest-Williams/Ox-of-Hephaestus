# G19 — full original equipment-family closure audit

**Audit baseline:** 29 October 2026
**Reference:** original fitted v0.5 ship, 808 hardware identities in 91 families
**Branch:** `g19-complete-ship-systems` / integration PR #138

## Four different kinds of evidence, not one misleading completion percentage

The strict audit refuses any added, duplicated, moved or unreviewed original
piece of equipment. The 808 original Evennia equipment rows are compared
against their immutable IDs, exact families and actual installed rooms.
An unreviewed new family cannot silently pass as a generic machine.

| Evidence/disposition | Fitted hardware | Families | Interpretation |
| --- | ---: | ---: | --- |
| Direct physics and output/control paths | **339** | 32 | Mapped to individual source/plant/process/telemetry logic, including 40 separately valved cabin fan-coils and the two finite surveyed rescue LSS units. A live contract is not a guarantee of every failure mode. |
| Interface or material custody | **159** | 26 | Connector, pressure boundary, passive storage, mounting or bulk infrastructure generally exercised through the owning access/cargo/rotor/water subsystem rather than a second invented machine. |
| Condition/interlock and supply hardware | **306** | 31 | Original equipment whose existence, condition, feeder, valve or receipt can affect the enclosing operation. Individual positive output is not claimed without a dedicated test. |
| Outstanding independent interactions | **4** | 2 | Real original portable or exterior machinery still requiring independently proved deployment, power/media/traction, sustained output and recovery. |
| **As-fitted total** | **808** | **91** | Complete identity and location inventory; no fictional additions. |

The category names are deliberately **evidence tiers**, not an assertion
that 790 units are fully functional or that every interlock is signed off.

## Installed and pure acceptance

- Forty residential fan-coil terminals in **HAB-01, HAB-03, HAB-05 and HAB-07** now have original independent live power and LT coolant eligibility, physical cabin-local commands, timed positive sensible-heat output and explicit shared LT radiator budget. All three jobs passed in [CI #40894829437](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40894829437).
- Full 808/91 inventory identity, room placement and fail-closed unknown family review passed both pure and installed jobs in [CI #40895961792](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40895961792).
- Both original rescue-craft independent air packages now have a finite as-found survey of cartridge CO2 capacity and onboard operating time, sealed-hatch restrictions, room-local crew controls, measured retained CO2 and no invented breathing oxygen. The original craft rooms retain their pressure cells. Dedicated workflow: `.github/workflows/ox-g19-survival-air.yml`; acceptance must be recorded from its completed runtime results before final subsystem signoff.

## Outstanding four original fitted mobile units

| Original equipment ID | Family | As-installed space |
| --- | --- | --- |
| `EVA-CRAWLER-1` | `eva_rail_crawler` | `EVA-FWD` |
| `EVA-CRAWLER-2` | `eva_rail_crawler` | `EVA-AFT` |
| `DRUM-INSPECT-ROBOT-1` | `inspection_robot` | `EVA-FWD` |
| `DRUM-INSPECT-ROBOT-2` | `inspection_robot` | `EVA-AFT` |

Four original crawlers/robots remain open for their own completed
installed-world acceptance. The other **14 portable machines** have now passed
the original finite-output and real crew/source-control test gates:
[portable pumps/fans #40916094333](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40916094333)
and [portable CO2 #40916246389](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40916246389).
Their three fitted families are classified as direct physics, bringing the
audited source-control tier from 325 to 339 original equipment identities.

The four remaining crawler/robot machines have newly committed separate
timed autonomous rail and remote drum-inspection logic; they stay open until
the corrected, as-built installed-world CI is green. The original rail
stations and *separate*, normally-closed 180-second drum skin platforms must
not be conflated. The robot inspects from the fixed rail.

## Integration and signoff policy

An individual powered unit is not credited with positive output just because
an upstream board or room panel is energised. Machine measurements must be
causally linked to physically delivered heat removal, fluid movement, air
processing, or crew/product movement. Data is owned by the original Evennia
world clock and durable apparatus records; repairing a fault must not
implicitly restart an isolated machine.

The machine inventory audit is a **coverage instrument**, not a new ship or
parallel simulation. It should be rerun after each outstanding family is
implemented, with the disposition of each unit changed only after relevant
installed-world acceptance and recovery regressions pass.
