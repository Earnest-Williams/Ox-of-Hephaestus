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

The native brain accepts validated addressed-event timestamps through
`observe_event()`, and can accept newer **authoritative world game-time
readouts** through `advance_game_time()` without adding a memory or a new
world observation. Production scheduler call sites must supply such readouts
during otherwise silent intervals. This change does not fabricate a wall
clock or introduce an unauthenticated timer, and does not yet introduce a
new world-side `oxclock` command.

## Regression and limitations

Tests cover exact conversions, late deliveries, cursor idempotence, non-event
aging, stale inference rejection, legacy checkpoint restore, and refusal of
future rehearsal. The G8 500-turn acceptance must pass after the change.

Not addressed here: calendar display, variable game-time acceleration, or
periodic live clock reads when the world has not sent any event. Those require
an authoritative time-read transport contract and should not be guessed from
elapsed handler wall seconds.
