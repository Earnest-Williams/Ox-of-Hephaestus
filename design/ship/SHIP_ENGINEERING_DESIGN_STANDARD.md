# Ox of Hephaestus — Ship Engineering Design Standard

**Status:** authoritative design philosophy for this fictional ship and its ship-only engineering models, candidate releases, documentation, validators and simulation scenarios. Applies to the prepared v0.4 world and subsequent v0.5+ proposals. This is the standard by which we decide that the *fictional ship design is sufficiently resolved for the game*.

## Our goal is verisimilitude, not NASA approval

**The Ox is a fictional, long-serving working bulk freighter for an autonomous-crew MUD and ship simulation. We are designing an internally credible, consequential ship, not an actual spacecraft to build, certify, insure, launch or present for NASA, ESA, a classification society, or a licensing authority to approve.**

A realistic-sounding diagram by itself is not sufficient; operating the ship must make sense. Equipment has a physical location and receives power, working fluid, access and control from somewhere. Rooms have boundaries, movement costs time, maintenance needs people and tools, reservoirs run down, faults propagate along real connections, and a damaged component can force a sensible but painful compromise. Characters see imperfect evidence of those facts and can make mistakes. These are **gameplay and narrative fidelity requirements**.

The ship is not limited to technologies we could qualify or manufacture today. Explicitly fictional propulsion, materials, heat rejection, fuel economy, or other established setting technologies may have selected fictional performance. We make those assumptions visible and propagate their consequences consistently; we do **not** demand real-world proof of feasibility before proceeding with the fictional design.

## What counts as engineering closure

For a play-relevant space, subsystem or operation, closure requires *enough* detail to answer these questions at useful resolution:

1. **Where is it?** Its space, parent structure, access route, pressure environment and movement/handling constraints are identifiable.
2. **What supplies it?** The relevant power, fluids, atmosphere, cooling, communications, controls, consumables and upstream isolation paths are coherent at the level the simulation uses.
3. **How is it run and serviced?** Startup, shutdown, local control, access for repair and sensible time/tool/crew constraints are described when consequential.
4. **What can fail?** Loss of power, breach, smoke, broken control, jammed valve, empty inventory, mislabelled refit, or failed auxiliary has a distinct, bounded consequence. Redundancy requires an actual alternate route or store.
5. **What can the crew know?** Sensed, inferred and documented information are distinct from actual world state. A healthy panel indicator cannot conjure a working valve.
6. **What choices emerge?** A credible incident can force isolation versus access, smoke containment versus ventilation, power shedding versus equipment operation, or repair exposure versus casualty progression.

Select a representative calculation or deterministic test when it helps establish **consistency**, mass/energy/inventory accounting, capacity margins, failure propagation and qualitative response ordering. Round or bound uncertain quantities. The numbers are scenario assumptions or reference design values until the game has an authoritative as-installed state; they are not claims of certified engineering performance.

**Stopping rule:** once the relevant spaces, causal dependencies, failure states, resource budgets and operational choices are coherent enough to play and test, **adopt that design**. Do not stall waiting for a finite-element model, acoustic/thermal CFD, stress-cycle certification, NASA-grade requirements verification, full fabrication drawings, shaft-bearing contact analysis, every fastener and seal tolerance, or a real-world airworthiness/safety certificate. Such work is out of scope unless it resolves an actual contradiction or materially improves play.

## Priorities when detail competes with play

Use this order:

- **First — internal consistency and consequential operation.** Fix contradictory geometry, disconnected services, free infinite air/water/power, impossible crew movement, phantom escape routes and a mismatch between protection claimed and protection actually modelled.
- **Second — distinct failure and recovery behaviour.** Support partial degradation, sectional isolation, slow repair, spare and supply limitations, local workarounds, mixed generations and other intermediate states.
- **Third — observational uncertainty.** Physical truth belongs to the simulated world; service manuals, labels, gauges and AI beliefs can be old, wrong or incomplete.
- **Fourth — plausible, appropriately bounded sizing.** Use engineering arithmetic to inform the story and constrain operations. Precision beyond the model's fidelity must not masquerade as validated performance.
- **Fifth — fabrication-level analysis only by explicit exception.** It is never a general approval gate.

Real-world scientific inconsistencies may be flagged and locally adjusted, **not** converted into an open-ended veto. If the setting gives a technology an established capability, preserve the capability and make its inputs, outputs, and failure consequences consistent. When something truly cannot operate even under stated fictional assumptions, correct the contradiction at the least expensive level.

## The ship as it exists today

The **original** Ox had comparatively organised, integrated, advanced utilities. The **current** ship is an old, continually repaired **Ship of Theseus**: a mixture of generations, refits, welded adapters, improvised but tested routes, manual valves where remote actuators failed, unusual wiring, handwritten instructions and hidden operational history. Its character is as much *Millennium Falcon* and *Firefly* as pristine *Star Trek* engineering.

Never restore ideal new-build symmetry simply to satisfy a tidy schema. A cabin fan-coil may share an unexpected corridor board, a BR-06 coolant valve may require manual operation, and field hardware may disagree with drawings. These are desirable provided they have intelligible physical explanations, discoverable evidence and real operational effects.

Preserve the **three separate truth layers**:

1. **Original engineering/design intent** — what the ship was supposed to be.
2. **As-installed current physical state** — what is actually in the world, damaged or working, authoritative in Evennia when integrated.
3. **Available documentation and character knowledge** — fallible evidence, individually acquired and possibly stale.

Design-reference JSON, Python casualty experiments and historical documentation are **not** sensor readings or world permissions. AI cognition must not obtain an omniscient ship state merely by reading a design file.

## Acceptable and unacceptable review findings

**Valid reasons to block a proposed ship change:** contradictory vessel topology, an access hatch that joins the wrong spaces, unaccounted reservoir mass, impossible route claims, protections that have no physical path, a narrative consequence the model cannot produce, or implementation code that unexpectedly changes the published ship or live Evennia world.

**Not valid blockers by themselves:** lack of NASA approval, absent fabrication blueprints, unqualified exotic drive efficiency, missing FEM/CFD/thermal certification, unspecified bolt counts, lack of actual built hardware, or a fictional system not achievable with 2026 materials.

A reviewer can record uncertainties, future refinement opportunities and numerical sensitivity without reclassifying all unresolved physical engineering as mandatory certification work. Mark what is **selected canon**, what remains a **candidate**, what is a **scenario assumption**, and what is **unmeasured as-installed**.

## Implications for repository work

- Put physical world identity and topology in the canonical ship model, and use adapters for future Evennia integration; don't create two independently authoritative ship databases.
- Build only the detail that affects crew decisions, service routing, work, supplies, damage, safety consequences or intelligible ship visualization.
- Keep ship candidates separate from the published runtime baseline until deliberately promoted. CI confirms design consistency and regression behaviour, **not real-world spacecraft safety**.
- Tie incident scripts to actual equipment, pressure cells, access IDs and inventory. Make deterministic and adversarial tests exercise the *different choices* the crew could make.
- **Finish playable ship engineering.** Proceed to physical operational exercises and AI-crew integration without holding the project hostage to construction-level qualification.

**Review phrase:** *Does this produce a coherent, believable working freighter with consequential failures and recoveries?* If yes, the fictional design has met its standard. **NASA approval is neither sought nor required.**
