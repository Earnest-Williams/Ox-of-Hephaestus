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
are starting values to be settled in playtesting. The design data has no
computing equipment or machine rooms today.

## Placement rule

The lead mind dies if three machines are lost close together, so **no single
fault should be able to take out three at once**:

- **No more than two machines per region** of the ship, so cutting the backbone
  between regions can isolate at most two.
- **No two machines on the same power board.** Today every room panel in the
  bow and aft hangs off main board B (`DB-B-BOW`, `DB-B-AFT`), so the machines
  need their own feeds.
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

**Each machine gets (New):**

- its own feeder from the protected bus with A/B selection, and a short battery
  ride-through, so a board trip or a feeder changeover doesn't drop it;
- cooling from its room's air handling, with its own over-temperature
  shutdown;
- two backbone links, one to each trunk route;
- a monitored, controlled-access door that records who entered.

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

1. Where does the forward-spine machine's feeder come from, and does making
   `XCON-GAP-23` controlled-access cost the crew a useful short cut?
2. Rebuild time and capacity steps: tune in playtesting.
