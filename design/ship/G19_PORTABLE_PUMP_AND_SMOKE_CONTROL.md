# G19 — ten original portable emergency pumps and smoke-control fans

**Integration branch:** \`g19-complete-ship-systems\` · **PR #138** (draft).

This is original fitted equipment, not a new \`damage-control machine\` family.
It creates no rooms, network nodes, pressure cells, shipboard inventory or
instant repair powers. Original equipment rows remain physically registered
at their as-installed stowage rooms; the separately persisted custody ledger
tracks where each particular unit is carried or deployed.

## Original machinery

- Four \`DC-PUMP-01..04\` at TRUNK-A-BOW, ENG-LOCKER, F2-BAY and
  TRUNK-B-AFT.
- Six \`DC-SMOKE-FAN-01..06\` at TRUNK-A-BOW, BE-05-SVC,
  ENG-LOCKER, F2-BAY, BE-11-SVC and TRUNK-B-AFT.

## Operator and crew procedure

The operator commissions \`commission_g19_portable_damage\` one time, then
attests each device's actually existing finite battery runtime; each smoke
fan additionally requires a positive as-found installed filter capacity.
Repeat surveying is refused, and no default battery charging or filter
replenishment is presumed.

The authenticated local Evennia command is:

\`oxplant <32hex> portable_damage <DEVICE> take|place|on|off\`

A portable pump must be carried to the actual **WASTE-PROC-A/B** machine's
fitted room, deployed, connected by \`route:A:grey\`, \`route:A:black\`,
\`route:B:grey\` or \`route:B:black\`, then turned on. These attach to
the **actual original source and discharge wet circuit**, not to an invented
hose across arbitrary rooms. When the original correct A/B rotary isolation
is positively open, liquid travels at up to 0.25 kg/s from that side's
finite local grey/black buffer to the existing fixed receiver. Original
local/fixed capacities bound output. Closed, damaged or wrong-side valves
leave output at zero; a good *other* side cannot serve as a bypass. The
original water and waste system maintains the actual finite source and
receiver registers. No free fire-main supply or compartment dewatering
beyond these existing authored wet holdings is asserted.

A smoke fan can be placed in a normally mapped pressure-cell compartment
and run as a local recirculating filtered fan. Delivered airflow is metered
in m3 and independently retained smoke in kg. The fan never opens a
nonexistent duct, draws from the vacuum, refills oxygen, or destroys smoke.
Effective capture is bounded by source smoke concentration, circulated air
volume, 0.002 kg/s capture envelope, and individually retained finite
as-found filter capacity. Smoke capture removes exactly the same mass and
thermal energy from the actual ship gas inventory; the filter is onboard
custody. A fan can still circulate air while the original cell is free of
smoke, consuming its own surveyed finite battery runtime.

Every active unit uses the existing replay-safe ten-second world clock.
A genuine original equipment failure latches the device off, requiring
crew restart after physical repair. Missing routes, depleted batteries,
exhausted filters and missing actual pressure-cell chemistry fail closed.
The unit may be lifted only when stopped; a carrier may not possess two
portable units in this family simultaneously. The identical actor must
physically arrive at the destination to deploy it, using the pre-existing
rated exits and their crew-transit gates.

Crew status:

\`oxplantread portable_damage:<DEVICE>\`

shows the individual actual room/carrier, original home, condition,
remaining power and filters, route, per-step output and cumulative meters.

## Evidence and remaining work

\`.github/workflows/ox-g19-portable-damage.yml\` is the new two-job gate
for pure conservation/custody/failure and installed Evennia crew/gas/rotary
wet-route acceptance. The implementation and tests are committed.
**Subsystem acceptance requires both jobs green at the same code head.**

The equipment-family closure audit must continue to report those original
units as outstanding until the relevant CI is accepted. The four original
portable CO2 scrubbers and the four independent EVA crawler/inspection
robots have different operating contracts and their acceptance is separate.

**Scope:** playable, bounded physical ship operations, not engineering
qualification of a real spacecraft.
