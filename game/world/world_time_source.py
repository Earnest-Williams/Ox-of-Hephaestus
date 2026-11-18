"""One read-only entrypoint for the *current* legacy world-time sample.

G19 T1 bridge, BEFORE enabling pause/watch-until. The Evennia absolute game
clock is still the scheduler target; it is not the last *committed* physical
tick. Callers never alter Evennia TIMEFACTOR or create another clock.

This module has no DB access, write path, tick authority, timer or actor
visibility. When the unified clock is commissioned, its implementation must
replace this source behind the same consumer contract rather than allowing
legacy clocks to keep progressing separately.
"""
from __future__ import annotations

import math

from evennia.utils import gametime

SOURCE = "evennia_absolute_game_time"
ALIGNMENT_SCHEMA = "ox.world-time-alignment/1"


class WorldTimeSourceError(ValueError):
    """A supplied or sampled time cannot be used as game seconds."""


def require_game_seconds(value: object) -> float:
    """Reject coercible text, booleans, NaN, infinities and negative time."""
    if type(value) not in (int, float):
        raise WorldTimeSourceError("Game time must be numeric, not inferred")
    try:
        seconds = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise WorldTimeSourceError("Game time is outside representable range") from exc
    if not math.isfinite(seconds) or seconds < 0:
        raise WorldTimeSourceError("Game time is not finite and nonnegative")
    return seconds


def scheduler_game_seconds() -> float:
    """Sample Evennia's existing scheduler time exactly once.

    This is an observer, never a simulation step or a pause authority. In
    particular it MUST NOT substitute the last committed physics time for
    a public character clock before the other world mutators are migrated.
    """
    return require_game_seconds(gametime.gametime(absolute=True))


def describe_time_alignment(scheduler_seconds: object,
                            committed_seconds: object | None = None) -> dict:
    """Pure, read-only diagnostic: scheduler target versus committed physics.

    The caller must obtain committed_seconds from the actual world clock
    under its appropriate access rules. This helper cannot inspect that
    state, authorize a catch-up tick, or expose it to a game character.
    """
    target = require_game_seconds(scheduler_seconds)
    if committed_seconds is None:
        return {
            "schema_version": ALIGNMENT_SCHEMA,
            "scheduler_source": SOURCE,
            "scheduler_seconds": target,
            "committed_physics_seconds": None,
            "uncommitted_delta_seconds": None,
            "relation": "physics_not_provided",
        }
    committed = require_game_seconds(committed_seconds)
    delta = target - committed
    if not math.isfinite(delta):
        raise WorldTimeSourceError("Time-source delta is not representable")
    return {
        "schema_version": ALIGNMENT_SCHEMA,
        "scheduler_source": SOURCE,
        "scheduler_seconds": target,
        "committed_physics_seconds": committed,
        "uncommitted_delta_seconds": delta,
        "relation": (
            "aligned" if delta == 0 else
            "scheduler_ahead" if delta > 0 else
            "committed_ahead"
        ),
    }
