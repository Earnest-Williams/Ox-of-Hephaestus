"""The SIXTEEN original unclassified industrial/service rooms (four aft + twelve bearings).

Every rated hatch, cell, compartment, panel and breaker is copied from the
fitted v0.5 candidate. Never infer breathable gas from a room kind or a suit.
This is a pure simulation ledger; Evennia installed state is authoritative.
"""
from __future__ import annotations

import copy
import math
import re

from world.ship_propulsion_bay_service import R_AIR, bay_pressure, bay_gas_safe, source_pressure

SITES = {
    "THERM-HT": {
        "door": "ACC-THERM-HT",
        "trunk": "TRUNK-B-AFT",
        "zone": "PZ-TRUNK-B-AFT",
        "max_m3": 369.92,
        "panel": "LP-THERM-HT",
        "breaker": "ISO-LP-THERM-HT",
        "family": "thermal_plant",
        "drum": None
    },
    "FTL-SVC": {
        "door": "ACC-FTL-SVC",
        "trunk": "TRUNK-A-AFT",
        "zone": "PZ-TRUNK-A-AFT",
        "max_m3": 514.08,
        "panel": "LP-FTL-SVC",
        "breaker": "ISO-LP-FTL-SVC",
        "family": "ftl_service",
        "drum": None
    },
    "FUEL-SVC": {
        "door": "ACC-FUEL-SVC",
        "trunk": "TRUNK-B-AFT",
        "zone": "PZ-TRUNK-B-AFT",
        "max_m3": 428.4,
        "panel": "LP-FUEL-SVC",
        "breaker": "ISO-LP-FUEL-SVC",
        "family": "fuel_service",
        "drum": None
    },
    "REACTION-SVC": {
        "door": "ACC-REACTION-SVC",
        "trunk": "TRUNK-B-AFT",
        "zone": "PZ-TRUNK-B-AFT",
        "max_m3": 342.72,
        "panel": "LP-REACTION-SVC",
        "breaker": "ISO-LP-REACTION-SVC",
        "family": "propellant_service",
        "drum": None
    },
    "BE-01-SVC": {
        "door": "ACC-BE-01-SVC",
        "trunk": "TRUNK-B-DR-01",
        "zone": "PZ-TRUNK-B-DR-01",
        "max_m3": 61.2,
        "panel": "LP-BE-01-SVC",
        "breaker": "ISO-LP-BE-01-SVC",
        "family": "bearing_service",
        "drum": "DR-01"
    },
    "BE-02-SVC": {
        "door": "ACC-BE-02-SVC",
        "trunk": "TRUNK-B-DR-01",
        "zone": "PZ-TRUNK-B-DR-01",
        "max_m3": 61.2,
        "panel": "LP-BE-02-SVC",
        "breaker": "ISO-LP-BE-02-SVC",
        "family": "bearing_service",
        "drum": "DR-01"
    },
    "BE-03-SVC": {
        "door": "ACC-BE-03-SVC",
        "trunk": "TRUNK-B-DR-02",
        "zone": "PZ-TRUNK-B-DR-02",
        "max_m3": 61.2,
        "panel": "LP-BE-03-SVC",
        "breaker": "ISO-LP-BE-03-SVC",
        "family": "bearing_service",
        "drum": "DR-02"
    },
    "BE-04-SVC": {
        "door": "ACC-BE-04-SVC",
        "trunk": "TRUNK-B-DR-02",
        "zone": "PZ-TRUNK-B-DR-02",
        "max_m3": 61.2,
        "panel": "LP-BE-04-SVC",
        "breaker": "ISO-LP-BE-04-SVC",
        "family": "bearing_service",
        "drum": "DR-02"
    },
    "BE-05-SVC": {
        "door": "ACC-BE-05-SVC",
        "trunk": "TRUNK-B-DR-03",
        "zone": "PZ-TRUNK-B-DR-03",
        "max_m3": 61.2,
        "panel": "LP-BE-05-SVC",
        "breaker": "ISO-LP-BE-05-SVC",
        "family": "bearing_service",
        "drum": "DR-03"
    },
    "BE-06-SVC": {
        "door": "ACC-BE-06-SVC",
        "trunk": "TRUNK-B-DR-03",
        "zone": "PZ-TRUNK-B-DR-03",
        "max_m3": 61.2,
        "panel": "LP-BE-06-SVC",
        "breaker": "ISO-LP-BE-06-SVC",
        "family": "bearing_service",
        "drum": "DR-03"
    },
    "BE-07-SVC": {
        "door": "ACC-BE-07-SVC",
        "trunk": "TRUNK-B-DR-04",
        "zone": "PZ-TRUNK-B-DR-04",
        "max_m3": 61.2,
        "panel": "LP-BE-07-SVC",
        "breaker": "ISO-LP-BE-07-SVC",
        "family": "bearing_service",
        "drum": "DR-04"
    },
    "BE-08-SVC": {
        "door": "ACC-BE-08-SVC",
        "trunk": "TRUNK-B-DR-04",
        "zone": "PZ-TRUNK-B-DR-04",
        "max_m3": 61.2,
        "panel": "LP-BE-08-SVC",
        "breaker": "ISO-LP-BE-08-SVC",
        "family": "bearing_service",
        "drum": "DR-04"
    },
    "BE-09-SVC": {
        "door": "ACC-BE-09-SVC",
        "trunk": "TRUNK-B-DR-05",
        "zone": "PZ-TRUNK-B-DR-05",
        "max_m3": 61.2,
        "panel": "LP-BE-09-SVC",
        "breaker": "ISO-LP-BE-09-SVC",
        "family": "bearing_service",
        "drum": "DR-05"
    },
    "BE-10-SVC": {
        "door": "ACC-BE-10-SVC",
        "trunk": "TRUNK-B-DR-05",
        "zone": "PZ-TRUNK-B-DR-05",
        "max_m3": 61.2,
        "panel": "LP-BE-10-SVC",
        "breaker": "ISO-LP-BE-10-SVC",
        "family": "bearing_service",
        "drum": "DR-05"
    },
    "BE-11-SVC": {
        "door": "ACC-BE-11-SVC",
        "trunk": "TRUNK-B-DR-06",
        "zone": "PZ-TRUNK-B-DR-06",
        "max_m3": 61.2,
        "panel": "LP-BE-11-SVC",
        "breaker": "ISO-LP-BE-11-SVC",
        "family": "bearing_service",
        "drum": "DR-06"
    },
    "BE-12-SVC": {
        "door": "ACC-BE-12-SVC",
        "trunk": "TRUNK-B-DR-06",
        "zone": "PZ-TRUNK-B-DR-06",
        "max_m3": 61.2,
        "panel": "LP-BE-12-SVC",
        "breaker": "ISO-LP-BE-12-SVC",
        "family": "bearing_service",
        "drum": "DR-06"
    }
}
DOORS = {spec["door"]: room for room, spec in SITES.items()}
MAX_BLEED_KG = 20.0
MAX_EQUALIZATION_PA = 2000.0
MAX_SURVEY_AGE_S = 600.0
MAX_ADVANCE_S = 60.0
MAX_LEAK_KG_S = 0.25
HAND_PATCH_LEAK_KG_S = 0.05
SEAL_PARTS_KG = 2.0
SEAL_WORK_S = 180.0
EPS = 1e-6


class IndustrialAccessError(ValueError):
    """Fitted industrial containment, safe admission or material seal failed."""


def _num(x, low=0, high=math.inf):
    if type(x) not in (float, int) or not math.isfinite(x) or not low <= x <= high:
        raise IndustrialAccessError("Invalid bounded measured industrial quantity")
    return float(x)


def initial_industrial():
    return {"version": 1, "sites": {
        room: {"gas": None, "initial_kg": 0.0, "received_kg": 0.0,
               "lost_kg": 0.0, "leak_kg_s": 0.0, "skin_k": None,
               "permit": None, "seal": None, "entries": 0,
               "inspections": 0, "repairs": 0}
        for room in SITES}}


def validate_industrial(ledger):
    if (not isinstance(ledger, dict) or set(ledger) != {"version", "sites"}
            or ledger["version"] != 1 or not isinstance(ledger["sites"], dict)
            or set(ledger["sites"]) != set(SITES)):
        raise IndustrialAccessError("Fitted sixteen-room register corrupted")
    occupied = set()
    for room, row in ledger["sites"].items():
        if not isinstance(row, dict) or set(row) != {
            "gas", "initial_kg", "received_kg", "lost_kg", "leak_kg_s",
            "skin_k", "permit", "seal", "entries", "inspections", "repairs"}:
            raise IndustrialAccessError("Industrial site fields unexpected")
        for k in ("initial_kg", "received_kg", "lost_kg"):
            _num(row[k])
        _num(row["leak_kg_s"],0,MAX_LEAK_KG_S)
        if any(type(row[k]) is not int or row[k] < 0 for k in (
                "entries","inspections","repairs")):
            raise IndustrialAccessError("Impossible service receipt counts")
        gas = row["gas"]
        if gas is None:
            if (row["initial_kg"] or row["received_kg"] or row["lost_kg"]
                    or row["leak_kg_s"] or row["skin_k"] is not None
                    or row["permit"] is not None or row["seal"] is not None
                    or row["entries"] or row["inspections"] or row["repairs"]):
                raise IndustrialAccessError("Unobserved service room cannot own gas or damage")
            continue
        if not isinstance(gas,dict) or set(gas) != {
                "mass_kg", "oxygen_kg", "co2_kg", "smoke_kg",
                "temperature_k", "volume_m3", "sample_s"}:
            raise IndustrialAccessError("Unknown industrial gas measurement fields")
        _num(gas["volume_m3"],1,SITES[room]["max_m3"])
        _num(gas["mass_kg"])
        _num(gas["oxygen_kg"])
        _num(gas["co2_kg"])
        _num(gas["smoke_kg"])
        _num(gas["temperature_k"],250,330)
        _num(gas["sample_s"])
        _num(row["skin_k"],250,400)
        if (gas["oxygen_kg"]+gas["co2_kg"]+gas["smoke_kg"] > gas["mass_kg"]+EPS
                or not math.isclose(row["initial_kg"]+row["received_kg"],
                                    gas["mass_kg"]+row["lost_kg"],
                                    rel_tol=1e-10,abs_tol=1e-5)
                or bay_pressure(gas)>130000):
            raise IndustrialAccessError("Original compartment gas does not conserve")
        permit = row["permit"]
        if permit is not None:
            if (not isinstance(permit,dict)
                    or set(permit)!={"holder","issued_s"}
                    or not isinstance(permit["holder"],str)
                    or not re.fullmatch(r"#[0-9]+",permit["holder"])):
                raise IndustrialAccessError("Industrial work permit not owned")
            _num(permit["issued_s"])
            if permit["holder"] in occupied:
                raise IndustrialAccessError("One worker cannot hold two industrial hatches")
            occupied.add(permit["holder"])
        seal = row["seal"]
        if seal is not None:
            if (permit is None or not isinstance(seal,dict)
                    or set(seal)!={"holder","remaining_s","required_kg"}
                    or seal["holder"]!=permit["holder"]
                    or seal["required_kg"]!=SEAL_PARTS_KG
                    or row["leak_kg_s"]<=0):
                raise IndustrialAccessError("A false worksite leak patch was staged")
            _num(seal["remaining_s"],0,SEAL_WORK_S)
    return True


def positive_survey(ledger, room, *, volume_m3, pressure_pa,
                    temperature_k, oxygen_fraction, co2_fraction,
                    smoke_fraction, skin_k, now_s, hatch_closed):
    """Discover as-found air ONCE. A later gauge must agree with remaining mass."""
    validate_industrial(ledger)
    if room not in SITES or not hatch_closed:
        raise IndustrialAccessError("Positive sealed-room observation requires original hatch")
    v=_num(volume_m3,1,SITES[room]["max_m3"])
    p=_num(pressure_pa,0,130000)
    t=_num(temperature_k,250,330)
    o=_num(oxygen_fraction,0,1)
    c=_num(co2_fraction,0,1)
    s=_num(smoke_fraction,0,1)
    now=_num(now_s)
    surface=_num(skin_k,250,400)
    if o+c+s>1:
        raise IndustrialAccessError("Impossible mixed atmosphere")
    result=copy.deepcopy(ledger)
    row=result["sites"][room]
    if row["permit"] is not None:
        raise IndustrialAccessError("Survey cannot reset occupied or sealed room")
    mass=p*v/(R_AIR*t)
    if row["gas"] is None:
        row["gas"]={"mass_kg":mass,"oxygen_kg":mass*o,"co2_kg":mass*c,
                    "smoke_kg":mass*s,"temperature_k":t,"volume_m3":v,
                    "sample_s":now}
        row["initial_kg"]=mass
    else:
        previous=row["gas"]
        if (now<previous["sample_s"]
                or abs(previous["volume_m3"]-v)>1e-4
                or abs(bay_pressure(previous)-p)>150
                or abs(previous["temperature_k"]-t)>1
                or abs(previous["oxygen_kg"]/max(previous["mass_kg"],EPS)-o)>.002
                or abs(previous["co2_kg"]/max(previous["mass_kg"],EPS)-c)>.002
                or abs(previous["smoke_kg"]/max(previous["mass_kg"],EPS)-s)>.00001):
            raise IndustrialAccessError("Gauge disagrees with already-conserved gas")
        previous["sample_s"]=now
    row["skin_k"]=surface
    validate_industrial(result)
    return result


def bleed(ledger, room, *, kg, source, source_safe, hatch_closed,
          isolated, now_s):
    """Single 0-20 kg manual hatch tap; NO reverse poison vent or free refill."""
    validate_industrial(ledger)
    if room not in SITES or not all((source_safe,hatch_closed,isolated)):
        raise IndustrialAccessError("Original isolated hatch and clean source required")
    moved=_num(kg,EPS,MAX_BLEED_KG)
    now=_num(now_s)
    row=ledger["sites"][room]
    if (row["gas"] is None or row["permit"] is not None
            or row["leak_kg_s"]>0):
        raise IndustrialAccessError("Breathing supply cannot feed a leaking/occupied unknown bay")
    gas=row["gas"]
    if now<gas["sample_s"] or now-gas["sample_s"]>MAX_SURVEY_AGE_S:
        raise IndustrialAccessError("Unknown-bay gas sample has expired")
    src={k:_num(source[k]) for k in ("mass_kg","oxygen_kg","co2_kg",
                                   "smoke_kg","temperature_k","volume_m3")}
    if (src["mass_kg"]<=moved*10
            or sum(src[k] for k in ("oxygen_kg","co2_kg","smoke_kg"))>src["mass_kg"]):
        raise IndustrialAccessError("Source gas insufficient")
    diff=source_pressure(src)-bay_pressure(gas)
    if diff<=MAX_EQUALIZATION_PA:
        raise IndustrialAccessError("No physical upstream gas differential")
    equilibrium=diff/(R_AIR*(src["temperature_k"]/src["volume_m3"]+
                             gas["temperature_k"]/gas["volume_m3"]))
    if moved>equilibrium+EPS:
        raise IndustrialAccessError("Transfer would reverse actual pressure flow")
    result=copy.deepcopy(ledger)
    new=result["sites"][room]["gas"]
    original_mass=new["mass_kg"]
    new["temperature_k"]=(new["temperature_k"]*original_mass+
                          src["temperature_k"]*moved)/(original_mass+moved)
    new["mass_kg"]+=moved
    for key in ("oxygen_kg","co2_kg","smoke_kg"):
        parcel=moved*src[key]/src["mass_kg"]
        new[key]+=parcel
        src[key]-=parcel
    src["mass_kg"]-=moved
    new["sample_s"]=now
    result["sites"][room]["received_kg"]+=moved
    validate_industrial(result)
    return result,src


def enterable(ledger,room,*, source_pa, source_safe,
              hatch_sound, isolated, now_s, need_permit=True,
              allow_small_leak=False):
    validate_industrial(ledger)
    if room not in SITES:
        return False
    site=ledger["sites"][room]
    gas=site["gas"]
    leak=site["leak_kg_s"]
    if (gas is None or not all((source_safe,hatch_sound,isolated))
            or (leak>0 and (not allow_small_leak or leak>HAND_PATCH_LEAK_KG_S))
            or not bay_gas_safe(gas)
            or site["skin_k"]>315
            or abs(_num(source_pa)-bay_pressure(gas))>MAX_EQUALIZATION_PA
            or _num(now_s)<gas["sample_s"]):
        return False
    if need_permit:
        return site["permit"] is not None
    return _num(now_s)-gas["sample_s"]<=MAX_SURVEY_AGE_S


def secure(ledger,room,worker,now_s):
    validate_industrial(ledger)
    if room not in SITES or ledger["sites"][room]["permit"] is not None or (
            not isinstance(worker,str) or not re.fullmatch(r"#[0-9]+",worker)):
        raise IndustrialAccessError("Signed exclusive industrial permit unavailable")
    if any(entry["permit"] is not None and entry["permit"]["holder"]==worker
           for entry in ledger["sites"].values()):
        raise IndustrialAccessError("One worker cannot occupy separate isolated work rooms")
    result=copy.deepcopy(ledger)
    result["sites"][room]["permit"]={"holder":worker,"issued_s":_num(now_s)}
    validate_industrial(result)
    return result


def inspect(ledger,room,worker,*,entry=False):
    validate_industrial(ledger)
    if room not in SITES or (ledger["sites"][room]["permit"] or {}).get("holder")!=worker:
        raise IndustrialAccessError("An unauthorised worker cannot inspect original room")
    result=copy.deepcopy(ledger)
    result["sites"][room]["entries" if entry else "inspections"]+=1
    validate_industrial(result)
    return result


def release(ledger,room,worker,*, hatch_closed, no_crew, repairs_active):
    validate_industrial(ledger)
    if (room not in SITES or not hatch_closed or not no_crew
            or repairs_active or ledger["sites"][room]["seal"] is not None
            or (ledger["sites"][room]["permit"] or {}).get("holder")!=worker):
        raise IndustrialAccessError("Occupied, open or unfinished service room cannot release")
    result=copy.deepcopy(ledger)
    result["sites"][room]["permit"]=None
    validate_industrial(result)
    return result


def attest_leak(ledger,room,*,leak_kg_s):
    """Operator witnesses genuine casing/shell defect: NEVER create gas."""
    validate_industrial(ledger)
    if room not in SITES or ledger["sites"][room]["gas"] is None:
        raise IndustrialAccessError("Unmeasured industrial void cannot assert leak rate")
    leak=_num(leak_kg_s,EPS,MAX_LEAK_KG_S)
    result=copy.deepcopy(ledger)
    if result["sites"][room]["seal"] is not None:
        raise IndustrialAccessError("Active leak job cannot silently change fault")
    result["sites"][room]["leak_kg_s"]=leak
    validate_industrial(result)
    return result


def begin_seal(ledger,room,worker):
    validate_industrial(ledger)
    if (room not in SITES or
            (ledger["sites"][room]["permit"] or {}).get("holder")!=worker or
            ledger["sites"][room]["seal"] is not None or
            not 0<ledger["sites"][room]["leak_kg_s"]<=HAND_PATCH_LEAK_KG_S):
        raise IndustrialAccessError("Only minor contained leak may receive internal seal")
    result=copy.deepcopy(ledger)
    result["sites"][room]["seal"]={
        "holder":worker,"remaining_s":SEAL_WORK_S,
        "required_kg":SEAL_PARTS_KG}
    validate_industrial(result)
    return result


def tick(ledger,seconds,*,ready_workers=frozenset()):
    """Leak real species into space; finished interior patch needs 2kg on hand.

    The caller debits verified carried repair spares and credits their installed
    mass in the very same ship transaction when a seal finishes. A deep breach
    has NO internal patch shortcut.
    """
    validate_industrial(ledger)
    dt=_num(seconds,0,MAX_ADVANCE_S)
    result=copy.deepcopy(ledger)
    lost=0.0
    finished=[]
    for room,site in sorted(result["sites"].items()):
        gas=site["gas"]
        if gas is None:
            continue
        old_mass=gas["mass_kg"]
        escaping=min(old_mass,site["leak_kg_s"]*dt)
        if escaping and old_mass:
            f=escaping/old_mass
            for key in ("oxygen_kg","co2_kg","smoke_kg"):
                gas[key]=max(0.0,gas[key]*(1-f))
            gas["mass_kg"]=max(0.0,old_mass-escaping)
            site["lost_kg"]+=escaping
            lost+=escaping
        work=site["seal"]
        if work and (room,work["holder"]) in ready_workers:
            work["remaining_s"]=max(0,work["remaining_s"]-dt)
            if work["remaining_s"]<=EPS:
                site["leak_kg_s"]=0.0
                site["seal"]=None
                site["repairs"]+=1
                finished.append((room,work["holder"],SEAL_PARTS_KG))
    validate_industrial(result)
    return result,lost,tuple(finished)
