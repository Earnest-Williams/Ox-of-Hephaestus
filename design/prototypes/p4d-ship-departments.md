# P4d — specialist departments and a useful seven-compartment freighter

**Status:** PR #17 integration candidate. Acceptance is the focused
`ox-departments.yml` workflow plus all triggered prior Ox regressions.
For merged-state truth, see [../STATUS.md](../STATUS.md).

## Scope and navigable layout

The existing Bridge, Connecting Passage and Engineering remain in place.
Four new permanent rooms branch off their original connections:

```text
                         Bridge
                           |
                    Connecting Passage --- Crew Mess
                       /       \
          Environmental Plant   Cargo Hold
                       |
      (the original path to Engineering remains)
                           Engineering --- Machine Shop
```

**Exact navigational links:** Bridge ↔ Connecting Passage via `aft/fore`;
Connecting Passage ↔ Engineering via `engineering/out`;
Connecting Passage ↔ Cargo Hold via `starboard/port`;
Connecting Passage ↔ Environmental Plant via `port/starboard`;
Connecting Passage ↔ Crew Mess via `mess/out`;
Engineering ↔ Machine Shop via `workshop/out`.
The workshop and mess have environmental descriptions and exits, not
implemented fabrication/cooking systems.

All compartments, fixtures and crew are tagged for idempotent `build_ship()`
construction. Rerunning it preserves existing positions, physical damage,
event journals and scarce consumable stock.

## New roles and world-owned work

- **Mara Voss — cargo officer.** Works in Cargo Hold, inspecting restraint
  grid **C-01**. It starts secured with eight sealed containers in twelve
  positions. A world/developer cargo-shift fault loosens two restraints,
  requiring local survey (`inspect cargo`), `restow cargo`, another
  independent post-restow inspection, and `certify cargo`. The world
  rejects wrong role, wrong room, missing inspection or invalid sequence.
- **Teo Hale — environmental technician.** Works in Environmental Plant
  on **A-01**, a replaceable-cartridge atmosphere scrubber. An authored
  saturation fault requires local `inspect scrubber`, `isolate scrubber`,
  `replace scrubber`, fresh inspection and `restart scrubber`. The world
  tracks two available local spare cartridges; replacement consumes one,
  and subsequent service cannot proceed without a spare.
- **Lin Sato — bridge officer.** Has a new **Operations Console** that
  reads both subsystem states without providing remote control. Cargo
  shift and scrubber saturation produce genuinely addressed `ox_event`
  alarms for Lin and the corresponding specialist, not for unrelated crew.
- **Ari Sen and Iona Vek — engineering.** The existing P-01, independent
  safety review, GOAP and watch handover remain the tested AI-controlled
  workflow.
- A **Department Duty Board** in the passage posts durable standard
  responsibilities, which are public shipboard information rather than
  a character's private memory.

The code declares descriptive prospective competence labels:
`cargo_rigging`, `cargo_inspection`, `atmosphere_diagnostics`,
`environmental_maintenance`, and `systems_validation`. There are no
numerical skills, practice events, levels or gates at P4d. These tags
identify where skill-by-use should attach later, after task execution
and successful world receipts are generalised.

## Physical authority and provenance

The cargo and atmospheric operations are **ordinary local Evennia
commands**, with a persistent independent physical event history each.
The handler cannot write equipment state directly; developer-only
`shipfault cargo` and `shipfault scrubber` simply provide test stimulus.

These new operations are *not yet routed through P-01's actor-bound
`oxaction` durable receipt protocol*. A later AI-agent integration
should implement equipment-generic receipts and interrupted-action
reconciliation before claiming crash-safe autonomous servicing. The
new roles are existing in-world bodies, **not additional native
Concordia sessions**. The P4c supervisor still controls Lin/Ari/Iona;
it does not yet automatically handle the new event kinds or issue a
maintenance work order to Mara/Teo.

Recipient-private alarms temporarily use the existing world-authoritative
`ox_event` mailbox persisted with P-01, pending extraction of a shipwide
mailbox. No NPC reads another member's addressed event from the handler.

## Acceptance tests

`.github/workflows/ox-departments.yml` checks physical role/presence
authorization, inspections, inventory exhaustion, idempotent construction,
compartment links, per-recipient alarms, the legacy coolant behavior,
and cross-process SQLite persistence. Existing P4a/P4b/P4c full-server
workflows are regressions; this expansion must not compromise them.

## Next step

Extend independently authenticated crew and event dispatch from three to
five identities, introduce generic world-confirmed actions for cargo and
environmental fixtures, then test conflicting incidents and task priority.
Only after these work reliably should competency acquisition and
skill-by-use progression attach to verified successful actions.
