# G19 original portable emergency CO2 scrubbers

**Slice:** four as-fitted `PORT-SCRUB-01..04`; PR #138 remains draft.

The original equipment records remain in their original fitted locations
(TRUNK-A-BOW, ENG-LOCKER, F2-BAY and TRUNK-B-AFT). Portable custody is a
separate authoritative ledger recording the present room or the sole carrier.
Crew must physically attend the unit to take/place it; carriage follows the
same authenticated Evennia actor who must use normal crew traversal.

## Operations

1. Commission `commission_g19_portable_air(operator_approved=True)`
   without resetting a previously enrolled ledger.
2. Record *once*, for each original unit, the finite as-found sorbent and
   remaining independent battery runtime with `survey_g19_portable_air`.
   No implicit fresh media or charging is inferred.
3. A crew member at the original stowage may issue receipted
   `oxplant <32hex> portable_air PORT-SCRUB-01 take`.
   The person must physically travel to the target room and issue
   `place`. A running unit cannot be taken.
4. At the deployed site, `on|off` operates the local machine.
   `oxplantread portable_air:PORT-SCRUB-01` reports its actual custody,
   condition, sorbent, battery and measured CO2 capture.
5. Every existing ten-second physics step requires a sound original unit,
   genuine mapped pressure-cell gas, enough pressure and positive finite
   battery/media. The sorbent retains exactly the CO2 removed from the
   existing atmosphere. Oxygen is unchanged; there is no free atmosphere,
   purge to vacuum, new power bus or fictional machine identity.

The four original items are still classified `open_interaction` in the
strict 808-piece audit until same-runtime pure and installed Evennia CI
succeeds. The operating slice intentionally does not simulate spent-cartridge
replacement, portable smoke fans, portable liquid pumps, exterior rail
crawlers or inspection robots. These are distinct original machines requiring
separate physical routing, custody, output and recovery tests.

## Acceptance

`.github/workflows/ox-g19-portable-air.yml` runs the pure finite
custody/gas tests and the installed Evennia original-room/crew/pressure tests.
The current slice is **committed, acceptance pending**, and must not be
reported as CI green without the actual matching workflow result.
