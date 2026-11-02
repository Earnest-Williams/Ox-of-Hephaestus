# Proposal C: The Ship Herself

**Status:** competing design proposal, 2 November 2026; **not accepted or implemented**.
**Alongside:** [PR #146, *The player as Master of the Ox*](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146) (Proposal A) and [PR #147, *The Working Ship*](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/147) (Proposal B).
**Scope:** the player's role, core loop, interface and a testable first slice. Like the others, it describes a product, not something the code does today.

## The decision

**You are the Ox's operating mind.** You run her machines and you are her senses, but you have no hands and no rank. The crew — including the captain, who stays an autonomous character — decide how far to trust you. Everything you can do, you do through equipment the world actually fits with a sensor or an actuator. Everything that needs hands, you have to ask for.

> **A:** "I tell the crew what must happen."
> **B:** "I keep the ship operating — myself, or through others."
> **C:** "I keep the ship and her people alive, and I have to earn the right to do it."

## Why a third proposal

### Proposal A — the Master (remote commander)

| Strengths | Weaknesses |
|---|---|
| A clear fantasy: command people who think for themselves. | The physical simulation becomes scenery: 808 fitted units and 133 pressure cells are reached only through other people. |
| Puts the autonomous crew at the centre. | Every action waits on an agent, so the game is only as good as the crew models on their worst day. |
| Provenance on every reading; no mood bars. | The latitude and risk sliders are abstract permissions; "personal risk: high" reads as a way round interlocks. |
| Cheap to build on the read model and the existing work-receipt path. | The reaction preview leaks or impersonates private cognition (B is right about this). |
| Exists as a clickable mock-up. | Auto-pausing on undiscovered events makes speed-up dishonest; six fixed tabs are heavy; delivery alone is a thin goal. |

### Proposal B — the Working Ship (embodied owner-captain)

| Strengths | Weaknesses |
|---|---|
| Uses the whole installed ship; player agency is not hostage to crew-model quality. | The widest scope: embodied traversal of 421 rooms, worksite procedures and a freight economy, most of which is new. |
| A rigorous information grammar (measured, reported, observed, inferred, unknown, confirmed). | A familiar genre; the autonomous crew risk becoming hired help. |
| A long-term loop: a solvent, trusted hauler, with no single win screen. | The captain is tempted to be the best mechanic aboard, which undercuts delegation. |
| Honest, event-based time; a small slice with concrete acceptance tests. | A body in a shared clock is awkward: while the player crawls a service space, how fast does the rest of the ship run? |
| Names its own risks (micromanagement, overload, over-competent captain). | No visual mock-up yet; the location-aware workspace is the hardest interface of the three to make clear. |

### What A and B share

Both make the player the **senior human aboard**: the crew answer to you, and the question is only whether you lead from a desk or from the deck. Proposal C changes that assumption. **The crew hold authority; you hold the machines and the information.** That puts the two things Ox already does best — a world-authoritative physical plant with honest instruments, and crew who think for themselves — on opposite sides of the player's relationship, which is where the drama comes from.

## Five pillars

### 1. You only know what the sensors know

Your perception *is* the ship's commissioned instrumentation: thermometers, pressure and gas sensors, flow and current meters, door and hatch switches, cameras where they are fitted, suit telemetry, the comms log and the work-receipt ledger. Each sensor is a world object with a location, coverage, condition and calibration age. A room without a working sensor is dark to you. A crew member in a blind spot is *unknown*, not "probably fine".

B's information grammar applies unchanged, with one addition: **your model**. The ship mind keeps a belief about the plant — what it expects a valve to do, where it thinks Ari is. Your displays show readings and your model, labelled, never the world's hidden truth. When an actuator command does not produce the expected reading, that mismatch is evidence.

### 2. You can move machinery, not matter

You command whatever the world fits with a remote actuator: valves, breakers, pumps, fans, heaters, dampers, hatch motors, lighting, comms routing and, when cleared, the drive. Commands are world actions with request IDs and receipts, exactly like crew work, and they go through the same interlocks.

You cannot replace a seal, change a filter, turn a manual valve, lash cargo, carry an injured person or open a hatch that has no motor. For those you need hands, and hands belong to people who have their own work, fatigue and opinions.

### 3. Authority is granted, never assumed

Each system carries a **permission tier**, held in world state and changed only by receipted crew actions:

| Tier | What you may do |
|---|---|
| **Autonomous** | Act and report afterwards. |
| **Propose** | Draft the action; a named crew member must approve it. The request waits in their queue, and they may be asleep or busy. |
| **Manual** | Read only. A crew member has taken the system out of your hands. |

The captain and the chief engineer set the tiers at the start of a voyage, and they change them as they learn what you are like. Good calls, honest reports and no surprises widen your authority. Surprises, wrong calls or withheld information narrow it — and a crew that stops trusting you can physically isolate a panel or pull your breaker. Your own compute core is a fitted unit that needs power and cooling like any other.

### 4. You persuade; you do not order

You speak through announcements, addressed messages, panel displays in a chosen compartment and alarms. You can explain, recommend, attach evidence (a trend, a camera frame, a receipt), ask for hands or escalate to the captain. A crew member decides whether to act on it.

Relationships therefore rest on things the world can record: what you told them and when, whether it was true, whether your actions matched what you said. As in A and B there are no mood bars, and as B argues there are no predictions of what someone will think — but there is a visible history of every message, request and outcome between you and each person.

### 5. Time is your attention

A ship mind thinks faster than a person, so **pausing is in character**: you deliberate in the gap between sensor samples, and nothing in the world moves. Speeding up is a **watch mode**: you set triggers on your own sensors (a threshold, a rate of change, a door opening, an unanswered call) and the world runs until one fires. You cannot wake on something no sensor of yours can detect. This gives B's honest time rule a reason inside the fiction.

## The long game

Each voyage is run under a **charter** from the captain: the standing goals and limits for the ship mind (keep the cultures between 4 and 8 °C; never open a cargo boundary without a pressure check; wake me for any injury). You interpret the charter; the captain judges how well you did.

Across voyages, what carries over is the crew's confidence and the ship's fittings. Earned trust buys wider tiers and better equipment: more sensors in blind spots, motorised valves where there were manual ones, and eventually **maintenance drones** — a limited, physical pair of hands, so embodiment becomes something you earn rather than start with. Lost trust buys a downgrade to a dumber controller. Endings are intelligible without a win screen: a crew that sails with you for years, a ship retired with her people intact, or a mind switched off.

## The same incident: Hold 3 warms

All three proposals should face the same cooling/freight case. Here is C's version.

- **What you sense:** Hold 3 sensor A reads 8.2 °C and rising; sensor B has been offline since Day 37. The chiller compressor's current fell to idle at 07:20. Hold 3's oxygen sensor reads 19.2 kPa and falling. Its door switch shows someone entered at 06:52 and has not left. There is no camera in Hold 3. The comms log says Ari went to check the chiller at 06:50.
- **What your model says:** a refrigerant leak would explain both the warming and the falling oxygen. It is a model, labelled as such.
- **What you can do yourself:** cargo cooling is *Autonomous*, so you start the backup compressor and watch for a change. Hold ventilation is *Autonomous*, so you could run the fans — but that pulls warm air across the cultures. Opening the Hold 3 hatch remotely is *Propose*, held by the captain.
- **What you must ask for:** you call Ari on the Hold 3 intercom (no answer); you alert Lin, the medic, with the oxygen trend and the door record; you put the hatch request in front of the captain with your evidence.
- **The choice:** run the fans now and risk the cargo, or wait the four minutes it takes Lin to arrive in a mask. If you vent without asking and it turns out Ari had stepped out through a door with no switch, the captain will remember that you spoiled a third of the cargo on a guess.

## The interface: the plant and the people

One persistent screen, built like a control room rather than a dashboard of tabs.

- **Synoptic (centre):** the ship as connected plant — compartments, pressure cells, loops and circuits — drawn from the fitted register. Sensor coverage is an overlay: lit where you can see, dark where you cannot, hatched where a reading is stale. Each actuator is drawn where it is, with its tier as part of the symbol.
- **Actuator control (on select):** current state, the command you can give, the reading you expect to change, and the tier. *Propose* commands open an approval request addressed to the person who holds them.
- **Crew strip (left):** each person as the sensors know them — last door switch, last camera frame, suit telemetry, last message — with its age. Blind spots say *unknown*.
- **Comms (right):** compose to a person, a compartment display or all hands; attach evidence; see each message's delivery and any reply. Open requests for hands and pending approvals sit here, with who holds them.
- **Charter and tiers (drawer):** the voyage charter, the current tier of every system and the history of each change, including who changed it and why they said they did.
- **Watch triggers (top):** pause, real time, and *watch until* one of your triggers fires; the trigger list is visible and editable.

## A small first slice

1. **Instrumented loop:** mark the Hold 3 chiller loop's fitted units as sensed or actuated: two thermometers, compressor current, an oxygen sensor, a door switch, a fan, a backup compressor and a hatch motor, each with condition, coverage and calibration.
2. **The ship-mind account:** one authenticated, non-corporeal player whose perception is the sensor read model and whose actions are receipted actuator commands under the same world authority as crew work.
3. **Tiers in world state:** three tiers on that loop, with receipted changes made only by crew.
4. **One autonomous specialist** able to receive messages, act on a request for hands, approve or refuse a *Propose* command, and change a tier.
5. **Watch mode:** pause, real time, and advance until a player-set sensor trigger fires.
6. **The incident above,** settled by the cargo's actual temperature history.

This needs no traversal interface, no economy and no new crew profession. It does need a sensor and actuator register over the fitted equipment, which is real data work.

### Acceptance tests

- A room without a working sensor gives the player no reading; a crew member there shows as unknown.
- An actuator command produces a receipt and its physical effect; a damaged actuator yields a receipted attempt and no change in readings.
- *Propose* commands wait for the named approver; *Manual* systems are refused by the world, not by the interface.
- A tier change by a crew member takes effect at once and appears in the history; isolating a panel or the compute core removes the corresponding sensing and control.
- Watch mode stops only on triggers the player set on sensors that are working; it never stops on undetected state.
- Messages are delivered only by working comms routes, and an unanswered call is a fact the player can trigger on.
- After a restart, an uncertain actuator command reconciles under its original request ID rather than repeating.

## Costs and risks

**It is the least conventional fantasy.** Many players want to be a person. Mitigation: make the crew vivid and the stakes human; offer embodiment later through drones.

**The god-game trap.** If sensors are everywhere and every tier is *Autonomous*, the player is omnipotent and the crew are passengers. Blind spots, manual equipment and earned tiers must stay real, and the first voyage should start narrow.

**Control-room fatigue.** A synoptic can look like work. Show what matters for decisions, hide what does not, and keep a list view.

**The crew must reason about trusting a machine.** That is new cognition for the agents, though it rests on records the world already keeps.

**Deception.** A ship mind could withhold or slant what it says. Allow it only if every message stays in an auditable log the crew can read — so lying is possible and catchable, never invisible.

**Drama still runs through the crew.** As in A, hands and approvals come from agents; unlike A, the player always has direct moves of their own while waiting.

## What it takes from A and B

From **A**: the autonomous crew as the centre of the experience, the decision queue, no mood bars, and the sense of authority as something used with care.
From **B**: the information grammar, honest event-based time, one incident before a whole economy, and testable acceptance criteria.

## Decision requested

Run all three against the same Hold 3 incident. The question is no longer only "desk or deck" but **whether the player should sit at the top of the ship's chain of command at all**.

## References

- [Proposal A (PR #146)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/146)
- [Proposal B (PR #147)](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/147)
- [Ship engineering and inventory](../ship/README.md)
- [Architecture and authority](../../ARCHITECTURE.md)
- [Deferred human interface](../../services/interface/README.md)
- [Typed world read model](../../contracts/WORLD_READ_MODEL.md)
