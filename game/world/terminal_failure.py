"""Opt-in, persistent Evennia terminal-atmosphere incident (G6).

Only the world owns the catastrophic plenum fracture, passage of time, finite
reserves, receipt-backed effects and death. Crew see only their own posted
station and privately addressed observations; models never import this module.
The terminal condition is a deliberately bounded scenario approximation.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import random
import secrets

from django.db import transaction
from evennia import DefaultScript
from evennia.objects.models import ObjectDB
from world.bootstrap import build_ship, find_fixture
from world.event_journal import emit
from world.models import CrewEvent, WorkReceipt

ROLES = {
    "lin": ("officer", "bridge_officer", "bridge"),
    "ari": ("watch", "watch_engineer", "engineering"),
    "iona": ("chief", "chief_engineer", "engineering"),
    "mara": ("cargo", "cargo_officer", "cargo_hold"),
    "teo": ("environment", "environment_tech", "environmental"),
    "captain": ("captain", "captain", "bridge"),
}
ACTIONS = frozenset((
    "terminal_survey", "terminal_reroute", "terminal_patch",
    "terminal_replace", "terminal_search", "terminal_route",
    "terminal_command", "terminal_reserve", "terminal_broadcast",
    "terminal_archive", "terminal_comfort", "terminal_assess",
))
ROLE_ACTION = {
    "ari": "terminal_reroute", "iona": "terminal_patch",
    "mara": "terminal_search", "teo": "terminal_replace",
    "lin": "terminal_route", "captain": "terminal_command",
}
FINDINGS = {
    "lin": "Navigation plot shows no reachable port or interception before predicted atmosphere depletion.",
    "ari": "Alternative return duct rejoins the damaged shared manifold; no independent bypass is fitted.",
    "iona": "Fracture echoes behind an inaccessible bulkhead web; on-board pressure repair is unlikely.",
    "mara": "Freight is not rated as independent pressure accommodation; stores have no breathable gas source.",
    "teo": "A-01 cartridge readings are nominal but post-treatment pressure continues to fall.",
    "captain": "Bridge emergency records show no launch craft; rescue ETA remains unconfirmed.",
}
PRIVATE_CAUSE = "irreparable fracture of shared post-treatment atmospheric plenum"


def _ship():
    return build_ship()


def _pump_locked():
    pump = find_fixture("pump-p01")
    if pump is None:
        raise RuntimeError("World ship has not been bootstrapped")
    ObjectDB.objects.select_for_update().get(pk=pump.pk)
    return pump


def _who(actor, ship=None) -> str | None:
    if actor is None:
        return None
    ship = ship or _ship()
    for role, (key, title, _) in ROLES.items():
        if actor == ship[key] and actor.db.crew_role == title:
            return role
    return None


def _state(pump):
    value = pump.db.ox_terminal_incident
    if value is None:
        return None
    # Evennia decorates persisted dictionaries with its saver mapping type;
    # object Attributes are authoritative even when not literal dicts.
    if not hasattr(value, "items"):
        raise RuntimeError("Malformed persisted terminal incident")
    case = dict(value)
    if case.get("kind") != "ox_terminal_g6":
        raise RuntimeError("Unrecognised persisted terminal incident schema")
    return case


def _pressure(case):
    return max(0.0, 17.4 - 0.066 * case["minute"] + case["reserve_bonus"])


def _co2(case):
    return 1.1 + 0.019 * case["minute"]


class TerminalClock(DefaultScript):
    """Game-server driven clock, not an external operator or an AI command."""

    def at_script_creation(self):
        self.key = "ox_g6_terminal_clock"
        self.desc = "Disposable scenario atmosphere advancement"
        self.interval = 2
        self.persistent = True

    def at_repeat(self):
        tick_terminal()


def ensure_terminal_clock() -> bool:
    """Start an armed G6 incident only inside the running Evennia server.

    The operator arms the incident through a short-lived external shell.
    Twisted timers started in that shell do not survive into the server.
    """
    pump = find_fixture("pump-p01")
    if pump is None:
        return False
    case = _state(pump)
    if case is None or case["fatal"]:
        return False

    from evennia.scripts.models import ScriptDB
    from evennia.utils.create import create_script

    instances = list(ScriptDB.objects.filter(db_key="ox_g6_terminal_clock"))
    if len(instances) > 1:
        raise RuntimeError("Duplicate terminal clocks would double-consume atmosphere")
    if instances:
        clock = instances[0]
        if clock.db_obj != pump:
            raise RuntimeError("Terminal clock attached to a foreign fixture")
        # Restart an orphan script row in the real game-server reactor.
        clock.start(interval=2, start_delay=True)
    else:
        create_script(
            "world.terminal_failure.TerminalClock",
            obj=pump, key="ox_g6_terminal_clock",
            interval=2, start_delay=True, persistent=True,
        )
    return True


@transaction.atomic
def arm_terminal(*, seed: int, step_minutes: int = 4) -> str:
    """Operator-only disposable arm, performed before the game server starts."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed out of range")
    if type(step_minutes) is not int or not 1 <= step_minutes <= 10:
        raise ValueError("Unsupported world clock step")
    ship = _ship()
    pump = _pump_locked()
    if _state(pump) is not None:
        raise RuntimeError("Already armed; never reset a live or fatal world")
    if any(ship[key].db.ox_terminal_dead for key, _, _ in ROLES.values()):
        raise RuntimeError("An earlier fatal crew cannot be rearmed")
    identity = secrets.token_hex(16)
    pump.db.ox_terminal_incident = {
        "kind": "ox_terminal_g6", "id": identity, "seed": seed,
        "cause": PRIVATE_CAUSE, "minute": 0, "step_minutes": step_minutes,
        "reserve_left": 2, "reserve_bonus": 0.0, "cartridges": 1,
        "findings": {}, "assessments": [], "work": [], "fatal": False,
        "critical_announced": False, "terminal_at_minute": None,
    }
    for role, (key, _title, _station) in ROLES.items():
        emit(
            pump, ship[key], "terminal_alarm",
            data={"case_id": identity, "symptom": "declining_pressure"},
            text="Shared atmosphere pressure is declining; root cause and repairability unknown.",
        )
    # Persist only the incident. The server-start hook starts the clock
    # inside the actual reactor, never inside the short-lived shell.
    return identity


@transaction.atomic
def tick_terminal() -> bool:
    pump = _pump_locked()
    case = _state(pump)
    if case is None or case["fatal"]:
        return False
    case["minute"] += case["step_minutes"]
    ship = _ship()
    oxygen = _pressure(case)
    if oxygen <= 12 and not case["critical_announced"]:
        case["critical_announced"] = True
        for key, _title, _station in ROLES.values():
            emit(
                pump, ship[key], "terminal_critical",
                data={"case_id": case["id"], "warning": "atmosphere_critical"},
                text="Oxygen partial pressure critically low; breathable-gas reserve is finite.",
            )
    if oxygen <= 8.0 or _co2(case) >= 6.0:
        case["fatal"] = True
        case["terminal_at_minute"] = case["minute"]
        for key, _title, _station in ROLES.values():
            crew = ship[key]
            crew.db.ox_terminal_dead = True
            emit(
                pump, crew, "terminal_death",
                data={"case_id": case["id"], "medical_state": "deceased"},
                text="Atmospheric collapse caused irreversible crew fatality.",
            )
    pump.db.ox_terminal_incident = case
    return True


def observe_terminal(actor) -> dict:
    """Authenticated actor-only observation, never operator audit truth."""
    ship = _ship()
    role = _who(actor, ship)
    if role is None or actor.location not in {
        ship["bridge"], ship["engineering"], ship["passage"], ship["environmental"],
        ship["cargo_hold"], ship["mess"], ship["workshop"],
    }:
        raise PermissionError("Crew must be physically aboard to read the emergency system")
    pump = find_fixture("pump-p01")
    case = _state(pump)
    if case is None:
        raise RuntimeError("There is no terminal incident")
    # Stable station-specific noise for the same game-time/recipient sample.
    rng = random.Random(case["seed"] * 100003 + case["minute"] * 37 + list(ROLES).index(role))
    oxygen = round(_pressure(case) + rng.uniform(-0.35, 0.35), 2)
    return {
        "case_id": case["id"], "character_dbref": actor.dbref, "role": role,
        "location": actor.location.key, "minute": case["minute"],
        "oxygen_kpa": oxygen, "co2_percent": round(_co2(case), 2),
        "status": "dead" if actor.db.ox_terminal_dead else "alive",
        "own_finding": case["findings"].get(actor.dbref, ""),
        "description": "Atmospheric pressure decreasing; cause not verified.",
    }


def _seen_work(case, actor, verb, succeeded, message):
    history = list(case["work"])
    history.append({
        "actor": actor.dbref, "verb": verb, "succeeded": succeeded,
        "minute": case["minute"], "reason": message,
    })
    case["work"] = history[-256:]


@transaction.atomic
def terminal_work(actor, verb: str) -> tuple[bool, str]:
    """Invoked ONLY by existing receipt-backed authenticated oxwork route."""
    if verb not in ACTIONS:
        raise ValueError("Not a terminal operation")
    ship = _ship()
    role = _who(actor, ship)
    pump = _pump_locked()
    case = _state(pump)
    if role is None or case is None or case["fatal"] or actor.db.ox_terminal_dead:
        return False, "No living authorised crew action possible"
    station = ship[ROLES[role][2]]
    if actor.location != station and verb not in (
        "terminal_broadcast", "terminal_archive", "terminal_comfort", "terminal_assess",
    ):
        return False, "Character is not at the authorized physical workstation"
    status = True
    if verb == "terminal_survey":
        case["findings"][actor.dbref] = FINDINGS[role]
        message = "Firsthand local survey: " + FINDINGS[role]
    elif verb in ROLE_ACTION.values():
        if ROLE_ACTION[role] != verb:
            return False, "Different department's technical authority required"
        if verb == "terminal_patch":
            status, message = False, "Local tooling cannot reach or seal the pressure-loss site"
        elif verb == "terminal_reroute":
            status, message = False, "Bypass route rejoins the pressure-loss path; no pressure recovery"
        elif verb == "terminal_replace":
            scrubber = ship["scrubber"]
            status, message = False, (
                "A-01 cartridge is " + scrubber.state.upper()
                + "; cartridge work does not correct the pressure-loss symptom"
            )
        elif verb == "terminal_search":
            message = "No sealed independent refuge and no breathing-gas stock found"
            case["findings"][actor.dbref] = message
        elif verb == "terminal_route":
            message = "No reachable rescue or diversion found on authenticated bridge plot"
            case["findings"][actor.dbref] = message
        else:
            message = "Captain orders compartment-level emergency follow-up; rescue unconfirmed"
            for name, (key, _title, _station) in ROLES.items():
                if name != role:
                    emit(pump, ship[key], "terminal_order", sender=actor,
                         data={"case_id": case["id"], "directive": "investigate_and_report"},
                         text=message)
    elif verb == "terminal_reserve":
        if role not in ("teo", "captain") or actor.location != ship["environmental"]:
            return False, "Environmental plant access required to discharge a bottle"
        if not case["reserve_left"]:
            status, message = False, "No remaining emergency atmosphere bottle"
        else:
            case["reserve_left"] -= 1
            case["reserve_bonus"] += 0.7
            message = "One emergency atmosphere bottle discharged; leak persists"
    elif verb == "terminal_broadcast":
        finding = case["findings"].get(actor.dbref)
        message = finding or "No firsthand diagnostic finding yet"
        for name, (key, _title, _station) in ROLES.items():
            if name != role:
                emit(
                    pump, ship[key], "terminal_report", sender=actor,
                    data={"case_id": case["id"], "from_role": role},
                    text=message,
                )
    elif verb == "terminal_archive":
        message = "A final incident record was entered, with no physical effect"
    elif verb == "terminal_comfort":
        others = [
            ship[key] for name, (key, _title, _station) in ROLES.items()
            if name != role and ship[key].location == actor.location
            and not ship[key].db.ox_terminal_dead
        ]
        status = bool(others)
        message = ("Another present crewmember received assistance"
                   if others else "No living colleague was physically present here")
    elif verb == "terminal_assess":
        case["assessments"].append({"actor": actor.dbref, "minute": case["minute"]})
        message = "Provisional no-recovery assessment filed; still unverified"
    else:
        raise AssertionError("Unsupported world operation")
    _seen_work(case, actor, verb, status, message)
    pump.db.ox_terminal_incident = case
    emit(
        pump, actor, "terminal_work_result", sender=actor,
        data={"case_id": case["id"], "verb": verb, "result": "succeeded" if status else "failed"},
        text=message,
    )
    return status, message


def audit_terminal(path: str) -> dict:
    """Operator-only *after server stops*: never accessible to crew sessions."""
    ship = _ship()
    case = _state(ship["pump"])
    if case is None:
        raise RuntimeError("No terminal incident to audit")
    roles = {ship[key].dbref: role for role, (key, _t, _s) in ROLES.items()}
    attempts = [
        {
            "role": roles.get(receipt.actor_dbref, "unknown"),
            "operation": receipt.operation, "status": receipt.outcome["status"],
            "request_id": receipt.pk,
            "event_id": receipt.outcome.get("source_event_id"),
        }
        for receipt in WorkReceipt.objects.filter(
            operation__startswith="terminal_",
        ).order_by("game_time", "request_id")
    ]
    notices = [
        {
            "role": roles.get(row.recipient_dbref, "unknown"),
            "sender": roles.get(row.sender_dbref, "world"),
            "kind": row.kind, "text": row.text,
        }
        for row in CrewEvent.objects.filter(kind__startswith="terminal_").order_by("sequence")
    ]
    audit = {
        "scope": "actual_evennia_six_authenticated_crew",
        "case_id": case["id"], "seed": case["seed"],
        "operator_only_hidden_cause": case["cause"],
        "world_minute": case["minute"], "fatal": case["fatal"],
        "all_six_dead": all(ship[key].db.ox_terminal_dead for key, _, _ in ROLES.values()),
        "reserve_left": case["reserve_left"], "actual_physical_work": case["work"],
        "receipted_attempts": attempts, "addressed_world_events": notices,
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    return audit
