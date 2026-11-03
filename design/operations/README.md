# Ship operations: how the lead mind runs the Ox

**Status:** first complete draft, 2 November 2026. Not
implemented except where marked **Runtime**.

This specification describes how the Ox runs when her lead mind, the ship's
AI, is doing its job. It is written as if operating the ship were the whole
game: complete enough that every system has a normal, a way to drift from
normal, and a record of what happened. The player's own objectives are out of
scope here.

## The roles in operations

- **The lead mind** runs the ship. Wherever a working network path reaches a
  device, it operates that device directly — valves, breakers, setpoints,
  schedules — and keeps the ship in her normal operating state without being
  asked. It is the most general intelligence aboard, not the only one.
- **The human captain** commands: route, freight, money, staffing and human
  safety policy. The captain is an autonomous character and the lead mind's
  partner. Within delegated authority, routine control is the lead mind's.
- **The crew** are the hands. They do what needs a body: manual-only valves,
  repairs, inspections, cargo handling, medical care, anything behind a dead
  link or inside a blind spot. They keep their own view of the ship through
  local panels, and any of them can take a system into **local control**.
- **Other machine minds** — specialist AIs, local controllers, ordinary
  automation — run their own parts of the plant and talk to the lead mind
  through gateways that translate imperfectly.

## Principles

1. **The world owns physics, time and records.** The lead mind requests;
   Evennia decides whether anything happened and records it. A command
   accepted is not a machine working.
2. **The lead mind knows only what reaches it.** Every reading has a source,
   a path, an age and a translation. Where nothing reaches, it does not know.
3. **Capability is fitted, permission is conferred, interpretation is
   learned.** Four separate questions govern every action: perception,
   connectivity, interpretation and authority ([network](network.md)).
4. **Normal is specified.** Every system states its normal consumption, wear
   and maintenance, so departures from normal are measurable.
5. **Everything leaves a record.** Every command, effect, movement and
   reading that the world can know is kept ([records](records.md)).
6. **Local control always survives.** Machinery stays operable by hand when
   the network, a gateway or the lead mind is down, and local takeover always
   beats remote command.

## Status labels

Every capability in these chapters carries one label:

| Label | Meaning |
|---|---|
| **Runtime** | Implemented in the installed G19 game today. |
| **Data** | Present in the ship's design data (`design/ship/ox_full_ship.json`) but not modelled by the runtime. |
| **New** | Proposed here; neither in the data nor the runtime. |

## Starting state

The ship is under way and humming. One ship-wide backbone network joins every
segment through its gateway, and almost all of them work. Trouble comes from
wear, failures and replacements during the voyage, not from a broken opening.

## Chapters

| Chapter | Contents | State |
|---|---|---|
| [Network](network.md) | Backbone, segments and gateways; what is remote and what is manual; local takeover | Drafted |
| [Lead mind's core](lead-mind-core.md) | The nine machines: placement, dependencies, parity, capacity, handover | Proposed |
| [Records](records.md) | Every record the ship keeps, and its status | Drafted |
| [Power](power.md) | Generation, storage, distribution, protection | Drafted |
| [Cargo](cargo.md) | Drums, cargo climate, freight handling, rotation | Drafted |
| [Cooling](cooling.md) | LT and HT loops, radiators, the shared heat budget | Drafted |
| [Air](air.md) | Atmosphere, pressure cells, ECLSS trains, emergency oxygen | Drafted |
| [Water and waste](water-and-waste.md) | Potable, grey and black water; recycling; disposal | Drafted |
| [Food](food.md) | Cultivation, stores, galley | Drafted |
| [Movement](movement.md) | Trunks, doors, locks, indexed transfers, logistics tube | Drafted |
| [Propulsion and navigation](propulsion-and-navigation.md) | Drive, RCS, helm, FTL readiness | Drafted |
| [Fire and damage control](fire-and-damage-control.md) | Fire main, lockers, casualty response | Drafted |
| [Medical](medical.md) | Physiology, treatment, casualty transport | Drafted |
| [Communications](communications.md) | Comms nodes, alarms relay, intercoms | Drafted |
| [Workshop and exterior](workshop-and-exterior.md) | Fabrication, welding, exterior rail and EVA | Drafted |
| [Watch routine](watch-routine.md) | How a day runs; the split between lead mind and crew | Drafted |

## Decided

1. **Network:** one ship-wide backbone, with gateways joining each segment to
   it.
2. **Starting state:** in medias res; almost every gateway works.
3. **`LCS-DR-03`** (and by extension each local control station) hosts its
   segment's gateway and is a crew console with local takeover.
4. **The lead mind's core** is distributed across nine machines around the
   ship, two of them acting as parity. It goes down only if it loses three in
   quick succession; it can reallocate machines to parity at the cost of
   capacity, and hand systems to capable subsystems
   ([network](network.md#the-lead-minds-core)).
5. **Doors:** most are motorised and can seal against vacuum
   ([movement](movement.md)).
6. **Controlled access:** the ship's entrances, the bridge and the lead mind's
   machines are monitored and have controlled access.
7. **Crew:** the ship is designed for 40 with one main watch and three skeleton
   watches. The actual crew is 16, on three overlapping 14-hour shifts: one
   twelve-person main shift, always including the captain, and two two-person
   shifts, mostly monitoring, whose members rotate
   ([watch routine](watch-routine.md)).
8. **The ship's day is 36 hours**, and everyone is perpetually on call: a staffing
   convention, not being awake; emergencies never wait for off-shift crew.

## Related

- [The player's role: the Ox's lead mind](../interface/ship-mind.md)
- [Drum 3 fit-out survey](../interface/drum3-fitout-survey.md)
- [Major-system operating doctrine v0.5](../ship/SYSTEM_OPERATING_STATES_v0.5.md)
- [Ship engineering index](../ship/README.md)
- [ADR 0009: world events and durable work](../decisions/0009-durable-events-and-work.md)
