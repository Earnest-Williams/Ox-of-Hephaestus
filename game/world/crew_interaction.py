"""Character-scoped human-to-crew hails and authoritative bounded replies.

Hails are requests for information, never instructions to execute equipment
actions. Evennia owns addressing, visibility, reply content and deduplication.
The AI handler may only select an offered response type.
"""
from __future__ import annotations

import re

from world.bootstrap import build_ship
from world.live_crew import emit

HAIL_MODES = frozenset({"status", "ack", "decline"})
HAIL_ID = re.compile(r"hail-[0-9]{4,}")


def _crew(ship):
    return {
        "lin": ship["officer"], "ari": ship["watch"],
        "iona": ship["chief"], "mara": ship["cargo"],
        "teo": ship["environment"],
    }


def send_hail(actor, role: str, message: str) -> tuple[bool, str]:
    """Accept one bounded, in-ship request addressed to a real crew member."""
    ship = build_ship()
    target = _crew(ship).get(role.strip().lower())
    message = message.strip()
    if target is None:
        return False, "Unknown crew member; use lin, ari, iona, mara or teo."
    if actor.location not in (
        ship["bridge"], ship["passage"], ship["engineering"],
        ship["cargo_hold"], ship["environmental"],
        ship["mess"], ship["workshop"],
    ):
        return False, "Shipboard communications are unavailable here."
    if actor == target:
        return False, "You cannot hail yourself."
    if (not 1 <= len(message) <= 160
            or any(ord(char) < 32 or ord(char) == 127 for char in message)):
        return False, "Hail must contain 1-160 printable characters."
    pump = ship["pump"]
    ledger = dict(pump.db.ox_hails or {})
    if any(
        entry["sender"] == actor.dbref and entry["recipient"] == target.dbref
        and entry["state"] == "pending"
        for entry in ledger.values()
    ):
        return False, "An unanswered hail to that crewmember is already pending."
    serial = int(pump.db.ox_hail_seq or 0) + 1
    hail_id = f"hail-{serial:04d}"
    pump.db.ox_hail_seq = serial
    ledger[hail_id] = {
        "sender": actor.dbref, "recipient": target.dbref,
        "message": message, "state": "pending", "answer": None,
    }
    pump.db.ox_hails = ledger
    emit(
        pump, target, "crew_hail", sender=actor,
        data={"hail_id": hail_id, "message": message},
        text=f"{actor.key} requests a shipboard reply.",
    )
    return True, f"OX_HAIL_ACCEPTED {hail_id}"


def answer_hail(actor, hail_id: str, mode: str) -> tuple[bool, str]:
    """Resolve a request once and deliver a recipient-private reply.

    A repeated answer for an already resolved hail is acknowledged without
    duplicate delivery, including when the original acknowledgement was lost.
    """
    if not HAIL_ID.fullmatch(hail_id) or mode not in HAIL_MODES:
        return False, "Usage: oxanswer <hail-id> <status|ack|decline>"
    ship = build_ship()
    if actor not in _crew(ship).values():
        return False, "Only the named shipboard crew can answer hails."
    pump = ship["pump"]
    ledger = dict(pump.db.ox_hails or {})
    entry = ledger.get(hail_id)
    if entry is None or entry["recipient"] != actor.dbref:
        return False, "No hail addressed to this crewmember."
    if entry["state"] == "answered":
        return True, f"OX_HAIL_ANSWERED {hail_id}"
    if mode == "status":
        if actor == ship["officer"] and actor.location == ship["bridge"]:
            # Remote BRIDGE telemetry is intentionally available to Lin only.
            answer = ship["console"].readout()
        elif actor == ship["cargo"] and actor.location == ship["cargo_hold"]:
            answer = ship["cradle"].readout()
        elif actor == ship["environment"] and actor.location == ship["environmental"]:
            answer = ship["scrubber"].readout()
        elif actor.location == ship["engineering"]:
            # The local sensor, not an agent's alleged belief, supplies facts.
            answer = pump.readout()
        else:
            answer = "I cannot verify the requested station from here."
    elif mode == "ack":
        answer = "Your hail is received. I am continuing my posted duties."
    else:
        answer = "I cannot provide a verified answer at present."
    entry["state"] = "answered"
    entry["answer"] = mode
    ledger[hail_id] = entry
    pump.db.ox_hails = ledger
    from evennia.objects.models import ObjectDB
    sender = ObjectDB.objects.filter(id=int(entry["sender"][1:])).first()
    if sender is not None:
        emit(
            pump, sender, "crew_reply", sender=actor,
            data={"hail_id": hail_id, "crew": actor.key, "mode": mode},
            text=f"{actor.key}: {answer}",
        )
    emit(
        pump, actor, "hail_answered", sender=actor,
        data={"hail_id": hail_id, "mode": mode},
        text="World recorded the addressed hail response.",
    )
    return True, f"OX_HAIL_ANSWERED {hail_id}"
