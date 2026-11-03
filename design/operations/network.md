# The plant-control network

How the lead mind reaches the ship: one backbone, segments behind gateways,
and the local control that survives when any of it fails.

## The four questions

Every action the lead mind takes must clear four separate questions:

| Question | Asks | Changed by |
|---|---|---|
| **Perception** | What measured it, what does it cover, how fresh is it? | Fitting, repairing or calibrating instruments. |
| **Connectivity** | Is it reachable: backbone, gateway, local panel only, intermittent, or not at all? | Fitting, powering, repairing or isolating links and gateways. |
| **Interpretation** | Does the lead mind know what the device's words and units mean? | Learning and verifying a device's vocabulary; updating a gateway's mapping. |
| **Authority** | Is the lead mind allowed to do this, and does it need a person, a reset or an interlock cleared? | Standing agreements with the captain and crew, recorded in world state. |

## What exists today

**Runtime.** The installed game has no plant-control network.

- 116 local panels each read only their own room, when powered and intact.
- The only ship-wide link is the protected fire and pressure relay: alarms
  from the eight habitat sections reach `ENG-CONTROL`, `CMD-PRIMARY` and
  `CMD-EMERG`, through each section's fire detector and comms node.
- Two remote switch paths are hard-wired: `ISO-GAS-BANK-A` from `WATER-FWD`,
  and `ISO-RAD-HT-1`/`-2` from `ENG-CONTROL`. Every other valve or breaker is
  operated by someone standing in its room.

**Data.** The design data describes much more:

- An "original plant-control network", named in the generator B refit
  (`MOD-GEN-B`: "uses a gateway to the original plant-control network").
- 559 of 1,092 isolation points flagged `remote_operable`.
- 33 local control stations, each built for local takeover, a hard-wired
  emergency trip and safe functions that don't depend on the network. The
  local-control contract says "local takeover is logged".
- Equipment from five eras: original build, life-extension refits,
  accommodation and cultivation refits, accumulated repairs, and the current
  fit. 235 of 692 equipment rows are not original.

## The backbone and its segments

**New.** One ship-wide backbone carries traffic between the lead mind's core
and every segment. Each segment is a group of machinery behind one gateway.
The 33 local control stations already define most segments (**Data**); the
habitat and command segments are proposed.

| Segment group | Gateway host | Covers | Source |
|---|---|---|---|
| Cargo drums ×6 | `LCS-DR-01` … `LCS-DR-06` | Drum rotation, locks, service interfaces, cargo machinery | Data |
| Bearings ×12 | `LCS-BE-01` … `LCS-BE-12` | Lubrication, cooling, rescue skids, bearing observations | Data |
| Energy storage ×2 | `LCS-F1`, `LCS-F2` | Flywheel modules, isolation, cooling, converters | Data |
| Generation ×3 | `LCS-GEN-M`, `LCS-GEN-A`, `LCS-GEN-B` | One generator each | Data |
| Aft distribution | `LCS-PWR-AFT` | Aft distribution, generator ties, protected buses | Data |
| Cooling ×2 | `LCS-HT`, `LCS-LT` | HT and LT pumps, radiator branches, major interfaces | Data |
| Atmosphere ×2 | `LCS-ECLSS-A`, `LCS-ECLSS-B` | The two ECLSS processing trains | Data |
| Workshop rotor | `LCS-WR` | WR-01 bearings, drives, extension, indexing, balance | Data |
| Propulsion | `LCS-PROP` | Sublight safing, feed, service state | Data |
| FTL | `LCS-FTL` | FTL field machinery safing and readiness | Data |
| Fire main ×2 | `LCS-FIRE-FWD`, `LCS-FIRE-AFT` | Fire pumps and cross-connects | Data |
| Habitat sections ×8 | `HAB-01-COMMS-NODE` … `HAB-08-COMMS-NODE` | Cabins, cabin panels, local services in each section | New (hosts are Data) |
| Command | Command and engineering rooms | Bridge, engineering control, navigation, comms, cargo control | New |
| Navigation computer | None: on the backbone directly | Specialist AI; speaks the backbone's own protocol | Decided (New) |
| Water | To be decided | Potable, grey and black water | New: no local control station covers water |

Assigning each of the 1,092 isolation points to a segment is **New** work.

## Remote and manual, by system

**Data**, from the isolation points' `remote_operable` flag:

| Network | Remote-operable | Manual only |
|---|---:|---:|
| Power | 236 | 230 |
| Atmosphere | 68 | 153 |
| Fire main | 73 | 0 |
| LT cooling | 25 | 62 |
| Cargo cooling | 48 | 0 |
| Cargo atmosphere | 48 | 0 |
| Potable water | 20 | 32 |
| Grey water | 18 | 32 |
| Black water | 18 | 14 |
| HT cooling | 5 | 0 |
| Emergency oxygen | 0 | 10 |
| **Total** | **559** | **533** |

The lead mind can operate a remote-operable device only when its segment's
gateway and the backbone path to it are working, and only within its
authority. Manual-only devices always need a person.

## Known gateways and quirks

**Data**, recorded in the design data and operating doctrine:

| Where | Quirk |
|---|---|
| Generator B | Replacement unit "more reliable but uses a gateway to the original plant-control network". |
| ECLSS train B | "Mixed-generation gateway." |
| Bridge BR-06 | Rebuilt service sleeve: "remote indication exists but remote actuation was not restored for every service". |
| HAB-03 cabin 07 | Fan-coil fed from a different branch than its labelled panel. |
| HAB-03 | Non-interchangeable scrubber fan controller. |
| Bearing BE-08 | Narrower filter extraction access. |

These are the seeds of the patchwork. More quirks come from replacements made
during play.

## How a gateway behaves

**New.** A gateway is fitted equipment with a location, power supply, ports,
a protocol mapping, firmware, capacity and condition.

- **Provenance:** each reading carries its source device, mapping revision
  and source time. An unknown source is never relabelled as authoritative.
- **Meaning:** the raw term is kept alongside its translation. A device's
  "running" is not shown as "delivering output" without independent evidence.
- **Link state:** working, degraded, stale, timed out, isolated or dead. No
  new data is not the same as a reading of zero.
- **Commands:** each command has a request ID; the gateway records requested,
  accepted, attempted and refused separately. Only a measured effect confirms
  it worked.
- **Arbitration:** local takeover beats remote command; protective trips beat
  both; conflicting remote requests are refused with a reason, never resolved
  by whoever wrote last.
- **Recovery:** when a link drops, the segment's machinery keeps its local
  safe functions. On reconnection, state is reconciled; nothing queued is
  replayed.

**Where faults come from:** power loss resetting firmware; a part replaced at
port that speaks a newer dialect; wear and calibration drift; a mapping update
with a mistake in it; a gateway's own supply failing. All are modelled causes
with records, not random events.

## Local takeover

**New behaviour on Data hardware.** At a local control station, a crew member
can:

- read the segment's machinery directly, without the network;
- operate it within local interlocks;
- **take the segment into local control**, which refuses remote commands —
  including the lead mind's — until someone hands control back;
- trip the segment's machinery with the hard-wired emergency trip.

Takeover and hand-back are receipted and logged. The lead mind sees that a
segment is in local control and who took it; it cannot override that.

## The lead mind's core

**Decided; New.** The lead mind runs on **nine machines distributed through
the ship, two of them acting as parity**.

- **It goes down only if it loses three machines in quick succession**, before
  it can restore parity.
- **It reallocates parity dynamically.** After losing a machine, it turns one
  of the remaining working machines into parity, so it can survive further
  losses. The cost is parallel capacity: fewer machines left doing the
  thinking. Losses spread out over time make it slower, not more fragile.
- **It can hand control to capable subsystems.** When short of capacity, or
  when it chooses, the lead mind relinquishes control of a system to a
  subsystem advanced enough to run it and fitted with that system's controls
  (a specialist AI or a capable local controller). It keeps watching what it
  still can, and takes control back when it has capacity again.
- Machines returning to service are rebuilt into the array.

Placement, dependencies, parity timing, capacity and handover candidates are
proposed in [the lead mind's core](lead-mind-core.md).
- **Each machine is fitted equipment** with a location, power supply, cooling,
  backbone link and condition, like anything else on the ship. A machine cut
  off from the backbone counts as lost even if it is still running.
- **Each machine's room is monitored and has controlled access**, so every
  entry is recorded with who entered.
- When the lead mind is down entirely, the ship keeps running on local
  controllers and local control (principle 6).

## Open questions

1. Where are the nine machines, and what does each depend on (which power
   board, which cooling, which backbone route)?
2. How quick is "quick succession": how long does restoring parity take?
3. What does reduced capacity mean in play: slower responses, fewer systems
   attended at once, more handed to subsystems?
4. Which subsystems are capable enough to take over which systems?
5. Which segments start degraded or quirky, beyond the recorded quirks above?
3. Which crew roles may take local control of which segments?
4. Does the backbone itself have a topology that can be cut in places (a
   route through the spine that a single fault can sever)?
