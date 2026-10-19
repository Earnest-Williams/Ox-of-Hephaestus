"""Persistent game-authoritative duty deadlines: no handler/LLM clock control.

The script is a coarse, bounded world timer. It never advances an agent, calls
a model, or invents an incident. The world checks one persisted duty deadline
and persists the delivered recipient-specific observations.
"""
from __future__ import annotations

from django.db import transaction
from evennia.scripts.scripts import DefaultScript
from evennia.utils import gametime

SCRIPT_NAME = "OxShipDutyClock"


def schedule_handover(*, delay_game_seconds: float = 5.0) -> None:
    """Arm the initial handover; activation occurs in the live game server.

    Persist the relative delay rather than using a separate shell process's
    gametime epoch. The Script resolves it in the live server.
    """
    from world.bootstrap import find_fixture
    if not 0.1 <= delay_game_seconds <= 86400:
        raise ValueError("Invalid world duty delay")
    roster = find_fixture("roster-board")
    if roster is None:
        raise RuntimeError("Ship watch roster is missing")
    roster.db.ox_handover_delay_seconds = float(delay_game_seconds)
    roster.db.ox_handover_due_at = None
    roster.db.ox_autoadvance_on_resolution = False


@transaction.atomic
def tick_game_clock(*, now_game_time: float | None = None) -> bool:
    """Advance one due world obligation idempotently; true only when fired."""
    from world.bootstrap import build_ship
    from world.live_crew import emit
    ship = build_ship()
    from evennia.objects.models import ObjectDB
    # Read the duty fields AFTER acquiring the roster lock. Otherwise two
    # independent Script/database writers can both emit a due notification.
    roster = ObjectDB.objects.select_for_update().get(pk=ship["roster"].pk)
    delay = roster.db.ox_handover_delay_seconds
    if delay is None:
        return False
    now = (float(now_game_time) if now_game_time is not None
           else float(gametime.gametime(absolute=True)))
    if roster.db.ox_handover_due_at is None:
        roster.db.ox_handover_due_at = now + float(delay)
        return False
    if roster.db.ox_handover_due or roster.db.ox_active_engineer != ship["watch"].dbref:
        return False
    if now < float(roster.db.ox_handover_due_at):
        return False
    for person in (ship["watch"], ship["chief"]):
        emit(
            ship["pump"], person, "handover_due",
            data={"minute": str(int(roster.db.ox_handover_at))},
            text="Engineering watch handover is due by the ship clock.",
        )
    # The deadline must not be consumed until every addressed notification
    # is recorded. A failed second emit rolls back the first event as well.
    roster.db.ox_world_minute = int(roster.db.ox_handover_at)
    roster.db.ox_handover_due = True
    roster.db.ox_handover_delay_seconds = None
    return True


class ShipDutyClock(DefaultScript):
    """Evennia persistent Script; no separate cron, model or handler timer."""

    def at_script_creation(self) -> None:
        self.key = SCRIPT_NAME
        self.desc = "World-owned watch deadlines (does not call models)"
        self.interval = 2
        self.persistent = True
        self.start_delay = True

    def at_repeat(self) -> None:
        tick_game_clock()
        from world.independent_rounds import tick_rounds
        tick_rounds()
        from world.captain import tick_captain_obligations
        tick_captain_obligations()


def ensure_clock_script() -> None:
    """Idempotent per-server-start creation; never reset a live duty deadline."""
    from evennia.scripts.models import ScriptDB
    from evennia.utils.create import create_script

    if not ScriptDB.objects.filter(db_key=SCRIPT_NAME).exists():
        create_script("world.live_clock.ShipDutyClock", key=SCRIPT_NAME)
