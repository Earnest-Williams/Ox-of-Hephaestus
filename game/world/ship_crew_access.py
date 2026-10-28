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
from world.ship_hazardous_access import (
    LOCKS as BAY_LOCKS, CYCLE_S as BAY_CYCLE_S, BayAccessError,
    validate_bay_access, begin_bay_transit,
)
from world.ship_eva_operations import (
    EVAError, LOCKS as EVA_LOCKS, lock_contract, suit_of,
    begin_eva_transit, human_exterior_site_safe,
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
    from world.continuous_ship_physics import _clock
    ship_clock = _clock()
    food = ship_clock.details.get("food")
    if food and actor.dbref in food["last"]["incapacitated"]:
        raise CrewTransitError("Crew member is physically incapacitated by prolonged underfeeding")
    # The casualty and two carriers occupy a timed, physical doorway.
    # No parallel self-walking, freight/EVA or indexed route may silently
    # remove a person before the manual-carry order finishes.
    rescue = ship_clock.details.get("rescue")
    if rescue is not None and any(
            actor.dbref in {patient, job["lead"], job["helper"]}
            for patient, job in rescue["jobs"].items()):
        raise CrewTransitError("Crew member committed to casualty transport")
    bay_access = ship_clock.details.get("bay_access")
    if bay_access is not None and actor.dbref in bay_access["jobs"]:
        raise CrewTransitError("Worker already occupies a sealed bay airlock")
    eva = ship_clock.details.get("eva")
    if eva is not None:
        _, suit = suit_of(eva, actor.dbref)
        if suit and suit["exposure"]["condition"] in {
                "incapacitated", "critical", "dead"}:
            raise CrewTransitError("Suited worker has suffered disabling exposure")
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
        if (clock.details["rotors"]["HAB"]["passenger_indexer"]
                or clock.details.get("hab_sync", {}).get("mode") not in {
                    None, "stowed"}):
            raise CrewTransitError("Moving or parked HAB collar excludes fixed-side hatch")
        for ident in (f"IX-{station}-CARRIER", f"IX-{station}-FIXED-COLLAR"):
            if state("equipment", ident).condition in _BROKEN:
                raise CrewTransitError("Fixed-side HAB indexer hardware damaged")
        return
    if door.source_id == "ACC-WR-FIXED-IX":
        if {src.db.ox_frame, dst.db.ox_frame} != {
                "fixed", "indexer-workrotor"}:
            raise CrewTransitError("Workshop indexer does not meet its fixed dock")
        if _clock().details["rotors"]["WR-01"]["passenger_indexer"]:
            raise CrewTransitError("Workshop fixed hatch and rotating capture overlap")
        if state("equipment", "WR-INDEXER").condition in _BROKEN:
            raise CrewTransitError("Workshop personnel indexer damaged")
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
    rotor_name = names.pop()
    clock = _clock()
    rotor = clock.details.get("rotors", {}).get(rotor_name)
    if rotor_name == "HAB" and door.source_id in {
            "ACC-IX-A-ROT", "ACC-IX-B-ROT"}:
        from world.ship_hab_sync import moving_hab_ready, HabSyncError
        try:
            if moving_hab_ready(
                    clock.details.get("hab_sync"), station=door.source_id[7],
                    hab_rpm=rotor["rpm"], hab_phase_rad=rotor["phase_rad"],
                    hardware_ok=True, powered=True):
                return
        except (HabSyncError, TypeError, KeyError):
            pass
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
    from world.ship_freight_service import GATES, QUALIFIED_ROLES
    if link in GATES:
        # Maintenance workers must actually secure the original freight
        # opening at its upstream station; normal freight runs never imply
        # permission to enter a moving industrial trunk.
        if (actor.db.crew_role not in QUALIFIED_ROLES
                and not actor.check_permstring("Developer")):
            raise CrewTransitError("Freight machinery access requires a qualified worker")
        from world.continuous_ship_physics import _freight_service_entry_ready
        if not _freight_service_entry_ready(link):
            raise CrewTransitError("Service hatch not secured or plant/air no longer safe")
        return door

    if kind == "service_airlock":
        # The two existing F1/F2 assemblies are pressure-sealed, time-bound
        # suit ports. Unknown flywheel-bay gas is NOT ordinary hatch air.
        if link not in BAY_LOCKS or door.setting != "closed":
            raise CrewTransitError("No available rated sealed flywheel service lock")
        from world.continuous_ship_physics import _clock
        from world.ship_crew_exposure import OXYGEN_KG_S
        from world.ship_hazardous_access import validate_bay_access
        corridor, bay, panel_id = BAY_LOCKS[link]
        if {src_id, dst_id} != {corridor, bay} or (
                actor.location.db.ox_frame != dest.db.ox_frame or
                actor.location.db.ox_frame != "fixed"
                or door.reference.get("pressure_boundary") is not True):
            raise CrewTransitError("Flywheel bay service lock has wrong fitted geometry")
        clock = _clock()
        bay_access = clock.details.get("bay_access")
        if bay_access is None:
            raise CrewTransitError("Sealed F1/F2 service access not commissioned")
        validate_bay_access(bay_access)
        if bay not in bay_access["surveyed_bays"]:
            raise CrewTransitError("Unsurveyed F1/F2 service access is closed")
        from world.full_ship_operations import MODEL
        if not CanonicalShipState.objects.filter(
                pk="crew_health:" + actor.dbref, source_model=MODEL).exists():
            raise CrewTransitError("Real suited worker must be physiologically enrolled")
        eva = clock.details.get("eva")
        if eva is None:
            raise CrewTransitError("Fitted EVA suit plant not commissioned")
        _, suit = suit_of(eva, actor.dbref)
        if (not suit or suit["integrity"] < .8
                or suit["exposure"]["condition"] in {
                    "incapacitated", "critical", "dead"}
                or suit["exposure"]["suit_oxygen_kg"] <
                   OXYGEN_KG_S * (BAY_CYCLE_S + 60)):
            raise CrewTransitError("No physically issued suit with remaining F1/F2 cycle oxygen")
        panel = state("equipment", panel_id)
        if panel.space_id != bay or panel.condition in _BROKEN:
            raise CrewTransitError("Actual flywheel local service panel is damaged")
        from world.continuous_ship_physics import _topology, _air_safe
        zone = _topology()[0].get(corridor)
        if (zone != "PZ-TRUNK-A-" + bay[:2] or
                _topology()[0].get(bay) != "VACUUM"):
            raise CrewTransitError("Survey is not of the original unpressurised bay")
        if not _air_safe(state("pressure", zone)):
            raise CrewTransitError("Breathing-safe trunk required before sealed cycle")
        return door
    from world.ship_propulsion_bay_service import (
        HATCH as PROP_BAY_HATCH, BAY as PROP_BAY, finish_entry,
        BayAccessError,
    )
    if link == PROP_BAY_HATCH:
        # The original PROP-SVC hatch is a rated pressure boundary to a
        # formerly unclassified atmosphere. Do not use ordinary-door
        # clearance or accept PPE without a matched, measured gas register.
        from world.continuous_ship_physics import (
            _clock, _propulsion_bay_ready, _propulsion_bay_worker_ready,
        )
        clock = _clock()
        if (door.setting != "open" or
                not _propulsion_bay_worker_ready(
                    actor, clock.details, inside=False)
                or not _propulsion_bay_ready(clock.details)):
            raise CrewTransitError(
                "PROP-SVC requires live equalized gas, a sound rated hatch, a genuine issued suit and the owner's safed permit")
        return door
    indexed = (kind == "indexed_rotary_transfer"
               or link == "ACC-WR-IX-HUB" and kind == "indexer_hatch")
    if (indexed and door.setting != "closed"
            or not indexed and door.setting not in {"open", "closed_or_auto"}):
        raise CrewTransitError("Access boundary is not in its rated transfer position")
    zones = _topology()[0]
    za, zb = zones.get(src_id), zones.get(dst_id)
    # EVA's pre-installed outer airlocks, work platforms and external rails
    # are VACUUM by topology. Never misclassify them as normal air doors.
    from world.continuous_ship_physics import _clock
    eva = _clock().details.get("eva")
    if (link in {lock_contract(room)["inner"] for room in EVA_LOCKS}
            or link in {lock_contract(room)["outer"] for room in EVA_LOCKS}
            or kind in {"eva_rail", "eva_work_platform_transfer"}):
        if eva is None:
            raise CrewTransitError("Fitted EVA suits and airlock machinery not commissioned")
        _, suit = suit_of(eva, actor.dbref)
        if link in {lock_contract(room)["inner"] for room in EVA_LOCKS}:
            room = next(room for room in EVA_LOCKS
                        if lock_contract(room)["inner"] == link)
            spec = lock_contract(room)
            outer = state("access", spec["outer"])
            if (eva["locks"][room]["mode"] != "pressurised"
                    or outer.setting != "closed"
                    or door.setting != "open"):
                raise CrewTransitError("Inner hatch not isolated from external vacuum")
            if not za.startswith("PZ-") or not zb.startswith("PZ-"):
                raise CrewTransitError("No real pressure cells at inner lock")
            a, b = state("pressure", za), state("pressure", zb)
            if not _air_safe(a) or not _air_safe(b):
                raise CrewTransitError("Unsafe breathing gas on either side of airlock")
            pa = a.quantity * R_SPECIFIC_AIR * a.details["temperature_k"] / a.details["gas_volume_m3"]
            pb = b.quantity * R_SPECIFIC_AIR * b.details["temperature_k"] / b.details["gas_volume_m3"]
            if abs(pa - pb) > 2000:
                raise CrewTransitError("Airlock inner hatch unequal pressure")
            return door
        if not suit or suit["integrity"] < 0.8 or (
                suit["exposure"]["suit_oxygen_kg"] <= 0):
            raise CrewTransitError("Exterior traversal requires a charged issued suit")
        crawler = state("equipment", lock_contract(suit["home"])["crawler"])
        if crawler.condition in _BROKEN:
            raise CrewTransitError("Assigned real EVA crawler is unserviceable")
        if link in {lock_contract(room)["outer"] for room in EVA_LOCKS}:
            room = next(room for room in EVA_LOCKS
                        if lock_contract(room)["outer"] == link)
            spec = lock_contract(room)
            if (eva["locks"][room]["mode"] != "vacuum"
                    or state("access", spec["inner"]).setting != "closed"
                    or state("pressure", spec["zone"]).quantity > 0.001
                    or {src_id, dst_id} != {room, spec["outside"]}):
                raise CrewTransitError("Outer hatch lacks pumped-down gas isolation")
            return door
        if kind not in {"eva_rail", "eva_work_platform_transfer"}:
            raise CrewTransitError("No rated EVA access")
        if (za != "VACUUM" or zb != "VACUUM"
                or not src_id.startswith("EXT-") or not dst_id.startswith("EXT-")):
            raise CrewTransitError("External route does not join two real vacuum sites")
        if kind == "eva_work_platform_transfer":
            if state("equipment", "EVA-WORK-PLATFORM").condition in _BROKEN:
                raise CrewTransitError("Rated exterior work platform damaged")
            from world.ship_exterior_radiators import FACES as RADIATOR_FACES
            if dst_id in RADIATOR_FACES:
                from world.continuous_ship_physics import _radiator_worksite_ready
                details = _clock().details
                radiator = RADIATOR_FACES[dst_id]
                if not _radiator_worksite_ready(
                        details, radiator,
                        {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="equipment")},
                        {row.source_id: row for row in
                         CanonicalShipState.objects.filter(category="isolator")}):
                    raise CrewTransitError(
                        "Radiator remains hot, running, unisolated or without an issued work permit")
            elif dst_id == "EXT-PROP-AFT":
                # The original nozzle face is a hazardous work pad, not an
                # unsurveyed generic EVA shortcut. Demand the real locally
                # commissioned plume permit and propulsion/RCS safing.
                from world.continuous_ship_physics import _propulsion_exterior_ready
                details = _clock().details
                hardware = {row.source_id: row for row in
                            CanonicalShipState.objects.filter(category="equipment")}
                if not _propulsion_exterior_ready(details, hardware):
                    raise CrewTransitError(
                        "No positively surveyed, inhibited aft plume inspection permit")
            elif (src_id not in RADIATOR_FACES
                    and src_id != "EXT-PROP-AFT"
                    and not human_exterior_site_safe(
                        door.reference.get("to"),
                        _clock().details.get("rotors", {}))):
                raise CrewTransitError(
                    "Rotating skin or unsupported hot exterior worksite")
            # Retreat from the exterior pad to a fixed rail remains possible
            # even after insulation/power/valve loss; do not strand a crew
            # member simply because the equipment just became unsafe.
        return door
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
                powered=True, hab_sync=clock.details.get("hab_sync")):
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

    if link in BAY_LOCKS and door.reference.get("kind") == "service_airlock":
        from world.continuous_ship_physics import _snapshot, _event
        clock = _clock(lock=True)
        try:
            bay_access = begin_bay_transit(
                clock.details["bay_access"], actor=actor.dbref,
                link=link, direction=exit_obj.db.ox_access_direction,
                source=origin, destination=dest.db.ox_space_id,
                request_id=request_id)
        except BayAccessError as exc:
            raise CrewTransitError(str(exc)) from exc
        before = _snapshot(clock)
        details = dict(clock.details)
        details["bay_access"] = bay_access
        clock.details = details
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        event = _event(clock, "crew_flywheel_sealed_service_queued",
                       before, actor=actor, request_id=request_id)
        outcome = {
            "request_id": request_id, "actor_dbref": actor.dbref,
            "operation": "traverse", "target": link, "status": "queued",
            "source_event_id": str(event.sequence),
            "destination": dest.db.ox_space_id,
            "travel_seconds": BAY_CYCLE_S,
        }
        WorkReceipt.objects.create(
            request_id=request_id, actor_dbref=actor.dbref,
            target="ship_physics", operation="traverse", arguments=args,
            outcome=outcome, game_time=float(clock.details["last_game_time"]))
        return outcome
    if (door.reference.get("kind") == "indexed_rotary_transfer"
            or link == "ACC-WR-IX-HUB"):
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
    if (link in {lock_contract(room)["outer"] for room in EVA_LOCKS}
            or door.reference.get("kind") in {
                "eva_rail", "eva_work_platform_transfer"}):
        from world.continuous_ship_physics import _snapshot, _event
        item = _clock(lock=True)
        eva = item.details.get("eva")
        if eva is None:
            raise CrewTransitError("EVA suit system is not commissioned")
        try:
            altered = begin_eva_transit(
                eva, actor=actor.dbref, link=link,
                source=origin, destination=dest.db.ox_space_id,
                seconds=door.reference["traverse_time_s"], request_id=request_id)
        except EVAError as exc:
            raise CrewTransitError(str(exc)) from exc
        previous = _snapshot(item)
        d = dict(item.details)
        d["eva"] = altered
        item.details = d
        item.revision += 1
        item.save(update_fields=["details", "revision"])
        event = _event(item, "crew_eva_transit_queued", previous,
                       actor=actor, request_id=request_id)
        outcome = {
            "request_id": request_id, "actor_dbref": actor.dbref,
            "operation": "traverse", "target": link, "status": "queued",
            "source_event_id": str(event.sequence),
            "destination": dest.db.ox_space_id,
            "travel_seconds": door.reference["traverse_time_s"],
        }
        WorkReceipt.objects.create(
            request_id=request_id, actor_dbref=actor.dbref,
            target="ship_physics", operation="traverse", arguments=args,
            outcome=outcome, game_time=float(item.details["last_game_time"]))
        return outcome
    from world.continuous_ship_physics import _clock
    if (_clock().details.get("eva") is not None and
            actor.dbref in _clock().details["eva"]["transits"]):
        raise CrewTransitError("Suit traveler is already on an exterior route")
    if any(j["actor"] == actor.dbref for j in
           (_clock().details.get("personnel_transfers") or
            {"jobs": {}})["jobs"].values()):
        raise CrewTransitError("Crew cannot leave a moving personnel carriage")
    if not actor.move_to(dest):
        raise CrewTransitError("Crew movement vetoed")
    if link == PROP_BAY_HATCH and dest.db.ox_space_id == PROP_BAY:
        from world.continuous_ship_physics import _snapshot, _event
        entry_before = _snapshot(clock)
        details = dict(clock.details)
        try:
            details["propulsion_bay"] = finish_entry(
                details["propulsion_bay"], worker=actor.dbref)
        except BayAccessError as exc:
            raise CrewTransitError(str(exc)) from exc
        clock.details = details
        clock.revision += 1
        clock.save(update_fields=["details", "revision"])
        _event(clock, "g19_suited_propulsion_bay_entry", entry_before, actor=actor)
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
