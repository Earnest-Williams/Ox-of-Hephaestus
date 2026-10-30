# G18b — coupled casualty and local recovery (Ox full-ship world)

**Historical acceptance stage:** G18b **merged as PR #136 on 25 October 2026**;
this file preserves that incremental design and the test requirements of
its time. G19 subsequently completed the integrated ship; use the
[current G19 acceptance record](G19_ACCEPTANCE_RECORD_2026-10-29.md).
This stage extended the merged G18 opt-in world physics without introducing
a separate simulator or changing the v0.5 ship's spatial reference model.

## What is now coupled

- A physically **open rated pressure hatch** between two already installed,
  known gas cells exchanges finite air mass, gas species (including smoke)
  and enthalpy over game time. Open ventilation ducts are a separate path:
  shutting hatches does **not** shut ducts. Unknown cargo atmosphere is never
  treated as vacuum or given a fictitious mixing rate.
- A **jammed-open** atmosphere valve remains a physical flow path even when
  its controls refuse to move. This can defeat a mistaken isolation order.
- A scenario-only *valved service-side leak* can name a real, locally manually
  operable atmosphere isolator in its own pressure cell. Crew physically at
  that station may close the valve and stop further external loss. A direct
  hull breach with no such valve remains uncontained; no crew action magically
  repairs a hole in the pressure hull.
- Hot compartments now generate real persistent **equipment protection
  trips** in the installed ECLSS/generator/thermal/fire-pump equipment they
  contain. Accumulated heat exposure separately degrades and eventually
  fails authored equipment; neither mode is cleared by merely restoring
  electrical power. These mechanisms are reproducible deterministic screens,
  not measured thermal qualification ratings.
- Power dispatch, independently switched feeders, cooling availability,
  fan-driven smoke circulation, fire, gas loss and delayed plant startup
  therefore share the same clock and persistent ship tables.

## Two new local crew actions

Through the same globally deduplicated `oxplant` command:

- `oxplant <id> hatch ACC-BR-03-HAB-03 open|closed` actuates only the
  ordinary **HAB bridge pressure hatches**, from one of their physical
  endpoint rooms, and only for an authorised live engineer/environment
  technician. Opening requires two known bounded cells with breathable,
  non-burning, non-leaking air, a pressure differential no greater than
  2 kPa, intact machinery and a shut opposite BR hatch. A dangerous or
  jammed opening is denied. Closing a working hatch is allowed during a
  casualty. No cargo, EVA, indexed lift or rotary-transfer hatch is
  inferred safe from this routine.
- `oxplant <id> service ECLSS-A reset` (or another supported plant)
  clears **only** an explicitly world-generated local overtemperature
  *protection* trip after shutdown and independent verification of
  physically safe local air, temperature and absence of lasting thermal
  damage. Generator reset additionally requires its real feeder breaker
  to be open. This is not a general parts-free repair. Restart remains a
  separate timed `plant on` operation.

All physical changes and globally unique request receipts commit together.
Commands operate at the character's actual Evennia location; an AI does not
receive a remote global casualty oracle. The local readout also exposes
current access-hatch condition from either endpoint.

**Not yet activated:** ordinary traversal of the 1,034 v0.4 directional
exits; they remain Developer-only. A permitted *hatch state change* is not
a permitted route for an NPC. Subsequent work must connect traversal,
suit checks, damage-control equipment, separate actual pressure-equalisation
machinery, rotor/hard-lock witnesses and the 42 authored maintenance groups.
No blanket "suit verified" boolean is treated as sufficient access evidence.

## Acceptance gates

The new `world.tests.test_coupled_casualty` suite uses the installed
421 rooms, 133 gas cells, 808 equipment units, the authored service graph,
actual world-writable records and located Evennia crew bodies. It proves:

1. Real manually valved service leak stops upon an authorised local closure,
   but resumes if the physical valve jams open; a denied command has no receipt.
2. A real BR-03 pressure hatch opens only after safe local checks and cannot
   have its opposite hatch opened simultaneously. With BR atmospheric ducts
   shut, smoke crosses *only* the open pressure hatch and stops spreading
   after it closes.
3. Loss of a real generator stops available cooling and powered atmospheric
   circulation; a qualified crew member restarts it with elapsed startup
   time. Fire continues consuming oxygen and generating smoke and lasting
   equipment damage rather than being cured by power alone.
4. Heat at a real ECLSS plant trips protection; an unsafe remote or hot
   reset cannot clear it. Operators may not overwrite global work receipts.
5. Deterministic stateful casualty fuzz checks conservation, finite values
   and replay behavior over varied world states.

The dedicated G18 CI runs both new tests and the original G18/G17
regressions, then independently reopens the world in another process.

**Engineering criterion:** verisimilitude of a long-serving, unevenly
refitted working freighter and internally consistent consequences for play;
not NASA approval, certified aerospace design, CFD, measured installation
performance or construction-ready equipment tolerances.
