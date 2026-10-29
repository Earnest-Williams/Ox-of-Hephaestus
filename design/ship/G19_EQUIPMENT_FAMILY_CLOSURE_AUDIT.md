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
| Direct physics and output/control paths | **325** | 29 | Mapped to individual source/plant/process/telemetry logic, including 40 separately valved cabin fan-coils and the two finite surveyed rescue LSS units. A live contract is not a guarantee of every failure mode. |
| Interface or material custody | **159** | 26 | Connector, pressure boundary, passive storage, mounting or bulk infrastructure generally exercised through the owning access/cargo/rotor/water subsystem rather than a second invented machine. |
| Condition/interlock and supply hardware | **306** | 31 | Original equipment whose existence, condition, feeder, valve or receipt can affect the enclosing operation. Individual positive output is not claimed without a dedicated test. |
| Outstanding independent interactions | **18** | 5 | Real original portable or exterior machinery still requiring independently proved deployment, power/media/traction, sustained output and recovery. |
| **As-fitted total** | **808** | **91** | Complete identity and location inventory; no fictional additions. |

The category names are deliberately **evidence tiers**, not an assertion
that 790 units are fully functional or that every interlock is signed off.

## Installed and pure acceptance

- Forty residential fan-coil terminals in **HAB-01, HAB-03, HAB-05 and HAB-07** now have original independent live power and LT coolant eligibility, physical cabin-local commands, timed positive sensible-heat output and explicit shared LT radiator budget. All three jobs passed in [CI #40894829437](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40894829437).
- Full 808/91 inventory identity, room placement and fail-closed unknown family review passed both pure and installed jobs in [CI #40895961792](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40895961792).
- Both original rescue-craft independent air packages now have a finite as-found survey of cartridge CO2 capacity and onboard operating time, sealed-hatch restrictions, room-local crew controls, measured retained CO2 and no invented breathing oxygen. The original craft rooms retain their pressure cells. Dedicated workflow: `.github/workflows/ox-g19-survival-air.yml`; acceptance must be recorded from its completed runtime results before final subsystem signoff.

## Outstanding eighteen original fitted items

| Original equipment ID | Family | As-installed space |
| --- | --- | --- |
| `DC-PUMP-01` | `portable_pump` | `TRUNK-A-BOW` |
| `DC-PUMP-02` | `portable_pump` | `ENG-LOCKER` |
| `DC-PUMP-03` | `portable_pump` | `F2-BAY` |
| `DC-PUMP-04` | `portable_pump` | `TRUNK-B-AFT` |
| `DC-SMOKE-FAN-01` | `portable_fan` | `TRUNK-A-BOW` |
| `DC-SMOKE-FAN-02` | `portable_fan` | `BE-05-SVC` |
| `DC-SMOKE-FAN-03` | `portable_fan` | `ENG-LOCKER` |
| `DC-SMOKE-FAN-04` | `portable_fan` | `F2-BAY` |
| `DC-SMOKE-FAN-05` | `portable_fan` | `BE-11-SVC` |
| `DC-SMOKE-FAN-06` | `portable_fan` | `TRUNK-B-AFT` |
| `PORT-SCRUB-01` | `portable_scrubber` | `TRUNK-A-BOW` |
| `PORT-SCRUB-02` | `portable_scrubber` | `ENG-LOCKER` |
| `PORT-SCRUB-03` | `portable_scrubber` | `F2-BAY` |
| `PORT-SCRUB-04` | `portable_scrubber` | `TRUNK-B-AFT` |
| `EVA-CRAWLER-1` | `eva_rail_crawler` | `EVA-FWD` |
| `EVA-CRAWLER-2` | `eva_rail_crawler` | `EVA-AFT` |
| `DRUM-INSPECT-ROBOT-1` | `inspection_robot` | `EVA-FWD` |
| `DRUM-INSPECT-ROBOT-2` | `inspection_robot` | `EVA-AFT` |

These are **actual fitted machines**, not missing hull geometry. The open
work items must preserve the same principles as the accepted installed systems:

- **Four portable pumps:** actual dewatering or fire-main flow from a
  physically present and compatible liquid inventory, with real delivery
  routing, local setup, finite operating power and retained effluent custody.
- **Six portable smoke-control fans and four portable scrubbers:** real carried
  location/crew access, valid source power or surveyed finite battery charge,
  independently attributable air movement, filter/sorbent exhaustion, and
  contamination disposal. Circulation must not silently destroy smoke/CO2;
  an open duct must not imply permissible vacuum purge.
- **Two EVA rail crawlers and two drum inspection robots:** authentic exterior
  rail/rotor restrictions, crew or robot custody, independent drive energy,
  remote survey evidence, bounded traversal and recovery. A remote visual
  scan must not claim to be a heavy structural repair.

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
