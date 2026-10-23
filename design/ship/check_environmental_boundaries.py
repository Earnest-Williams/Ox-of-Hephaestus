#!/usr/bin/env python3
"""Unknown-environment cargo/industrial threshold integrity and casualty screen.

The selected v0.5 nominal pressure-bulkhead hardware is not an assertion of
as-installed seals, valid atmosphere samples, safe access, or Evennia state.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
from math import isfinite
from pathlib import Path

HERE = Path(__file__).resolve().parent

def read(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))

def insist(condition: bool, reason: str):
    if not condition:
        raise ValueError(reason)

ENV_ROLES = {
    "manifest_dependent_cargo_sector",
    "commercial_cargo_portal",
    "bearing_service_annulus",
    "high_energy_industrial_plant",
    "unoccupied_shield_or_trim_bay",
}
REQUIRED_RESTRICTIONS = {
    "receiving compartment pressure and composition must be measured locally before release",
    "positive differential-pressure equalisation required; PPE alone does not permit hatch opening",
    "retention of known-side pressure and containment unless an independently isolated transfer is established",
}

def may_release(record: dict, readings: dict, control: dict) -> tuple[bool,str]:
    """Pure permission screen, not an actuator command or simulation mutation."""
    pressure = readings.get("known_kPa"), readings.get("receiving_kPa")
    if not readings.get("both_local_pressure_samples_verified"):
        return False,"local_pressure_sample_missing"
    if not all(isinstance(p,(int,float)) and isfinite(p) and p>=0 for p in pressure):
        return False,"invalid_pressure_sample"
    if abs(pressure[0]-pressure[1])>2.0:
        return False,"differential_pressure_unsafe"
    if not readings.get("local_chemistry_verified"):
        return False,"receiving_chemistry_unknown"
    if not control.get("local_authority_and_access_permit"):
        return False,"no_local_release_permission"
    if not control.get("gate_mechanically_verified"):
        return False,"gate_capture_or_seal_unproven"
    # A maintenance approval is not physical proof of a third sealed volume.
    # No such independently bounded transfer cell is identified at these
    # direct cargo/plant thresholds; a separate rated transfer sequence is needed.
    if not readings.get("environment_compatible"):
        return False,"incompatible_media_requires_separate_transfer_cell"
    role=record["environment_role"]
    if role == "manifest_dependent_cargo_sector":
        if not control.get("all_other_sector_boundaries_shut"):
            return False,"cargo_sector_second_door_not_contained"
        if not control.get("sector_cargo_manifest_matched"):
            return False,"cargo_manifest_unverified"
    if role == "commercial_cargo_portal" and not control.get("external_capture_verified"):
        return False,"outer_portal_not_secure"
    if role in {"bearing_service_annulus","high_energy_industrial_plant",
                "unoccupied_shield_or_trim_bay"} and not control.get("machinery_energy_isolated"):
        return False,"energised_or_moving_machinery"
    return True,"release_preconditions_proven"

def validate(ship: dict, pressure: dict, gas: dict, manifest: dict) -> dict:
    spaces={s["id"]:s for s in ship["spaces"]}
    links={e["id"]:e for e in ship["access_links"]}
    boundary={e["id"]:e for e in pressure["pressure_boundary_doors"]}
    tasks={t["id"] for t in ship["maintenance_tasks"]}
    policies={p["space_id"]:p for p in gas["unclassified_nonbreathable_by_default"]}
    insist(len(spaces)==421 and len(links)==517 and len(boundary)==339
           and len(pressure["pressure_boundary_doors"])==339,
           "pressure bulkhead identity/count broken")
    insist(len(tasks)==42 and len(policies)==83
           and len(manifest["doors"])==131,"unclassified ship access coverage changed")
    ids=[e["access_link_id"] for e in manifest["doors"]]
    insist(len(set(ids))==131,"duplicated unknown-environment access closure")
    rows={e["access_link_id"]:e for e in manifest["doors"]}
    actual={}
    for edge in links.values():
        a,b=spaces[edge["from"]]["pressure_zone"],spaces[edge["to"]]["pressure_zone"]
        if a==b:
            continue
        insist(edge.get("pressure_boundary") is True,
               "open cross-environment hatch: "+edge["id"])
        if a is None or b is None:
            insist((a is None) != (b is None),
                   "unknown-to-unknown transition must not be called a pressure boundary")
            # The other side is a known, pressurised gas cell (not known vacuum).
            known=b if a is None else a
            insist(known is not None and known!="VACUUM",
                   "unclassified hatch leads somewhere other than a protected cell")
            actual[edge["id"]]=edge
    insist(set(actual)==set(rows) and len(actual)==131,
           "unregistered or extra unclassified environmental boundary")
    insist(set(boundary)=={e["id"] for e in links.values() if e["pressure_boundary"]},
           "pressure register and world-rated hatch identities disagree")
    insist(pressure["totals"]["pressure_boundary_doors"]==339
           and pressure["pressure_access_closure"]["rated_pressure_boundaries_total"]==339
           and pressure["pressure_access_closure"]["unknown_environment_crossings_added"]==131,
           "updated environmental closure metrics inconsistent")
    by_role=Counter()
    by_kind=Counter()
    sector_doors=defaultdict(list)
    for id,record in rows.items():
        edge=actual[id]
        a,b=spaces[edge["from"]],spaces[edge["to"]]
        unknown=a if a["pressure_zone"] is None else b
        known=b if a["pressure_zone"] is None else a
        policy=policies[unknown["id"]]
        role=policy["environment_role"]
        insist(role in ENV_ROLES
               and policy["normal_breathability_unverified"] is True
               and policy["crew_unsuited_access_permitted_by_default"] is False,
               "unclassified cargo/industrial compartment mistakenly breathable")
        insist(record["from_space_id"]==edge["from"] and record["to_space_id"]==edge["to"]
               and record["known_pressure_zone_id"]==known["pressure_zone"]
               and record["unclassified_space_id"]==unknown["id"]
               and record["environment_role"]==role and record["door_kind"]==edge["kind"],
               "wrong environmental-interface physical endpoints")
        insist(edge["isolatable"] is True
               and edge["normal_state"]=="closed"
               and REQUIRED_RESTRICTIONS.issubset(set(edge.get("restrictions",[])))
               and any("v0.5 environmental boundary:" in n for n in edge.get("notes",[])),
               "known-to-unclassified hatch has no dependable containment doctrine")
        insist(record["nominal_design_differential_kPa"]==150
               and record["requires_local_pressure_sample"] is True
               and record["requires_local_atmosphere_sample"] is True
               and record["requires_positive_pressure_equalisation"] is True
               and record["requires_compatible_medium_or_sealed_transfer"] is True
               and record["permits_opening_solely_on_ppe"] is False
               and record["permitted_to_vent_protected_gallery_for_access"] is False
               and record["locked_default"] is True,
               "pressure hatch can be opened without containment proof")
        insist(record["maintenance_group_id"] in tasks,
               "maintainable pressure hatch has no assigned owner")
        obj=boundary[id]
        insist(obj["from_space_id"]==edge["from"] and obj["to_space_id"]==edge["to"]
               and obj["from_pressure_zone_id"]==a["pressure_zone"]
               and obj["to_pressure_zone_id"]==b["pressure_zone"]
               and obj["role"]=="rated_unknown_environment_containment"
               and obj["design_normal_state"]=="closed",
               "environment boundary not independently identified in pressure register")
        by_role[role]+=1
        by_kind[edge["kind"]]+=1
        if role=="manifest_dependent_cargo_sector":
            sector_doors[unknown["id"]].append(edge)
    insist(by_role==Counter({
        "manifest_dependent_cargo_sector":96,
        "commercial_cargo_portal":12,
        "bearing_service_annulus":12,
        "high_energy_industrial_plant":9,
        "unoccupied_shield_or_trim_bay":2,
    }),"incorrect quantity or classification of hazardous access closures")
    insist(by_kind==Counter({
        "cargo_service_door":48,
        "freight_handling_route":48,
        "cargo_portal_inner":12,
        "service_door":20,
        "service_hatch":2,
        "freight_door":1,
    }),"missing cargo-side or industrial threshold")
    insist(len(sector_doors)==48
           and all({x["kind"] for x in gates}==
                   {"cargo_service_door","freight_handling_route"}
                   and len(gates)==2 for gates in sector_doors.values()),
           "cargo sector has a bypass around protected personnel/freight hatches")
    rules=manifest["operating_rules"]
    insist(rules["opening_requires_local_pressure_differential_kPa_at_most"]==2
           and rules["nominal_max_differential_design_kPa"]==150
           and rules["suit_is_not_a_depressurisation_permit"] is True
           and rules["unknown_pressure_never_equal_to_room_pressure_without_observation"] is True,
           "PPE or uncertain pressure wrongly permits unknown-sector release")
    example=next(row for row in rows.values()
                 if row["environment_role"]=="manifest_dependent_cargo_sector")
    readings={"known_kPa":101,"receiving_kPa":101,
              "both_local_pressure_samples_verified":True,
              "local_chemistry_verified":True,
              "environment_compatible":True}
    control={"local_authority_and_access_permit":True,
             "gate_mechanically_verified":True,
             "all_other_sector_boundaries_shut":True,
             "sector_cargo_manifest_matched":True}
    insist(may_release(example,readings,control)==
           (True,"release_preconditions_proven"),
           "safe sector transfer cannot pass local release screen")
    for damaged,override in [
        ("pressure_drop",{"receiving_kPa":0}),
        ("pressure_unmeasured",{"both_local_pressure_samples_verified":False}),
        ("toxic_uncontained",{"environment_compatible":False}),
        ("chemistry_stale",{"local_chemistry_verified":False}),
    ]:
        altered=dict(readings,**override)
        insist(may_release(example,altered,control)[0] is False,
               "unsafe sector release accepted: "+damaged)

    # A forged generic "approved transfer" flag cannot make a direct hatch
    # into incompatible cargo atmosphere safe without an actual isolated cell.
    insist(may_release(example,
           dict(readings, environment_compatible=False),
           dict(control, approved_sealed_transfer=True))[0] is False,
           "nonexistent sealed-transfer volume accepted for direct hatch")
    for damaged,override in [
        ("remote_only",{"local_authority_and_access_permit":False}),
        ("other_sector_gate_open",{"all_other_sector_boundaries_shut":False}),
        ("manifest_uncertain",{"sector_cargo_manifest_matched":False}),
        ("mechanical_capture_fault",{"gate_mechanically_verified":False}),
    ]:
        altered=dict(control,**override)
        insist(may_release(example,readings,altered)[0] is False,
               "unsafe sector release accepted: "+damaged)
    return {"additional_rated_unknown_environment_boundaries":len(rows),
            "total_rated_boundaries":len(boundary),
            "previously_rated_boundaries":len(boundary)-len(rows),
            "cargo_sector_dual_entries":len(sector_doors),
            "unknown_spaces_remain_unverified":len(policies),
            "breathable_gas_credits_added":0}

def negative_tests(ship,pressure,gas,manifest):
    def reject(mutate):
        args=deepcopy((ship,pressure,gas,manifest))
        mutate(*args)
        try:
            validate(*args)
        except (ValueError,KeyError,TypeError,IndexError):
            return
        raise AssertionError("dangerous environmental transition mutation accepted")
    def edge(ship,id):
        return next(e for e in ship["access_links"] if e["id"]==id)
    def row(manifest,id):
        return next(e for e in manifest["doors"] if e["access_link_id"]==id)
    reject(lambda s,p,g,m: edge(s,"ACC-DR-01-SEC-01").update(pressure_boundary=False))
    reject(lambda s,p,g,m: edge(s,"ACC-DR-04-FREIGHT-SEC-06").update(isolatable=False))
    reject(lambda s,p,g,m: edge(s,"ACC-GEN-M-ROOM").update(pressure_boundary=False))
    reject(lambda s,p,g,m: edge(s,"ACC-DR-02-P2").update(normal_state="open"))
    reject(lambda s,p,g,m: edge(s,"ACC-BE-12-SVC").update(restrictions=[]))
    reject(lambda s,p,g,m: edge(s,"ACC-LOGI-AFT-PROP-SVC").update(pressure_boundary=False))
    reject(lambda s,p,g,m: row(m,"ACC-DR-01-SEC-01").update(permits_opening_solely_on_ppe=True))
    reject(lambda s,p,g,m: row(m,"ACC-DR-03-P1").update(maintenance_group_id="NO_SUCH_MAINTENANCE"))
    reject(lambda s,p,g,m: row(m,"ACC-DR-06-SEC-08").update(requires_positive_pressure_equalisation=False))
    reject(lambda s,p,g,m: m["doors"].pop())
    reject(lambda s,p,g,m: p["pressure_boundary_doors"].pop())
    reject(lambda s,p,g,m: next(e for e in g["unclassified_nonbreathable_by_default"]
           if e["space_id"]=="DR-05-SEC-06").update(crew_unsuited_access_permitted_by_default=True))
    reject(lambda s,p,g,m: m["operating_rules"].update(suit_is_not_a_depressurisation_permit=False))

if __name__=="__main__":
    inputs=[read(n) for n in (
        "ox_full_ship_v0.5_candidate.json",
        "pressure_zone_topology_v0.5.json",
        "pressure_gas_recovery_v0.5.json",
        "environmental_access_boundaries_v0.5.json")]
    print(json.dumps(validate(*inputs),indent=2,sort_keys=True))
    negative_tests(*inputs)
    print("OX_UNKNOWN_ENVIRONMENT_ACCESS_AND_THIRTEEN_NEGATIVE_TESTS_PASS")
