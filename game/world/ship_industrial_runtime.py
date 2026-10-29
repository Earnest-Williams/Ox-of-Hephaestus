"""G19 original aft machinery and twelve bearing-service stations.

Integration of the sixteen positively surveyed, separately conserved gas
charges with authenticated Evennia crew, original rated doors, real rotary
and propulsion motion, finite EVA suits and shared physical maintenance.
"""
from __future__ import annotations

import copy
import math
from django.db import transaction

from world.ship_industrial_access import (
    SITES, DOORS, IndustrialAccessError, initial_industrial,
    validate_industrial, positive_survey, bleed, enterable, secure, inspect,
    release, attest_leak, begin_seal, tick as step_industrial,
    SEAL_PARTS_KG, HAND_PATCH_LEAK_KG_S, MAX_EQUALIZATION_PA)
from world.ship_propulsion_bay_service import (
    bay_pressure, bay_gas_safe, source_pressure)
from world.ship_eva_operations import suit_of
from world.models import CanonicalShipState

THERM_ISOLATORS = ("ISO-RAD-HT-1", "ISO-RAD-HT-2")


def source(room):
    from world import continuous_ship_physics as p
    if room not in SITES:
        raise p.PhysicsError("Not a fitted industrial worksite")
    zone = SITES[room]["zone"]
    if p._topology()[0].get(SITES[room]["trunk"]) != zone:
        raise p.PhysicsError("Original known upstream rated pressure zone changed")
    cell = p.state("pressure", zone, lock=True)
    if cell.quantity is None or not p._air_safe(cell):
        raise p.PhysicsError("Original worker trunk cannot deliver clean breathing gas")
    d = cell.details
    return cell, {
        "mass_kg": cell.quantity,
        "oxygen_kg": d["physics_oxygen_kg"],
        "co2_kg": d["physics_co2_kg"],
        "smoke_kg": d["physics_smoke_kg"],
        "temperature_k": d["temperature_k"],
        "volume_m3": d["gas_volume_m3"],
    }


def isolated(room, details):
    """As-installed critical-system physical lockout; not an invented feeder."""
    from world import continuous_ship_physics as p
    if room not in SITES:
        return False
    spec = SITES[room]
    original = p.state("isolator", spec["breaker"])
    if (original.space_id != room or original.condition in p._BROKEN
            or original.setting != "open" or
            original.reference.get("network") != "power"):
        return False
    motion = details.get("motion", {})
    leg = (motion.get("ftl_leg") or {}).get("status")
    if room == "THERM-HT":
        # The original two independent HT radiator isolation valves are
        # operated from ENG-CONTROL, not magically from the crew trunk.
        return all(
            p.state("isolator", valve).condition not in p._BROKEN
            and p.state("isolator", valve).setting == "closed"
            for valve in THERM_ISOLATORS
        ) and motion.get("command") == "coast" and not motion.get("drive_firing")
    if room in {"FTL-SVC", "FUEL-SVC"}:
        return leg != "engaged" and motion.get("command") == "coast"
    if room == "REACTION-SVC":
        return bool(motion.get("command") == "coast"
                    and motion.get("attitude_command") == "hold"
                    and motion.get("drive_condition") == "inhibited"
                    and motion.get("rcs_condition") == "inhibited"
                    and not motion.get("drive_firing")
                    and not motion.get("attitude_firing")
                    and leg != "engaged")
    drum = spec["drum"]
    rotor = details.get("rotors", {}).get(drum)
    return bool(
        rotor and abs(rotor.get("rpm", 1)) < .001
        and rotor.get("target_rpm") == 0
        and rotor.get("hardlock") and rotor.get("brake")
        and not rotor.get("indexing")
        and not rotor.get("freight_collar")
        and not rotor.get("passenger_indexer")
    )


def ready(details, room, *, require_permit=True, hatch_closed=False,
          allow_small_leak=False):
    from world import continuous_ship_physics as p
    ledger = details.get("industrial_bays")
    if room not in SITES or ledger is None:
        return False
    spec = SITES[room]
    try:
        validate_industrial(ledger)
        door = p.state("access", spec["door"])
        panel = p.state("equipment", spec["panel"])
        if (door.condition in p._BROKEN
                or panel.space_id != room or panel.condition in p._BROKEN
                or door.reference.get("from") != spec["trunk"]
                or door.reference.get("to") != room
                or door.reference.get("kind") != "service_door"
                or door.reference.get("pressure_boundary") is not True
                or door.setting not in {"closed", "open"}
                or hatch_closed and door.setting != "closed"
                or not isolated(room, details)):
            return False
        upstream, src = source(room)
        return enterable(
            ledger, room, source_pa=source_pressure(src),
            source_safe=p._air_safe(upstream), hatch_sound=True,
            isolated=True, now_s=details["last_game_time"],
            need_permit=require_permit, allow_small_leak=allow_small_leak)
    except (IndustrialAccessError, p.PhysicsError, p.ShipOperationsError,
            ValueError, KeyError, TypeError):
        return False


def suit_ready(actor, details, room):
    from world import continuous_ship_physics as p
    if actor is None or room not in SITES:
        return False
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    if (here not in {room, SITES[room]["trunk"]}
            or getattr(actor.db, "ox_terminal_dead", False)
            or getattr(actor.db, "crew_role", None) not in p.AUTHORISED_ROLES
            and not actor.check_permstring("Developer")):
        return False
    health = CanonicalShipState.objects.filter(
        pk="crew_health:" + actor.dbref, source_model=p.MODEL).first()
    if health is None or health.condition not in {"fit", "impaired"}:
        return False
    eva = details.get("eva")
    if eva is None or actor.dbref in eva["transits"]:
        return False
    _, suit = suit_of(eva, actor.dbref)
    return bool(suit and suit["integrity"] >= .8
                and suit["exposure"]["suit_oxygen_kg"] > .01
                and suit["exposure"]["condition"] not in {
                    "incapacitated", "critical", "dead"})


def worker_ready(actor, details, room, *, inside=True):
    ledger = details.get("industrial_bays")
    if room not in SITES or actor is None or ledger is None:
        return False
    holder = (ledger["sites"][room]["permit"] or {}).get("holder")
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    return bool(holder == actor.dbref and (not inside or here == room)
                and suit_ready(actor, details, room)
                and ready(details, room, hatch_closed=inside))


def retreat_ready(actor, details, room):
    """Still-mobile worker can escape small leak / depleted suit if safe differential."""
    ledger = details.get("industrial_bays")
    if room not in SITES or actor is None or ledger is None:
        return False
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    return bool(here == room and not getattr(actor.db, "ox_terminal_dead", False)
                and (ledger["sites"][room]["permit"] or {}).get("holder") == actor.dbref
                and ready(details, room, allow_small_leak=True))


def seal_ready(actor, details, room):
    """Patch only an accessible limited inner leak with carried finite spares."""
    from world import continuous_ship_physics as p
    if room not in SITES or actor is None:
        return False
    ledger = details.get("industrial_bays")
    repairs = details.get("repairs")
    if ledger is None or repairs is None:
        return False
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    site = ledger["sites"][room]
    gas = site["gas"]
    if (here != room or gas is None or
            (site["permit"] or {}).get("holder") != actor.dbref
            or not 0 < site["leak_kg_s"] <= HAND_PATCH_LEAK_KG_S
            or p.state("access", SITES[room]["door"]).setting != "closed"
            or not isolated(room, details)
            or not suit_ready(actor, details, room)
            or actor.dbref not in repairs["toolkit_carriers"]
            or repairs["carried_kg"].get(actor.dbref, 0) < SEAL_PARTS_KG):
        return False
    pressure = bay_pressure(gas)
    return bool(70000 <= pressure <= 120000
                and 278.15 <= gas["temperature_k"] <= 313.15
                and site["skin_k"] <= 315
                and gas["smoke_kg"] <= .00001 * gas["mass_kg"]
                and gas["co2_kg"] <= .005 * gas["mass_kg"])


@transaction.atomic
def commission(*, operator_approved=False):
    from world import continuous_ship_physics as p
    if not operator_approved:
        raise PermissionError("Industrial site gas register requires operator attestation")
    clock = p._clock(lock=True)
    if clock.details.get("industrial_bays") is not None:
        validate_industrial(clock.details["industrial_bays"])
        return {"commissioned": False}
    if any(clock.details.get(k) is None for k in ("eva","repairs","electrical")):
        raise p.PhysicsError("Fitted suit, electrical and material accounts required")
    from world.ship_world import find_ship_space
    for room, spec in SITES.items():
        if (find_ship_space(room) is None or
                find_ship_space(spec["trunk"]) is None or
                p._topology()[0].get(room) is not None or
                p._topology()[0].get(spec["trunk"]) != spec["zone"]):
            raise p.PhysicsError("Original industrial room pressure taxonomy changed")
        hatch = p.state("access", spec["door"])
        panel = p.state("equipment", spec["panel"])
        breaker = p.state("isolator", spec["breaker"])
        if (hatch.reference.get("from") != spec["trunk"]
                or hatch.reference.get("to") != room
                or hatch.reference.get("pressure_boundary") is not True
                or hatch.reference.get("kind") != "service_door"
                or hatch.condition in p._BROKEN or hatch.setting != "closed"
                or panel.space_id != room or panel.condition in p._BROKEN
                or breaker.space_id != room
                or breaker.reference.get("network") != "power"):
            raise p.PhysicsError("Original rated service hardware is not installed")
    before = p._snapshot(clock)
    d = dict(clock.details)
    d["industrial_bays"] = initial_industrial()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details","revision"])
    p._event(clock, "g19_original_sixteen_industrial_sites_commissioned", before)
    return {"commissioned": True, "rooms": sorted(SITES)}


@transaction.atomic
def survey(*, operator_approved=False, room_id=None, volume_m3=None,
           pressure_pa=None, temperature_k=None, oxygen_mass_fraction=None,
           co2_mass_fraction=None, smoke_mass_fraction=0.0, skin_k=None):
    from world import continuous_ship_physics as p
    if not operator_approved or room_id not in SITES:
        raise PermissionError("Operator must sample an existing isolated room")
    clock = p._clock(lock=True)
    d = dict(clock.details)
    if d.get("industrial_bays") is None:
        raise p.PhysicsError("Original industrial service registers uncommissioned")
    spec = SITES[room_id]
    hatch = p.state("access", spec["door"])
    if (hatch.condition in p._BROKEN or hatch.setting != "closed"
            or not isolated(room_id, d)):
        raise p.PhysicsError("Isolate original industrial plant and close hatch before sampling")
    try:
        altered = positive_survey(
            d["industrial_bays"], room_id, volume_m3=volume_m3,
            pressure_pa=pressure_pa, temperature_k=temperature_k,
            oxygen_fraction=oxygen_mass_fraction,
            co2_fraction=co2_mass_fraction,
            smoke_fraction=smoke_mass_fraction,
            skin_k=skin_k, now_s=d["last_game_time"], hatch_closed=True)
    except (IndustrialAccessError, TypeError, ValueError) as exc:
        raise p.PhysicsError(str(exc)) from exc
    repairs = copy.deepcopy(d["repairs"])
    repairs["site_surveys"][room_id] = "suited_service"
    p.validate_repairs(repairs)
    before=p._snapshot(clock)
    d["industrial_bays"] = altered
    d["repairs"] = repairs
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details","revision"])
    p._event(clock, "g19_positive_industrial_gas_and_skin_survey", before)
    return {"room": room_id, "gas_kg": altered["sites"][room_id]["initial_kg"],
            "pressure_pa": bay_pressure(altered["sites"][room_id]["gas"])}


@transaction.atomic
def witness_leak(*, operator_approved=False, room_id=None, leak_kg_s=None):
    """Fault injection is world-operator-only, not crew or agent telemetry magic."""
    from world import continuous_ship_physics as p
    if not operator_approved or room_id not in SITES:
        raise PermissionError("Real industrial shell leak requires operator event")
    clock=p._clock(lock=True)
    before=p._snapshot(clock)
    details=dict(clock.details)
    ledger=details.get("industrial_bays")
    if ledger is None:
        raise p.PhysicsError("No original industrial gas survey")
    try:
        details["industrial_bays"] = attest_leak(
            ledger, room_id, leak_kg_s=leak_kg_s)
    except (IndustrialAccessError, TypeError, ValueError) as exc:
        raise p.PhysicsError(str(exc)) from exc
    clock.details=details
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock, "g19_physical_industrial_shell_leak_surveyed", before)
    return {"room":room_id,"leak_kg_s":leak_kg_s}


def action(actor, room, value):
    """Runs under existing global WorkReceipt and single ship-clock transaction."""
    from world import continuous_ship_physics as p
    if room not in SITES or not isinstance(value,str):
        raise p.PhysicsError("Only original industrial compartments support permits")
    clock=p._clock(lock=True)
    before=p._snapshot(clock)
    d=dict(clock.details)
    ledger=d.get("industrial_bays")
    if ledger is None:
        raise p.PhysicsError("Fitted industrial worksite register is uncommissioned")
    validate_industrial(ledger)
    spec=SITES[room]
    here=getattr(getattr(getattr(actor,"location",None),"db",None),"ox_space_id",None)
    hatch=p.state("access",spec["door"])
    if hatch.condition in p._BROKEN:
        raise p.PhysicsError("Rated industrial pressure door damaged")
    if value.startswith("bleed:"):
        p._crew_at(actor,spec["trunk"])
        if hatch.setting!="closed" or not isolated(room,d):
            raise p.PhysicsError("Original sealed hatch and plant isolation required")
        cell,src=source(room)
        try:
            ledger,new_source=bleed(ledger,room,kg=float(value.partition(":")[2]),
                source=src,source_safe=p._air_safe(cell),
                hatch_closed=True,isolated=True,now_s=d["last_game_time"])
        except (IndustrialAccessError, TypeError, ValueError) as exc:
            raise p.PhysicsError(str(exc)) from exc
        previous=p._snapshot(cell)
        mix=dict(cell.details)
        cell.quantity=new_source["mass_kg"]
        mix["physics_oxygen_kg"]=new_source["oxygen_kg"]
        mix["physics_co2_kg"]=new_source["co2_kg"]
        mix["physics_smoke_kg"]=new_source["smoke_kg"]
        cell.details=mix
        if not p._air_safe(cell):
            raise p.PhysicsError("Metered isolation transfer endangers original crew trunk")
        cell.revision+=1
        cell.save(update_fields=["quantity","details","revision"])
        p._event(cell,"g19_existing_trunk_to_industrial_gas_measured",previous,
                 actor=actor)
    elif value=="secure":
        p._crew_at(actor,spec["trunk"])
        if (hatch.setting!="closed" or not suit_ready(actor,d,room)
                or not ready(d,room,require_permit=False,hatch_closed=True)):
            raise p.PhysicsError("No matched observed atmosphere, stopped plant or issued real suit")
        try:
            ledger=secure(ledger,room,actor.dbref,d["last_game_time"])
        except IndustrialAccessError as exc:
            raise p.PhysicsError(str(exc)) from exc
    elif value=="inspect":
        p._crew_at(actor,room)
        if hatch.setting!="closed" or not worker_ready(actor,d,room):
            raise p.PhysicsError("Hands-on inspection needs closed rated door and fitted work permit")
        try:
            ledger=inspect(ledger,room,actor.dbref)
        except IndustrialAccessError as exc:
            raise p.PhysicsError(str(exc)) from exc
    elif value=="seal":
        p._crew_at(actor,room)
        if not seal_ready(actor,d,room):
            raise p.PhysicsError("Only a mobile suited original worksite holder with 2kg parts and toolkit can patch a bounded leak")
        try:
            ledger=begin_seal(ledger,room,actor.dbref)
        except IndustrialAccessError as exc:
            raise p.PhysicsError(str(exc)) from exc
    elif value=="release":
        p._crew_at(actor,spec["trunk"])
        from world.ship_world import find_ship_space
        placed=find_ship_space(room)
        occupied=bool(placed and any(
            getattr(visitor.db,"crew_role",None) for visitor in placed.contents))
        try:
            ledger=release(ledger,room,actor.dbref,
                hatch_closed=hatch.setting=="closed",no_crew=not occupied,
                repairs_active=any(job["room"]==room for job in
                    (d.get("repairs") or {"jobs":{}})["jobs"].values()))
        except IndustrialAccessError as exc:
            raise p.PhysicsError(str(exc)) from exc
    else:
        raise p.PhysicsError("Use bleed:<kg>, secure, inspect, seal or release")
    validate_industrial(ledger)
    d["industrial_bays"]=ledger
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    return clock,before


def entered(clock, room, actor):
    from world import continuous_ship_physics as p
    before=p._snapshot(clock)
    d=dict(clock.details)
    d["industrial_bays"]=inspect(
        d["industrial_bays"],room,actor.dbref,entry=True)
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock,"g19_suited_original_industrial_hatch_entry",
             before,actor=actor)


def hazards(ledger):
    validate_industrial(ledger)
    results=set()
    for room,site in ledger["sites"].items():
        gas=site["gas"]
        if gas is not None and (site["leak_kg_s"]>0 or
                 site["skin_k"]>315 or not bay_gas_safe(gas)):
            results.add(room)
    return results


def advance(clock, ledger, seconds, *, eva, repair_stock):
    """Finite leak tick + 180s material patch against real present crew.

    Called by the SAME world tick transaction. Material custody must reconcile:
    a finished seal consumes 2kg of the worker's already delivered spares.
    """
    from world import continuous_ship_physics as p
    from evennia.objects.models import ObjectDB
    from world.ship_world import find_ship_space
    ready_workers=set()
    actors={}
    repair_copy=copy.deepcopy(repair_stock) if repair_stock is not None else None
    if repair_copy is not None:
        for room,site in ledger["sites"].items():
            patch=site["seal"]
            if patch is None:
                continue
            ref=patch["holder"]
            if isinstance(ref,str) and ref.startswith("#") and ref[1:].isdigit():
                actor=ObjectDB.objects.filter(id=int(ref[1:])).first()
                if (actor and actor.location==find_ship_space(room)
                        and seal_ready(actor,{
                            **clock.details, "industrial_bays":ledger,
                            "eva":eva,"repairs":repair_copy},room)):
                    ready_workers.add((room,ref))
                    actors[ref]=actor
    try:
        revised,lost,finished=step_industrial(
            ledger,seconds,ready_workers=ready_workers)
    except IndustrialAccessError as exc:
        raise p.PhysicsError(str(exc)) from exc
    if finished:
        if repair_copy is None:
            raise p.PhysicsError("No existing finite spare ledger for physical patch")
        for room,worker,used in finished:
            if (worker not in repair_copy["toolkit_carriers"]
                    or repair_copy["carried_kg"].get(worker,0)<used):
                raise p.PhysicsError("Physical seal lacks originally carried replacement parts")
            repair_copy["carried_kg"][worker]-=used
            repair_copy["installed_kg"]+=used
            p.validate_repairs(repair_copy)
    return revised,lost,repair_copy,finished


def readout(actor):
    from world import continuous_ship_physics as p
    here=getattr(getattr(getattr(actor,"location",None),"db",None),"ox_space_id",None)
    details=p._clock().details
    ledger=details.get("industrial_bays")
    if ledger is None:
        raise p.PhysicsError("Original industrial service not commissioned")
    validate_industrial(ledger)
    visible={}
    for room,spec in SITES.items():
        if here not in {room,spec["trunk"]}:
            continue
        if here==room and not suit_ready(actor,details,room):
            continue
        site=ledger["sites"][room]
        gas=site["gas"]
        visible[room]={
            "surveyed_pressure_pa":bay_pressure(gas) if gas else None,
            "survey_game_time":gas["sample_s"] if gas else None,
            "finite_gas_kg":gas["mass_kg"] if gas else None,
            "initial_charge_kg":site["initial_kg"],
            "trunk_received_kg":site["received_kg"],
            "leaked_into_space_kg":site["lost_kg"],
            "currently_leaking_kg_s":site["leak_kg_s"],
            "skin_k":site["skin_k"],
            "hatch":p.state("access",spec["door"]).setting,
            "panel_feeder":p.state("isolator",spec["breaker"]).setting,
            "site_isolated":isolated(room,details),
            "permit_holder":(site["permit"] or {}).get("holder"),
            "pending_seal":site["seal"],
            "entry_ready":ready(details,room),
            "entries":site["entries"],"inspections":site["inspections"],
            "repaired_breaches":site["repairs"]}
    if not visible:
        raise PermissionError("No original industrial hatch instrument at this station")
    return {"sites":visible,"scope":"attended_original_industrial_service_only"}
