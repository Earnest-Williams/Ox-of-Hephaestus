# P5 world read — follow-on plan (31 October 2026)

**Status:** planned, not started. Follows the sketch branch
`sketch/p5-world-read-beliefs-inspection`, which already carries the
approved immediate changes:

- `ox.world.read/1` amended in place before any producer: `null` event
  datums, and `local_panel` evidence may cite its delivery event;
- `emit()` requires non-empty text (social agreement steps now get a
  world-authored summary line);
- capability caps raised from 16 to 64 exits and fixtures;
- the world-read producer is an optional extra (`game/requirements-ox.txt`)
  loaded on first use, and is gated in `ox-world-read-contract.yml`.

What follows is the deferred work. Each item names its state owner, the
decision it needs, and a "done when" test.

## 1. G19 navigation reads exits from `ox.world.read`, not `oxcapabilities`

**Why.** The 64-exit cap fixes today's failure, but `oxcapabilities` was
built for the seven-room proving ground: exits are identified by Evennia
dbref and command word, it does not run the G19 traversal gate, and its
fixture targets are limited to pump/cargo/scrubber. The actor page already
carries link IDs, from/to space IDs and an assessment from the real
`_clearance` gate, bounded at 128 per page.

**Owner.** World (exit assessment); handler (navigation knowledge).

**Steps.**

1. Navigation knowledge keyed by `link_id` and `space_id` instead of
   dbref/command. Keep the existing actor-private, explored-only rule: no
   global topology is loaded.
2. Traversal still uses the ordinary exit command, looked up from the
   room's exit whose `ox_access_link_id` matches; success is confirmed only
   by the next actor page's `location_id`.
3. `blocked` exits are remembered with their observation time and retried
   after expiry, not treated as permanent.
4. `oxcapabilities` stays as the proving-ground protocol with no G19
   special cases. Equipment affordances for G19 panels and machinery come
   from a separate typed list (to be added to the actor page or a G19
   capability command, decided at step 1).

**Decision needed.** Whether G19 equipment affordances join `ox.world.read`
(requires a new schema version once a producer has published) or stay a
separate command.

**Done when.** An engineer starting in `HAB-01-COR` (20 exits) plans and
walks to `ENG-CONTROL` using only actor pages, under real pressure and
suit gates; a closed hatch encountered mid-route causes a replan, not a
failure; replay gives the same route.

## 2. Belief capacity: working set in `AgentEpistemics`, history in the evidence index

**Why.** `AgentEpistemics.CAP` (128 observations) is a cognition budget and
should stay. 94 of 116 panels sit in a gas cell; roughly 116 availability
facts plus 94 × 8 readings will never fit, and raising the cap would turn
the ledger into a telemetry store.

**Owner.** Handler only. The world is unchanged.

**Steps.**

1. **Evidence index is the store of record for panel readings.** Panel
   reads are journaled `panel_reading` events, so the existing actor-private
   SQLite index (`runtime/evidence_index.py`) already holds them, rebuilt
   only from authenticated inbox pages. Add a typed query: latest reading
   per panel and metric, with sample time and event ID.
2. **Working set.** `AgentEpistemics` holds only facts for the engineer's
   current duty area, for example one HAB arc: about 10–15 panels ×
   availability, pressure and O₂ (~45 facts). The duty area is authored
   data, not inferred.
3. **Over-cap becomes a known unknown.** Facts that do not fit are recorded
   with `ask()` ("LP-X not checked recently") instead of being reported as
   deferred and dropped. Questions also cap at 128, so questions are
   per-panel, not per-metric.
4. **Eviction.** Leaving a duty area evicts its facts from the working set
   oldest-first; the readings remain in the evidence index and can be
   re-admitted from it with their original evidence IDs.
5. **Inspection history endpoint.** `ox.handler.inspect/1` gains a second,
   separately authorized route that reads the evidence index (latest
   reading per panel, paged), so the P5 view can show beliefs outside the
   working set. Same authorization rule: developer, or the character's own
   grant; refusals look like "not found".

**Decisions needed.** How a duty area is authored (role default, captain
assignment, or both); whether eviction is by area change only or also by
age.

**Done when.** An engineer who has read every HAB panel keeps ≤ 128
observations, can answer "what did LP-X last read and when" from the index
with the original event ID, re-verifies that event with exact `oxevent`
lookup, and the P5 view shows working-set and indexed beliefs distinctly.

## Also open from the sketch

Smaller items to settle when the sketch becomes a PR:

- Wire `journal_panel_reading()` into `local_physics_readout`'s panel branch,
  register `oxworldread` in the cmdset and the developer route in
  `web/urls.py`.
- Actor-page cursors bind `publication_seq` (the latest world event
  sequence), which changes on every tick; decide whether actor pages need the
  same per-publication cache as developer pages.
- The actor event window is the latest 512 addressed events; decide whether
  the actor page should page from a caller cursor like `oxinbox` instead.
- OOB frame size: a full actor page with 128 events can approach the
  handler's 1 MiB frame bound; measure on the installed ship.
- Run the four Django/Evennia adapters against a live installed world in an
  installed-world workflow, as G19 does.
