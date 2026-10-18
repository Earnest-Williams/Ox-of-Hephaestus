"""P3c world-authoritative cooperation, recipient-scoped events and handover.

All functions run inside Evennia in response to *ordinary character commands*
or the explicit operator fixture setup. None is a privileged handler API.
Physical operations remain in CoolingPump; private events are world-owned.
"""
from __future__ import annotations

import json

from evennia.utils import gametime
from world.bootstrap import build_ship, find_fixture


def _world():
    ship = build_ship()
    return ship, ship["pump"], ship["roster"]


def emit(pump, recipient, kind: str, *, sender=None, data=None, text="") -> dict:
    """Persist and deliver ONE recipient's authored world observation."""
    items = list(pump.db.ox_private_events or [])
    event = {
        "event_id": "oxevt-%04d" % (len(items) + 1),
        "recipient_dbref": recipient.dbref,
        "sender_dbref": sender.dbref if sender else None,
        "kind": kind,
        "data": dict(data or {}),
        "text": text,
        "game_time": float(gametime.gametime(absolute=True)),
    }
    items.append(event)
    pump.db.ox_private_events = items
    # Nested dicts are lossy in the Evennia Portal/Server OOB scrubber.
    # Transmit the scoped event as one serialized JSON positional argument.
    recipient.msg(ox_event=([json.dumps(event, sort_keys=True)], {}))
    return event


def inbox(actor, *, after: int = 0) -> list[dict]:
    """No agent may query another character's events or aggregate journal."""
    if after < 0:
        raise ValueError("Invalid event cursor")
    pump = find_fixture("pump-p01")
    events = list(pump.db.ox_private_events or []) if pump else []
    return [dict(event) for event in events
            if event["recipient_dbref"] == actor.dbref
            and int(event["event_id"].split("-")[-1]) > after][:128]


def fixture_setup() -> None:
    """Operator-only deterministic scenario setup; called before server boot."""
    ship, pump, roster = _world()
    if pump.state != "normal":
        raise ValueError("Scenario requires a fresh normal pump")
    pump.db.ox_chief_gate = True
    pump.db.ox_chief_released = False
    pump.db.ox_incident_closed = False
    pump.db.ox_private_events = []
    pump.db.ox_inspections = {}
    roster.db.ox_active_engineer = ship["watch"].dbref
    roster.db.ox_world_minute = 180
    roster.db.ox_handover_at = 475
    roster.db.ox_handover_due = False
    roster.db.ox_handover_offer = None
    roster.db.ox_autoadvance_on_resolution = True
    succeeded, reason = pump.inject_fault()
    if not succeeded:
        raise RuntimeError(reason)


def fault_alarm(pump) -> None:
    """Open/re-open an incident and deliver telemetry ONLY to bridge watch."""
    ship, _pump, _roster = _world()
    history = list(pump.db.event_history or [])
    alarm_id = history[-1]["event_id"]
    pump.db.ox_active_alarm = alarm_id
    pump.db.ox_chief_released = False
    pump.db.ox_release_request = None
    pump.db.ox_chief_inspection_version = None
    pump.db.ox_engineer_verified_version = None
    pump.db.ox_incident_closed = False
    emit(pump, ship["officer"], "coolant_alarm",
         data={"alarm_id": alarm_id, "equipment": "P-01"},
         text="Bridge cooling telemetry reports an abnormal pressure alert.")


def _on_watch(actor, ship, roster) -> bool:
    return (actor == ship["watch"] and actor.location == ship["engineering"]
            and actor.db.crew_role == "watch_engineer"
            and roster.db.ox_active_engineer == actor.dbref)


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
    ship, _pump, _roster = _world()
    if actor == ship["chief"] and pump.db.ox_release_request:
        pump.db.ox_chief_inspection_version = int(pump.db.event_seq or 0)
    if actor == ship["watch"] and pump.state == "normal":
        pump.db.ox_engineer_verified_version = int(pump.db.event_seq or 0)


def request_release(actor) -> tuple[bool, str]:
    ship, pump, roster = _world()
    if (not _on_watch(actor, ship, roster) or pump.state != "repaired"
            or not pump.db.ox_chief_gate or pump.db.ox_release_request):
        return False, "No authorised repaired pump awaits chief review"
    request_id = "release-%04d" % int(pump.db.event_seq or 0)
    pump.db.ox_release_request = request_id
    pump.db.ox_chief_inspection_version = None
    emit(pump, ship["chief"], "release_request", sender=actor,
         data={"request_id": request_id},
         text="Ari requests a physical safety inspection before commissioning.")
    return True, "Chief release request delivered"


def approve_release(actor) -> tuple[bool, str]:
    ship, pump, _roster = _world()
    if (actor != ship["chief"] or actor.location != pump.location
            or actor.db.crew_role != "chief_engineer"
            or pump.state != "repaired" or not pump.db.ox_release_request
            or pump.db.ox_chief_inspection_version != int(pump.db.event_seq or 0)
            or pump.db.ox_chief_released):
        return False, "Chief must personally inspect the repaired P-01"
    pump.db.ox_chief_released = True
    emit(pump, ship["watch"], "release_granted", sender=actor,
         data={"approver_id": actor.dbref,
               "request_id": pump.db.ox_release_request},
         text="Chief Iona has approved commissioning after local inspection.")
    emit(pump, actor, "release_recorded", sender=actor,
         data={"request_id": pump.db.ox_release_request},
         text="Chief release registered by Evennia.")
    return True, "Chief commissioning authorization recorded"


def report_resolution(actor) -> tuple[bool, str]:
    ship, pump, roster = _world()
    if (not _on_watch(actor, ship, roster)
            or pump.state != "normal" or pump.db.ox_incident_closed
            or pump.db.ox_engineer_verified_version != int(pump.db.event_seq or 0)
            or not pump.db.ox_active_alarm):
        return False, "Fresh verified normal pressure required to close incident"
    pump.db.ox_incident_closed = True
    for person in (ship["officer"], ship["chief"]):
        emit(pump, person, "incident_resolved", sender=actor,
             data={"alarm_id": pump.db.ox_active_alarm},
             text="Ari confirms P-01 has been repaired and verified normal.")
    if roster.db.ox_autoadvance_on_resolution:
        # Explicitly synthetic world-clock advance for this acceptance
        # fixture. No LLM supplies the time or invents a duty obligation.
        roster.db.ox_world_minute = int(roster.db.ox_handover_at)
        roster.db.ox_handover_due = True
        for person in (ship["watch"], ship["chief"]):
            emit(pump, person, "handover_due", data={"minute": "475"},
                 text="07:55 engineering watch handover is due.")
    return True, "Verified incident closed"


def offer_watch(actor) -> tuple[bool, str]:
    ship, pump, roster = _world()
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


def accept_watch(actor) -> tuple[bool, str]:
    ship, pump, roster = _world()
    if (actor != ship["chief"] or actor.location != ship["engineering"]
            or actor.db.crew_role != "chief_engineer"
            or roster.db.ox_handover_offer != ship["watch"].dbref
            or not roster.db.ox_handover_due):
        return False, "No authorised watch handover to accept"
    roster.db.ox_active_engineer = actor.dbref
    roster.db.ox_handover_due = False
    roster.db.ox_handover_offer = None
    for person in (ship["watch"], actor):
        emit(pump, person, "watch_transferred", sender=actor,
             data={"new_watch": actor.dbref},
             text="Engineering watch transferred to Iona.")
    return True, "Engineering watch transferred"
