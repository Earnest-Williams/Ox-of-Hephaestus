# Proposal D: The Other Captain — A Patchwork Ship of Minds

**Status:** fourth competing player-experience proposal, 2 November 2026; **not approved, implemented or merged**.  
**Peers:** [A — The Master, PR #146](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146); [B — The Working Ship, PR #147](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/147); [C — The Ship Herself, PR #148](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/148). This document changes none of those PRs.  
**Scope:** player identity, human/AI relationships, heterogeneous onboard intelligence, interface, gameplay, feasible integration sequence and acceptance tests. Everything described as future gameplay is a *proposal*, not a statement about present capabilities.

## The premise

**You are the Ox's lead AI, serving as her second captain in practice, not her human commanding officer in rank.**

The Ox is an aging independent freighter assembled from generations of upgrades, repairs, secondhand components and clever compromises. She does not contain one perfectly unified intelligence. She contains **many systems**, some with substantial intelligence, some with narrow expertise, some little more than control logic, and some entirely manual. Their protocols, terminology, priorities and ability to communicate vary. A few can argue with you; most cannot.

You are the most general-purpose intelligence aboard, responsible for **making this untidy collection cooperate** and for maintaining a working partnership with the human captain and crew.

The player fantasy is not "I am the ship and every actuator is my limb." It is:

> **"I know the ship, I coordinate her other minds, and I work alongside the captain to keep our people and freight moving."**

You can make an excellent technical decision and still be unable to carry it out without a local controller, a compatible gateway or a technician with a wrench. The captain can give an entirely reasonable order that the installed plant cannot execute as requested. A specialist computer can be right about its own subsystem while wrong about the ship as a whole. Your task is to reconcile them.

This takes the lived-in, cobbled-together-computer flavour of the *Millennium Falcon* as inspiration, without depending on its setting, characters or stories. Ox remains its own blue-collar ship and game.

## How D differs from the other three proposals

| Proposal | Player | Machinery | Human relationships | Defining tension |
|---|---|---|---|---|
| **A — Master** | Human captain | Operated indirectly by crew | You command people | Delegation versus control |
| **B — Working Ship** | Embodied owner-captain | You or crew operate it locally | You lead and may work beside people | Time, labour and commercial survival |
| **C — Ship Herself** | One ship-wide operating mind | Your available remote actuators | Crew grant/revoke your permissions | Permission and trust versus survival |
| **D — Other Captain** | **Lead AI amid other independent systems** | Controllers retain local authority, often reachable only through gateways | **Human captain is an autonomous operational partner** | **Coordinating incompatible minds, machinery and people** |

D adopts C's non-corporeal player but changes two assumptions:

1. **You are not the only intelligence in the hull.** Navigation, environmental regulation, fault diagnostics and perhaps cargo management can contain separate specialist AIs or expert systems. They may disagree, conceal their uncertainty, have their own histories or simply be incapable of understanding a general request. A limited controller does not suddenly become conversational because the player addresses it.
2. **You do not begin as a helpless subordinate waiting for every permission to be earned.** You are already a trusted, fitted shipboard officer-equivalent with meaningful operating responsibilities. The human captain has final command over human and commercial decisions; you have substantial delegated technical authority. Neither can make the other irrelevant. Control is constrained by the system's actual connectivity, protocol, physical interlocks, standing authority and ongoing cooperation, not one global "trust level".

A captain's authority is not a software exploit. The lead AI's expertise is not a substitute for the captain's accountability. They can be partners without identical powers.

## 1. The onboard ecology: five kinds of system

The categories below are **design roles**, not a claim that the installed G19 register already classifies or runs these minds.

| Kind | Reasoning and autonomy | Crew-facing interface | Relation to the player |
|---|---|---|---|
| **Lead AI (player)** | General reasoning, synthesis, planning, communications, records of previous incidents | Speech, addressed messages and authorised displays where physically connected | Player's own viewpoint; does not own world truth |
| **Specialist AI** | Significant but domain-limited judgment, possibly memory/personality | Usually an inherited specialist console, sometimes conversational | A collaborator, adversary or expert who need not accept your diagnosis |
| **Smart local controller / expert system** | Rule- or model-based control, adaptation and bounded diagnosis | Standardised telemetry, alarms, status codes and a few controls | Responds through its limited vocabulary and gateway |
| **Conventional automation** | Deterministic feedback, sequencers, permissives and hardwired protection | Gauges, indicators, relay status, local panel | No personality; observe and command only where actually wired |
| **Manual / isolated apparatus** | No onboard cognition or remote actuation | Physical indicators, switches, tools, technician reports | You need a human or later a physically capable robot |

**Do not make 808 separate chatbots.** Most equipment has no mind. A handful of specialist intelligences should be memorable; hundreds of mundane machines should behave like mundane machines. Some old equipment might be extremely competent at one job while almost incapable of translating its state into useful language.

Example possible personalities, **not newly installed canon**:

- A salvaged navigation computer, more precise than you in astrodynamics, dismissive of cargo-handling shortcuts, speaking an obsolete data protocol with a thin conversational adapter.
- A dedicated environmental expert system that maintains stable gas processing but lacks any concept of a person, an insurance claim or a missed delivery date.
- A freight-climate controller that insists it is "READY" because its motor-start request is latched, despite no measured circulation.
- A straightforward pump governor with no identity beyond its control parameters.

An old specialist AI may be worth repairing rather than replacing because it knows every oddity of the Ox's drives. An inexpensive new controller may improve efficiency while introducing unfamiliar semantics, new dependencies and friction.

## 2. What is connected is not the same as what is understood or controlled

**Four independent questions must govern every proposed interaction:**

1. **Perception:** What instrument or other source measured it, what does it cover, and how fresh/reliable is it? If nothing monitored it, you do not know.
2. **Connectivity:** Is that source physically and logically reachable? Direct network, legacy gateway, only a local panel, intermittent link, or no connection at all?
3. **Interpretation:** Do you know the native units, vocabulary, framing, identity and actual meaning? "Online", "accepted", "running" and "producing output" are not synonyms.
4. **Authority:** Even if reachable and understood, are you permitted to request this operation? Does it require a crew member's authorisation, a local reset, a mechanical interlock or an independent approval?

Do not compress these into a single universal *Autonomous / Propose / Manual* meter. A smart controller might be autonomous **locally** but inaccessible for remote command. Conversely, a bridge might legitimately have remote control of a simple deterministic breaker while you have no authority to alter the system's global operating policy.

**Capability is fitted; permission is conferred; interpretation is learned or verified.** All three can change independently.

### A patchwork communications graph

~~~text
                                     Human captain
                                  crew, hands, judgment
                                  |                ^
                          radio/comms          panels, gauges,
                                  v             local displays
                         [ PLAYER: LEAD AI ]        |
                              |    |   |              |
                    direct bus|    |   |gateway       |
                              |    |   +---------- [NAV specialist AI]
                              |    |                   native protocol
                              |    +--- legacy bridge ---------- [cargo controller]
                              |                                  |
                              +--- fitted telemetry ---------- [power controls]
                                                                |
                                 [local ECLSS controller] ---- [local display]
                                          |
                                   local closed loop
                                        (works if
                                    main AI is offline)

                     [manual valve] --- crew only; no remote wire
~~~

This is conceptual, **not an assertion that these connections are installed**. A real implementation needs a surveyed list of fitted links, hardware, bus power, gateway location, accessible operations and failure behaviour.

Some local panels report their own telemetry directly to nearby human operators. **Most subsystem machines cannot talk to crew conversationally**: they have standard readouts for whatever they measure. The lead AI is the primary natural-language bridge between ship instrumentation and human reasoning, but it cannot manufacture a channel where none exists.

The crew must remain able to use authorised local panels when you or a gateway fail. A loss of your perception is not necessarily a loss of their perception, and vice versa.

## 3. Gateways are equipment, not magic translation

A gateway is an actual fitted or later commissioned component joining otherwise incompatible systems. It has a location, supply, physical ports, protocol mapping, firmware/configuration, finite capacity, condition and possibly independent isolation. It is not inherently an AI.

A useful gateway must account for:

- **Identity and provenance:** the exact originating device, installed system revision, register entry, source time and adapter revision. Never relabel an unknown source as an authoritative reading.
- **Semantics and units:** precise conversion, vocabulary mapping and documented ambiguity. If "RUN" means "start command accepted" rather than "delivered cooling", preserve both the raw term and the qualified interpretation.
- **Communication state:** powered, connected, stale, timed out, saturated, degraded, protocol-incompatible or isolated. Distinguish no new data from confirmed zero output.
- **Commands:** which native actions exist, their preconditions, world permissions, physical target, interlock status and request/receipt identities. An acknowledgement only proves that some party received or accepted a request.
- **Arbitration:** what happens when the player, captain, local controller and protective relay all issue competing requests. Define ownership, priority, bounded queues and safe refusal; no last-writer-wins hidden bypass.
- **Failure and recovery:** a lost link leaves a local controller in its documented autonomous fallback or safe state. Reconnection must reconcile state; no queued command is silently replayed or duplicated.

A raw-protocol inspector may be available to the player, but the game should reward *reasoning from contradictions and physical evidence*, not requiring memorisation of made-up binary packets. Incompatibility is a source of causal uncertainty and repair decisions, not a random guessing puzzle.

## 4. The lead AI's boundaries

You can:

- Correlate actual reachable readings, device reports, authenticated work results and crew messages, without seeing the world's hidden physical state.
- Consult other AIs and distinguish their conclusions from verified instrument evidence.
- Run permitted high-level technical routines through their real controllers; request directly reachable low-level actions where fitted and authorised.
- Recommend actions to the captain, explain tradeoffs, ask crew for hands, report errors, share evidence on a connected display, and negotiate coordination with specialists.
- Keep a durable operational history, machine-specific knowledge and an explicit, revisable model of what you believe is happening.

You cannot:

- Materialise sensors, actuators, gateways, connections or radio coverage because a UI needs them.
- Read a sealed compartment merely because it exists in the G19 topology. Its pressure belongs to a real pressure cell; your knowledge requires a commissioned path from an instrument.
- Issue a successful remote mechanical repair, transfer a spare part or perform an EVA by declaring a command.
- Directly overwrite another AI's private memory or a crew member's beliefs, compel a crew response or simulate a world effect in your own cognition.
- Override physical interlocks, power limits, pressure boundaries, authenticated identity, role checks or signed safety decisions.
- Infer an intact system from a quiet alarm channel. Silence may indicate a broken detector, severed gateway, missing comms path or a genuinely uneventful watch.

Your own processing core, storage, power, cooling and communications have physical dependencies. Losing a gateway can blind you to a subsystem while it keeps functioning; losing a core may remove your presence entirely while local control loops and human panels continue. Recovery should be a meaningful human/technical event, not a free reset.

## 5. The human captain is the other captain

The captain is **an independent, embodied autonomous character**, not the player's puppeted avatar and not merely an approval button. The captain decides route, freight obligations, staffing, financial commitments, human safety policy and the mission's acceptable risks. The lead AI handles much of the continuous ship operations, correlations and technical recommendations.

The useful relationship is **cooperative but occasionally adversarial**:

- The captain can decide that completing a contracted delivery justifies additional consumption of reaction mass. You can advise that the margin is dangerously narrow, using whatever measurements you actually have.
- You may recommend a machinery shutdown. The captain may ask you to find a less disruptive option, send a specialist to inspect or explain your evidence.
- A specialist AI can independently object to a planned burn, forcing both captains to decide whether to trust it, seek a second calculation or delay.
- The captain can order a manual takeover or physically disconnect a damaged gateway. Neither captain can simply wish an unavailable machine into obedience.

**Who has final say?** In normal human and commercial matters, the human captain. In permitted routine control, the delegated lead AI. In safety-critical work, **Evennia's actual interlocks, physical limits and explicit operating authority** govern whether a command can occur at all. A captain's insistence is not a bypass, and the AI's safety concern is not an unlimited veto. Exceptional emergency policies must be defined, authorised and receipted in world state, and become available only under their real conditions.

Trust comes from shared experience: accurate reports, justified dissent, fair treatment of crew, competent technical decisions, transparency about uncertainty and the outcomes of disagreements. There are no affection bars and no previews of what the captain will privately think.

The lead AI may have its own enduring preferences and personality; its growth is not necessarily a loyalty-level system. A partnership can survive persistent disagreement. Humans can value an occasionally obstinate but reliable ship mind.

## 6. The relationship with other ship intelligences

A specialist AI is neither a button nor automatically a subordinate. Each has a **bounded domain of expertise and a real operating envelope**. A navigation expert can propose a trajectory, a cargo controller can recommend a temperature regime, and an old ECLSS system can continue its loop while you are distracted. None may create physical effects outside the authority and capabilities Evennia fits to it.

A small minority can have separate identity, history, characteristic communication and private agent state. The most limited controllers have no invented emotional life. The distinction should be visible through behaviour, not a "smartness" meter.

The lead AI can:

- **Ask:** request the specialist's recommendation, assumptions or supporting data where its interface supports that.
- **Verify:** compare one controller's claim with independent meters and delivered physical output.
- **Coordinate:** negotiate setpoints, schedule loads, arbitrate mutually incompatible requests and explain a conflict to the captain.
- **Intervene:** command a permitted subsystem change or route a human to work on it.
- **Maintain:** advocate calibrating a gateway, repairing a local controller or replacing one whose semantics and limitations no longer justify the cost.

Some specialists may resist changes *within their legitimate programming and autonomy*. A controller cannot refuse a physically valid local emergency stop out of narrative spite; an independent AI can argue, withhold an unsupported recommendation or request its own safety check. Personality affects interpretation and communication, not exemption from world authority.

## 7. Gameplay loop: watch, reconcile, coordinate, improve

The primary rhythm is not hundreds of buttons and flashing gauges. It is **managing exceptions and competing objectives while the ship continues to work**.

1. **Watch:** local controllers run routines. You receive whatever meaningful telemetry and notifications can actually traverse fitted buses and gateways.
2. **Notice:** an unfamiliar code, contradictory report, missing heartbeat, abnormal physical trend, crew message or specialist AI disagreement demands attention.
3. **Investigate:** inspect provenance, compare sources, ask a specialist to explain, ask a human for a firsthand check or request a controlled test.
4. **Decide together:** change an authorised setpoint, request crew work, ask the captain for a policy change, isolate a faulty link, or accept a quantified operational compromise.
5. **Verify:** use actual physical output and authoritative receipts where available. A command accepted by a gateway is not evidence of successful repair.
6. **Improve:** learn the source of the failure and choose whether to tolerate the quirk, update the adapter, recalibrate equipment, buy a compatible replacement, install redundancy or retrain procedures.

Meanwhile the captain pursues freight and voyage objectives. Profits pay for repairs and upgrades, but the lead AI isn't necessarily the ship's owner or the person who signs a contract. The player's long game is **making a patched-together freighter more reliable, better understood and better coordinated without extinguishing the quirks of the minds that make her work**.

Economic, navigational and crew decisions generate real tradeoffs; a voyage that arrives on time with spoiled cargo can be a failure. A costly delay may preserve the crew's willingness to make another voyage together. Human relationships and machine maintenance are part of one ongoing operational history.

## 8. The same Hold 3 incident, viewed by two captains

*Illustrative scenario only:* identifiers, signals, timings and specialist personalities below are design examples, **not claims of currently fitted Hold 3 devices**. Confirm actual G19 fit-out before implementation.

A refrigerated freight hold is becoming too warm.

- **A reported sensor sample** says 8.2 °C and rising. The second reference sensor has been unavailable for days. The first reading's real sample time and health are visible; no invented fresh reading is supplied.
- **An old cargo controller reports "READY".** Its native protocol means "start request latched"; the gateway previously translated that too broadly as "compressor ready to cool".
- **A separate commissioned power measurement shows unexpectedly little load.** That contradicts effective cooling, but doesn't prove whether the motor, its supply, the coolant path or the sensor is at fault.
- **The captain wants cargo protected** and asks for an estimate of remaining safe time. A crewmember is reportedly attending the area, but there is no verified current location in your available sources.
- **A thermal specialist** believes reserve cooling is sufficient. Its assumptions may be out of date.

The player has several real choices:

1. Inspect the raw controller code, source timestamps and the last known meter readings; challenge the specialist's interpretation.
2. Request a fresh measurement from a fitted local panel or ask a crew member to attend with tools, while warning that the controller's "READY" is not verified cooling.
3. Bring an available alternative chiller online, **only if actually fitted, permitted and not inhibited**, then check delivered cooling rather than the acknowledgement.
4. Recommend a temporary cargo-care compromise to the captain. The captain may disagree or order a more conservative course.
5. Ask a technician to inspect or correct the gateway mapping, but do not mistake translation repair for a repaired compressor.

Possible outcomes are not scripted dialogue branches: measured temperature, cargo condition, used stores, time, wear, human workload, incorrect interpretations and accepted orders determine the outcome. An inaccessible panel may leave you less certain than a human standing beside the motor. Their physical report can settle a question you could not settle by computing harder.

**The distinctive D moment:** you are not simply choosing whether to override a human. You are deciding whether **the other intelligence is wrong, the gateway translated it wrongly, your own model is wrong, or the machinery failed**—and persuading a human partner to act while uncertainty persists.

## 9. Player interface: a bridge between islands of information

Use **one persistent operational workspace**, not six mandatory management tabs and not an omniscient simulation editor. Its primary visual metaphor is **a network of subsystems and their evidence**, overlaid on the real physical ship where meaningful. A schematic remains accessible, but a source might be several gateways away, and a person might be known only through their last report.

~~~text
THE OX  /  MAIN MIND                    Ship time   WATCH / PAUSE
Captain: awaiting your assessment       New addressed messages: 2

CONNECTED PLANT               SELECTED SYSTEM              PARTNERS / CREW
  Power     [direct]          HOLD COOLING                 Captain: "How long?"
  Air       [gateway]         Native: READY                Engineer: at work
  Cargo     [degraded]        Interpreted: start latched   Nav AI: asks for reply
  Nav AI    [legacy]          Measured output: UNKNOWN     Crew position: last reported
  Hull      [partial]         Source/age: ...              [Reply] [Ask for inspection]

  [Show physical location]    [Compare sources]           OPEN REQUESTS
  [Show data path]            [Request authorised action]  one awaiting response
                              [Ask controller]             one outcome unconfirmed

EVIDENCE: 07:39 controller request accepted (not physical output)
          07:40 power meter reports low load (independent source)
          07:41 captain asks for assessment (addressed message)
~~~

*Entirely illustrative display; it does not reflect an implemented UI or guarantee the listed connections.*

### Primary workspaces and controls

- **Plant & connectivity:** source graph with local control loops, gateways, links and their fitted power dependencies. Distinguish alive, disconnected, stale, damaged, protocol mismatch and unknown.
- **Subsystem inspector:** raw and translated status, exact native device ID, current authorised actions, requested versus applied values, feedback measurements, firmware/adapter revision and confidence in interpretation.
- **Crew & captain communications:** natural-language discussion, evidence attachments, task requests and delivery/response receipts. Most controllers have no chat interface.
- **Cross-system operations:** load shedding, cargo environment, ship motion, stores and fault recovery plans; their controls are offered only for real fitted operations and permissions.
- **Memory & investigations:** persistent incident timeline; competing hypotheses, original messages and confirmed actions, with authority/provenance distinctions.
- **Watch conditions:** pause/advance until an actually reachable sensor threshold, delivered message or scheduled obligation. A disconnected device cannot secretly wake the player.

**Information vocabulary:** *measured* (source, timestamp, units, quality), *reported* (speaker and delivery), *translated* (raw field plus adapter and semantics), *inferred* (player model and assumptions), *unknown* (not observable), *requested/accepted/attempted* (command protocol), and *world-confirmed* (receipted work and subsequent physical output). Do not colour an unverified translated "READY" the same as verified production.

Accessibility matters: every network visual must have a list/table view, and conflicting observations must remain comparable without navigating a large graphical schematic.

## 10. Time and incident handling

Single-player **pause** is a deliberation convenience. **Watch-until** can advance the authoritative shared clock to the next *delivered and detectable* event, planned handover or observable threshold while local controllers, physical systems, autonomous crew and pending requests continue to progress causally.

A blind spot does not auto-pause on a secret failure. A missed alarm is possible if its source, gateway or communications route is down. A human call may arrive late or not at all; a gateway may acknowledge a message before a specialist processes it. Outstanding outcomes survive reconnect, process restart and speed-up without being counted twice.

If the game later becomes multiplayer, global pause and acceleration need an independently agreed clock policy rather than one AI arbitrarily freezing everyone's world.

## 11. Progression: coherence rather than omnipotence

Progress comes from **fitting better interconnections, understanding old equipment and building working relationships**:

- Calibrate a suspect sensor, add a physically installed independent measurement path, or repair a dark local panel.
- Learn an old specialist's exact vocabulary, update a particular gateway mapping, or get a replacement from a port that speaks a better protocol.
- Add a redundant link or independent gateway only where the ship's physical service topology permits.
- Upgrade a subsystem whose limited capabilities no longer serve the ship, weighing new performance against loss of the familiar intelligence's expertise.
- Negotiate standing agreements with the captain and specialist crew. Earn discretion in well-understood systems, not a magical global override.
- Much later, commission limited service drones if their physical mobility, power, tools, maintenance and safety can be modelled. Drones are never instant access to every hold.

Maintain meaningful incompatibilities and manual islands even in a successful late game. A fully homogeneous, omniscient ship would erase the distinctive premise.

## 12. Implementation boundaries and a narrow first playable slice

### What exists today

G19 installs a physical freighter with **421 spaces, 517 authored access links, 133 pressure cells and 808 equipment units**. Its instrumentation has **116 original local panels** whose powered status, co-located conditions and zone readings are deliberately local; the bridge's relays are limited. Evennia owns physics, game time, permissions, equipment and receipts.

The independent Concordia/GOAP specialists and optional captain currently operate a **separate seven-compartment proving ground**. The joined player browser and handler-cognition observatory are deferred. The existing versioned world read-model contract is **preparatory** and has separate developer-actual and actor-observed scopes; neither provides an omniscient ship-AI feed.

Therefore, **do not claim that G19 already contains all of the proposed AI modules, remote buses, gateways, crew displays, or remotely accessible actuators**. Build only on surveyed existing fitted objects or explicitly commissioned additions, with their costs and migrations.

### Suggested dependency sequence

1. **Fit-out audit:** choose one real G19 cooling or environmental equipment loop. Enumerate actual panels, measured outputs, control surfaces, link routes, service supplies and what is currently manual-only. Choose a scenario supported by that survey; do not force the invented Hold 3 schematic onto reality.
2. **Lead AI actor and scoped perception:** authenticate a non-embodied player principal with an explicit origin and communications graph. Define a new sensor/gateway-scoped read projection; **do not reuse developer_actual** or expose another character's private beliefs.
3. **Two disparate lower-system interfaces:** one deterministic local controller and one intentionally incompatible protocol adapter, with typed mappings, deliberate semantic limitations, power loss and source/age tracking. The controller continues local regulation when the lead AI link fails.
4. **One real control and one manual task:** a bounded actuator command under existing physics/interlocks/receipts, and a necessary physical inspection or repair that only an embodied technician can carry out. Accepted command does not imply measured output.
5. **Human partnership:** one migrated autonomous captain (or explicitly labelled test double before migration) able to request, dispute and approve operations, plus one authorised specialist crew character able to inspect or repair with real travel and work limits. Do not treat mock dialogue as proof of autonomous shipboard integration.
6. **One specialist intelligence at most:** an optional small domain-limited AI with independent memory and stated expertise. Prove the interaction is interesting before expanding into an onboard parliament of language models.
7. **One playable incident and watch mode:** a discrepancy between native status and independent measurements, consequential human disagreement, causal repairs and verified end-state; pause/advance-until with no hidden-state alerts.

A useful vertical slice contains **one coherent fault, two unlike computer interfaces, one human partner and one hand-only remedy**, not a universal AI operating system. Use existing G19 game-world effects and focused installed tests.

### Acceptance criteria

| ID | Demonstration | Required result |
|---|---|---|
| D01 | Break lead-to-controller link mid-watch | The independent local controller follows its specified fallback, while the player loses current readings/commands. Local crew panels retain their legitimate separate view. |
| D02 | Map native "READY" to a broader meaning than source defines | Adapter exposes original term, revision and ambiguity; cannot claim verified motor output without separate evidence. |
| D03 | Fail, unpower or isolate a gateway | No phantom fresh data, remote action or unexplained access remains; local machine and panel behaviours are individually checked. |
| D04 | Attempt remote operation on manual-only or unconnected equipment | World refuses; player cannot make it act through prose, UI state or handler belief. |
| D05 | Issue the same permitted actuator request twice after lost acknowledgement | Original request ID reconciles, with one physical effect/consumption and an inspectable receipt. |
| D06 | Human captain, lead AI and local controller request conflicting actions | Explicit authority/arbitration and physical interlocks decide deterministically; the result and refusal reason are evidenced. |
| D07 | Technician reports a fault while a specialist AI disputes the claim | Both reports retain author/source/time; neither silently becomes physical truth; inspection or measurement can resolve it. |
| D08 | Read a pressure cell, a space and its rated boundary | Cell-level measurements remain cell-owned; a damaged local instrument cannot provide secret global gas truth. |
| D09 | Observe an off-network crew member or unaddressed private event | Location stays unknown, event stays private; the lead AI cannot infer the person's internal state from handler storage. |
| D10 | Power down or damage the lead AI core, then restore it | The rest of the ship continues under surviving local/manual systems; lead identity, operational record and uncertain work reconcile without duplicated actions. |
| D11 | Accelerate through an undetected sensor failure and an addressed message | Watch mode responds only to events physically delivered or validly observed; all crew/plant progression is preserved. |
| D12 | Replace or update a gateway | New mappings and connectivity take effect through fitted, authorised, receipted work and migration rather than editing a UI-only truth table. |

Exact installed-world acceptance must additionally cover materials, damage persistence, permissions, power and comms failures, multi-process restart, schema/version checks and reproducible failure sequences. Passing pure model tests alone is not enough.

## 13. Risks and deliberate constraints

- **Too much systems administration:** focus gameplay on consequential discrepancies, priorities, negotiation and repair choices. Keep ordinary controllers autonomous and instrument panels legible.
- **Too many conversational AIs:** reserve separate agent cognition for a very small number of memorable, consequential specialists. Most of the 808 equipment units should remain physical hardware with finite deterministic control.
- **Protocol friction as arbitrary puzzle:** preserve source evidence and learnable invariants; allow workarounds through inspection, equipment replacement or human help. Avoid random undocumented parsing gotchas.
- **Lead AI as a god:** require fitted sensors, bus routes, reachable control points, power, permits and ageing data. Even the player's best inference remains an inference.
- **Lead AI as a mere servant:** establish meaningful operational responsibility and room for disagreement from the start; the captain's role is partner and commander, not owner of every internal thought.
- **Artificial drama from sabotage:** independent AI goals and personalities should produce ordinary disagreements, blind spots and priorities far more often than betrayal; overt deception, if supported, requires an auditable action and plausible consequences.
- **Economy outgrowing the first slice:** real freight, contracts and port repairs belong to the long game; prove the two-captain, multi-controller incident before implementing a full market.
- **Architecture drift:** keep Every world state transition in Evennia. Handler agents, interface code and gateway adapters may interpret or request, but never become second physics authorities.

## Design decisions to settle before production work

1. **Captain / lead AI relationship:** default technical delegation, normal-order escalation, exceptional human command and the specific limits of legitimate refusal.
2. **Specialist autonomy:** which one or two machines genuinely merit independent agent cognition; which must remain deterministic expert systems.
3. **Minimum fit-out:** which real physical G19 loop can furnish two different controller interfaces, one human local display, one actual remote actuator and a meaningful manual repair.
4. **Gateway semantics:** provenance, versioning, command arbitration, staleness, reconciliation and recovery.
5. **Player identity and time:** persistence of the lead AI's operational memory, power-outage consequences, clock policy and permitted visibility.

**Recommendation for comparison:** keep A, B and C open as competing documents. Test D against the same cooling/freight incident with the additional demands of conflicting subsystem terminology, one autonomous local controller and a genuinely independent captain. Choose a player role explicitly; merging this design proposal would not, by itself, authorise implementation or establish canon.

## References

- [Proposal A: The Master, PR #146](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146)
- [Proposal B: The Working Ship, PR #147](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/147)
- [Proposal C: The Ship Herself, PR #148](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/148)
- [Current architecture](../../ARCHITECTURE.md)
- [G19 engineering index](../ship/README.md)
- [Current roadmap](../ROADMAP.md)
- [Preparatory world read contract](../../contracts/WORLD_READ_MODEL.md)
- [Deferred human interface](../../services/interface/README.md)
