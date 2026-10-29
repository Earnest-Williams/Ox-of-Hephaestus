"""Installed Evennia authority for 63 non-industrial unclassified spaces.

Only existing fitted doors/room, manifest lots, gas pressure cells, machinery
and finite crew stock may authorise actions. No new walkable shield/tank,
cargo hatch bypass, invented freight lot or pressurised loading passage.
"""
from __future__ import annotations

import copy
import math
from django.db import transaction
from world.models import CanonicalShipState
from world.ship_unclassified_spaces import (
    SECTORS, PERSONNEL_DOORS, FREIGHT_ROUTES, PORTALS, PORTAL_DOORS,
    VOIDS, NONPERSONNEL_LINKS, UnclassifiedSpaceError,
    initial_unclassified, validate_unclassified, survey_sector, secure_sector,
    note_entry, release_sector, inject_sector_leak, begin_sector_seal,
    tick_unclassified, certify_portal, invalidate_portal, portal_ready,
    permit_ready, inspect_void, drum_parked, complete_manifest,
    MINOR_PATCH_KG_S, PATCH_SPARES_KG)
from world.ship_propulsion_bay_service import bay_pressure

CARGO_CREW_ROLES = frozenset({
    "cargo_officer", "watch_engineer", "chief_engineer", "environment_tech"})
CASUALTY_CREW_ROLES = frozenset({"watch_engineer","chief_engineer",
                                "environment_tech"})
BAD_CONDITION = frozenset({"degraded","faulted","failed","jammed","severed"})


def _clock():
    from world.continuous_ship_physics import _clock as physical_clock
    return physical_clock(lock=True)


def _room(actor):
    return getattr(getattr(getattr(actor,"location",None),"db",None),
                   "ox_space_id",None)


def _at(actor,room,roles=CARGO_CREW_ROLES):
    if actor is None or _room(actor)!=room:
        raise PermissionError("Actual signed crew must attend the original room")
    if (getattr(actor.db,"ox_terminal_dead",False)
            or getattr(actor.db,"crew_role",None) not in roles
            and not actor.check_permstring("Developer")):
        raise PermissionError("Shipboard role or health forbids cargo operation")


def _source(sector):
    from world import continuous_ship_physics as p
    drum=sector[:5]
    gallery=drum+"-GALLERY"
    zone=p._topology()[0].get(gallery)
    if zone!="PZ-"+drum+"-SVC":
        raise p.PhysicsError("Real rotating cargo gallery pressure cell missing")
    cell=p.state("pressure",zone)
    if not p._air_safe(cell):
        raise p.PhysicsError("Cargo gallery air cannot safely receive another atmosphere")
    pa=(cell.quantity*p.R_SPECIFIC_AIR*cell.details["temperature_k"]/
        cell.details["gas_volume_m3"])
    return cell,pa


def _physical_sector_door(sector,*,must_closed=False):
    from world import continuous_ship_physics as p
    door=p.state("access","ACC-"+sector)
    if (door.reference.get("from")!=sector[:5]+"-GALLERY"
            or door.reference.get("to")!=sector
            or door.reference.get("kind")!="cargo_service_door"
            or door.reference.get("pressure_boundary") is not True
            or door.condition in p._BROKEN or
            must_closed and door.setting!="closed"):
        raise p.PhysicsError("Original cargo-sector rated door is unavailable")
    return door


def _health_good(actor):
    from world.continuous_ship_physics import MODEL
    hp=CanonicalShipState.objects.filter(
        pk="crew_health:"+actor.dbref,source_model=MODEL).first()
    return bool(hp is not None and hp.condition in {"fit","impaired"})


def _suit_good(actor,details):
    from world.ship_eva_operations import suit_of
    eva=details.get("eva")
    if eva is None:
        return False
    _,suit=suit_of(eva,actor.dbref)
    return bool(suit is not None and suit["integrity"]>=.8
                and suit["exposure"]["suit_oxygen_kg"]>.01
                and suit["exposure"]["condition"] not in {
                    "incapacitated","critical","dead"})


def access_ready(actor,details,sector,*,from_inside=False,
                 allow_small_leak=False,hatch_closed=False):
    from world import continuous_ship_physics as p
    if sector not in SECTORS or not _health_good(actor):
        return False
    row=(details.get("unclassified_spaces") or
         {"sectors":{}})["sectors"].get(sector)
    if row is None or (row["permit"] or {}).get("holder")!=actor.dbref:
        return False
    if _room(actor)!=(sector if from_inside else sector[:5]+"-GALLERY"):
        return False
    if (getattr(actor.db,"crew_role",None) not in CARGO_CREW_ROLES
            and not actor.check_permstring("Developer")):
        return False
    try:
        hatch=_physical_sector_door(sector,must_closed=hatch_closed)
        gallery,pressure=_source(sector)
        return permit_ready(
            details["unclassified_spaces"],details["cargo"],
            details["rotors"],sector,source_pressure_pa=pressure,
            source_safe=p._air_safe(gallery),
            now_s=details["last_game_time"],allow_minor_leak=allow_small_leak)
    except (UnclassifiedSpaceError,p.PhysicsError,KeyError,TypeError,
            ValueError):
        return False


def prepare_hatch(actor,door,value):
    from world import continuous_ship_physics as p
    if door.source_id in NONPERSONNEL_LINKS:
        raise p.PhysicsError("Freight routes, commercial portals and shield/tank hatches are not personnel entrances")
    sector=PERSONNEL_DOORS.get(door.source_id)
    if sector is None:
        raise p.PhysicsError("No original cargo-sector personnel hatch")
    if value=="open":
        if not access_ready(actor,_clock().details,sector,
                            from_inside=_room(actor)==sector,
                            allow_small_leak=_room(actor)==sector,
                            hatch_closed=True):
            raise p.PhysicsError("Cargo-sector hatch requires original safe atmosphere, full live manifest and owner permit")
    elif value!="closed":
        raise p.PhysicsError("Unknown cargo-sector rated hatch position")
    _at(actor,_room(actor))


def _seal_ready(actor,details,sector,*,for_start=False):
    from world import continuous_ship_physics as p
    row=(details.get("unclassified_spaces") or {"sectors":{}})[
        "sectors"].get(sector)
    repairs=details.get("repairs")
    if row is None or repairs is None or _room(actor)!=sector:
        return False
    if (not _suit_good(actor,details)
            or getattr(actor.db,"crew_role",None) not in CASUALTY_CREW_ROLES
            and not actor.check_permstring("Developer")
            or actor.dbref not in repairs["toolkit_carriers"]
            or repairs["carried_kg"].get(actor.dbref,0)<PATCH_SPARES_KG
            or not access_ready(actor,details,sector,from_inside=True,
                                allow_small_leak=True,hatch_closed=True)):
        return False
    return bool(0<row["leak_kg_s"]<=MINOR_PATCH_KG_S
                and (for_start or row["seal"] is not None))


@transaction.atomic
def commission(*,operator_approved=False):
    from world import continuous_ship_physics as p
    from world.ship_world import find_ship_space
    if not operator_approved:
        raise PermissionError("Original cargo boundaries require operator survey authority")
    clock=p._clock(lock=True)
    if clock.details.get("unclassified_spaces") is not None:
        validate_unclassified(clock.details["unclassified_spaces"])
        return {"commissioned":False}
    zones=p._topology()[0]
    for sector in SECTORS:
        drum=sector[:5]
        if (find_ship_space(sector) is None or
                find_ship_space(drum+"-GALLERY") is None or
                zones.get(sector) is not None or
                zones.get(drum+"-GALLERY")!="PZ-"+drum+"-SVC"):
            raise p.PhysicsError("Source-v0.5 sector still unclassified and fitted gallery required")
        a=p.state("access","ACC-"+sector)
        freight=p.state("access",f"ACC-{drum}-FREIGHT-{sector[6:]}")
        if (a.reference.get("from")!=drum+"-GALLERY"
                or a.reference.get("to")!=sector
                or a.reference.get("kind")!="cargo_service_door"
                or a.reference.get("pressure_boundary") is not True
                or freight.reference.get("from")!=drum+"-FREIGHT-HUB"
                or freight.reference.get("to")!=sector
                or freight.reference.get("kind")!="freight_handling_route"
                or freight.reference.get("pressure_boundary") is not True):
            raise p.PhysicsError("Original cargo service and freight route hardware mismatch")
    for portal in PORTALS:
        a=p.state("access","ACC-"+portal)
        if (zones.get(portal) is not None or
                find_ship_space(portal) is None or
                a.reference.get("to")!=portal
                or a.reference.get("from")!=portal[:5]+"-GALLERY"
                or a.reference.get("kind")!="cargo_portal_inner"
                or a.reference.get("pressure_boundary") is not True):
            raise p.PhysicsError("Commercial portal is not fitted as sealed cargo-only sleeve")
    for void,spec in VOIDS.items():
        if zones.get(void) is not None or find_ship_space(void) is None:
            raise p.PhysicsError("Original shield/trim enclosure is not unclassified")
        if spec["hatch"] is not None:
            door=p.state("access",spec["hatch"])
            if (door.reference.get("from")!=spec["control"]
                    or door.reference.get("to")!=void
                    or door.reference.get("pressure_boundary") is not True):
                raise p.PhysicsError("Shield or tank has wrong original rated access face")
        else:
            # Crucial: no new person-access hatch is to be fabricated for
            # the enclosed workshop trim reservoir.
            if any(
                    access.reference.get("to")==void
                    for access in CanonicalShipState.objects.filter(
                        category="access")):
                raise p.PhysicsError("Trim reservoir unexpectedly gained a personnel access")
    before=p._snapshot(clock)
    d=dict(clock.details)
    d["unclassified_spaces"]=initial_unclassified()
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock,"g19_original_cargo_portal_void_classification",before)
    return {"commissioned":True,"cargo_sectors":48,"portals":12,
            "sealed_noncrew_voids":3}


@transaction.atomic
def survey(*,operator_approved=False,sector=None,free_volume_m3=None,
           pressure_pa=None,temperature_k=None,oxygen_mass_fraction=None,
           co2_mass_fraction=None,smoke_mass_fraction=0,
           cargo_class=None,lot_ids=None):
    from world import continuous_ship_physics as p
    if not operator_approved or sector not in SECTORS:
        raise PermissionError("Only a sampled original cargo sector may be approved")
    clock=p._clock(lock=True)
    d=dict(clock.details)
    if d.get("unclassified_spaces") is None:
        raise p.PhysicsError("Original unclassified space register is not commissioned")
    try:
        door=_physical_sector_door(sector,must_closed=True)
        updated=survey_sector(
            d["unclassified_spaces"],d["cargo"],d["rotors"],sector,
            free_volume_m3=free_volume_m3,pressure_pa=pressure_pa,
            temperature_k=temperature_k,oxygen_fraction=oxygen_mass_fraction,
            co2_fraction=co2_mass_fraction,smoke_fraction=smoke_mass_fraction,
            cargo_class=cargo_class,lot_ids=lot_ids or [],
            now_s=d["last_game_time"],hatch_closed=door.setting=="closed")
    except (UnclassifiedSpaceError,ValueError,TypeError) as exc:
        raise p.PhysicsError(str(exc)) from exc
    before=p._snapshot(clock)
    d["unclassified_spaces"]=updated
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock,"operator_positive_cargo_sector_gas_and_manifest_survey",before)
    site=updated["sectors"][sector]
    return {"sector":sector,"surveyed_gas_kg":site["gas"]["mass_kg"],
            "assigned_actual_lots":site["lot_ids"],
            "manifest_full":complete_manifest(updated,d["cargo"],sector[:5])}


@transaction.atomic
def inspect_portal(*,operator_approved=False,portal=None,berth_id=None):
    from world import continuous_ship_physics as p
    if not operator_approved or portal not in PORTALS:
        raise PermissionError("Positive port sleeve inspection must be operator authorised")
    clock=p._clock(lock=True)
    d=dict(clock.details)
    ledger=d.get("unclassified_spaces")
    if ledger is None:
        raise p.PhysicsError("Commercial portal register is not commissioned")
    hatch=p.state("access","ACC-"+portal)
    handler=p.state("equipment",portal[:5]+"-RADIAL-FREIGHT-HANDLER")
    try:
        revised=certify_portal(
            ledger,d["cargo"],d["rotors"],portal,berth=berth_id,
            real_hatch_closed=hatch.setting=="closed",
            sound=hatch.condition not in p._BROKEN,
            machinery_healthy=handler.condition not in p._BROKEN,
            now_s=d["last_game_time"])
    except UnclassifiedSpaceError as exc:
        raise p.PhysicsError(str(exc)) from exc
    before=p._snapshot(clock)
    d["unclassified_spaces"]=revised
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock,"operator_real_moored_port_sleeve_and_seal_checked",before)
    return {"portal":portal,"certified_berth":berth_id,
            "crew_entrance":False}


@transaction.atomic
def witness_leak(*,operator_approved=False,sector=None,leak_kg_s=None):
    from world import continuous_ship_physics as p
    if not operator_approved or sector not in SECTORS:
        raise PermissionError("Cargo shell damage must be physically observed by world authority")
    clock=p._clock(lock=True)
    d=dict(clock.details)
    if d.get("unclassified_spaces") is None:
        raise p.PhysicsError("No surveyed cargo sector to damage")
    if _physical_sector_door(sector,must_closed=True).setting!="closed":
        raise p.PhysicsError("Open sector boundary needs gallery damage containment first")
    try:
        ledger=inject_sector_leak(d["unclassified_spaces"],sector,leak_kg_s)
    except UnclassifiedSpaceError as exc:
        raise p.PhysicsError(str(exc)) from exc
    before=p._snapshot(clock)
    d["unclassified_spaces"]=ledger
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock,"operator_real_cargo_sector_shell_casualty",before)
    return {"sector":sector,"leak_kg_s":leak_kg_s}


def action(actor,sector,value):
    """Cargo officer owns room permits; shell patch needs a suited engineer."""
    from world import continuous_ship_physics as p
    if sector not in SECTORS or not isinstance(value,str):
        raise p.PhysicsError("Only original cargo service sectors support this operation")
    clock=p._clock(lock=True)
    before=p._snapshot(clock)
    details=dict(clock.details)
    ledger=details.get("unclassified_spaces")
    if ledger is None:
        raise p.PhysicsError("Cargo-sector pressure and manifest ledger not commissioned")
    hatch=_physical_sector_door(sector)
    if value=="secure":
        _at(actor,sector[:5]+"-GALLERY")
        if (hatch.setting!="closed" or not _health_good(actor)
                or not access_ready_base(details,sector)):
            raise p.PhysicsError("Survey all eight actual sector manifests and gas charges before entry")
        try:
            ledger=secure_sector(ledger,sector,actor.dbref,
                                 details["last_game_time"])
        except UnclassifiedSpaceError as exc:
            raise p.PhysicsError(str(exc)) from exc
    elif value=="inspect":
        _at(actor,sector)
        if (hatch.setting!="closed"
                or not access_ready(actor,details,sector,from_inside=True)):
            raise p.PhysicsError("Cargo inspection requires living permit holder and safe shut hatch")
        ledger=note_entry(ledger,sector,actor.dbref,inspection=True)
    elif value=="seal":
        _at(actor,sector,CASUALTY_CREW_ROLES)
        if not _seal_ready(actor,details,sector,for_start=True):
            raise p.PhysicsError("Internal leak patch needs suited engineer, real toolkit, 2kg parts and small-survivable leak")
        try:
            ledger=begin_sector_seal(ledger,sector,actor.dbref)
        except UnclassifiedSpaceError as exc:
            raise p.PhysicsError(str(exc)) from exc
    elif value=="release":
        _at(actor,sector[:5]+"-GALLERY")
        from world.ship_world import find_ship_space
        room=find_ship_space(sector)
        occupied=bool(room and any(
            getattr(occupant.db,"crew_role",None) for occupant in room.contents))
        try:
            ledger=release_sector(
                ledger,sector,actor.dbref,
                closed=hatch.setting=="closed",empty=not occupied)
        except UnclassifiedSpaceError as exc:
            raise p.PhysicsError(str(exc)) from exc
    else:
        raise p.PhysicsError("Cargo sector operations: secure, inspect, seal, release")
    validate_unclassified(ledger)
    details["unclassified_spaces"]=ledger
    clock.details=details
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    return clock,before


def access_ready_base(details,sector):
    from world import continuous_ship_physics as p
    if sector not in SECTORS:
        return False
    try:
        hatch=_physical_sector_door(sector,must_closed=True)
        cell,pa=_source(sector)
        return permit_ready(
            details["unclassified_spaces"],details["cargo"],details["rotors"],
            sector,source_pressure_pa=pa,source_safe=p._air_safe(cell),
            now_s=details["last_game_time"],permit_required=False)
    except (UnclassifiedSpaceError,p.PhysicsError,KeyError,ValueError):
        return False


def entered(clock,sector,actor):
    from world import continuous_ship_physics as p
    before=p._snapshot(clock)
    d=dict(clock.details)
    d["unclassified_spaces"]=note_entry(
        d["unclassified_spaces"],sector,actor.dbref)
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    p._event(clock,"g19_real_manifest_and_pressure_checked_sector_entry",
             before,actor=actor)


def void_action(actor,void,value):
    from world import continuous_ship_physics as p
    if void not in VOIDS or value!="inspect":
        raise p.PhysicsError("Only original remote shield/tank inspection is available")
    spec=VOIDS[void]
    _at(actor,spec["control"],CASUALTY_CREW_ROLES)
    clock=p._clock(lock=True)
    before=p._snapshot(clock)
    d=dict(clock.details)
    ledger=d.get("unclassified_spaces")
    if ledger is None:
        raise p.PhysicsError("Original non-personnel enclosure is uncommissioned")
    if void=="WATER-SHIELD-FWD":
        valve=p.state("isolator","ISO-GAS-BANK-A")
        if valve.setting!="closed" or valve.condition in p._BROKEN:
            raise p.PhysicsError("Original shielded gas bank must be physically isolated for observation")
    elif void=="WR-TRIM-TANK-BAY":
        rotor=d["rotors"].get("WR-01",{})
        if (not rotor.get("hardlock") or not rotor.get("brake")
                or rotor.get("target_rpm")!=0 or abs(rotor.get("rpm",1))>=.001):
            raise p.PhysicsError("Trim-water remote check requires stopped hardlocked workshop")
    for machine in spec["equipment"]:
        fitted=p.state("equipment",machine)
        if fitted.space_id!=void:
            raise p.PhysicsError("Original shield installation is not at expected site")
    updated=inspect_void(ledger,void,d["last_game_time"])
    d["unclassified_spaces"]=updated
    clock.details=d
    clock.revision+=1
    clock.save(update_fields=["details","revision"])
    return clock,before


def advance(clock,ledger,seconds,*,eva,repair_stock):
    """Same transaction as the main world clock; persistent real air losses."""
    from world import continuous_ship_physics as p
    from evennia.objects.models import ObjectDB
    from world.ship_world import find_ship_space
    ready_seals=set()
    stock=copy.deepcopy(repair_stock) if repair_stock is not None else None
    if stock is not None:
        for sector,row in ledger["sectors"].items():
            seal=row["seal"]
            if seal is None:
                continue
            ref=seal["holder"]
            actor=ObjectDB.objects.filter(id=int(ref[1:])).first()
            if (actor and actor.location==find_ship_space(sector) and
                    _seal_ready(actor,{
                        **clock.details, "unclassified_spaces":ledger,
                        "eva":eva,"repairs":stock},sector)):
                ready_seals.add((sector,ref))
    try:
        updated,lost,finished=tick_unclassified(
            ledger,seconds,ready_seals=ready_seals)
    except UnclassifiedSpaceError as exc:
        raise p.PhysicsError(str(exc)) from exc
    for sector,worker,used in finished:
        if (stock is None or worker not in stock["toolkit_carriers"]
                or stock["carried_kg"].get(worker,0)<used):
            raise p.PhysicsError("No physically held finite cargo patch material")
        stock["carried_kg"][worker]-=used
        stock["installed_kg"]+=used
        p.validate_repairs(stock)
    return updated,lost,stock,finished


def readout(actor,target):
    from world import continuous_ship_physics as p
    room=_room(actor)
    if room is None:
        raise PermissionError("Original ship worksite is required")
    details=_clock().details
    ledger=details.get("unclassified_spaces")
    if ledger is None:
        raise p.PhysicsError("63-space worksite register not commissioned")
    validate_unclassified(ledger)
    if target=="cargo_sectors":
        visible={}
        for sector,row in ledger["sectors"].items():
            if room not in {sector,sector[:5]+"-GALLERY"}:
                continue
            gas=row["gas"]
            visible[sector]={
                "class":row["class"],"lot_ids":row["lot_ids"],
                "manifest_current":row["manifest_digest"] is not None and
                    complete_manifest(ledger,details["cargo"],sector[:5]),
                "pressure_pa":bay_pressure(gas) if gas is not None else None,
                "gas_kg":gas["mass_kg"] if gas else None,
                "lost_to_space_kg":row["lost_kg"],
                "leak_kg_s":row["leak_kg_s"],
                "permit":(row["permit"] or {}).get("holder"),
                "hatch":p.state("access","ACC-"+sector).setting,
                "ready":access_ready_base(details,sector),
                "entries":row["entries"],"inspections":row["inspections"],
                "internal_seals":row["seals_completed"]}
        if not visible:
            raise PermissionError("Cargo sectors are observed from their own gallery")
        return {"sectors":visible,"scope":"surveyed_current_manifest_and_local_pressure"}
    if target=="cargo_portals":
        visible={}
        for portal,row in ledger["portals"].items():
            if room not in {portal[:5]+"-GALLERY","CARGO-CTRL-FWD"}:
                continue
            visible[portal]={
                "berth":row["certified_berth"],
                "original_contact":details["cargo"].get("port_contacts",{}).get(portal),
                "seal_fault":row["seal_fault"],
                "hatch":p.state("access","ACC-"+portal).setting,
                "ready":portal_ready(ledger,details["cargo"],portal),
                "job":details["cargo"].get("port_jobs",{}).get(portal)}
        if not visible:
            raise PermissionError("Only an attended original cargo control may read portal status")
        return {"portals":visible,"passenger_access":False}
    if target=="shield_trim":
        available={}
        for void,spec in VOIDS.items():
            if room!=spec["control"]:
                continue
            row=ledger["voids"][void]
            available[void]={
                "kind":spec["type"],"walkable":False,
                "direct_hatch":spec["hatch"],
                "inspections":row["inspections"],
                "last_control_s":row["last_control_s"],
                "original_equipment":{
                    ident:p.state("equipment",ident).condition
                    for ident in spec["equipment"]}}
        if not available:
            raise PermissionError("Shield/trim readout requires original local control")
        return {"closed_enclosures":available,
                "new_gas_kg":0,"new_cargo_mass_kg":0}
    raise p.PhysicsError("Unknown original unclassified-space readout")
