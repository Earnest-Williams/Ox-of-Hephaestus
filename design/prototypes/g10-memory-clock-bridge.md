# G10 — explicit memory clock ownership and game-time conversion

## Time domains

The G8 experiment deliberately uses a **virtual, deterministic turn** for
interpersonal decisions. The live Evennia world uses
`evennia.utils.gametime.gametime(absolute=True)`: authoritative
**simulated game seconds**, not handler wall time and not a count of memories.

`MemoryClockBridge` maps them only when its immutable origin, origin turn and
positive seconds-per-turn scale are supplied:

`turn = origin_turn + floor((game_seconds - origin_game_seconds) / seconds_per_turn)`.

The reverse mapping identifies the beginning of a memory tick. Rounding never
invents a future time. Late world events cannot rewind an agent's clock.
The native LiveCrewBrain uses 1 Evennia game second per memory tick, anchored
to the first **recipient-addressed, authenticated world timestamp**, and
retains its bridge and cursor across checkpoints. Older checkpoints retain
the latest existing memory-domain timestamp as a migration fallback.
No existing historical `occurred_turn` is rewritten.

G8 explicitly advances every one of its six character clocks for each
virtual decision turn, whether or not any episode is added. The scenario's
virtual timeline remains distinct from real Evennia event timestamps. This
preserves the deterministic 500-decision experiment without pretending that
500 model decisions always consume 500 game seconds.

## Consistency boundary

- Private memory ranking reads the owner-authorized current clock, never the
  newest memory's timestamp.
- Voluntary rehearsal and reconsideration use the current clock; they are
  cognition-revisioned mutations. The readonly prompt projection still never
  rehearses.
- Inference fork and checkpoint restore copy both clock cursor and conversion
  origin; a live clock advance invalidates an in-flight stale choice.
- Future-dated memories and interpretations are not shown in prompts before
  the appropriate simulation time. Old addressed events keep historical
  occurrence and learning times.
- World state, elapsed game time, and receipt provenance remain world-owned.
  The handler cannot issue world-side time advances.

## Live-time advancement contract

The native brain accepts validated addressed events through
`observe_event()` and newer authoritative world-time reads through
`advance_game_time()`, without adding a memory or world event.
**Completed follow-up G10b (PR #81):** an ordinary authenticated
`oxclock <nonce>` returns Evennia game seconds. The handler verifies
the nonce and actor, then advances that character's clock just before
native model inference. Original G10 did not yet include that
transport path; the follow-up closed the gap without wall-clock guesses.
See [G10b](g10b-world-clock-read.md).

## Regression and limitations

Tests cover exact conversions, late deliveries, cursor idempotence, non-event
aging, stale inference rejection, legacy checkpoint restore, and refusal of
future rehearsal. The G8 500-turn acceptance must pass after the change.

Still outside this scope: calendar display, variable game-time acceleration
and a separate always-on clock-polling service. G10b implements
**pre-decision authoritative reads** during otherwise silent periods,
without guessing from elapsed handler wall time. Earlier G10 limitations
are retained as historical evidence.
