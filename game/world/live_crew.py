"""P3c world-authoritative cooperation, recipient-scoped events and handover.

All functions run inside Evennia in response to *ordinary character commands*
or the explicit operator fixture setup. None is a privileged handler API.
Physical operations remain in CoolingPump; private events are world-owned.
"""
from __future__ import annotations

from django.db import transaction

from world.bootstrap import build_ship
from world.event_journal import emit, inbox, inbox_page, wire_event


def _world():
    ship = build_ship()
    return ship, ship["pump"], ship["roster"]


def _mutating_world():
    """Lock shared world effects before reading mutable world Attributes.

    Social commands and oxwork acquire locks in pump-then-roster order.
    The independent clock locks just the roster and never takes P-01.
    """
    from evennia.objects.models import ObjectDB
    ship, pump, roster = _world()
    pump = ObjectDB.objects.select_for_update().get(pk=pump.pk)
    roster = ObjectDB.objects.select_for_update().get(pk=roster.pk)
    return ship, pump, roster


def fixture_setup(*, scheduled_clock: bool = False) -> None:
    """Operator-only deterministic scenario setup; called before server boot."""
    ship, pump, roster = _world()
    if pump.state != "normal":
        raise ValueError("Scenario requires a fresh normal pump")
    pump.db.ox_chief_gate = True
    pump.db.ox_chief_released = False
    pump.db.ox_incident_closed = False
    # ONLY this disposable operator fixture may discard journal history.
    # A real ship upgrade must instead run the idempotent legacy importer.
    from world.models import CrewEvent
    CrewEvent.objects.all().delete()
    pump.db.ox_private_events = []
    pump.db.ox_event_journal_migrated = True
    pump.db.ox_inspections = {}
    roster.db.ox_active_engineer = ship["watch"].dbref
    roster.db.ox_world_minute = 180
    roster.db.ox_handover_at = 475
    roster.db.ox_handover_due = False
    roster.db.ox_handover_offer = None
    roster.db.ox_autoadvance_on_resolution = not scheduled_clock
    roster.db.ox_safety_reviewer = ship["chief"].dbref
    roster.db.ox_handover_delay_seconds = None
    roster.db.ox_handover_due_at = None
    pump.db.ox_release_reviewer = None
    if scheduled_clock:
        from world.live_clock import schedule_handover
        schedule_handover(delay_game_seconds=5.0)
    succeeded, reason = pump.inject_fault()
    if not succeeded:
        raise RuntimeError(reason)


@transaction.atomic
def fault_alarm(pump) -> None:
    """Open/re-open an incident and deliver telemetry ONLY to bridge watch."""
    ship, _pump, _roster = _world()
    history = list(pump.db.event_history or [])
    alarm_id = history[-1]["event_id"]
    pump.db.ox_active_alarm = alarm_id
    pump.db.ox_chief_released = False
    pump.db.ox_release_request = None
    pump.db.ox_release_reviewer = None
    pump.db.ox_chief_inspection_version = None
    pump.db.ox_engineer_verified_version = None
    pump.db.ox_incident_closed = False
    emit(pump, ship["officer"], "coolant_alarm",
         data={"alarm_id": alarm_id, "equipment": "P-01"},
         text="Bridge cooling telemetry reports an abnormal pressure alert.")


def _on_watch(actor, ship, roster) -> bool:
    return bool(
        actor in (ship["watch"], ship["chief"])
        and actor.location == ship["engineering"]
        and actor.db.crew_role in ("watch_engineer", "chief_engineer")
        and roster.db.ox_active_engineer == actor.dbref
    )


def relay_alarm(actor) -> tuple[bool, str]:
    ship, pump, roster = _world()
    if (actor != ship["officer"] or actor.location != ship["bridge"]
            or actor.db.crew_role != "bridge_officer" or not pump.db.ox_active_alarm
            or pump.db.ox_incident_closed):
        return False, "No authorised bridge alarm to relay"
    active = (ship["watch"] if roster.db.ox_active_engineer == ship["watch"].dbref
              else ship["chief"] if roster.db.ox_active_engineer == ship["chief"].dbref
              else None)
    if active is None:
        return False, "There is no valid active engineering watch"
    emit(pump, active, "radio_alert", sender=actor,
         data={"alarm_id": pump.db.ox_active_alarm, "equipment": "P-01"},
         text="Lin reports P-01 bridge pressure alarm; investigate locally.")
    return True, "Bridge alert relayed"


def note_inspection(actor, pump) -> None:
    """A normal local inspect command can certify ONLY a real local readout."""
    if actor.location != pump.location:
        return
    data = dict(pump.db.ox_inspections or {})
    data[actor.dbref] = int(pump.db.event_seq or 0)
    pump.db.ox_inspections = data
    ship, _pump, roster = _world()
    if (pump.db.ox_release_request
            and actor.dbref == pump.db.ox_release_reviewer
            and actor.dbref == roster.db.ox_safety_reviewer):
        pump.db.ox_chief_inspection_version = int(pump.db.event_seq or 0)
    if _on_watch(actor, ship, roster) and pump.state == "normal":
        pump.db.ox_engineer_verified_version = int(pump.db.event_seq or 0)


@transaction.atomic
def request_release(actor) -> tuple[bool, str]:
    ship, pump, roster = _mutating_world()
    if (not _on_watch(actor, ship, roster) or pump.state != "repaired"
            or not pump.db.ox_chief_gate or pump.db.ox_release_request):
        return False, "No authorised repaired pump awaits chief review"
    reviewer = (ship["chief"] if actor == ship["watch"] else ship["watch"])
    if (reviewer.dbref != roster.db.ox_safety_reviewer
            or reviewer == actor
            or reviewer.location != pump.location):
        return False, "No independent authorised reviewer available"
    request_id = "release-%04d" % int(pump.db.event_seq or 0)
    pump.db.ox_release_request = request_id
    pump.db.ox_release_reviewer = reviewer.dbref
    pump.db.ox_chief_inspection_version = None
    emit(pump, reviewer, "release_request", sender=actor,
         data={"request_id": request_id},
         text=f"{actor.key} requests independent safety inspection.")
    return True, "Safety release request delivered"


@transaction.atomic
def approve_release(actor) -> tuple[bool, str]:
    ship, pump, roster = _mutating_world()
    if (actor not in (ship["chief"], ship["watch"])
            or actor.location != pump.location
            or actor.db.crew_role not in ("chief_engineer", "watch_engineer")
            or actor.dbref != roster.db.ox_safety_reviewer
            or actor.dbref != pump.db.ox_release_reviewer
            or actor.dbref == roster.db.ox_active_engineer
            or pump.state != "repaired" or not pump.db.ox_release_request
            or pump.db.ox_chief_inspection_version != int(pump.db.event_seq or 0)
            or pump.db.ox_chief_released):
        return False, "Independent assigned reviewer must inspect repaired P-01"
    pump.db.ox_chief_released = True
    active = (ship["watch"] if roster.db.ox_active_engineer == ship["watch"].dbref
              else ship["chief"])
    emit(pump, active, "release_granted", sender=actor,
         data={"approver_id": actor.dbref,
               "request_id": pump.db.ox_release_request},
         text=f"{actor.key} independently approved commissioning.")
    emit(pump, actor, "release_recorded", sender=actor,
         data={"request_id": pump.db.ox_release_request},
         text="Independent safety approval recorded by Evennia.")
    return True, "Independent safety authorization recorded"


@transaction.atomic
def report_resolution(actor) -> tuple[bool, str]:
    ship, pump, roster = _mutating_world()
    if (not _on_watch(actor, ship, roster)
            or pump.state != "normal" or pump.db.ox_incident_closed
            or pump.db.ox_engineer_verified_version != int(pump.db.event_seq or 0)
            or not pump.db.ox_active_alarm):
        return False, "Fresh verified normal pressure required to close incident"
    pump.db.ox_incident_closed = True
    reviewer = (ship["chief"] if actor == ship["watch"] else ship["watch"])
    for person in (ship["officer"], reviewer):
        emit(pump, person, "incident_resolved", sender=actor,
             data={"alarm_id": pump.db.ox_active_alarm},
             text=f"{actor.key} confirms verified normal coolant pressure.")
    if roster.db.ox_autoadvance_on_resolution:
        # Explicitly synthetic world-clock advance for this acceptance
        # fixture. No LLM supplies the time or invents a duty obligation.
        roster.db.ox_world_minute = int(roster.db.ox_handover_at)
        roster.db.ox_handover_due = True
        for person in (ship["watch"], ship["chief"]):
            emit(pump, person, "handover_due", data={"minute": "475"},
                 text="07:55 engineering watch handover is due.")
    return True, "Verified incident closed"


@transaction.atomic
def offer_watch(actor) -> tuple[bool, str]:
    ship, pump, roster = _mutating_world()
    if (not _on_watch(actor, ship, roster) or not roster.db.ox_handover_due
            or roster.db.ox_handover_offer is not None
            or int(roster.db.ox_world_minute or 0)
            < int(roster.db.ox_handover_at or 0)
            or ship["chief"].location != actor.location):
        return False, "No authorised co-located handover is due"
    roster.db.ox_handover_offer = actor.dbref
    emit(pump, ship["chief"], "handover_offer", sender=actor,
         data={"source": "verbal_briefing", "uncertainty": "unverified"},
         text="Ari briefs Iona on an unverified engineering concern.")
    return True, "Watch handover offered"


@transaction.atomic
def accept_watch(actor) -> tuple[bool, str]:
    ship, pump, roster = _mutating_world()
    if (actor != ship["chief"] or actor.location != ship["engineering"]
            or actor.db.crew_role != "chief_engineer"
            or roster.db.ox_handover_offer != ship["watch"].dbref
            or not roster.db.ox_handover_due):
        return False, "No authorised watch handover to accept"
    roster.db.ox_active_engineer = actor.dbref
    # World-owned delegation: the outgoing engineer becomes independent
    # safety reviewer while the chief is on active duty. Self-signoff is
    # forbidden; this is not an AI-assigned privilege.
    roster.db.ox_safety_reviewer = ship["watch"].dbref
    roster.db.ox_handover_due = False
    roster.db.ox_handover_offer = None
    for person in (ship["watch"], actor):
        emit(pump, person, "watch_transferred", sender=actor,
             data={"new_watch": actor.dbref},
             text="Engineering watch transferred to Iona.")
    return True, "Engineering watch transferred"
