# G19 secondary machinery wear and service

## Operational reason

The Ox is an old, repeatedly refitted freighter. A breaker closing is not
a mechanical rebuild. The 26 fitted secondary cargo/environment,
cultivation and fabrication machines now accumulate **individual
service-hours since maintenance**, in addition to their existing
power/run/outage history.

The wear system works through the already installed, authoritatively
journalled shared ship clock, hardware condition rows and finite
spares/crew-equipment-repair operations.

## Machine service classes

| Family | Number | First inspection/deterioration interval | Faulted at |
| --- | ---: | ---: | ---: |
| Cargo heat exchangers and gas packs | 12 | 90 operating days | 112.5 operating days |
| Cultivation controllers/nutrient skids | 6 | 60 operating days | 75 operating days |
| Shop tools and welding cells | 8 | 30 operating days | 37.5 operating days |

These are fictional operational tuning values, not manufacturer
qualification. Only **measured powered runtime** advances fatigue.
Isolated motors, lost generators, a broken local fuse, stopped
commands and interrupted wiring stop adding wear, although environmental
process consequences continue.

## Persistent history and restored machinery

- `equipment_wear.units[ID]` tracks assessed elapsed wear, the source
  machine's own runtime reading, stage, originally observed repair stamp
  and prior wear-failure count. The `last` meter records local maintenance
  warnings and newly detected faults.
- A previously operating machine crossing its calibrated interval becomes
  **degraded** in its original installed equipment row. Exceeding 125% of
  the interval latches **faulted**, stops local machinery and returns it
  to the existing supervised repair procedure.
- Real repairs use the existing crew-on-site toolkit, finite spare parts,
  safe isolation, bounded work time, and the recorded original
  `repair_completed_game_time` equipment timestamp. The subsequent
  physics tick recognises this newer physical repair, retires the worn
  component's accumulated wear and advances normal service from its
  original monotonic runtime count. Merely toggling a breaker, changing
  physical condition or replaying a request never reduces wear.
- Upgrading a previously active ship copies the original runtime into
  the new wear meter and imports any **pre-existing** repair receipt.
  Earlier service is not misread as additional new duty; an old repair
  stamp cannot erase a newly surveyed worn component.
- An operator may explicitly attest inherited fatigue once via
  `survey_g19_equipment_wear(operator_approved=True, unit_id=...,
  equivalent_hours=...)`, leaving all existing actual conditions
  unchanged. A local engineer reads the current stage, operating hours,
  assessed hours since service and original breaker's status through
  `oxplantread <equipment-id>`.

## Verification

Pure `world.tests.test_ship_equipment_wear` exercises old-runtime
migration, inherited repair stamps, independently failed machines,
outage-paused wear, progressive thresholds, failure latch, controlled
repair and nonphysical-value rejection.

Installed `test_inherited_cnc_wear_causes_actual_degradation_and_local_fault`
verifies the actual generator-to-SHOP-MECH electrical route, a correctly
attested near-expired mill, real persistent equipment condition
degradation, eventual fault and attended-crew restart inhibition.

The tests are part of the existing four-job electrical/ECLSS/cargo
compatibility workflow. The ship's retained core machine repair contract
is documented in the G19 repair and waste/offload design materials.
