# G19 — sixteen original industrial galleries and bearing-service rooms

PR #138 is a draft integration branch. All work describes a functioning fictional freighter, not flight-rated spacecraft.

The as-fitted v0.5 model contains four aft high-energy machinery galleries (THERM-HT, FTL-SVC, FUEL-SVC and REACTION-SVC) and twelve independent BE-01..12 service rooms, paired across six cargo drums. Existing rated doors connect these sixteen distinct rooms to real PZ-* crew trunks. There are no new compartments, airlocks, inventory accounts or free gas.

Each site receives an independent first positive survey of its original free volume, pressure, O2, CO2, smoke and temperature. That one-time survey discovers previously uncounted sealed gas. Any later measurement must reconcile with retained charge, genuine prior leak and finite trunk bleed. A metered manual rated-hatch transfer of at most 20 kg can ONLY flow from a higher-pressure safe crew trunk to a lower-pressure clean isolated industrial bay; it never vents contaminated room gas into the crew trunk. Ordinary personnel entry requires a pressure difference no greater than 2 kPa.

The same genuine Evennia character must hold a fresh issued EVA suit (finite oxygen), possess an exclusive individual maintenance permit and physically traverse the original rated exit. It does not suffice to mark a boolean 'suited'. Station geometry and the existing panel are checked on commissioning. The original panel breaker is inside the room and thus is not impossibly demanded open before personnel entry; actual machinery safing uses the original HT valves, FTL idle state, inhibited main/RCS or physically braked/indexed cargo drum.

Isolation remains effective during work. Normal FTL engagement, main-drive release, unsafe radiator valve reopening, affected drum restart and cargo movement are prevented while the corresponding site is occupied or hazardous. Damage to an industrial fuel/FTL enclosure aborts an engaged FTL leg. Reaction-mass or HT damage inhibits propulsion and leaves it needing attended restart. Bearing shell damage orders the respective moving cargo drum to coast down without instantaneous braking.

Surveyed physical leaks draw species from the original isolated room and add the exact quantity to the authoritative lost-to-space ledger. A worker ALREADY inside may repair a small continuing leak of at most 0.05 kg/s using the fitted toolkit and 2 kg of genuinely carried INV-SPARES. The work requires 180 seconds of live attended service, a shut rated hatch, live suit oxygen and unchanged machinery safing; only upon completed work is the leak stopped and the 2 kg booked as physically installed material. Leaked atmosphere never returns through a repair reset. Major leaks and incompatible gas remain isolated pending an actual exterior rescue or repair route.

Verification is organized under .github/workflows/ox-g19-industrial.yml: pure gas/material/permit tests, installed Evennia passage and finite-spares leak restoration, and generator/propulsion compatibility. Whole-ship G19 acceptance remains separate; the user-excluded 40-crew voyage is not run.

The remaining unclassified geometry includes 48 manifest-dependent cargo sectors, 12 cargo portals and 3 original shield/trim rooms; these have independent environmental rules, not generic industrial permits.
