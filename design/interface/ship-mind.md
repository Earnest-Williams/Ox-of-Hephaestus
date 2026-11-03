# The player: the Ox's lead mind

**Status:** chosen player-role direction, 2 November 2026. It merges
[Proposal C, *The Ship Herself* (#148)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/148)
and [Proposal D, *The Other Captain* (#149)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/149),
taking D's authority model, and replaces all four proposals, A to D
(#146–#149). **This is a product design.** Nothing below exists in the game
yet except where it names installed G19 hardware.

## The role

**The player is the lead mind of an old, much-refitted freighter**: the ship's
AI. It is the most general intelligence aboard, but not the only one, and not
in command.

- **It runs the ship.** Wherever a working network path reaches a device, the
  lead mind operates it directly and keeps the ship in her normal state. How it
  does that, system by system, is the [operations specification](../operations/README.md).
- **The human captain is its partner.** An autonomous character who owns
  route, freight, staffing, money and human safety policy. The lead mind holds
  delegated technical authority.
- **The crew are its hands.** Anything manual, behind a dead link or in a blind
  spot needs a person with their own work, fatigue and opinions. Any of them
  can take a system into local control.
- **Other machine minds exist, but few.** A machine gets a mind of its own only
  where its judgement changes outcomes.

The player's objectives beyond running the ship are outside this document.

## Why this fits the Ox

The ship's own records describe an original plant-control network, a refit
generator that "uses a gateway" to it, 559 valves and breakers built for remote
operation, and 33 local control stations meant to keep working when the network
is down ([network](../operations/network.md)). Equipment from five eras sits
side by side, which is where the gateways and their quirks come from.

**The game starts in medias res.** The ship is under way and humming, with
almost every gateway working. The crew keep their own view through 116 local
panels that read only their own rooms.

## What each proposal contributed

| From | Kept |
|---|---|
| **A — the Master** | Autonomous crew at the centre; no mood bars. |
| **B — the Working Ship** | A labelled vocabulary for how anything is known; honest, event-based time; testable acceptance criteria. |
| **C — the Ship Herself** | A player with no body whose perception is the fitted instruments; the crew as hands; persuasion rather than orders; pause as deliberation and watch mode; an auditable message log. |
| **D — the Other Captain** | The four-question authority model; other minds and gateways between incompatible systems; the captain as partner; "accepted" is not "working"; survey the real fit-out first. |

## Authority

Four separate questions govern every action — perception, connectivity,
interpretation and authority — set out in the
[network chapter](../operations/network.md#the-four-questions). **Capability is
fitted, permission is conferred, interpretation is learned.**

**Who decides.** The captain has the final say in human and commercial matters.
The lead mind decides routine control within its delegated authority. In
safety-critical work, the world's interlocks, physical limits and recorded
authority decide whether a command can happen at all. Local takeover always
beats remote command.

## The ecology of systems

| Kind | Example | How the lead mind deals with it |
|---|---|---|
| **Lead mind** | — | Its own model and records; never world truth. |
| **Specialist AI** | The navigation computer: reasonably capable, on the backbone with no gateway | A colleague who can disagree. |
| **Local controller** | A cargo thermal skid's control loop | A limited vocabulary through a gateway; keeps running if the lead mind is offline. |
| **Conventional automation** | Breakers, relays, permissives | Observed and commanded where wired. |
| **Manual equipment** | 533 manual-only valves and breakers | Needs a person. |

## How the lead mind knows things

Every displayed fact carries one label:

| Label | Meaning |
|---|---|
| **Measured** | An instrument sample with source, units, quality and game time. |
| **Reported** | A person's statement, with sender and delivery time. |
| **Translated** | A gateway's reading: raw term, mapping revision and interpretation. |
| **Model** | The lead mind's own inference, with premises and uncertainty. |
| **Unknown** | No reachable source, a dark panel or a lost link. |
| **Requested / accepted / attempted** | Where a command stands. |
| **World-confirmed** | Receipted work followed by a measured physical effect. |

A person in a blind spot is *unknown*, not "probably fine". A quiet alarm
channel is not an all-clear. The full list of what the ship records is in
[records](../operations/records.md).

## Dealing with people

The lead mind speaks through announcements, addressed messages, displays on
panels it can reach, and alarms. It explains, recommends, attaches evidence and
asks for hands; people decide whether to act. There are no mood bars and no
predictions of what someone will think — only a recorded history of what was
said, whether it was true, and whether actions matched words. Every message
stays in a log the crew can read.

## Time

**Pausing is in character:** the lead mind deliberates between samples and
nothing moves. **Speeding up is watch mode:** the world runs until a trigger the
lead mind set fires — a threshold on a reachable sensor, a delivered message, a
scheduled obligation. It cannot be woken by anything it has no way to detect.

## The interface

One persistent workspace:

- **Plant and connectivity:** the ship as connected plant, with sensor coverage
  and the data path to any source.
- **Subsystem inspector:** raw and translated status, requested versus applied
  values, independent measurements, mapping revision.
- **Crew and captain:** each person as the lead mind's sources know them, with
  age; messages with delivery receipts; open requests.
- **Authority:** standing agreements and segments in local control.
- **Evidence timeline:** events, competing explanations and confirmed work.
- **Watch triggers:** pause, real time and *watch until*.

Every graphical view has a list or table equivalent.

## First build slice

1. **Fit-out survey:** done — [drum 3](drum3-fitout-survey.md).
2. **The lead-mind player:** an authenticated player with no body, whose
   perception is a new network-scoped read view. It must not reuse the
   developer view or expose any character's private beliefs.
3. **The backbone, one gateway and one local controller:** drum 3's segment
   gateway at `LCS-DR-03`, with typed mappings, one deliberate translation
   flaw, link and power faults; the skid keeps regulating if the link drops.
4. **One remote action, one crew console and one hand-only task:**
   `ISO-DR-03-LT-IF` through the network under existing interlocks;
   `LCS-DR-03` as a crew console with local takeover; an inspection inside the
   drum that only an engineer can do.
5. **The human partners:** the captain (or a labelled test double until
   migration) and one engineer with real travel and work limits.
6. **One specialist AI:** the navigation computer, as new equipment on the
   backbone (no gateway).
7. **Watch mode:** pause and watch-until, with no alerts from undetected state.

## Acceptance tests

| ID | Demonstration | Required result |
|---|---|---|
| S01 | Break the gateway link mid-watch | The skid follows its own fallback; the lead mind loses current readings and commands; the local panel keeps its own view. |
| S02 | Read a status through a broad mapping | Raw term, mapping revision and ambiguity are shown; no claim of output without independent evidence. |
| S03 | Unpower or isolate the gateway | No phantom fresh data, remote action or access remains. |
| S04 | Command manual-only or unconnected equipment | The world refuses; prose, interface state or beliefs cannot make it act. |
| S05 | Repeat a command after a lost acknowledgement | It reconciles under the original request ID: one effect, one consumption, one receipt. |
| S06 | Captain, lead mind and controller request conflicting actions | Recorded authority and interlocks decide; outcome and refusal reason are evidenced. |
| S07 | An engineer's report and the navigation computer disagree | Both keep author, source and time; neither becomes truth until measured. |
| S08 | Read a pressure cell through a damaged instrument | No secret ship-wide gas truth; readings stay cell-owned. |
| S09 | A crew member is off every reachable sensor | Their location is unknown; their private state is never inferred from handler storage. |
| S10 | Lose the lead mind's machines one at a time, then three in quick succession, then restore them | Spaced losses: it reallocates parity and runs on with less capacity. Three quick losses: it goes down and the ship continues on local and manual control. On restore, records and uncertain work reconcile without duplicates. |
| S15 | The lead mind hands a system to a capable subsystem, then takes it back | The handover and return are receipted; the subsystem runs only what it is fitted to control; nothing is commanded twice. |
| S11 | Watch mode through an undetected fault and a delivered message | It stops only on detected or delivered events. |
| S12 | Replace or update the gateway | New mappings take effect only through fitted, authorised, receipted work. |
| S13 | Send a message over a failed comms route | It is not delivered, and the failure is itself a fact. |
| S14 | A crew member takes drum 3 into local control | Remote commands to the drum are refused until it is handed back; both are receipted. |

## Risks

- **The all-seeing mind.** Starting with almost everything connected makes the
  lead mind capable from the first minute. Manual-only equipment, local panels,
  local takeover, ageing data and the captain's authority must stay real.
- **Machines crowding out people.** Keep specialist AIs few.
- **New cognition.** Crew and captain must reason about trusting a machine
  partner, from records the world already keeps.
- **Architecture drift.** Every world change stays in Evennia; gateways, the
  interface and the handler interpret or request, never act as a second physics
  authority.

## Decisions

**Decided:** one ship-wide backbone with segment gateways; in medias res with
almost every gateway working; each local control station hosts its segment's
gateway and is a crew console with local takeover; the lead mind runs on nine
distributed machines, two acting as parity, goes down only if three are lost
in quick succession, reallocates parity at the cost of capacity and can hand
systems to capable subsystems; most doors are motorised and seal against
vacuum; entrances, the bridge and the lead mind's machine rooms have
monitored, controlled access; a crew of 16 on three overlapping 14-hour shifts,
the captain always on the main shift and the two small monitoring shifts
rotating their members; a 36-hour ship's day, with everyone perpetually on call.

**Open:** the exact split between captain and lead mind; whether the navigation
computer is the right first specialist; gateway semantics in detail; what
persists of the lead mind across power loss, and its voice; which gateways
start degraded or quirky.

## References

- [Operations specification](../operations/README.md)
- Superseded proposals: [A #146](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146),
  [B #147](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/147),
  [C #148](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/148),
  [D #149](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/149)
- [Architecture and authority](../../ARCHITECTURE.md)
- [Typed world read model](../../contracts/WORLD_READ_MODEL.md)
