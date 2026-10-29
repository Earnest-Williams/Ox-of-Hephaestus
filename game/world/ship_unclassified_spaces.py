"""G19 as-fitted closure for 48 manifest-based cargo sectors, 12 loading
portals and the three non-habitable bow/trim spaces.

This is a closed-world *classification and access* register, not 63 new
pressure cells. Each sector retains UNKNOWN air until a positive volume and
chemistry survey; a port's verified cargo seal is not breathable air.
The original shield and trim spaces have no personnel entry mechanism.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

from world.ship_cargo_manifest import DRUMS, validate_cargo
from world.ship_propulsion_bay_service import (
    R_AIR, bay_pressure, bay_gas_safe)
from world.ship_crew_physiology import GAS_CP_KJ_KG_K

SECTORS = tuple(
    f"{drum}-SEC-{n:02d}" for drum in DRUMS for n in range(1, 9))
PERSONNEL_DOORS = {f"ACC-{s}": s for s in SECTORS}
FREIGHT_ROUTES = {f"ACC-{s[:5]}-FREIGHT-{s[6:]}": s for s in SECTORS}
PORTALS = tuple(f"{drum}-P{n}" for drum in DRUMS for n in (1, 2))
PORTAL_DOORS = {f"ACC-{portal}": portal for portal in PORTALS}
VOIDS = {
    "BOW-SHIELD-FOREPEAK": {
        "control": "TRUNK-B-BOW", "hatch": "ACC-BOW-SHIELD-FOREPEAK",
        "type": "solid_penetrated_shield",
        "equipment": ("MMOD-BOW-SHIELD", "DUST-IONIZER-FWD",
                      "DUST-FIELD-COILS")},
    "WATER-SHIELD-FWD": {
        "control": "WATER-FWD", "hatch": "ACC-WATER-SHIELD-FWD",
        "type": "sealed_annular_tank",
        "equipment": ("GAS-REFILL-BANK-A",)},
    "WR-TRIM-TANK-BAY": {
        "control": "WR-ROTOR-MACHINERY", "hatch": None,
        "type": "closed_rotating_trim_water",
        "equipment": ()},
}
NONPERSONNEL_LINKS = {
    **FREIGHT_ROUTES, **PORTAL_DOORS,
    **{v["hatch"]: k for k, v in VOIDS.items() if v["hatch"]},
}
CLASSIFICATIONS = frozenset({
    "empty", "ordinary_cargo", "inert_cargo",
    "hazardous_cargo", "pressurised_cargo"})
MAX_FREE_VOLUME_M3 = 30000.0  # bounded per eighth of fitted cargo drum
MAX_DRUM_SECTOR_VOLUME_M3 = 240000.0
MAX_SAMPLE_AGE_S = 600.0
MAX_LEAK_KG_S = 1.0
MINOR_PATCH_KG_S = .05
PATCH_SECONDS = 180.0
PATCH_SPARES_KG = 2.0
MAX_TICK_S = 60.0
MAX_DELTA_PA = 2000.0
EPS = 1e-6


class UnclassifiedSpaceError(ValueError):
    """Fitted boundary, evidenced manifest or finite gas failed validation."""


def _num(value, low=0.0, high=math.inf):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < low or value > high):
        raise UnclassifiedSpaceError("Invalid as-fitted measured quantity")
    return float(value)


def _person(x):
    return isinstance(x, str) and re.fullmatch(r"#[0-9]+", x) is not None


def cargo_signature(manifest, drum):
    """A digest of actual stowed freight, not a simulated lot relocation."""
    if drum not in DRUMS or not isinstance(manifest, dict):
        raise UnclassifiedSpaceError("No fitted manifest for sector survey")
    lots = manifest.get("lots", {})
    if not isinstance(lots, dict):
        raise UnclassifiedSpaceError("Malformed commercial manifest")
    rows = [
        (key, lot["location"], lot["mass_kg"], lot["kind"],
         lot["restrained"], lot["azimuth_rad"], lot["radius_m"])
        for key, lot in sorted(lots.items())
        if lot["drum"] == drum and lot["location"] == drum
    ]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"),
                                     sort_keys=True).encode()).hexdigest()


def stowed_lots(manifest, drum):
    return {key for key, lot in manifest["lots"].items()
            if lot["drum"] == drum and lot["location"] == drum}


def drum_parked(rotors, drum):
    row = rotors.get(drum) if isinstance(rotors, dict) else None
    return bool(row is not None
        and row.get("hardlock") is True and row.get("brake") is True
        and abs(row.get("rpm", 1)) < .001 and row.get("target_rpm") == 0
        and not row.get("freight_collar") and not row.get("passenger_indexer")
        and not row.get("indexing"))


def initial_unclassified():
    return {
        "version": 1,
        "sectors": {s: {
            "gas": None, "initial_kg": 0.0, "lost_kg": 0.0,
            "leak_kg_s": 0.0, "class": None, "lot_ids": [],
            "manifest_digest": None, "permit": None,
            "entries": 0, "inspections": 0, "seal": None,
            "seals_completed": 0
        } for s in SECTORS},
        "portals": {p: {
            "certified_berth": None, "seal_revision": None,
            "inspections": 0, "seal_fault": False
        } for p in PORTALS},
        "voids": {v: {
            "inspections": 0, "last_control_s": None,
        } for v in VOIDS}
    }


def validate_unclassified(ledger):
    template = initial_unclassified()
    if (not isinstance(ledger, dict) or set(ledger) != set(template)
            or ledger.get("version") != 1
            or not all(isinstance(ledger.get(k), dict)
                       and set(ledger[k]) == set(template[k])
                       for k in ("sectors", "portals", "voids"))):
        raise UnclassifiedSpaceError("63 original unclassified spaces not conserved")
    holders = set()
    for site, row in ledger["sectors"].items():
        if not isinstance(row, dict) or set(row) != set(template["sectors"][site]):
            raise UnclassifiedSpaceError("Cargo sector ledger has unexpected fields")
        for k in ("initial_kg", "lost_kg", "leak_kg_s"):
            _num(row[k], 0, MAX_LEAK_KG_S if k == "leak_kg_s" else math.inf)
        for k in ("entries", "inspections", "seals_completed"):
            if type(row[k]) is not int or row[k] < 0:
                raise UnclassifiedSpaceError("Impossible crew service count")
        gas = row["gas"]
        if gas is None:
            if (row["class"] is not None or row["lot_ids"]
                    or row["manifest_digest"] is not None
                    or any(row[k] for k in ("initial_kg", "lost_kg",
                                           "leak_kg_s", "entries",
                                           "inspections", "seals_completed"))
                    or row["permit"] is not None or row["seal"] is not None):
                raise UnclassifiedSpaceError("Unsampled cargo sector was made breathable")
            continue
        if not isinstance(gas, dict) or set(gas) != {
                "volume_m3", "mass_kg", "oxygen_kg", "co2_kg",
                "smoke_kg", "temperature_k", "sample_s"}:
            raise UnclassifiedSpaceError("Unknown enclosed sector sample")
        _num(gas["volume_m3"], 1.0, MAX_FREE_VOLUME_M3)
        _num(gas["mass_kg"])
        _num(gas["oxygen_kg"])
        _num(gas["co2_kg"])
        _num(gas["smoke_kg"])
        _num(gas["temperature_k"], 240, 350)
        _num(gas["sample_s"])
        if (not math.isclose(row["initial_kg"],
                gas["mass_kg"]+row["lost_kg"],
                rel_tol=1e-10, abs_tol=1e-5)
                or sum(gas[k] for k in ("oxygen_kg","co2_kg","smoke_kg")) >
                   gas["mass_kg"]+EPS or bay_pressure(gas) > 150000):
            raise UnclassifiedSpaceError("Measured cargo-sector mixture not conserved")
        if (row["class"] not in CLASSIFICATIONS
                or not isinstance(row["lot_ids"], list)
                or row["lot_ids"] != sorted(set(row["lot_ids"]))
                or not isinstance(row["manifest_digest"], str)
                or not re.fullmatch("[0-9a-f]{64}",row["manifest_digest"])
                or row["class"] == "empty" and bool(row["lot_ids"])):
            raise UnclassifiedSpaceError("Unwitnessed sector cargo class or allotment")
        permit = row["permit"]
        if permit is not None:
            if (not isinstance(permit, dict)
                    or set(permit) != {"holder", "issued_s"}
                    or not _person(permit["holder"])
                    or permit["holder"] in holders):
                raise UnclassifiedSpaceError("Cargo access permit missing or double held")
            _num(permit["issued_s"])
            holders.add(permit["holder"])
        seal = row["seal"]
        if seal is not None:
            if (permit is None or not isinstance(seal, dict)
                    or set(seal) != {"holder", "remaining_s"}
                    or seal["holder"] != permit["holder"]
                    or not 0 < row["leak_kg_s"] <= MINOR_PATCH_KG_S):
                raise UnclassifiedSpaceError("Cargo sealing job lacks real damaged worksite")
            _num(seal["remaining_s"], 0, PATCH_SECONDS)
    for drum in DRUMS:
        total = sum(r["gas"]["volume_m3"]
                    for s,r in ledger["sectors"].items()
                    if s.startswith(drum + "-") and r["gas"] is not None)
        if total > MAX_DRUM_SECTOR_VOLUME_M3+EPS:
            raise UnclassifiedSpaceError("Sector gas volumes exceed fitted drum envelope")
    for portal,row in ledger["portals"].items():
        if (not isinstance(row,dict)
                or set(row)!=set(template["portals"][portal])
                or row["certified_berth"] is not None
                and (not isinstance(row["certified_berth"],str)
                     or not re.fullmatch("[A-Za-z0-9][A-Za-z0-9_-]{0,47}",
                                         row["certified_berth"]))
                or (row["seal_revision"] is not None
                    and (type(row["seal_revision"]) is not int or row["seal_revision"]<0))
                or (row["certified_berth"] is None) != (row["seal_revision"] is None)
                or type(row["inspections"]) is not int
                or row["inspections"]<0
                or type(row["seal_fault"]) is not bool):
            raise UnclassifiedSpaceError("Commercial portal not independently classified")
    for void,row in ledger["voids"].items():
        if (not isinstance(row,dict)
                or set(row)!=set(template["voids"][void])
                or type(row["inspections"]) is not int or row["inspections"]<0):
            raise UnclassifiedSpaceError("Non-habitable void account malformed")
        if row["last_control_s"] is not None:
            _num(row["last_control_s"])
    return True


def survey_sector(ledger, manifest, rotors, sector, *,
                  free_volume_m3, pressure_pa, temperature_k,
                  oxygen_fraction, co2_fraction, smoke_fraction,
                  cargo_class, lot_ids, now_s, hatch_closed):
    """Positive operator survey; NEVER reinitialise an existing gas mass."""
    validate_unclassified(ledger)
    if sector not in SECTORS or not hatch_closed:
        raise UnclassifiedSpaceError("Actual original cargo sector hatch must seal")
    drum = sector[:5]
    if (drum not in manifest.get("verified_drums", ())
            or manifest.get("jobs", {}).get(drum)
            or any(p.startswith(drum) for p in manifest.get("port_jobs", {}))
            or not drum_parked(rotors,drum)):
        raise UnclassifiedSpaceError("Unsurveyed or moving original cargo drum")
    if cargo_class not in CLASSIFICATIONS:
        raise UnclassifiedSpaceError("Manifest does not classify cargo contents")
    if (not isinstance(lot_ids,(list,tuple))
            or len(lot_ids)!=len(set(lot_ids))
            or not set(lot_ids)<=stowed_lots(manifest,drum)
            or cargo_class=="empty" and bool(lot_ids)):
        raise UnclassifiedSpaceError("Sector allotment does not match actual stowed lots")
    volume=_num(free_volume_m3,1,MAX_FREE_VOLUME_M3)
    pressure=_num(pressure_pa,0,150000)
    temperature=_num(temperature_k,240,350)
    o=_num(oxygen_fraction,0,1)
    co=_num(co2_fraction,0,1)
    smoke=_num(smoke_fraction,0,1)
    now=_num(now_s)
    if o+co+smoke>1:
        raise UnclassifiedSpaceError("Unphysical ship cargo atmosphere")
    row=ledger["sectors"][sector]
    if row["permit"] is not None or row["seal"] is not None:
        raise UnclassifiedSpaceError("Occupied cargo sector cannot be re-surveyed")
    updated=copy.deepcopy(ledger)
    site=updated["sectors"][sector]
    sampled_mass=pressure*volume/(R_AIR*temperature)
    if site["gas"] is None:
        site["gas"]={
            "volume_m3":volume,"mass_kg":sampled_mass,
            "oxygen_kg":sampled_mass*o,"co2_kg":sampled_mass*co,
            "smoke_kg":sampled_mass*smoke,
            "temperature_k":temperature,"sample_s":now}
        site["initial_kg"]=sampled_mass
    else:
        gas=site["gas"]
        if (now<gas["sample_s"] or abs(gas["volume_m3"]-volume)>1e-4
                or abs(bay_pressure(gas)-pressure)>150
                or abs(gas["temperature_k"]-temperature)>1
                or abs(gas["oxygen_kg"]/max(gas["mass_kg"],EPS)-o)>.002
                or abs(gas["co2_kg"]/max(gas["mass_kg"],EPS)-co)>.002
                or abs(gas["smoke_kg"]/max(gas["mass_kg"],EPS)-smoke)>.00001):
            raise UnclassifiedSpaceError("As-found sector gas cannot be invented again")
        gas["sample_s"]=now
    site["class"]=cargo_class
    site["lot_ids"]=sorted(lot_ids)
    site["manifest_digest"]=cargo_signature(manifest,drum)
    validate_unclassified(updated)
    return updated


def complete_manifest(ledger,manifest,drum):
    """Every currently stowed real lot must be accounted for exactly once."""
    if drum not in DRUMS or drum not in manifest.get("verified_drums",()):
        return False
    expected = stowed_lots(manifest,drum)
    assigned=[]
    digest=cargo_signature(manifest,drum)
    for sector in (s for s in SECTORS if s.startswith(drum+"-")):
        row=ledger["sectors"][sector]
        if row["gas"] is None or row["manifest_digest"]!=digest:
            return False
        assigned.extend(row["lot_ids"])
    return sorted(assigned)==sorted(expected) and len(assigned)==len(set(assigned))


def permit_ready(ledger,manifest,rotors,sector, *,
                 source_pressure_pa,source_safe,now_s,
                 permit_required=True,allow_minor_leak=False,
                 allow_stale_retreat=False):
    """Strict entry; a held worker may retreat from the same rotating frame.

    A sector and its gallery rotate together. Returning to that gallery is
    not a fixed-to-rotating transfer and must not demand a newly hardlocked
    drum or a fresh cargo manifest after a casualty. The original owner,
    living air sample, pressure differential and rated hatch still apply.
    """
    if type(allow_stale_retreat) is not bool or (
            allow_stale_retreat and not permit_required):
        raise UnclassifiedSpaceError(
            "Expired survey may be bypassed only for an already held permit")
    validate_unclassified(ledger)
    if sector not in SECTORS or not source_safe:
        return False
    drum=sector[:5]
    row=ledger["sectors"][sector]
    gas=row["gas"]
    if (gas is None or row["class"] not in {"empty","ordinary_cargo"}
            or (not allow_stale_retreat
                and not drum_parked(rotors,drum))
            or manifest.get("jobs",{}).get(drum)
            or any(p.startswith(drum) for p in manifest.get("port_jobs",{}))
            or (not allow_stale_retreat
                and not complete_manifest(ledger,manifest,drum))
            or not bay_gas_safe(gas)
            or row["leak_kg_s"] > (MINOR_PATCH_KG_S if allow_minor_leak else 0)
            or _num(now_s)<gas["sample_s"]
            or (not allow_stale_retreat
                and _num(now_s)-gas["sample_s"]>MAX_SAMPLE_AGE_S)
            or abs(_num(source_pressure_pa)-bay_pressure(gas))>MAX_DELTA_PA):
        return False
    return row["permit"] is not None if permit_required else True


def secure_sector(ledger, sector, holder, now_s):
    validate_unclassified(ledger)
    if (sector not in SECTORS or not _person(holder)
            or ledger["sectors"][sector]["permit"] is not None
            or any(row["permit"] and row["permit"]["holder"]==holder
                   for row in ledger["sectors"].values())):
        raise UnclassifiedSpaceError("Sector service permit is exclusive and physically owned")
    updated=copy.deepcopy(ledger)
    updated["sectors"][sector]["permit"]={"holder":holder,"issued_s":_num(now_s)}
    validate_unclassified(updated)
    return updated


def note_entry(ledger,sector,holder,*,inspection=False):
    validate_unclassified(ledger)
    if (sector not in SECTORS or
            (ledger["sectors"][sector]["permit"] or {}).get("holder")!=holder):
        raise UnclassifiedSpaceError("Crew access receipt needs a real owner")
    updated=copy.deepcopy(ledger)
    updated["sectors"][sector]["inspections" if inspection else "entries"]+=1
    return updated


def release_sector(ledger,sector,holder,*,closed,empty):
    validate_unclassified(ledger)
    if (sector not in SECTORS or not closed or not empty
            or ledger["sectors"][sector]["seal"] is not None
            or (ledger["sectors"][sector]["permit"] or {}).get("holder")!=holder):
        raise UnclassifiedSpaceError("No empty, closed, finished cargo sector to release")
    updated=copy.deepcopy(ledger)
    updated["sectors"][sector]["permit"]=None
    validate_unclassified(updated)
    return updated


def inject_sector_leak(ledger,sector,leak_kg_s):
    validate_unclassified(ledger)
    if sector not in SECTORS or ledger["sectors"][sector]["gas"] is None:
        raise UnclassifiedSpaceError("Unsampled sector cannot have observed gas-loss rate")
    rate=_num(leak_kg_s,EPS,MAX_LEAK_KG_S)
    updated=copy.deepcopy(ledger)
    row=updated["sectors"][sector]
    if row["seal"] is not None:
        raise UnclassifiedSpaceError("Cannot alter a currently active patch condition")
    row["leak_kg_s"]=rate
    validate_unclassified(updated)
    return updated


def begin_sector_seal(ledger,sector,holder):
    validate_unclassified(ledger)
    if (sector not in SECTORS or
            (ledger["sectors"][sector]["permit"] or {}).get("holder")!=holder
            or ledger["sectors"][sector]["seal"] is not None or
            not 0<ledger["sectors"][sector]["leak_kg_s"]<=MINOR_PATCH_KG_S):
        raise UnclassifiedSpaceError("Only a fitted, minor and occupied leak can be patched inside")
    updated=copy.deepcopy(ledger)
    updated["sectors"][sector]["seal"]={"holder":holder,
                                       "remaining_s":PATCH_SECONDS}
    validate_unclassified(updated)
    return updated


def cancel_sector_seal(ledger,sector,holder,*,hatch_closed,empty):
    """Abort unfinished work after real retreat; leave loss and spares intact."""
    validate_unclassified(ledger)
    if (sector not in SECTORS or not hatch_closed or not empty
            or (ledger["sectors"][sector]["permit"] or {}).get("holder")!=holder
            or (ledger["sectors"][sector]["seal"] or {}).get("holder")!=holder):
        raise UnclassifiedSpaceError(
            "Only evacuated original work permit holder may abandon a seal")
    result=copy.deepcopy(ledger)
    result["sectors"][sector]["seal"]=None
    validate_unclassified(result)
    return result


def tick_unclassified(ledger,seconds,*,ready_seals=frozenset()):
    validate_unclassified(ledger)
    seconds=_num(seconds,0,MAX_TICK_S)
    updated=copy.deepcopy(ledger)
    lost=0.0
    finished=[]
    for sector,row in updated["sectors"].items():
        gas=row["gas"]
        if gas is None:
            continue
        old=gas["mass_kg"]
        leaked=min(old,row["leak_kg_s"]*seconds)
        if leaked:
            fraction=leaked/old
            for k in ("oxygen_kg","co2_kg","smoke_kg"):
                gas[k]*=1-fraction
            gas["mass_kg"]-=leaked
            row["lost_kg"]+=leaked
            lost+=leaked
        job=row["seal"]
        if job is not None and (sector,job["holder"]) in ready_seals:
            job["remaining_s"]=max(0.0,job["remaining_s"]-seconds)
            if job["remaining_s"]<=EPS:
                finished.append((sector,job["holder"],PATCH_SPARES_KG))
                row["seal"]=None
                row["leak_kg_s"]=0.0
                row["seals_completed"]+=1
    validate_unclassified(updated)
    return updated,lost,tuple(finished)


def certify_portal(ledger,manifest,rotors,portal,*,berth,
                   real_hatch_closed,sound,machinery_healthy,
                   now_s, hatch_revision):
    validate_unclassified(ledger)
    if portal not in PORTALS or not real_hatch_closed or not sound or not machinery_healthy:
        raise UnclassifiedSpaceError("Original cargo pressure sleeve/handler not physically secured")
    contact=manifest.get("port_contacts",{}).get(portal)
    if (not contact or not contact.get("docked")
            or contact.get("berth_id")!=berth or
            not drum_parked(rotors,portal[:5])
            or any(p.startswith(portal[:5]) for p in manifest.get("port_jobs",{}))
            or manifest.get("jobs",{}).get(portal[:5])
            or not drum_clear_for_freight(ledger,portal[:5])):
        raise UnclassifiedSpaceError("Port needs positive external berth, stopped drum and isolated cargo")
    _num(now_s)
    if type(hatch_revision) is not int or hatch_revision<0:
        raise UnclassifiedSpaceError("Original hatch revision is not measured")
    updated=copy.deepcopy(ledger)
    p=updated["portals"][portal]
    if p["seal_fault"]:
        raise UnclassifiedSpaceError("Faulted loading sleeve needs real repair and reinspection")
    p["certified_berth"]=berth
    p["seal_revision"]=hatch_revision
    p["inspections"]+=1
    validate_unclassified(updated)
    return updated


def invalidate_portal(ledger,portal):
    validate_unclassified(ledger)
    if portal not in PORTALS:
        raise UnclassifiedSpaceError("No fitted cargo portal")
    updated=copy.deepcopy(ledger)
    updated["portals"][portal]["certified_berth"]=None
    updated["portals"][portal]["seal_revision"]=None
    validate_unclassified(updated)
    return updated


def drum_clear_for_freight(ledger,drum):
    if drum not in DRUMS:
        return False
    return all(not row["permit"] and row["leak_kg_s"]==0
               and row["seal"] is None
               for sector,row in ledger["sectors"].items()
               if sector.startswith(drum+"-"))


def portal_ready(ledger,manifest,portal,*,hatch_revision,hatch_closed,
                 hatch_sound,handler_sound):
    validate_unclassified(ledger)
    if portal not in PORTALS:
        return False
    row=ledger["portals"][portal]
    berth=(manifest.get("port_contacts",{}).get(portal) or {}).get("berth_id")
    return bool(row["certified_berth"] is not None
                and row["certified_berth"]==berth
                and row["seal_revision"]==hatch_revision
                and hatch_closed and hatch_sound and handler_sound
                and not row["seal_fault"]
                and drum_clear_for_freight(ledger,portal[:5]))


def inspect_void(ledger,void,now_s):
    """Records local control inspection; never records entry into solid/tank."""
    validate_unclassified(ledger)
    if void not in VOIDS:
        raise UnclassifiedSpaceError("No fitted sealed shield/trim space")
    updated=copy.deepcopy(ledger)
    updated["voids"][void]["inspections"]+=1
    updated["voids"][void]["last_control_s"]=_num(now_s)
    validate_unclassified(updated)
    return updated


def breathing_sample(ledger,sector):
    """Virtual physiology adapter for one *measured* cargo sector only.

    A virtual cell is a view of a prior as-found measured charge, not an
    extra pressure cell or the rotating gallery's real crew air. Exposure
    may use its finite oxygen; heat loads existing cargo lining thermal
    capacity. Unsurveyed cargo returns None, i.e. absolutely no oxygen.
    """
    validate_unclassified(ledger)
    if sector not in SECTORS:
        raise UnclassifiedSpaceError("Unknown human occupancy cargo position")
    gas=ledger["sectors"][sector]["gas"]
    if gas is None:
        return None
    capacity=1000.0+10.0*gas["volume_m3"]
    return {
        "mass":gas["mass_kg"],"oxygen":gas["oxygen_kg"],
        "co2":gas["co2_kg"],"smoke":gas["smoke_kg"],
        "volume":gas["volume_m3"],"temperature":gas["temperature_k"],
        "capacity":capacity,
        "energy":(capacity+gas["mass_kg"]*GAS_CP_KJ_KG_K)*gas["temperature_k"],
    }


def commit_breathing_sample(ledger,sector,measured):
    """Crediting CO2 by the exact oxygen breathed conserves sector gas."""
    validate_unclassified(ledger)
    if sector not in SECTORS:
        raise UnclassifiedSpaceError("Unknown occupied cargo-sector authority")
    original=ledger["sectors"][sector]["gas"]
    if original is None:
        if measured is not None:
            raise UnclassifiedSpaceError("Unmeasured sector cannot receive invented air")
        return ledger
    if not isinstance(measured,dict):
        raise UnclassifiedSpaceError("Measured sector gas unexpectedly disappeared")
    previous=breathing_sample(ledger,sector)
    for k in ("mass","volume","smoke","oxygen","co2","temperature","energy"):
        _num(measured.get(k))
    if (not math.isclose(measured["mass"],previous["mass"],abs_tol=1e-7)
            or not math.isclose(measured["volume"],previous["volume"],abs_tol=1e-7)
            or not math.isclose(measured["smoke"],previous["smoke"],abs_tol=1e-7)
            or measured["oxygen"]>previous["oxygen"]+EPS
            or measured["co2"]<previous["co2"]-EPS
            or not math.isclose(
                previous["oxygen"]-measured["oxygen"],
                measured["co2"]-previous["co2"],abs_tol=1e-7)
            or measured["temperature"]<previous["temperature"]-EPS
            or measured["temperature"]>350):
        raise UnclassifiedSpaceError("Cargo breathing attempted unaccounted oxygen or heat")
    updated=copy.deepcopy(ledger)
    row=updated["sectors"][sector]["gas"]
    row["oxygen_kg"]=measured["oxygen"]
    row["co2_kg"]=measured["co2"]
    row["temperature_k"]=measured["temperature"]
    validate_unclassified(updated)
    return updated
