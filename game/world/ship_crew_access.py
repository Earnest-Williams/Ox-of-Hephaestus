"""G19 canonical traversals: installed Evennia exits plus live physical gates."""
from __future__ import annotations

import math
import uuid

from django.db import transaction

from world.full_ship_operations import _BROKEN, ShipOperationsError, _require_installed, state
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_world import find_ship_space
from world.ship_indexed_personnel import (
    IndexedTransferError, begin_personnel_transfer,
    indexed_mechanism_ready, link_contract,
)


class CrewTransitError(ShipOperationsError):
    """An actual crew movement failed a physical or safety check."""


def _health_gate(actor):
    if actor is None or getattr(actor, "location", None) is None:
        raise CrewTransitError("Physical crew member at the exit required")
    if actor.db.ox_terminal_dead:
        raise CrewTransitError("Deceased crew cannot travel")
    health = CanonicalShipState.objects.filter(pk="crew_health:" + str(actor.dbref)).first()
    if health and health.condition in {"incapacitated", "critical", "dead"}:
        raise CrewTransitError("Crew member is physically unable to travel")
    if not actor.db.crew_role and not actor.check_permstring("Developer"):
        raise CrewTransitError("No shipboard crew identity")


def _rotary_gate(src, dst, door):
    """Only an indexed, stopped, actually captured transfer may bridge frames."""
    from world.continuous_ship_physics import _clock
    from world.ship_motion_machinery import ROTORS

    if src.db.ox_frame == dst.db.ox_frame:
        return
    # HAB's independently movable capsule can dock to the stationary spine
    # only when its rotary capture is fully retracted. The fixed-end hatch
    # remains a separate positively opened pressure boundary.
    if door.source_id in {"ACC-IX-A-FIX", "ACC-IX-B-FIX"}:
        station = door.source_id[7]
        if {src.db.ox_frame, dst.db.ox_frame} != {"fixed", "indexer"}:
            raise CrewTransitError("Habitation capsule is not at its fixed dock")
        clock = _clock()
        if clock.details["rotors"]["HAB"]["passenger_indexer"]:
            raise CrewTransitError("Fixed and rotary HAB collars cannot both be captured")
        for ident in (f"IX-{station}-CARRIER", f"IX-{station}-FIXED-COLLAR"):
            if state("equipment", ident).condition in _BROKEN:
                raise CrewTransitError("Fixed-side HAB indexer hardware damaged")
        return
    names = []
    for rotor in ROTORS:
        if (str(src.db.ox_space_id).startswith(rotor + "-") or
                str(dst.db.ox_space_id).startswith(rotor + "-")):
            names.append(rotor)
    for rotor, prefix in (("HAB", "HAB-"), ("WR-01", "WR-")):
        if (str(src.db.ox_space_id).startswith(prefix) or
                str(dst.db.ox_space_id).startswith(prefix)):
            names.append(rotor)
    names = set(names)
    if len(names) != 1:
        raise CrewTransitError("Moving-frame transfer mechanism unclassified")
    rotor = _clock().details.get("rotors", {}).get(names.pop())
    if not rotor or not (
            rotor.get("passenger_indexer") and not rotor.get("freight_collar")
            and rotor.get("hardlock") and rotor.get("brake")
            and rotor.get("target_rpm") == 0
            and abs(rotor.get("rpm", 1.0)) < 0.001):
        raise CrewTransitError("Personnel carriage is not captured and hardlocked")


def _clearance(actor, exit_obj, dest):
    from world.continuous_ship_physics import (
        _air_safe, _hatch_open_preflight, _topology, R_SPECIFIC_AIR,
    )

    _health_gate(actor)
    if actor.location != exit_obj.location or dest != exit_obj.destination:
        raise CrewTransitError("Exit does not begin at this character's location")
    src_id = actor.location.db.ox_space_id
    dst_id = dest.db.ox_space_id
    link = exit_obj.db.ox_access_link_id
    direction = exit_obj.db.ox_access_direction
    if not link or direction not in {"forward", "reverse"}:
        raise CrewTransitError("Unrecognised authored ship exit")
    if find_ship_space(src_id) != actor.location or find_ship_space(dst_id) != dest:
        raise CrewTransitError("Unrecognised or stale physical ship space")
    door = state("access", link, lock=True)
    ends = ((door.reference.get("from"), door.reference.get("to"))
            if direction == "forward" else
            (door.reference.get("to"), door.reference.get("from")))
    if (src_id, dst_id) != ends or door.condition in _BROKEN:
        raise CrewTransitError("Access link damaged or not in the approved topology")
    kind = str(door.reference.get("kind", "")).lower()
    indexed = kind == "indexed_rotary_transfer"
    if (indexed and door.setting != "closed"
            or not indexed and door.setting not in {"open", "closed_or_auto"}):
        raise CrewTransitError("Access boundary is not in its rated transfer position")
    zones = _topology()[0]
    za, zb = zones.get(src_id), zones.get(dst_id)
    if (not isinstance(za, str) or not isinstance(zb, str)
            or not za.startswith("PZ-") or not zb.startswith("PZ-")):
        raise CrewTransitError("Unknown atmosphere or EVA access cannot be traversed")
    a, b = state("pressure", za, lock=True), state("pressure", zb, lock=True)
    if not _air_safe(a) or not _air_safe(b):
        raise CrewTransitError("Unsafe atmosphere at an access endpoint")
    if indexed:
        # An indexed passage begins as a sealed, time-bound *machine cycle*,
        # not an instantly traversable open doorway. Both pressure cells must
        # be healthy and matched before the captive personnel carrier moves.
        from world.continuous_ship_physics import _clock
        clock = _clock()
        transfers = clock.details.get("personnel_transfers")
        if transfers is None:
            raise CrewTransitError("Indexed crew transfer has not been commissioned")
        if any(j["actor"] == actor.dbref for j in transfers["jobs"].values()):
            raise CrewTransitError("Crew member is already inside an active carriage")
        try:
            spec = link_contract(link)
        except IndexedTransferError as exc:
            raise CrewTransitError(str(exc)) from exc
        if not door.reference.get("pressure_boundary") or za == zb:
            raise CrewTransitError("Indexed carriage has no independent rated gas boundary")
        access = {link: door, spec["fixed_hatch"]:
                  state("access", spec["fixed_hatch"], lock=True)}
        hardware = {key: state("equipment", key)
                    for key in spec["hardware"]}
        if not indexed_mechanism_ready(
                link, rotors=clock.details["rotors"], equipment=hardware,
                access=access, pressure={za: a, zb: b},
                room_zones=zones, pressure_safe=_air_safe,
                powered=True):
            raise CrewTransitError("Indexer capture, fixed hatch or live air is unsafe")
        return door
    if za != zb:
        if door.reference.get("pressure_boundary") is not True or door.setting != "open":
            raise CrewTransitError("No positively opened rated pressure boundary")
        pa = a.quantity * R_SPECIFIC_AIR * a.details["temperature_k"] / a.details["gas_volume_m3"]
        pb = b.quantity * R_SPECIFIC_AIR * b.details["temperature_k"] / b.details["gas_volume_m3"]
        if not math.isfinite(pa) or not math.isfinite(pb) or abs(pa - pb) > 2000:
            raise CrewTransitError("Pressure differential exceeds transfer limit")
        if link.startswith("ACC-BR-"):
            _hatch_open_preflight(door)
    if door.reference.get("pressure_boundary") and door.setting != "open":
        raise CrewTransitError("Rated boundary requires explicit opening")
    if any(word in kind for word in ("eva", "external", "freight", "airlock")):
        raise CrewTransitError("Special transfer mechanism required")
    _rotary_gate(actor.location, dest, door)
    return door


@transaction.atomic
def traverse_canonical_exit(actor, exit_obj, dest, *, request_id=None):
    """Execute and journal a physical exit movement once, under the world clock."""
    from world.continuous_ship_physics import _clock

    _require_installed()
    clock = _clock(lock=True)
    request_id = request_id or uuid.uuid4().hex
    if not isinstance(request_id, str) or len(request_id) != 32 or any(
            x not in "0123456789abcdef" for x in request_id):
        raise CrewTransitError("Invalid movement request ID")
    previous = WorkReceipt.objects.select_for_update().filter(pk=request_id).first()
    link = exit_obj.db.ox_access_link_id
    args = {"link": link, "direction": exit_obj.db.ox_access_direction}
    if previous:
        if (previous.actor_dbref != actor.dbref or previous.target != "ship_physics"
                or previous.operation != "traverse" or previous.arguments != args):
            raise CrewTransitError("Global movement request-ID collision")
        return dict(previous.outcome)
    door = _clearance(actor, exit_obj, dest)
    origin = actor.location.db.ox_space_id
    if door.reference.get("kind") == "indexed_rotary_transfer":
        from world.continuous_ship_physics import _snapshot, _event
        clock = _clock(lock=True)
        try:
            transfers = begin_personnel_transfer(
                clock.details["personnel_transfers"],
                link=link, actor=actor.dbref, origin=origin,
                destination=dest.db.ox_space_id, request_id=request_id)
        except IndexedTransferError as exc:
            raise CrewTransitError(str(exc)) from exc
        before = _snapshot(clock)
        details = dict(clock.details)
        details["personnel_transfers"] = transfers
        clock.details = details
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        event = _event(clock, "crew_indexed_transfer_queued", before,
                       actor=actor, request_id=request_id)
        outcome = {
            "request_id": request_id, "actor_dbref": actor.dbref,
            "operation": "traverse", "target": link, "status": "queued",
            "source_event_id": str(event.sequence),
            "destination": dest.db.ox_space_id,
            "travel_seconds": link_contract(link)["seconds"],
        }
        WorkReceipt.objects.create(
            request_id=request_id, actor_dbref=actor.dbref,
            target="ship_physics", operation="traverse", arguments=args,
            outcome=outcome, game_time=float(clock.details["last_game_time"]),
        )
        return outcome
    from world.continuous_ship_physics import _clock
    if any(j["actor"] == actor.dbref for j in
           (_clock().details.get("personnel_transfers") or
            {"jobs": {}})["jobs"].values()):
        raise CrewTransitError("Crew cannot leave a moving personnel carriage")
    if not actor.move_to(dest):
        raise CrewTransitError("Crew movement vetoed")
    event = CanonicalShipEvent.objects.create(
        component_key=door.key, operation="crew_traverse",
        before={"space_id": origin}, after={"space_id": dest.db.ox_space_id},
        actor_dbref=actor.dbref, request_id=request_id,
        game_time=float(clock.details["last_game_time"]),
    )
    outcome = {
        "request_id": request_id, "actor_dbref": actor.dbref,
        "operation": "traverse", "target": link, "status": "succeeded",
        "source_event_id": str(event.sequence), "destination": dest.db.ox_space_id,
    }
    WorkReceipt.objects.create(
        request_id=request_id, actor_dbref=actor.dbref, target="ship_physics",
        operation="traverse", arguments=args, outcome=outcome,
        game_time=float(clock.details["last_game_time"]),
    )
    return outcome
