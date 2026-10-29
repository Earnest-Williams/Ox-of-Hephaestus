"""Installed G19 generator-room permits bound to actual Evennia machinery.

No surrogate pressure cell, teleport, free gas, unattended switch or boolean
suit shortcut. Existing GEN-M/A/B original rooms and their rated doors only.
"""
from __future__ import annotations

import copy
from django.db import transaction

from world.ship_generator_bay_service import (
    ROOMS, DOORS, GeneratorBayError, initial_generator_bays,
    validate_generator_bays, survey_room, bleed_room, entry_ready,
    secure_room, enter_or_inspect, release_room)
from world.ship_propulsion_bay_service import (
    bay_pressure, source_pressure)
from world.ship_eva_operations import suit_of
from world.models import CanonicalShipState


def source(room):
    from world import continuous_ship_physics as p
    if room not in ROOMS:
        raise p.PhysicsError("Unknown as-fitted generator service room")
    _, _, trunk, zone, _, _ = ROOMS[room]
    if p._topology()[0].get(trunk) != zone:
        raise p.PhysicsError("Fitted generator service trunk topology mismatch")
    cell = p.state("pressure", zone, lock=True)
    if cell.quantity is None or not p._air_safe(cell):
        raise p.PhysicsError("Original service trunk is not breathing safe")
    d = cell.details
    return cell, {
        "mass_kg": cell.quantity,
        "oxygen_kg": d["physics_oxygen_kg"],
        "co2_kg": d["physics_co2_kg"],
        "smoke_kg": d["physics_smoke_kg"],
        "temperature_k": d["temperature_k"],
        "volume_m3": d["gas_volume_m3"],
    }


def stopped(room):
    from world import continuous_ship_physics as p
    gen, door_id, trunk, zone, feeder_id, _ = ROOMS[room]
    machine = p.state("equipment", gen)
    iso = p.state("isolator", feeder_id)
    return bool(machine.space_id == room
                and iso.space_id == room and iso.condition not in p._BROKEN
                and iso.setting == "open"
                and not machine.details.get("physics_online", True)
                and not machine.details.get("physics_commanded_on", True))


def room_ready(details, room, *, require_permit=True, hatch_closed=False):
    from world import continuous_ship_physics as p
    ledger = details.get("generator_bays")
    if ledger is None or room not in ROOMS:
        return False
    gen, door_id, trunk, zone, feeder_id, _ = ROOMS[room]
    try:
        validate_generator_bays(ledger)
        door = p.state("access", door_id)
        if (door.condition in p._BROKEN
                or door.reference.get("pressure_boundary") is not True
                or door.reference.get("from") != trunk
                or door.reference.get("to") != room
                or door.reference.get("kind") != "service_door"
                or door.setting not in {"closed", "open"}
                or hatch_closed and door.setting != "closed"
                or not stopped(room)):
            return False
        cell, gas = source(room)
        return entry_ready(
            ledger, room, source_pa=source_pressure(gas),
            source_safe=p._air_safe(cell), hatch_sound=True,
            feeder_open=True, generator_stopped=True,
            now_s=details["last_game_time"], permit_required=require_permit)
    except (GeneratorBayError, p.PhysicsError, p.ShipOperationsError,
            KeyError):
        return False


def suit_ready(actor, details, room):
    from world import continuous_ship_physics as p
    if actor is None or room not in ROOMS:
        return False
    _, _, trunk, _, _, _ = ROOMS[room]
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    if (here not in {room, trunk}
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
    ledger = details.get("generator_bays")
    if room not in ROOMS or ledger is None or actor is None:
        return False
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    return bool((ledger["rooms"][room]["permit"] or {}).get("holder") == actor.dbref
                and (not inside or here == room)
                and suit_ready(actor, details, room)
                and room_ready(details, room, hatch_closed=inside))


def retreat_ready(actor, details, room):
    ledger = details.get("generator_bays")
    if room not in ROOMS or ledger is None or actor is None:
        return False
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    return bool(here == room and not getattr(actor.db, "ox_terminal_dead", False)
                and (ledger["rooms"][room]["permit"] or {}).get("holder") == actor.dbref
                and room_ready(details, room))


@transaction.atomic
def commission(*, operator_approved=False):
    from world import continuous_ship_physics as p
    if not operator_approved:
        raise PermissionError("Generator-room pressure survey requires operator attestation")
    clock = p._clock(lock=True)
    if clock.details.get("generator_bays") is not None:
        validate_generator_bays(clock.details["generator_bays"])
        return {"commissioned": False}
    if any(clock.details.get(k) is None for k in ("electrical", "repairs", "eva")):
        raise p.PhysicsError("Generator service requires actual power, repair and EVA ledgers")
    from world.ship_world import find_ship_space
    for room, (machine, hatch_id, trunk, zone, feeder, _) in ROOMS.items():
        if (not find_ship_space(room) or not find_ship_space(trunk)
                or p._topology()[0].get(room) is not None
                or p._topology()[0].get(trunk) != zone):
            raise p.PhysicsError("Original unclassified room geometry differs")
        hatch = p.state("access", hatch_id)
        gen = p.state("equipment", machine)
        breaker = p.state("isolator", feeder)
        if (hatch.condition in p._BROKEN or hatch.setting != "closed"
                or hatch.reference.get("from") != trunk
                or hatch.reference.get("to") != room
                or hatch.reference.get("pressure_boundary") is not True
                or hatch.reference.get("kind") != "service_door"
                or gen.space_id != room or breaker.space_id != room
                or breaker.reference.get("network") != "power"):
            raise p.PhysicsError("Fitted generator, breaker or rated hatch missing")
    before = p._snapshot(clock)
    d = dict(clock.details)
    d["generator_bays"] = initial_generator_bays()
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    p._event(clock, "g19_fitted_generator_room_ledger_commissioned", before)
    return {"commissioned": True, "rooms": sorted(ROOMS)}


@transaction.atomic
def survey(*, operator_approved=False, room_id=None,
           volume_m3=None, pressure_pa=None, temperature_k=None,
           oxygen_mass_fraction=None, co2_mass_fraction=None,
           smoke_mass_fraction=0.0, skin_temperature_k=None):
    from world import continuous_ship_physics as p
    if not operator_approved or room_id not in ROOMS:
        raise PermissionError("Only the operator can positively sample original generator gas")
    clock = p._clock(lock=True)
    d = dict(clock.details)
    if d.get("generator_bays") is None:
        raise p.PhysicsError("Original generator rooms not commissioned")
    _, hatch_id, _, _, _, _ = ROOMS[room_id]
    hatch = p.state("access", hatch_id)
    if (hatch.setting != "closed" or hatch.condition in p._BROKEN
            or not stopped(room_id)):
        raise p.PhysicsError("Generator survey requires dead machinery, open breaker and shut rated hatch")
    try:
        ledger = survey_room(d["generator_bays"], room_id,
            volume_m3=volume_m3, pressure_pa=pressure_pa,
            temperature_k=temperature_k,
            oxygen_fraction=oxygen_mass_fraction,
            co2_fraction=co2_mass_fraction,
            smoke_fraction=smoke_mass_fraction,
            skin_k=skin_temperature_k, now_s=d["last_game_time"],
            hatch_closed=True)
    except (GeneratorBayError, TypeError, ValueError) as exc:
        raise p.PhysicsError(str(exc)) from exc
    repairs = copy.deepcopy(d["repairs"])
    repairs["site_surveys"][room_id] = "suited_service"
    p.validate_repairs(repairs)
    before = p._snapshot(clock)
    d["repairs"] = repairs
    d["generator_bays"] = ledger
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    p._event(clock, "g19_original_generator_gas_skin_measured", before)
    return {"room": room_id, "pressure_pa": bay_pressure(
        ledger["rooms"][room_id]["gas"]),
        "as_found_gas_kg": ledger["rooms"][room_id]["initial_kg"]}


def action(actor, room, value):
    """Called INSIDE the existing serialised replay-safe crew action transaction.

    Returns the original clock and its BEFORE snapshot to the durable receipt
    path; individual changed generator rows emit their own physical events.
    """
    from world import continuous_ship_physics as p
    if room not in ROOMS or not isinstance(value, str):
        raise p.PhysicsError("Only three original generator service enclosures exist")
    gen, hatch_id, trunk, _, breaker_id, _ = ROOMS[room]
    clock = p._clock(lock=True)
    before = p._snapshot(clock)
    d = dict(clock.details)
    ledger = d.get("generator_bays")
    if ledger is None:
        raise p.PhysicsError("Generator room service is uncommissioned")
    validate_generator_bays(ledger)
    hatch = p.state("access", hatch_id)
    generator = p.state("equipment", gen, lock=True)
    breaker = p.state("isolator", breaker_id, lock=True)
    if hatch.condition in p._BROKEN or breaker.condition in p._BROKEN:
        raise p.PhysicsError("Rated generator hatch or original feeder damaged")
    if value in {"trip", "rearm"}:
        p._crew_at(actor, "ENG-CONTROL")
        panel = p.state("equipment", "LP-ENG-CONTROL")
        if panel.space_id != "ENG-CONTROL" or panel.condition in p._BROKEN:
            raise p.PhysicsError("Actual engineering power management panel unavailable")
        if value == "trip":
            old_gen = p._snapshot(generator)
            unit = dict(generator.details)
            unit.update(physics_online=False, physics_commanded_on=False,
                        physics_startup_s=0.0)
            generator.details = unit
            generator.revision += 1
            generator.save(update_fields=["details", "revision"])
            p._event(generator, "g19_generator_real_emergency_trip", old_gen,
                     actor=actor)
            old_breaker = p._snapshot(breaker)
            breaker.setting = "open"
            breaker.revision += 1
            breaker.save(update_fields=["setting", "revision"])
            p._event(breaker, "g19_original_generator_breaker_tripped",
                     old_breaker, actor=actor)
        else:
            from world.ship_world import find_ship_space
            physical = find_ship_space(room)
            if (ledger["rooms"][room]["permit"] is not None
                    or hatch.setting != "closed" or physical is None
                    or any(getattr(person.db, "crew_role", None)
                           for person in physical.contents)
                    or any(job["room"] == room for job in
                           (d.get("repairs") or {"jobs": {}})["jobs"].values())
                    or generator.condition in p._BROKEN
                    or not stopped(room)
                    or breaker.details.get("physics_power_trip_latched")
                    or (d.get("electrical") or {}).get("shore", {}).get("connected")):
                raise p.PhysicsError("No remote rearm with worker, active fault or live shore lead")
            old_breaker = p._snapshot(breaker)
            breaker.setting = "closed"
            breaker.revision += 1
            breaker.save(update_fields=["setting", "revision"])
            p._event(breaker, "g19_original_generator_breaker_reconnected",
                     old_breaker, actor=actor)
            old_gen = p._snapshot(generator)
            unit = dict(generator.details)
            unit.update(physics_online=False, physics_commanded_on=True,
                        physics_startup_s=30.0)
            generator.details = unit
            generator.revision += 1
            generator.save(update_fields=["details", "revision"])
            p._event(generator, "g19_generator_remote_restart_requested",
                     old_gen, actor=actor)
    elif value.startswith("bleed:"):
        p._crew_at(actor, trunk)
        if hatch.setting != "closed" or not stopped(room):
            raise p.PhysicsError("Metered bleed requires isolated cold original enclosure")
        cell, src = source(room)
        try:
            ledger, remaining = bleed_room(ledger, room,
                kg=float(value.partition(":")[2]), source=src,
                now_s=d["last_game_time"], source_safe=p._air_safe(cell),
                hatch_closed=True, generator_stopped=True, feeder_open=True)
        except (GeneratorBayError, TypeError, ValueError) as exc:
            raise p.PhysicsError(str(exc)) from exc
        old_cell = p._snapshot(cell)
        gas = dict(cell.details)
        cell.quantity = remaining["mass_kg"]
        gas["physics_oxygen_kg"] = remaining["oxygen_kg"]
        gas["physics_co2_kg"] = remaining["co2_kg"]
        gas["physics_smoke_kg"] = remaining["smoke_kg"]
        cell.details = gas
        if not p._air_safe(cell):
            raise p.PhysicsError("Original crew trunk would be unsafe after bleed")
        cell.revision += 1
        cell.save(update_fields=["quantity", "details", "revision"])
        p._event(cell, "g19_generator_trunk_source_gas_metered",
                 old_cell, actor=actor)
    elif value == "secure":
        p._crew_at(actor, trunk)
        if (hatch.setting != "closed" or not suit_ready(actor, d, room)
                or not room_ready(d, room, require_permit=False,
                                  hatch_closed=True)):
            raise p.PhysicsError("No fresh measured gas, issued suit or isolated generator")
        ledger = secure_room(ledger, room, actor.dbref, d["last_game_time"])
    elif value == "inspect":
        p._crew_at(actor, room)
        if hatch.setting != "closed" or not worker_ready(actor, d, room):
            raise p.PhysicsError("Only original suited maintenance permit holder may inspect")
        ledger = enter_or_inspect(ledger, room, actor.dbref, inspect=True)
    elif value == "release":
        p._crew_at(actor, trunk)
        from world.ship_world import find_ship_space
        physical = find_ship_space(room)
        occupied = physical is not None and any(
            getattr(person.db, "crew_role", None) for person in physical.contents)
        ledger = release_room(ledger, room, actor.dbref,
            hatch_closed=hatch.setting == "closed", empty=not occupied,
            repairs_active=any(job["room"] == room for job in
                 (d.get("repairs") or {"jobs": {}})["jobs"].values()))
    else:
        raise p.PhysicsError("Use trip, bleed:<kg>, secure, inspect, release or rearm")
    validate_generator_bays(ledger)
    d["generator_bays"] = ledger
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    return clock, before


def entered(clock, room, actor):
    from world import continuous_ship_physics as p
    d = dict(clock.details)
    before = p._snapshot(clock)
    d["generator_bays"] = enter_or_inspect(
        d["generator_bays"], room, actor.dbref)
    clock.details = d
    clock.revision += 1
    clock.save(update_fields=["details", "revision"])
    p._event(clock, "g19_suited_original_generator_service_entry",
             before, actor=actor)


def readout(actor):
    from world import continuous_ship_physics as p
    here = getattr(getattr(getattr(actor, "location", None), "db", None),
                   "ox_space_id", None)
    ledger = p._clock().details.get("generator_bays")
    if ledger is None:
        raise p.PhysicsError("Generator rooms are not commissioned")
    validate_generator_bays(ledger)
    surveyed = {}
    for room, (gen, hatch, trunk, zone, breaker, _) in ROOMS.items():
        if here not in {room, trunk}:
            continue
        if here == room and not suit_ready(actor, p._clock().details, room):
            continue
        item = ledger["rooms"][room]
        gas = item["gas"]
        surveyed[room] = {
            "pressure_pa": bay_pressure(gas) if gas else None,
            "survey_time": gas["sample_s"] if gas else None,
            "original_gas_kg": item["initial_kg"],
            "trunk_bleed_kg": item["received_kg"],
            "skin_k": item["skin_k"],
            "permit_holder": (item["permit"] or {}).get("holder"),
            "original_hatch": p.state("access", hatch).setting,
            "original_breaker": p.state("isolator", breaker).setting,
            "generator_online": p.state("equipment", gen).details.get("physics_online"),
            "generator_condition": p.state("equipment", gen).condition,
            "entry_ready": room_ready(p._clock().details, room),
            "entries": item["entries"], "inspections": item["inspections"]}
    if not surveyed:
        raise PermissionError("No real original generator-service instrument at this room")
    return {"rooms": surveyed, "scope": "physically_attended_original_generator_only"}
