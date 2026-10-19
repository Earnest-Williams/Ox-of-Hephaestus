"""World-owned, opt-in duty windows and local condition discoveries.

Time supplies an opportunity, not an order or a hidden diagnosis. Wear
accumulates deterministically with elapsed *game* cycles; character recipients
learn only that a window opened. Only a physical inspection at the correct
station supplies evidence for a receipted report or preventive operation.
No handler reads world Attributes or invokes this operator scheduling API.
"""
from __future__ import annotations

import math

from django.db import transaction
from evennia.objects.models import ObjectDB
from evennia.utils import gametime

from world.bootstrap import build_ship, find_fixture
from world.event_journal import emit

STATIONS = {
    "bridge_officer": ("operations", "panel-operations"),
    "watch_engineer": ("pump", "pump-p01"),
    "chief_engineer": ("pump", "pump-p01"),
    "cargo_officer": ("cargo", "cargo-cradle"),
    "environment_tech": ("scrubber", "atmosphere-scrubber"),
}
WEAR_LIMIT = 3


def _game_time(now: float | None) -> float:
    value = float(gametime.gametime(absolute=True) if now is None else now)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Invalid game clock reading")
    return value


def schedule_rounds(*, period_game_seconds: float = 1800) -> None:
    """Opt in explicitly; ordinary bootstrap never arms background rounds."""
    period = float(period_game_seconds)
    if not math.isfinite(period) or not 1 <= period <= 86400:
        raise ValueError("Round window interval must be 1..86400 game seconds")
    ship = build_ship()
    roster = ship["roster"]
    if roster.db.ox_round_period is not None:
        raise RuntimeError("Rounds already scheduled; never erase a live cycle")
    roster.db.ox_round_period = period
    roster.db.ox_round_due_at = None
    roster.db.ox_round_cycle = 0
    roster.db.ox_round_reports = {}


@transaction.atomic
def tick_rounds(*, now_game_time: float | None = None) -> bool:
    """Catch up elapsed intervals in one bounded notification per actor.

    The event journal and physical wear advance in the same transaction.
    A long offline gap coalesces windows rather than spawning an event storm.
    """
    ship = build_ship()
    roster = ObjectDB.objects.select_for_update().get(pk=ship["roster"].pk)
    if roster.db.ox_round_period is None:
        return False
    now = _game_time(now_game_time)
    period = float(roster.db.ox_round_period)
    due = roster.db.ox_round_due_at
    if due is None:
        roster.db.ox_round_due_at = now + period
        return False
    due = float(due)
    if now < due:
        return False
    elapsed = 1 + int((now - due) // period)
    old_cycle = int(roster.db.ox_round_cycle or 0)
    cycle = old_cycle + elapsed
    if cycle > 2**53:
        raise OverflowError("World round sequence cannot be represented safely")
    # The notification contains NO wear, room contents, fault, or hidden fact.
    for person in (
        ship["officer"], ship["watch"], ship["chief"],
        ship["cargo"], ship["environment"],
    ):
        emit(
            ship["pump"], person, "crew_round_window",
            data={"cycle": cycle, "missed_windows": elapsed - 1},
            text="A free duty interval is available for self-directed station rounds.",
        )
    for fixture in (ship["cradle"], ship["scrubber"]):
        fixture.db.ox_round_wear = min(
            100, int(fixture.db.ox_round_wear or 0) + elapsed,
        )
    roster.db.ox_round_cycle = cycle
    roster.db.ox_round_due_at = due + elapsed * period
    return True


def _station(actor, station: str):
    spec = STATIONS.get(getattr(actor.db, "crew_role", None)) if actor else None
    if spec is None or spec[0] != station:
        return None
    fixture = find_fixture(spec[1])
    if fixture is None or actor.location != fixture.location:
        return None
    return fixture


def _reading(fixture, station: str) -> dict:
    if station == "operations":
        return {"telemetry": fixture.readout()}
    return {
        "state": str(fixture.state),
        "revision": int(fixture.db.event_seq or 0),
        "wear_index": (int(fixture.db.ox_round_wear or 0)
                       if station in ("cargo", "scrubber") else 0),
    }


def note_round_inspection(actor, fixture) -> None:
    """Called only after the ordinary local inspect command supplied readout."""
    roster = find_fixture("roster-board")
    if roster is None or roster.db.ox_round_period is None:
        return
    cycle = int(roster.db.ox_round_cycle or 0)
    if not cycle:
        return
    role = getattr(actor.db, "crew_role", None)
    spec = STATIONS.get(role)
    if spec is None or find_fixture(spec[1]) != fixture or actor.location != fixture.location:
        return
    observed = dict(fixture.db.ox_round_inspections or {})
    observed[actor.dbref] = {
        "cycle": cycle, "reading": _reading(fixture, spec[0]),
    }
    fixture.db.ox_round_inspections = observed


def fresh_round_inspection(actor, fixture, station: str) -> bool:
    roster = find_fixture("roster-board")
    if roster is None or not roster.db.ox_round_period:
        return False
    cycle = int(roster.db.ox_round_cycle or 0)
    observation = dict(fixture.db.ox_round_inspections or {}).get(actor.dbref)
    return bool(
        cycle and _station(actor, station) == fixture
        and observation == {
            "cycle": cycle, "reading": _reading(fixture, station),
        }
    )


def file_round_report(actor, station: str) -> tuple[bool, str]:
    """Report only current firsthand evidence; never relay a guessed fact.

    Called by the globally receipted world work executor under the pump lock.
    Its own actor-first event is the receipt's stable source; bridge delivery
    follows only after a successful verified firsthand report.
    """
    fixture = _station(actor, station)
    if fixture is None or not fresh_round_inspection(actor, fixture, station):
        return False, "A new local inspection in the current round is required"
    ship = build_ship()
    roster = ObjectDB.objects.select_for_update().get(pk=ship["roster"].pk)
    cycle = int(roster.db.ox_round_cycle or 0)
    reported = dict(roster.db.ox_round_reports or {})
    if reported.get(actor.dbref) == cycle:
        return False, "This actor already reported this duty interval"
    reading = _reading(fixture, station)
    wear = int(reading.get("wear_index", 0))
    state = reading.get("state", "monitored")
    if wear >= WEAR_LIMIT:
        finding = "maintenance_due"
    elif station == "pump" and state != "normal":
        finding = "equipment_attention"
    elif station == "cargo" and state != "secured":
        finding = "equipment_attention"
    elif station == "scrubber" and state != "nominal":
        finding = "equipment_attention"
    elif station == "operations" and (
        "LOW PRESSURE" in reading["telemetry"]
        or "SATURATED" in reading["telemetry"]
        or "UNSECURED" in reading["telemetry"]
    ):
        finding = "telemetry_attention"
    else:
        finding = "routine"
    details = {
        "station": station, "cycle": cycle, "finding": finding,
        "wear_index": wear,
    }
    emit(
        ship["pump"], actor, "round_recorded",
        data=details, text=f"Your firsthand {station} round was logged.",
    )
    emit(
        ship["pump"], ship["officer"], "crew_round_report",
        sender=actor, data=details,
        text=f"{actor.key} filed a verified {station} round: {finding}.",
    )
    # If bridge delivery fails, neither event nor this anti-duplicate marker
    # persists. The outer WorkReceipt transaction rolls back as well.
    reported[actor.dbref] = cycle
    roster.db.ox_round_reports = reported
    return True, "World logged firsthand inspection and notified the bridge"
