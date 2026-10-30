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
| Direct physics and output/control paths | **349** | 37 | Mapped to individual source/plant/process/telemetry logic, including 40 separately valved cabin fan-coils, the two finite surveyed rescue LSS units, and the refill banks, regulators and rotary unions ([casualty repressurisation](G19_ATMOSPHERE_REFILL.md)). A live contract is not a guarantee of every failure mode. |
| Interface or material custody | **159** | 26 | Connector, pressure boundary, passive storage, mounting or bulk infrastructure generally exercised through the owning access/cargo/rotor/water subsystem rather than a second invented machine. |
| Condition/interlock and supply hardware | **300** | 28 | Original equipment whose existence, condition, feeder, valve or receipt can affect the enclosing operation. Individual positive output is not claimed without a dedicated test. |
| Outstanding independent interactions | **0** | 0 | Real original portable or exterior machinery still requiring independently proved deployment, power/media/traction, sustained output and recovery. |
| **As-fitted total** | **808** | **91** | Complete identity and location inventory; no fictional additions. |

The category names are deliberately **evidence tiers**, not an assertion
that 790 units are fully functional or that every interlock is signed off.

## Installed and pure acceptance

- Forty residential fan-coil terminals in **HAB-01, HAB-03, HAB-05 and HAB-07** now have original independent live power and LT coolant eligibility, physical cabin-local commands, timed positive sensible-heat output and explicit shared LT radiator budget. All three jobs passed in [CI #40894829437](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40894829437).
- Full 808/91 inventory identity, room placement and fail-closed unknown family review passed both pure and installed jobs in [CI #40895961792](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40895961792).
- Both original rescue-craft independent air packages now have a finite as-found survey of cartridge CO2 capacity and onboard operating time, sealed-hatch restrictions, room-local crew controls, measured retained CO2 and no invented breathing oxygen. The original craft rooms retain their pressure cells. Dedicated workflow: `.github/workflows/ox-g19-survival-air.yml`; acceptance must be recorded from its completed runtime results before final subsystem signoff.

## Closure: zero outstanding original hardware identities

**808 original devices across 91 families have been explicitly classified.**
All original family identities and installed-room mappings remain unchanged;
none have been substituted, duplicated or silently hidden.

Fourteen original portable scrubbers, pumps and smoke-control fans passed
their dedicated pure and installed-world gates:

- [Pumps/fans — #40916094333](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40916094333)
- [Portable CO2 — #40916246389](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40916246389)

The last **four** original exterior machines, two EVA crawlers and two
drum-inspection robots, passed both focused pure and *installed Evennia*
checks at [CI #40924922323](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40924922323)
(commit `2ebab10d`). The real forward and aft recovered-gas
airlocks, individually verified electrical feeders, rated fixed-rail
sections, six separately restricted drum-skin work platforms, finite
motor batteries, physical crew occupancy, inspection measurements and
fault recovery were exercised.

This promotes the two corresponding families from `open_interaction`
to `direct_physics`. The strict audit then had **343** direct-physics
units, **159** interface/custody units, **306** interlocked/controlled
units, and **0** outstanding independent interaction identities.
This is *family coverage closure*, not blanket proof that every one
of 808 devices has separately demonstrated positive output under every
conceivable failure sequence.

The dedicated inventory evidence job now enforces the zero-open audit
and original crawler/robot roster; CI for the revised classification
must pass before its updated signoff is final.

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

## Casualty repressurisation promotion (30 October 2026)

The two refill banks, two regulators and two rotary unions now meter finite bank
air into pressure cells under the installed physics clock, with exact inventory
debit and route, seal and equipment checks every step. Their three families move
from `controlled_hardware` to `direct_physics`. The strict audit now has **349**
direct-physics units in 37 families, **159** interface/custody units in 26, **300**
controlled units in 28, and 0 open. See [casualty repressurisation](G19_ATMOSPHERE_REFILL.md).
