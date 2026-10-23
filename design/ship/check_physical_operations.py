#!/usr/bin/env python3
"""Validate ship v0.5 installed cargo-transfer, industrial waste and casualty states.

Mechanical design reference, not fabrication safety certification or runtime
world-state. Faulted measurements are not automatically true equipment state.
"""
from __future__ import annotations

from copy import deepcopy
from math import cos,hypot,isclose,pi,radians,sin
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE/name).read_text(encoding="utf-8"))


def insist(ok,message):
    if not ok:
        raise ValueError(message)


def unique(rows,label):
    keys=[r["id"] for r in rows]
    insist(len(set(keys))==len(keys), "duplicate "+label)
    return {r["id"]:r for r in rows}


def close(a,b,tolerance=1e-6):
    return isclose(a,b,rel_tol=0,abs_tol=tolerance)


def cyclic_gap(a,b):
    return abs((a-b+180)%360-180)


def validate(ship,model,mechanics):
    equip=unique(ship["equipment"],"installed equipment")
    spaces=unique(ship["spaces"],"spaces")
    tasks=unique(ship["maintenance_tasks"],"maintenance")
    inventory=unique(ship["inventories"],"inventories")
    access=unique(ship["access_links"],"access links")
    arc={x["id"]:x for x in mechanics["arcs"]}
    insist((len(equip),len(inventory),len(tasks),len(spaces),len(access))
           ==(808,15,42,421,517),"candidate equipment counts unexpectedly altered")
    insist(set(model["installed_transfer_equipment_ids"]) ==
           {f"DR-{i:02d}-{kind}" for i in range(1,7) for kind in
            ("PERSONNEL-INDEXER","FREIGHT-COLLAR")},
           "six full independent drum transfer pairs absent")
    for n in range(1,7):
        prefix=f"DR-{n:02d}"
        passenger=equip[prefix+"-PERSONNEL-INDEXER"]
        freight=equip[prefix+"-FREIGHT-COLLAR"]
        pa,fr=passenger["attributes"],freight["attributes"]
        fixed=spaces[prefix+"-SERVICE-LOCK"]
        lock=spaces[prefix+"-FREIGHT-LOCK"]
        crew_at=sum(fixed["location"]["x_m"])/2
        cargo_at=sum(lock["location"]["x_m"])/2
        require_gap=(
          pa["physical_moving_carrier_radial_envelope_m"][0]>=8.55
          and pa["physical_moving_carrier_radial_envelope_m"][1] <= 11.55
          and crew_at-cargo_at == 18
          and crew_at-2.5 >= cargo_at+6+9.5
        )
        insist(require_gap,"crew indexer collides axially with stopped freight station")
        insist(passenger["space_id"]==fixed["id"]
               and freight["space_id"]==lock["id"]
               and pa["nominal_occupants"]==2
               and pa["freight_station_axial_separation_m"]==18,
               "drum indexed carrier assigned to incorrect fixed station")
        insist(pa["requires_two_closing_boundaries"]
               and pa["must_not_move_with_fixed_or_rotating_collar_extended"]
               and pa["cargo_freight_collar_must_be_retracted"]
               and pa["requires_proven_phase_capture"]
               and pa["requires_pressure_equalisation"],
               "drum indexed transfer bypasses physical safety dependencies")
        insist(pa["pressure_end_access_link_ids"] ==
               [f"ACC-{prefix}-LOCK-FIX",f"ACC-{prefix}-LOCK-ROT"]
               and all(access[k]["pressure_boundary"]
                       and access[k]["isolatable"]
                       and access[k]["normal_state"]=="closed"
                       for k in pa["pressure_end_access_link_ids"]),
               "personnel pressure gates cannot isolate failed carriage")
        insist(fr["requires_drum_stopped"] and fr["requires_positive_hardlock"]
               and fr["prohibits_passenger_indexer_motion_when_extended"]
               and fr["requires_pressure_equalisation"],
               "moving freight collar incorrectly used while drum rotating")
        insist(fr["served_access_link_id"] == f"ACC-{prefix}-FREIGHT-CAPTURE"
               and access[fr["served_access_link_id"]]["pressure_boundary"],
               "indexed heavy freight transfer missing isolatable rated boundary")
        insist(fr["clear_internal_freight_lock_m"]==[12,4.6,4.6]
               and fr["full_sled_bounding_box_m"]==[3.8,3.4,8]
               and fr["routine_load_limit_t"]==50
               and fr["restricted_load_limit_t"]==100,
               "full sled/load no longer fits freight lock")
        insist(passenger["current_condition"] in ("serviceable","degraded")
               and freight["current_condition"] in ("serviceable","degraded")
               and passenger["onboard_maintainable"]
               and freight["onboard_maintainable"],
               "independent drum interfaces cannot be locally repaired")
    tt=ship["transit_contract"]["indexed_drum_personnel_transfer"]
    insist(tt["count"]==6
           and tt["selected_axial_offset_from_freight_station_m"]==18
           and tt["swept_collar_retract_before_freight_handling"]
           and tt["internal_moving_carrier_radial_envelope_m"]==[8.55,11.55],
           "drum-indexed cargo/crew transfer doctrine drift")
    disposal=ship["industrial_waste_and_recovery_contract"]
    insist(disposal["design_people"]==model["population_design_max"]==40
           and disposal["reference_days"]==model["reference_voyage_days"]==730,
           "waste design population/voyage changed")
    insist(close(disposal["normal_reference_industrial_scrap_kg_day"]*730/1000,
                 disposal["reference_industrial_scrap_t_730d"])
           and close(disposal["normal_reference_hazardous_solid_kg_day"]*730/1000,
                     disposal["reference_hazardous_solids_t_730d"]),
           "generated industrial/contaminated waste mass not conserved")
    bins={
      "IND-SCRAP-HOLD-A":(4,"SPARES-CENTRAL"),
      "IND-SCRAP-HOLD-B":(4,"MATERIAL-STOCK"),
      "HAZ-ISO-HOLD-A":(1,"PARTS-WASH"),
      "HAZ-ISO-HOLD-B":(1,"STORE-CRIT-SPARES"),
    }
    insist(set(bins)==set(model["hazardous_receivers"]+model["industrial_receivers"]),
           "industrial waste bins not physically separable")
    for id,(cap,room) in bins.items():
        e=equip[id];attrs=e["attributes"]
        insist(e["space_id"]==room
               and e["onboard_maintainable"] is True
               and attrs["capacity_t"]==cap
               and attrs["nominal_departure_fill_t"]==0
               and attrs["requires_inner_seal_closed_before_handling"]
               and attrs["requires_manifest_or_chemistry_classification"]
               and attrs["quarantine_if_unidentified"],
               "unsealed/overfilled industrial waste receiver: "+id)
        insist("hydrogen gas" in attrs["incompatible_with"]
               and "unprocessed blackwater" in attrs["incompatible_with"]
               and "general dry sanitary residue" in attrs["incompatible_with"],
               "dangerous waste mixing allowed: "+id)
    for suffix,capacity,equipment_ids in (
        ("INDUSTRIAL-SCRAP",8,disposal["industrial_bin_equipment_ids"]),
        ("HAZARDOUS-RESIDUE",2,disposal["hazardous_bin_equipment_ids"])):
        inv=inventory["INV-"+suffix]
        insist(inv["nominal_mass_t"]==0 and inv["capacity_t"]==capacity
               and inv["source_inventory_is_transformed_not_additional"] is True
               and sum(equip[k]["attributes"]["capacity_t"]
                       for k in equipment_ids)==capacity,
               "industrial waste destination has phantom capacity or departure mass")
    insist(sum(x["capacity_t"] for x in (
        inventory["INV-INDUSTRIAL-SCRAP"],
        inventory["INV-HAZARDOUS-RESIDUE"]))==10,
        "industrial/contaminated waste receiving capacities changed")
    insist(inventory["INV-WASTE-RESIDUE"]["capacity_t"]==16
           and disposal["independent_from_domestic_waste"]
           and disposal["mass_borrowed_from_departure_manifest_not_additional"]
           and disposal["reserve_stocks_not_a_disposal_sink"],
           "dry sanitary waste confused with hazardous/industrial storage")
    insist(disposal["reference_industrial_scrap_t_730d"] <= 8
           and disposal["reference_hazardous_solids_t_730d"] <= 2
           and "quarantine" in disposal["unknown_material_default"],
           "normal trash accounting assumes unbounded industrial waste disposal")
    # Angular/axial guards based on actual 38deg B-prime arcs and cradle locations.
    endpoints={x["id"]:x for x in mechanics["arcs"]}
    ports=model["hab_arc_ports"]
    insist(len(ports)==4 and
           set(p["equipment_id"] for p in ports)=={
             f"ECLSS-{a}-{medium}-VENT" for a in "AB" for medium in ("H2","CO2")},
           "missing segregated rotating byproduct outlet")
    envelope=model["pressure_head_guard"]
    insist(envelope["arc_radius_m"]==73.15
           and envelope["pressure_shell_guard_radius_m"]==77.92
           and envelope["sliding_outer_saddles_relative_deg"]==[-12,12]
           and envelope["end_heads_relative_deg"]==[-19,19],
           "wrong habitation B-prime physical keepout baseline")
    for port in ports:
        equipment=equip[port["equipment_id"]]
        attrs=equipment["attributes"]
        host=port["host_arc"]
        needhost=("HAB-06" if port["source_train"]=="A" else "HAB-08")
        center=endpoints[host]["theta_center_deg"]
        theta=port["theta_deg"]
        radius=port["radial_outlet_m"]
        delta=cyclic_gap(theta,center)
        insist(host==needhost
               and equipment["space_id"]==host+"-SERVICE-GALLERY"
               and attrs["gas"]==port["byproduct"]
               and 0 < delta < 19
               and radius==79.5,
               "waste gas port on incorrect or unsafe rotating arc")
        insist(cyclic_gap(theta,center)>=envelope["port_min_angular_clearance_from_saddle_deg"]
               and min(cyclic_gap(theta,center+s)
                       for s in envelope["sliding_outer_saddles_relative_deg"])
                       >=envelope["port_min_angular_clearance_from_saddle_deg"]
               and min(cyclic_gap(theta,center+s)
                       for s in envelope["end_heads_relative_deg"])
                       >=envelope["port_min_angular_clearance_from_end_deg"],
               "byproduct nozzle intersects head or support saddle zone")
        xyz=attrs["selected_reference_port_xyz"]
        insist(close(xyz["x_m"],port["axial_x_m"])
               and close(xyz["y_m"],radius*cos(radians(theta)),1e-5)
               and close(xyz["z_m"],radius*sin(radians(theta)),1e-5),
               "Bprime exterior vent coordinates disagree with rotating hull")
        keep=attrs["eva_clearance_and_jet_keepout_contract"]
        insist(keep["verified_as_installed"] is False
               and keep["release_requires_positive_local_surveillance"] is True
               and keep["keepout_radius_m"]>=3
               and keep["theta_deg"]==theta
               and attrs["normally_closed"] is True
               and port["purge_occupancy_interlocked"] is True
               and port["requires_external_reaction_force_attitude_compensation"] is True
               and close(port["nominal_exterior_nozzle_clearance_to_pressure_shell_guard_m"],
                         radius-envelope["pressure_shell_guard_radius_m"]),
               "outlet exposed crew to an unguarded plume")
        insist(not(441.1<=xyz["x_m"]<=448.9
                   or 461.1<=xyz["x_m"]<=468.9),
               "outlet axial plane clashes with passenger indexer station")
    # Explicitly record coupled and independently recoverable casualty consequences.
    cases=model["local_system_degraded_cases"]
    insist(len(cases)>=8
           and len({x["equipment_id"] for x in cases})==len(cases),
           "insufficient independent machinery casualty paths")
    for case in cases:
        insist(case["equipment_id"] in equip
               and len(case["evidence"])>=2
               and len(case["reset_requires"])>=2
               and case["physical_fault"] and case["result"],
               "degraded equipment has no local evidence/recovery path")
    all_covered={id for t in tasks.values() for id in t["equipment_ids"]}
    insist(all_covered == set(equip),"unowned installed machinery or waste cassette")
    for id in model["installed_transfer_equipment_ids"]:
        needed=("MT-INDEXED-ROTARY-TRANSFER" if id.endswith("-PERSONNEL-INDEXER")
                else "MT-CARGO-SERVICE")
        insist(id in tasks[needed]["equipment_ids"],"new transfer has no local maintenance owner")
    for id in bins:
        insist(id in tasks["MT-WATER-WASTE-PLANT"]["equipment_ids"],
               "new industrial receiver has no containment maintenance procedure")
    mass=ship["mass"]
    insist(mass["reference_departure_t"] ==
           mass["dry_t"]+mass["commercial_cargo_t"]+mass["FTL_fuel_t"]+
           mass["sublight_reaction_mass_t"]+mass["mission_and_nonpropulsive_fluids_t"],
           "installed machinery/waste bins double-counted against dry/departure mass")
    return {
      "installed_maintainable_equipment":len(equip),
      "independent_drum_personnel_indexers":6,
      "independent_drum_freight_collars":6,
      "physically_distinct_byproduct_port_keepouts":4,
      "dry_domestic_residue_capacity_t":16,
      "generated_industrial_scrap_capacity_t":8,
      "generated_hazardous_solid_capacity_t":2,
      "departure_generated_residue_t":0,
      "independent_degraded_cases":len(cases),
      "all_equipment_maintained":True,
    }


def negative_tests(ship,model,mechanics):
    def bad(change):
        s,m,p=deepcopy((ship,model,mechanics))
        change(s,m,p)
        try:
            validate(s,m,p)
        except (ValueError,KeyError,TypeError):
            return
        raise AssertionError("invalid ship cargo/industrial/vent model accepted")
    def equip(s,id):
        return next(x for x in s["equipment"] if x["id"]==id)
    def inv(s,id):
        return next(x for x in s["inventories"] if x["id"]==id)
    def port(m,id):
        return next(x for x in m["hab_arc_ports"] if x["equipment_id"]==id)
    bad(lambda s,m,p: equip(s,"DR-01-PERSONNEL-INDEXER")["attributes"].update(
        must_not_move_with_fixed_or_rotating_collar_extended=False))
    bad(lambda s,m,p: equip(s,"DR-02-FREIGHT-COLLAR")["attributes"].update(
        requires_drum_stopped=False))
    bad(lambda s,m,p: equip(s,"DR-03-FREIGHT-COLLAR")["attributes"].update(
        restricted_load_limit_t=150))
    bad(lambda s,m,p: next(x for x in s["spaces"] if x["id"]=="DR-04-SERVICE-LOCK")
        ["location"].update(x_m=[610,615]))
    bad(lambda s,m,p: equip(s,"DR-05-PERSONNEL-INDEXER")["attributes"].update(
        pressure_end_access_link_ids=[]))
    bad(lambda s,m,p: equip(s,"HAZ-ISO-HOLD-B")["attributes"].update(
        nominal_departure_fill_t=1))
    bad(lambda s,m,p: equip(s,"IND-SCRAP-HOLD-A")["attributes"].update(
        capacity_t=2))
    bad(lambda s,m,p: inv(s,"INV-HAZARDOUS-RESIDUE").update(capacity_t=200))
    bad(lambda s,m,p: inv(s,"INV-INDUSTRIAL-SCRAP").update(nominal_mass_t=2))
    bad(lambda s,m,p: s["industrial_waste_and_recovery_contract"].update(
        reference_hazardous_solids_t_730d=99))
    bad(lambda s,m,p: equip(s,"HAZ-ISO-HOLD-A")["attributes"].update(
        incompatible_with=[]))
    bad(lambda s,m,p: port(m,"ECLSS-A-H2-VENT").update(theta_deg=244))
    bad(lambda s,m,p: equip(s,"ECLSS-B-CO2-VENT")["attributes"]
        ["eva_clearance_and_jet_keepout_contract"].update(verified_as_installed=True))
    bad(lambda s,m,p: port(m,"ECLSS-B-H2-VENT").update(radial_outlet_m=76))
    bad(lambda s,m,p: s["maintenance_tasks"][0]["equipment_ids"].append("INVENTED_ID"))
    bad(lambda s,m,p: m["local_system_degraded_cases"][0].update(evidence=[]))


if __name__=="__main__":
    world=read("ox_full_ship_v0.5_candidate.json")
    model=read("machinery_and_disposal_closure_v0.5.json")
    mechanical=read("hab_bprime_mechanical_interfaces_v0.5.json")
    print(json.dumps(validate(world,model,mechanical),indent=2,sort_keys=True))
    negative_tests(world,model,mechanical)
    print("OX_MACHINERY_AND_DISPOSAL_WITH_SIXTEEN_NEGATIVE_TESTS_PASS")
