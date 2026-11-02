# The player: the Ox's lead mind

**Status:** chosen player-role direction, 2 November 2026. It merges
[Proposal C, *The Ship Herself* (#148)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/148)
and [Proposal D, *The Other Captain* (#149)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/149),
taking D's authority model. It replaces all four proposals, A to D (#146–#149).
**This is a product design.** Nothing below exists in the game yet except where
it names installed G19 hardware, and each proposed addition is marked as one.

## The role

**You are the lead mind of an old, much-refitted freighter.** You are the most
general intelligence aboard, but not the only one, and not in command. Your
job is to keep the ship, her freight and her people going by making an untidy
collection of machines, minds and humans work together.

- **The human captain is your partner, not your avatar.** An autonomous
  character who owns route, freight, staffing, money and human safety policy.
  You hold delegated technical authority. Neither of you can make the other
  irrelevant.
- **The crew are your hands and your main relationships.** Anything without a
  motor and a reachable controller needs a person, who has their own work,
  fatigue and opinions.
- **Other machine minds exist, but few.** A machine gets a mind of its own only
  where its judgement changes outcomes. Most equipment is ordinary hardware.

> "I know the ship, I coordinate her other minds, and I work alongside the
> captain to keep our people and freight moving." — Proposal D

## Why this fits the Ox

The installed ship already tells this story. Her 116 fitted local panels are
deliberately local: each reads only its own room, and no workstation reads the
whole ship ([G19 instrumentation](../ship/G19_INSTRUMENTATION_AND_RECOVERY.md)).
The only thing that crosses the ship is the protected fire relay from the eight
habitat sections to three command and engineering rooms. A mind installed in
such a ship starts nearly blind and grows its reach one fitted link at a time.
That is the progression, and it is also the ship's history.

It also uses what the project does best: physics and instruments owned by the
world, with honest provenance and receipts, and crew who think for themselves.

## What each proposal contributed

| From | Kept |
|---|---|
| **A — the Master** | Autonomous crew at the centre; a queue of decisions; no mood bars. |
| **B — the Working Ship** | A labelled vocabulary for how anything is known; honest, event-based time; one incident before an economy; testable acceptance criteria; the freighter's long-term viability as the long game. |
| **C — the Ship Herself** | A player with no body whose perception is the fitted instruments; the crew as hands; persuasion rather than orders; pausing as deliberation and speed-up as sensor-triggered watch mode; drones as earned hands; an auditable message log. |
| **D — the Other Captain** | The four-question authority model; a few other minds and gateways between incompatible systems; a human captain as partner; "accepted" is not "working"; survey the real fit-out first. |

Dropped: A's command-only premise, latitude and risk sliders and reaction
previews; B's embodied player; C's single permission meter and its "earn every
permission from nothing" start.

## Authority: four separate questions

Every interaction is governed by four questions, each changed by different
things (from D):

| Question | Asks | Changed by |
|---|---|---|
| **Perception** | What measured it, what does it cover, how fresh is it? | Fitting, repairing or calibrating instruments. |
| **Connectivity** | Is the source reachable: direct bus, gateway, local panel only, intermittent, or not at all? | Fitting, powering, repairing or isolating links and gateways. |
| **Interpretation** | Do you know what the source's words and units actually mean? | Learning and verifying a device's vocabulary; updating a gateway's mapping. |
| **Authority** | Are you allowed to request this, and does it need a person, a local reset or an interlock cleared? | Standing agreements with the captain and crew, recorded and receipted in world state. |

**Capability is fitted, permission is conferred, interpretation is learned.**
All three change independently.

**Who decides.** The human captain has the final say in human and commercial
matters. You decide routine control within your delegated authority. In
safety-critical work, the world's interlocks, physical limits and recorded
operating authority decide whether a command can happen at all. A captain's
insistence is not a bypass, and your safety concern is not an unlimited veto.

You start as a trusted, fitted officer-equivalent with real responsibilities,
not a servant earning every permission. Trust still grows and shrinks with
accurate reports, justified dissent and outcomes, and it shows up as standing
agreements, never as a meter.

## The ecology of systems

| Kind | Example | How you deal with it |
|---|---|---|
| **Lead mind (you)** | — | Your own model and records; never world truth. |
| **Specialist AI** | A salvaged navigation computer that speaks an obsolete protocol | A colleague who can disagree and need not accept your diagnosis. |
| **Local controller** | A cargo thermal skid's own control loop | A limited vocabulary through a gateway; keeps running if you go offline. |
| **Conventional automation** | Breakers, relays, permissives | Observed and commanded only where actually wired. |
| **Manual equipment** | Isolation valves, lashings, seals | Needs a person, or much later a drone. |

**Start small and grow.** The first slice has one gateway with one real
translation flaw, one local controller and at most one specialist AI. More are
added only once that proves fun. Each specialist AI is another Concordia mind
on the same local hardware as the crew, so it has to earn its place.

## Gateways

A gateway is fitted equipment that joins incompatible systems, with a location,
power supply, ports, a protocol mapping, firmware, capacity and condition. It
is not an AI and not magic translation. Each must keep:

- **Provenance:** the originating device, revisions and source time. An
  unknown source is never relabelled as authoritative.
- **Meaning:** the raw term alongside its interpretation. If a controller's
  `RUN` means "start command latched", the display says so and does not show
  "cooling".
- **Link state:** powered, connected, stale, timed out, degraded or isolated.
  No new data is not the same as confirmed zero.
- **Commands:** which native actions exist, their preconditions, interlocks and
  request and receipt IDs. An acknowledgement proves only that something
  received the request.
- **Arbitration:** what happens when you, the captain, a local controller and a
  protective relay disagree. No hidden last-writer-wins.
- **Recovery:** a lost link leaves the controller in its own fallback; on
  reconnection state is reconciled and nothing queued is replayed.

**Faults must come from the simulation, not from riddles.** A translation
mystery is only a mystery once, so gateway problems arise from things the world
models: a power cut that resets firmware, a part replaced at port that speaks a
newer dialect, a gateway losing power and going quiet, wear that shifts
calibration, a mapping update with a mistake in it.

## How you know things

Every displayed fact carries one of these labels:

| Label | Meaning |
|---|---|
| **Measured** | An instrument sample with source, units, quality and game time. |
| **Reported** | A person's statement, with sender and delivery time. |
| **Translated** | A gateway's reading: raw term, mapping revision and interpretation. |
| **Your model** | Your own inference, its premises and uncertainty. Never hidden truth. |
| **Unknown** | No reachable source, a dark panel or a lost link. |
| **Requested / accepted / attempted** | Where a command stands in the protocol. |
| **World-confirmed** | Receipted work followed by a measured physical effect. |

A crew member in a blind spot is *unknown*, not "probably fine". A quiet alarm
channel is not an all-clear.

## Persuasion and the crew

You speak through announcements, addressed messages, displays on panels you can
reach, and alarms. You explain, recommend, attach evidence (a trend, a reading,
a receipt), ask for hands and escalate to the captain. People decide whether to
act.

There are no mood bars and no predictions of what someone will think. What you
see is a history the world can record: what you told each person and when,
whether it was true, and whether your actions matched your words. You may
withhold or slant information only through messages that stay in a log the
crew can read, so deception is possible and catchable, never invisible.

## Time

**Pausing is in character:** you deliberate between samples and nothing moves.
**Speeding up is watch mode:** the world runs until one of your triggers fires —
a threshold on a reachable sensor, a delivered message, a scheduled obligation.
You cannot be woken by anything you have no way to detect. Crew, plant and
pending work keep progressing causally through any speed-up.

## The long game

Each voyage runs under a **charter** from the captain: standing goals and limits
for the ship's mind (keep cold-chain lots in band; never open a cargo boundary
without a pressure check; wake the captain for any injury). The captain judges
how well you interpreted it.

Progress is **coherence, not omnipotence**: fitting and repairing gateways,
calibrating instruments, learning an old specialist's dialect, deciding whether
to keep a quirky old controller or replace it with one that speaks a better
protocol, building standing agreements with the captain and crew, and much
later limited maintenance drones. Manual islands and incompatibilities remain
even late in the game; a uniform, all-seeing ship would erase the premise.

Endings need no win screen: a crew that sails with you for years, a ship
retired with her people intact, or a mind switched off and replaced.

## The shared incident, on the real ship

The earlier proposals used an invented "Hold 3". The installed ship carries
cold-chain freight in six rotating cargo drums
([G19 cargo environment](../ship/G19_CARGO_ENVIRONMENT.md)). This version uses
drum 3.

**Installed today:**

- `DR-03-CARGO-HX`, the cargo thermal skid, and `DR-03-CARGO-GAS`, the
  cargo-atmosphere circulation pack, both fused from the `DR-03-SVC-DB` gallery
  distribution board.
- `DR-03-LT-IF`, the rotary low-temperature interface, fed from the LT plant
  through `EDGE-DR-03-LT-IF` and its isolation valve.
- `PZ-DR-03-SVC`, the measured service-gallery pressure cell the skid exchanges
  heat with.
- Cooling needs powered, serviceable skids **and** an unisolated LT interface.
  Each skid rejects at most 20 kW; the six drums together get at most 10 % of
  the LT plant capacity left after propulsion.
- A surveyed cold-chain lot outside its band accumulates permanent quality loss.
- The thermal target is changed only by an engineer at the drum's gallery skid,
  through a receipted local service operation. **There is no remote control.**

**Added for the slice (proposed, not fitted):** a cargo-control gateway at the
forward cargo control panel (`LP-CARGO-CTRL-FWD`) carrying drum 3's skid
status, cargo temperature and distribution-board current to the lead mind's
core. The skid's own controller stays a local controller with its own fallback.
The navigation computer is the one specialist AI.

**The moment.** Drum 3's translated status reads `RUN`; you learned two voyages
ago that this skid's `RUN` means "start latched", not "cooling". Its cargo
temperature, measured, is climbing towards the top of the cold-chain band. The
board current is lower than a running skid should draw. The navigation computer
wants to start a burn in two hours, and you know propulsion takes LT capacity
first.

- **What you can do yourself:** compare sources, check the gateway's link
  state, rerun the cargo-heat estimate against the burn plan, ask the
  navigation computer for its margins.
- **What you must ask for:** an engineer to go to the drum 3 gallery — through
  the drum's service lock, which takes time — to check the skid and the LT isolation
  valve, and set the target by hand if needed.
- **What the captain decides:** delay the burn and spend reaction mass and
  schedule, or burn on time and accept the cargo risk. The navigation computer
  objects to any delay, in its own terms.
- **What settles it:** the engineer's receipted work, then a measured change in
  drum temperature, then the lot's recorded condition at delivery.

**The distinctive moment:** deciding whether the skid, the gateway, the
navigation computer or your own model is wrong, and persuading a human partner
to act while you are still not sure.

## The interface

One persistent workspace, laid out like a control room:

- **Plant and connectivity (centre):** the ship as connected plant, drawn from
  the fitted register, with sensor coverage as an overlay (lit, dark, stale)
  and the data path to any source (direct, gateway, panel only, none).
- **Subsystem inspector (on select):** raw and translated status, native device
  ID, requested versus applied values, independent measurements, mapping
  revision and how sure you are of its meaning.
- **Crew and captain (left and right):** each person as your sources know them,
  with age; addressed messages with delivery receipts; open requests for hands
  and decisions waiting on the captain.
- **Charter and authority (drawer):** the voyage charter and every standing
  agreement, with who changed what and why.
- **Evidence timeline (bottom):** incidents, competing explanations, original
  messages and confirmed work, each labelled.
- **Watch triggers (top):** pause, real time and *watch until*, with the
  trigger list visible and editable.

Every graphical view has a list or table equivalent.

## First playable slice

1. **Fit-out survey:** confirm drum 3's skid, circulation pack, LT interface,
   valve, board, gallery cell and the nearest panels; record what is manual.
2. **The lead-mind player:** an authenticated player with no body, whose
   perception is a new sensor-and-gateway-scoped read view. It must not reuse
   the developer view or expose any character's private beliefs.
3. **One gateway and one local controller:** the cargo-control gateway with
   typed mappings, one deliberate semantic flaw (`RUN`), link and power faults;
   the skid controller keeps regulating if the link drops.
4. **One remote action and one hand-only task:** a bounded, receipted command
   through the gateway where it is fitted and permitted, and the gallery
   setpoint or valve check that only an engineer can do.
5. **The human partners:** the migrated autonomous captain, or a clearly
   labelled test double until migration, able to ask, dispute and decide; one
   engineer with real travel and work limits.
6. **One specialist AI:** the navigation computer, with its own memory and a
   narrow domain.
7. **The incident and watch mode:** the drum 3 case above, with pause and
   watch-until and no alerts from undetected state.

## Acceptance tests

| ID | Demonstration | Required result |
|---|---|---|
| S01 | Break the gateway link mid-watch | The skid follows its own fallback; you lose current readings and commands; the local panel keeps its own view. |
| S02 | Read `RUN` through a broad mapping | Raw term, mapping revision and ambiguity are shown; no claim of cooling without independent evidence. |
| S03 | Unpower or isolate the gateway | No phantom fresh data, remote action or access remains. |
| S04 | Command manual-only or unconnected equipment | The world refuses; prose, interface state or your beliefs cannot make it act. |
| S05 | Repeat a command after a lost acknowledgement | It reconciles under the original request ID: one effect, one consumption, one receipt. |
| S06 | Captain, lead mind and controller request conflicting actions | Recorded authority and interlocks decide; the outcome and any refusal reason are evidenced. |
| S07 | An engineer's report and the navigation computer disagree | Both keep author, source and time; neither becomes physical truth until measured. |
| S08 | Read a pressure cell through a damaged instrument | No secret ship-wide gas truth; cell-level readings stay cell-owned. |
| S09 | A crew member is off every reachable sensor | Their location is unknown; their private state is never inferred from handler storage. |
| S10 | Power down the lead mind's core, then restore it | The ship continues on local and manual control; your identity, records and uncertain work reconcile without duplicates. |
| S11 | Watch mode through an undetected fault and a delivered message | It stops only on detected or delivered events; all progression is kept. |
| S12 | Replace or update the gateway | New mappings take effect only through fitted, authorised, receipted work. |
| S13 | Send a message over a failed comms route | It is not delivered, and the failure is itself a fact you can trigger on. |

## Risks

- **Systems administration.** Keep ordinary controllers autonomous; build play
  around consequential discrepancies, priorities and persuasion, not packet
  inspection.
- **The god-mind trap.** Fitted links, ageing data, manual islands and the
  captain's authority must stay real.
- **Machines crowding out the crew.** Keep specialist AIs few; the crew remain
  the main relationships.
- **Puzzles that run out.** Gateway faults must arise from modelled causes, not
  authored riddles.
- **The least conventional fantasy.** Many players want to be a person: make
  the crew vivid and the stakes human; offer drones later.
- **New cognition.** Crew and captain must reason about trusting a machine
  partner, from records the world already keeps.
- **Architecture drift.** Every world change stays in Evennia; gateways, the
  interface and the handler interpret or request, never act as a second physics
  authority.

## Decisions still open

1. The exact split between the captain's command and the lead mind's delegated
   authority, including the limits of legitimate refusal.
2. Whether the navigation computer is the right first specialist.
3. Gateway semantics in detail: versioning, arbitration, staleness and recovery.
4. What persists of the lead mind across power loss, and its own voice.
5. Whether the cargo-control gateway at `LP-CARGO-CTRL-FWD` is the right first
   fitting, once the survey is done.

## References

- Superseded proposals: [A #146](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146),
  [B #147](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/147),
  [C #148](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/148),
  [D #149](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/149)
- [G19 cargo environment](../ship/G19_CARGO_ENVIRONMENT.md)
- [G19 instrumentation and recovery](../ship/G19_INSTRUMENTATION_AND_RECOVERY.md)
- [Ship engineering index](../ship/README.md)
- [Architecture and authority](../../ARCHITECTURE.md)
- [Typed world read model](../../contracts/WORLD_READ_MODEL.md)
- [Deferred human interface](../../services/interface/README.md)
