# The lead mind's core

Where the lead mind's nine machines are, what each depends on, how parity and
capacity work, and which subsystems can take over when it hands control away.

**Decided:** nine machines distributed through the ship, two acting as parity;
the lead mind goes down only if it loses three in quick succession; it can turn
working machines into parity at the cost of capacity; it can hand systems to
subsystems capable of running them; every machine room has monitored,
controlled access.

**Accepted (New), 3 November 2026:** the placement, parity and capacity
model and handover table below. Exact numbers — rebuild time, capacity steps —
are starting values to be settled in playtesting. The original v0.5 design has no
computing equipment or machine rooms. Draft PR #151 adds separately
commissioned machine hardware and support overlays rather than rewriting
the original ship model.

## Placement rule

The lead mind dies if three machines are lost close together, so **no single
fault should be able to take out three at once**:

- **No more than two machines per region** of the ship, so cutting the backbone
  between regions can isolate at most two.
- **No two machines on the same final distribution board.** Today bow and
  aft room panels hang off board B (`DB-B-BOW`, `DB-B-AFT`); the new machine
  feeders must not inherit those common room-panel failure points.
- **No single distribution fault may remove more than two machines.**
  Separate outgoing cables alone do not suffice when they still traverse
  the same bus, isolation switch, converter or reserve. The existing
  `PWR-PROT` protected bus is one such common failure point.
- **No more than two machines sharing a cooling path.**
- **Two backbone routes everywhere**, one along each personnel trunk (A and B),
  so a single cut never isolates a region.

## Proposed placement

| # | Room | Region | Ship position | Room's current panel feed | Why |
|---|---|---|---|---|---|
| 1 | `COMMS-FWD` | Bow | 50–60 m | `DB-B-BOW` | Beside forward communications |
| 2 | `ENV-FWD` | Bow | 77–88 m | `DB-B-BOW` | Engineering access, low traffic |
| 3 | `XCON-GAP-23` | Forward spine | 254–257 m | none | Between drums 2 and 3; needs a new feeder |
| 4 | `HUB-MAINT-BAY` | Hub | 430–440 m | `DB-A-HAB-HUB-SERVICES` | Engineering access, beside engineering control |
| 5 | `SHOP-ELEC` | Hub | 480–493 m | `DB-A-HAB-HUB-SERVICES` | The electronics shop that maintains them |
| 6 | `HAB-04-ENV-SAT` | Habitat ring | rotating | `HAB-04-PDB-B` | Environmental satellite room in the ring |
| 7 | `HAB-07-SG1-CUPBOARD` | Habitat ring | rotating | Houses distribution board `HAB-07-SG1-DB` | Engineering-access service cupboard, opposite side of the ring |
| 8 | `ENV-AFT` | Aft | 820–832 m | `DB-B-AFT` | Engineering access |
| 9 | `COMMS-AFT` | Aft | 890–900 m | `DB-B-AFT` | Beside aft emergency communications |

Regions: bow 2, forward spine 1, hub 2, habitat ring 2, aft 2. Machine 3 sits
in a cross-connection between the two trunks, so its room is a through route;
making it controlled-access closes a short cut between trunks A and B. An
alternative is to leave the forward spine empty and accept three machines in the
hub, where backbone routes are most redundant.

**Power supply design (New in the original model; PR #151 draft implementation):** the nine machines require at
least five separately isolated, locally buffered power islands, with at
most two machines assigned to any one island. A candidate arrangement is
islands for machines **1-2 (bow)**, **3 (forward spine)**, **4-5 (hub)**,
**6-7 (habitat)** and **8-9 (aft)**. The table above shows the rooms'
*existing panel feeds*, not approved routes for the lead mind. The
protected `PWR-PROT` bus and `BAT-COMMON-PROT` battery cannot be the sole
upstream supply or common reserve for these islands.

**Each machine gets (New):**

- a dedicated final feeder and breaker from its assigned isolated island,
  with no shared final distribution board with another machine;
- genuinely diverse A/B supply paths into the island (with safe transfer)
  and **island-local** energy storage sufficient to bridge the designed
  failure/reconfiguration interval. Neither feed may depend on a failed
  shared `PWR-PROT` node; an A/B selector *downstream* of that bus gives no
  redundancy against its failure. Any required independent switchgear,
  feeders and reserves must be added to the ship data, not assumed fitted;
- cooling from its room's air handling, with its own over-temperature
  shutdown;
- two backbone links, one to each trunk route;
- a monitored, controlled-access door that records who entered.

## Power fault-domain acceptance

**New acceptance criterion, before core implementation:** map each
machine's actual node/edge/isolator path, selected source and local
reserve. Run a single-fault sweep of power buses, feeders, switches,
converters and shared energy stores (including a sustained `PWR-PROT`
fault). After permitted transfer and within the specified island reserve
autonomy, each single fault must leave **at least seven of nine machines**
powered and connected; otherwise the proposed layout violates the
two-machine fault-domain rule. Specify and test reserve duration and
recovery behaviour; a ship-wide loss of all generating and stored energy
cannot be solved by a finite ride-through battery. This is a design
requirement, **not** an assertion that the existing power graph passes.

## Parity and capacity

**Proposed numbers, for tuning:**

| | Proposal |
|---|---|
| Rebuild time | Restoring parity after a loss takes **15 minutes** of game time per machine. |
| "Quick succession" | A third loss before the rebuild of the first two finishes. |
| Thinking machines | Working machines minus parity machines; 7 at full strength. |

| Thinking machines | Effect |
|---|---|
| 7 | Full capacity: every reachable system, all records, forecasts and plans. |
| 6 | Slower forecasts and planning; nothing handed over. |
| 5 | Hands routine, self-contained systems to capable subsystems. |
| 4 | Hands most systems over; keeps safety, communications, records and coordination. |
| 3 or fewer | Survival mode: keeps records and communications; everything else is handed over or left to local control. |

The lead mind chooses how many machines to hold as parity. More parity makes it
harder to kill and slower to think.

## Who can take over

**Proposed**, using subsystems that already exist in the data or are planned:

| System | Takes over | What it can do alone | What is lost |
|---|---|---|---|
| Power | Generator and distribution controllers (`LCS-GEN-*`, `LCS-PWR-AFT`) | Hold the current schedule; trip on faults | Dispatch changes, load shedding, storage planning |
| Air | The ECLSS trains' own controls; train B's gen-3 controls are the most capable | Hold oxygen and CO₂ targets in their own zones | Coordinating circulation between zones |
| Cooling | `LCS-LT`, `LCS-HT` | Run pumps and radiators; drive first | Planning the heat budget against burns and cargo |
| Cargo | Each drum's `LCS-DR-xx` and skid controller | Hold the last target; hold rotation | Pre-cooling, rebalancing, freight scheduling |
| Navigation | The navigation computer (specialist AI, decided) | Hold course; carry out an approved burn | Weighing burns against heat, cargo and crew |
| Fire | `LCS-FIRE-FWD`, `LCS-FIRE-AFT` | Run pumps and cross-ties | Coordinated isolation of utilities and ventilation |

Every handover and return is receipted (acceptance test S15). A subsystem runs
only what it is fitted to control.

## Records

Machine state, parity layout, rebuilds, handovers and returns, and every entry
to a machine room go into the [records](records.md): the access log, the
remote command log and a new **core log**.

## Open questions

1. **Resolved in the PR #151 candidate:** independent A/B taps at the
   existing gap-23 distribution boards feed a new local island. Machine 3
   occupies a monitored equipment rack within `XCON-GAP-23`; the two
   original cross-trunk doors remain public passages. The rack's own reader
   and the actual conductor penetrations still need commissioning.
   See [ADR 0011](../decisions/0011-ship-control-support-overlays.md).
2. Rebuild time and capacity steps: tune in playtesting.

## Support hardware design status, 10 November 2026

The draft [PR #151](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/151)
models two independent fibre rails along the original A/B personnel trunks,
with one separately attributed drop to each machine on each rail. Continuous
rotating HAB connectivity requires two **new** data couplers, independent of
the personnel indexers.

Each of the five electrical islands has a separate local thermal buffer and
heat rejector. Rated 2 kW/machine heat and 720 kJ/island finite nameplate
buffer give at least 120 seconds without assuming the original LT plant
remains available. Actual energy/temperature surveys are required, and the
buffer is not presumed charged at commissioning. The current implementation
does not provide machine parity, cognition, or network command authority.
