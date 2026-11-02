# Proposal B: The Working Ship

**Status:** competing design proposal, 2 November 2026; **not accepted or implemented**.  
**In response to:** [PR #146, *The player as Master of the Ox*](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146), including its six-screen concept.  
**Scope:** the player's place in the world, core experience, interaction model, interface and a testable first gameplay slice. This is a product design, not a claim that the deferred browser observatory or the commercial game loop exists today.

## The decision

**You own (or are paying off) an old working freighter, and you live and work aboard her.** You are ordinarily the captain and responsible for the business. But you are also a *real character in a real compartment*. You can go to the machinery, use a panel, perform permitted work, question someone face to face, or delegate everything you reasonably can.

**The ship, not the captain's desk, is the main play space.** The player can manage from the bridge, but being present somewhere has consequences, and knowing a measurement is different from knowing what is wrong.

A useful shorthand:

> **PR #146:** "I tell the crew what must happen."  
> **This proposal:** "I have a ship to keep operating. I decide what to handle myself, what to entrust to others, and what risks the business can bear."

The default role is **working owner-captain**, not a god, incorporeal ship intelligence or micromanaging industrial executive. Other starting roles might be interesting *later*, but should not dilute this initial design.

## What to retain and what to reject from PR #146

| PR #146 idea | Decision for Proposal B | Reason |
|---|---|---|
| Autonomous crew have their own minds, histories and mistakes | **Keep** | The crew's independence is the central distinction from a conventional engineering game. |
| Instrument and report provenance; imperfect knowledge | **Keep and make more rigorous** | World data reaches the player through an instrument, observation, report, or authorised log, never a hidden-state oracle. |
| No mood or personality bars | **Keep** | Behaviour, firsthand interactions, recorded qualifications and consequences communicate character. |
| The player cannot physically operate any machinery | **Reject** | It sidelines Ox's installed spatial and engineering simulation and makes every interaction wait on an agent. |
| A universal order-latitude slider and personal-risk slider | **Replace** | Use explicit goals, safety limits, time horizons, interruption rules and reporting requirements; risk is not a magic permission variable. |
| Forecasting how a named crew member will react | **Reject as default** | That would disclose or impersonate private cognition. Show task feasibility and observable constraints instead. |
| Six permanent management tabs | **Replace** | Make a persistent, location-aware ship workspace with contextual stations and task views. |
| Pause / 1x / 10x / 60x / 600x as a universal game promise | **Replace** | Use event-based advancement with causal crew and system clocks. Acceleration is a convenience, not teleportation through consequences. |
| A delivery deadline as the chief win condition | **Expand** | Each contract is a job; continuing as a solvent, operable, trusted independent hauler is the game. |

This is not a claim that the original is badly conceived. Its **crew-centred uncertainty** is excellent. The disagreement is about where player agency, navigation and the long-term loop belong.

## Five game pillars

### 1. Aboard, not above

The player has location, access rights, carried items, exposure and limits. A pressure boundary is a real boundary. An unsuited person cannot simply click an EVA destination; a machine needing isolation is not restored by authoring a work order. The player can attend a job personally, *when physically possible and qualified*, or send another character to do it.

Do not turn every hand-tool operation into a repetitive minigame. A contextual worksite presents valid procedures and the evidence needed to take them; Evennia determines whether the work was authorised, consumed supplies, took time and succeeded. The player can choose the amount of active involvement.

### 2. Delegation is powerful, not compulsory

Most successful voyages should involve substantial delegation. A competent crew takes routine watches, preventive rounds, stock transfers and maintenance without repeated player clicks. A short-handed or badly coordinated crew cannot do everything at once.

A dispatched instruction specifies an **objective** and its boundaries, not someone's emotions. An autonomous character can misunderstand, disagree, ask for clarification, work at a different pace, find a new problem, or decline an unsafe instruction. The player can respond by improving information, changing the job, reassigning it, helping, or accepting the consequence.

Player involvement therefore has a meaningful cost: while the captain is crawling through a service space, another decision might arrive on the bridge.

### 3. Incomplete information is playable

Knowledge is acquired through **local senses, commissioned instruments, authenticated messages and the log of actual work**. Show the reading, unit, source, observation time, availability and whether it is historical. An observation can be wrong without the game showing the player a secret correction.

Use the 133 pressure cells as physical entities with room membership and boundary/link states. Do not paint identical pressure values onto individual rooms as though they were independent measurements. A damaged or dark panel does not silently provide fresh readings.

A player can compare reports, go to a second instrument, ask a person to inspect, or work on an incomplete diagnosis. This is an investigative game mechanic, not just an information-warning badge.

The developer's actual-state observatory remains **separate** from the player's authorised view. A crew member's private belief is not a public telemetry field.

### 4. A ship that earns her keep

The operating loop is **freight and operations**, not a single prewritten crisis:

1. At a port, compare offers, cargo constraints, deadlines and likely expenses; accept or decline a job.
2. Inspect the ship, provision, allocate stores and crew work, prepare holds, load and secure the freight.
3. Choose a voyage plan and reserves; depart with real mass, fuel, power and machinery consequences.
4. Run watches and deal with failures, discoveries, fatigue, maintenance, human disagreements and incidental opportunities.
5. Deliver, settle accounts, repair, pay the crew, replenish supplies and choose what can be afforded next.

A cargo contract can be completed *unprofitably*. Arrival can be late but survivable; a costly repair can protect a larger future income; taking a dangerous shortcut can permanently cost the ship or its people. Outcomes should arise from verifiable state and contract terms, not arbitrary narrative punishment.

**Long-term progress** is continued financial and operational viability: debt, condition, commercial reputation, qualifications, crew retention, improvements and the ability to take better work. There need not be a universal "You Win" screen. Selling the ship, retiring solvent or losing her are intelligible endings; ordinary play is open-ended.

### 5. Causal rather than certification-grade engineering

The ship is a working-class hauler, not a NASA trainer. The systems should remain connected: loss of cooling can spoil cargo; additional electric load can alter reserves; a sealed hatch stops movement of people or gas according to actual state; damaged equipment stays damaged until restored.

Expose the effects that make decisions meaningful. Hide numerical machinery detail that offers no practical choice. More gauges alone do not produce a better game.

## Player actions: three deliberately different paths

**Act personally.** Travel through real exits to a worksite. Inspect local panels, fetch tools, isolate, conduct a permitted procedure, observe the resulting output. Skill, time, PPE, authorisation and physical state matter. The interface may present a concise interaction rather than requiring typed technical commands.

**Delegate a job.** Send an objective, priority, scope, deadline and report-back criteria to a person or team. The request may be delivered, accepted, questioned, underway, blocked, abandoned or completed. No "accepted" message certifies that a machine is working: that requires an actual world effect and subsequent measurement or receipt.

**Set an operating policy.** Define ordinary limits (reserve thresholds, permitted watch actions, cargo temperature bounds, escalation rules). Policies authorise or direct future *work*, rather than remotely changing a valve or guaranteeing that somebody complies. Safety-critical exceptions require explicit world-authorised procedures; a "high personal risk allowed" slider cannot bypass interlocks or force acceptance.

All three paths feed the **same Evennia-owned physics and transaction ledger**. The handler may propose actions and keep private beliefs but cannot create work effects by declaration. Unknown results reconcile by the original request ID; the UI must show "unconfirmed" rather than silently retry a consumable operation.

### Example: a chilled hold warms

The player's panel shows a *last measured* hold temperature and its instrument age. A log indicates a coolant problem, but its cause is not known.

- **Direct:** travel to the relevant panel, check it, investigate the service path, and restore the affected machinery if qualified and equipped.
- **Delegate:** ask Mara to diagnose the chill failure, tell her not to open the cargo boundary without a pressure check, and require a post-restart temperature sample.
- **Policy:** establish a standing requirement that a hold-temperature alarm prompts a local verification and an addressed report.

Each path spends different combinations of player time, crew time, spare parts and risk. A damaged sensor may mean the first decision is **whether to trust the alarm at all**.

## The interface: one ship, several workspaces

The primary screen is not six equal management pages. It is an **operations workspace** that changes with location and active task. A map is navigation and work context, not an all-seeing 3D model.

### Persistent frame

- **Top bar:** ship time, simulation state, current player location, connectivity/observability, urgent *known* events, current job and communications.
- **Left:** schematic or deck graph centred on the player's known location. Routes show known access, required transfers and relevant obstructions; unexplored or unobserved conditions remain unknown.
- **Centre:** local space and *available* panels/actions. At the bridge this is command/navigation; at a machine it is its instruments and procedures; at a cargo station it is manifests and handling.
- **Right:** addressed communications and a small actionable work queue: needs response, waiting on others, underway, unresolved outcomes.
- **Bottom/drawer:** chronological event and evidence log with timestamps, source, freshness and receipt provenance; selectable to compare observations.

Illustrative textual layout (not a built mock-up):

```text
OX OF HEPHAESTUS              DAY 41 07:42  |  1x / ADVANCE
YOU: Engineering Control       Incoming: 2  |  Job: Hold 3 cooling

SHIP / KNOWN ROUTES         LOCAL STATION              COMMS & WORK
Bridge -- ENG CONTROL       Panel LP-...               Mara: "Need a seal"
             |               Last sample: 07:39         Iona: Burn review
         HAB access         Feeder: isolated           Hold 3: Awaiting check
             |               Work options:
         Cargo gallery        [Inspect] [Test]          [Assign] [Answer]
             |                [Travel] [Request aid]
           Hold 3

EVENTS / EVIDENCE  07:38 Hold temperature reported high (panel, stale)
                   07:41 Mara requests seal (addressed message)
```

**All labels and readings above are illustrative.** They do not assert the
existence of a matching UI, event feed or commissioned panel at this site.

### Task-oriented workspaces

| Workspace | What is meaningfully different here |
|---|---|
| **Ship / Local** (default) | Traverse, inspect, interact, see compartments, pressure cells and permitted local hardware; issue work from the selected object |
| **Operations / Bridge** | Watch status, burns, course, energy priorities and known alarms, each bound to actual consoles and available measurements |
| **Crew & Dispatch** | Address messages, make assignments, review reports, schedule coverage; no global private-emotion inspector |
| **Cargo & Accounts** | Freight tenders, contracts, shipboard custody, lashing, hold conditions, payables, repairs and the voyage's financial outcome |
| **Log & Evidence** | Who observed what, when; conflicting testimony; acknowledged vs physically verified work; search by incident and receipt |
| **Personal / Kit** | The player's location, carried equipment, access qualifications, exposure, rest and active work |

These need not be separate full-page destinations. Open a contextual inspector when a panel, person, contract or issue is selected. Preserve the state of an interrupted task when the player attends to a new message. Support a text/list view of the same route and controls rather than forcing a complex wireframe.

### Information grammar

A displayed fact should be categorised rather than presented as anonymous global truth:

| Display | Meaning |
|---|---|
| **Measured** | Actual authorised instrument sample with source and game-time timestamp |
| **Reported** | Someone's statement, with sender and delivery time; not independently confirmed |
| **Observed directly** | The player's local observation, bounded by position and available senses |
| **Inferred** | A clearly labelled estimate, its premises and uncertainty; never hidden world truth |
| **Unknown / unavailable** | No valid evidence, lost signal or inaccessible instrument |
| **World-confirmed work** | A receipted action or actual observed equipment output, **not** a crew promise |

The UI must distinguish a machine's current condition from a crew member's old belief, and an action receipt from an observed successful restoration. A drawing only overlays a world state when topology and fitted-engineering model versions actually agree. Source inventories recorded in tonnes are converted to kilograms at the projection boundary; legacy fuel inventory rows are not added to the motion ledger's operational balances.

## Time, autonomy and interruption

**Simulation time is a scheduling feature, not a source of arbitrary emergencies.** Offer pause, normal progression and *advance until*: next known watch change, arrival at a known destination, an expected report or a material **delivered** event. Ordinary high speed is allowed only when the world can advance all systems and autonomous decisions under a coherent shared game clock.

- Never auto-pause because a *secret* fire exists if no character or valid sensor has discovered it. A trigger based on a delivered alarm or an objectively scheduled deadline is legitimate; unpublished hidden state is not a notification.
- Preserve realistic operation durations, travel, crew rest, communications, instrument age, repair stages, physical consumption and action-receipt reconciliation across accelerated time.
- If a player is reading a long report, pausing a single-player game is a user convenience, not a statement that crew can speak for hours instantaneously.
- If Ox later permits multiple human players in the same ship world, no individual player can globally pause or fast-forward everybody else's universe. This requires a separate multiplayer time policy.

A universal 600x setting is neither necessary nor excluded as a future optimisation. The first player-facing time control should be **"Advance until the next consequential, known event"**, with an inspectable reason for stopping.

## Character presentation and relationships

Show roles, duty, *reported* whereabouts, verified qualifications, history and observable behaviour. The player may talk by local conversation or addressed radio, but social exchange is **not** a compulsory gate on ordinary maintenance.

Do not print private mood, attachment, loyalty or exact intention values. Avoid "Mara will probably refuse" predictions derived from handler internals. Instead an order inspector can display factual operational limitations: travel may take time; a required tool is unaccounted for; the person is last reported on another job; an independent safety review is required.

Relationships matter because they alter future decisions and willingness to cooperate, not because a captain can optimise affection meters. A good crewmember is still allowed to disagree. Friendship should not suspend the physics of a punctured pressure cell.

## The first playable hour

Start **at a berth**, not in an abstract strategic crisis queue. Offer a modest, tangible job that teaches the complete loop:

1. **Accept:** review one freight contract, cargo-care requirement and operating margin.
2. **Prepare:** inspect a hold and the machinery needed to protect its cargo; delegate loading and verify its result.
3. **Depart:** choose a reserve-conscious course, observe the physical departure gates, and begin the first watch.
4. **Encounter:** a cooling alarm appears, but its originating instrument is stale. A crew member reports a conflicting diagnosis.
5. **Choose:** travel and inspect; request a second reading; or delegate a diagnosis while handling another obligation.
6. **Resolve:** an actual repair consumes time and material, requires access and produces an authoritative work result. The hold's temperature trend subsequently changes, or does not.
7. **Settle:** finish the leg or port call, observe a cargo outcome and settle money, spares and crew obligations.

The player should be able to understand three distinct costs: **ship resources, human attention and commercial opportunity**. The first hour needs a *choice* between doing and delegating, not twenty systems requiring simultaneous babysitting.

## A deliberately small implementation slice

This design proposal does not claim that the combined human interface, full-ship autonomous crew or freight economy is deployed. The current installed G19 ship has 421 rooms, 517 authored links, 133 gas cells and 808 fitted equipment; Concordia/GOAP specialists are still being migrated from their smaller fixture.

Suggested vertical slice, in dependency order:

1. **Player presence:** one authenticated ordinary human character, located on the installed G19 ship and subject to the *same* traversal, suit, worksite and permission gates as crew. Developer entry is not a game mechanic.
2. **One instrumented fault:** authoritative cell/equipment evidence visible at an actual worksite, plus a remote/report view with explicitly stale data and proper version and provenance checks.
3. **Two valid solutions:** the player can carry out one bounded physical correction locally or issue the same objective as a crew job through the existing actor-local capability and work-receipt infrastructure.
4. **One autonomous specialist:** migrate the relevant AI worker and its travel, observation, repair and post-restart confirmation, including interruption and unknown-outcome reconciliation.
5. **One accountable tradeoff:** a simple freight job with a measurable cargo-care requirement, finite supplies, time cost and end-of-leg settlement. Full markets, depreciation, insurance and social complexity can follow.
6. **One honest time control:** pause/advance-until delivered event, with all world and agent clocks, active jobs and causality accounted for.

Do not begin with the full 421-room interactive renderer, all crew professions, a giant game economy or a general-purpose chat interface. Make the *one-machine / one-crew / one-contract* experience engaging first, then broaden.

### Acceptance tests for the product concept

- Human and NPC may both physically attend the same worksite; neither can skip interlocks, missing tools, limited supplies or actual travel. Player action and delegated action produce world-origin evidence, not independent UI truth.
- A stale/dark sensor genuinely withholds current knowledge; the player can choose a second observation rather than having the interface reveal a hidden cause.
- Pressure is shown as a cell-level phenomenon associated with real rooms and boundary links, not invented per-room values. The player cannot see developer-only events or another person's private cognition.
- Work orders show submitted, acknowledged, attempted, blocked and verified states distinctly. Losing a response does not duplicate consumed materials after a restart.
- A tired or occupied crew member changes the real timing of a job, with a valid reassignment or direct-action alternative.
- Cooling restoration changes physical output and then observable cargo care. Contract resolution records the actual consequence, including an unprofitable success.
- Acceleration does not skip a previously addressed alarm or claim a delivered message that no observer could receive.

## Costs and risks of this alternative

**It is a wider game.** Physical presence, a useful ship map, hands-on work and an economy demand more integration than a captain-only dashboard. The remedy is a narrow vertical slice, not pretending the broader systems are already ready.

**It can become micromanagement.** Make routine work delegatable, give crews standing duties, use exception-driven attention and reduce repeated procedural clicks.

**It can overwhelm players with machinery.** Present actionable effects, local constraints and verified next steps; offer technical drill-downs when needed. Keep a usable list/text route alternative.

**It can make the captain too competent.** Authority is not expertise. The captain starts with finite skills, cannot certify his or her own prohibited safety steps and can recruit specialists. A good choice may be to keep hands off.

**It can make social play optional to a fault.** Crew relationships should still materially shape reliability, information exchange, willingness to re-sign and shared history, even when the player prefers work to extended conversation.

## What this proposal asks us to choose

Prefer **an embodied, financially responsible owner-captain with optional hands-on intervention and serious delegation**, over a remote "Master" whose only instrument is an order. Make **the working ship and its unfolding freight business** the through-line; let personal relationships and autonomous decisions emerge from actual work.

Use PR #146's strongest principles—crew autonomy, imperfect knowledge, behaviour instead of emotion bars—but do not accept its *commands-only* premise or its universal sliders as the foundation.

**No acceptance or merge of PR #146 is implied by adopting this document for comparison.** The two proposals should be tested against the same simple cooling/freight incident before selecting a player-experience direction.

## References

- [Original competing player-role proposal (PR #146)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146)
- [Current ship engineering and inventory](../ship/README.md)
- [Current roadmap](../ROADMAP.md)
- [Architecture and authority](../../ARCHITECTURE.md)
- [Deferred human interface](../../services/interface/README.md)
- [Typed world read model](../../contracts/WORLD_READ_MODEL.md)
