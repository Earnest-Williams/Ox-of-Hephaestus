#!/usr/bin/env python3
"""Verify 40-person/730-day waste and byproduct *physical* route consequences.

No Evennia or external package is required. A potential isolated route is
not a command to open a valve, permission for an unsuited worker, or proof that
a receiver has enough remaining usable capacity.
"""
from __future__ import annotations
from collections import defaultdict, deque
from copy import deepcopy
import json
from math import isclose
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load(name):
    return json.loads((HERE/name).read_text(encoding="utf-8"))

def must(ok, why):
    if not ok:
        raise ValueError(why)

def keyed(rows,label):
    ids=[r["id"] for r in rows]
    must(len(ids)==len(set(ids)),label+" duplicate identity")
    return {r["id"]:r for r in rows}

def reach(ship, network, start, excluding=frozenset()):
    graph=defaultdict(set)
    for edge in ship["service_edges"]:
        if edge["network"]!=network or edge["id"] in excluding:
            continue
        graph[edge["from_node"]].add(edge["to_node"])
        graph[edge["to_node"]].add(edge["from_node"])
    queue=deque([start])
    visited={start}
    while queue:
        for other in graph[queue.popleft()]:
            if other not in visited:
                visited.add(other)
                queue.append(other)
    return visited

def validate(ship):
    equip=keyed(ship["equipment"],"equipment")
    spaces=keyed(ship["spaces"],"spaces")
    node=keyed(ship["service_nodes"],"service nodes")
    edges=keyed(ship["service_edges"],"service edges")
    iso=keyed(ship["isolation_points"],"isolations")
    inventory=keyed(ship["inventories"],"inventory")
    nets=keyed(ship["networks"],"networks")
    must((len(equip),len(node),len(edges),len(iso),len(inventory))==
         (786,1180,1176,1251,11),"unexpected physical model counts")
    must("byproduct_exhaust" in nets,"missing distinct external gas discharge service")
    must(sum(x["network"]=="byproduct_exhaust" for x in node.values())==8
         and sum(x["network"]=="byproduct_exhaust" for x in edges.values())==4
         and sum(x["network"]=="byproduct_exhaust" for x in iso.values())==8,
         "byproduct vent graph counts wrong")
    must(sum(x["id"].startswith("EDGE-WET-") for x in edges.values())==4,
         "wet rotor receiver connections not distinct")
    physical=ship["life_support_contract"]
    waste=physical["byproduct_handling"]
    must(physical["protected_people_per_train"]==40
         and waste["reference_people"]==40 and waste["days"]==730,
         "life-support design population changed")
    must(isclose(waste["hydrogen_kg_day_at_35_6kg_O2"],
                 physical["oxygen_kg_person_day"]*40/8,abs_tol=1e-8),
         "electrolysis hydrogen mass is not conserved")
    must(isclose(waste["hydrogen_t_730d_if_vented"],
                 waste["hydrogen_kg_day_at_35_6kg_O2"]*730/1000,abs_tol=1e-8),
         "hydrogen voyage mass fails")
    must(isclose(waste["carbon_dioxide_kg_day"],
                 physical["CO2_kg_person_day"]*40,abs_tol=1e-8)
         and isclose(waste["carbon_dioxide_t_730d_if_vented"],
                     waste["carbon_dioxide_kg_day"]*730/1000,abs_tol=1e-8),
         "CO2 voyage mass fails")
    vent_ids=[]
    for side in "AB":
        arc="HAB-06" if side=="A" else "HAB-08"
        process=f"{arc}-ECLSS-{side}"
        gallery=f"{arc}-SERVICE-GALLERY"
        processor=equip[f"WASTE-PROC-{side}"]["attributes"]
        must(processor["design_served_people"]==40
             and processor["greywater_capacity_L_day"]>=1000
             and processor["blackwater_capacity_L_day"]>=80
             and processor["local_greywater_buffer_L"]>0
             and processor["local_blackwater_buffer_L"]>0
             and processor["residual_solids_are_not_destroyed"],
             "waste processor missing real flow/solid-consequence capacity")
        for medium in ("H2","CO2"):
            v=f"ECLSS-{side}-{medium}-VENT"
            source=f"ECLSS-{side}-O2-GEN" if medium=="H2" else f"ECLSS-{side}-CO2-REGEN"
            valve_in=f"ISO-BYP-{side}-{medium}-SOURCE"
            valve_out=f"ISO-BYP-{side}-{medium}-HULL"
            e=edges[f"EDGE-BYP-{side}-{medium}"]
            a=equip[v]["attributes"]
            must(equip[v]["space_id"]==gallery and
                 a["gas"]==medium and
                 a["source_equipment_id"]==source and
                 a["host_train_id"]==f"ECLSS-{side}" and
                 a["discharge_mode"].find("vacuum exterior")!=-1,
                 "vacuum vent not attached to its own active ECLSS source")
            must(e["network"]=="byproduct_exhaust"
                 and e["from_node"]==f"NODE-BYP-{side}-{medium}-SOURCE"
                 and e["to_node"]==f"NODE-BYP-{side}-{medium}-EXTERIOR"
                 and e["route_spaces"]==[process,gallery]
                 and set(e["isolator_ids"])=={valve_in,valve_out},
                 "vent line cross-connected or wrongly routed")
            must(node[e["from_node"]]["owner_id"]==source
                 and node[e["to_node"]]["owner_id"]==v,
                 "exhaust source or exterior receiver points to wrong hardware")
            must(all(iso[key]["normal_state"]=="closed"
                     and iso[key]["current_state"]=="closed"
                     for key in (valve_in,valve_out)),
                 "uncontrolled open hull exhaust at rest")
            must(iso[valve_in]["space_id"]==process
                 and iso[valve_out]["space_id"]==gallery,
                 "process/hull valves not separately locally serviceable")
            must(a["temporary_receiver_capacity_kg"]>0
                 and a["temporary_receiver_capacity_kg"]<=50
                 and a["normally_closed"]
                 and a["port_as_installed_survey"] and
                 a["manual_local_isolation"],
                 "external discharge implied unbounded or unserviceable")
            must(a["nominal_rate_capacity_kg_day"] >= (
                    physical["normal_oxygen_generation"]["oxygen_capacity_kg_day_each"]/8
                    if medium=="H2" else
                    physical["normal_CO2_removal"]["CO2_capacity_kg_day_each"]),
                 "a complete 40-person train cannot safely reject its byproduct")
            must(set(reach(ship,"byproduct_exhaust",e["from_node"])) ==
                 {e["from_node"],e["to_node"]},
                 "two physically incompatible gases share an exhaust line")
            vent_ids.append(v)
        for medium, prefix, qty in (
            ("greywater","GREYWATER",1100),
            ("blackwater","BLACKWATER",120),
        ):
            edgeid=f"EDGE-WET-{prefix}-{side}-ROTARY"
            e=edges[edgeid]
            a=equip[f"ROT-{prefix}-{side}"]["attributes"]
            fixed=f"ROTARY-UTIL-{side}"
            valveF=f"ISO-WET-{prefix}-{side}-FIXED"
            valveR=f"ISO-WET-{prefix}-{side}-ROTOR"
            must(e["network"]==medium and
                 e["from_node"]==f"NODE-ROT-{prefix}-{side}" and
                 e["to_node"]==f"NODE-{arc}-{prefix}-MAN" and
                 e["route_spaces"]==[fixed,gallery] and
                 set(e["isolator_ids"])=={valveF,valveR} and
                 e["capacity"]["L_day"]>=qty,
                 "wet receiver manifold never physically reaches its rotary union")
            must(iso[valveF]["space_id"]==fixed
                 and iso[valveR]["space_id"]==gallery
                 and iso[valveF]["normal_state"]=="closed"
                 and iso[valveR]["normal_state"]=="closed"
                 and a["crossing_edge_id"]==edgeid,
                 "wet rotary receiver double isolation lost")
    must(len(set(vent_ids))==4 and
         set(vent_ids)==set(waste["vent_equipment_ids"]),
         "byproduct reference and installed vents differ")
    for medium,prefix,hold in (
        ("greywater","GREYWATER","NODE-FIXED-GREY-HOLD"),
        ("blackwater","BLACKWATER","NODE-FIXED-BLACK-HOLD"),
    ):
        a=f"EDGE-WET-{prefix}-A-ROTARY"
        b=f"EDGE-WET-{prefix}-B-ROTARY"
        for n in range(1,9):
            start=f"NODE-HAB-{n:02d}-{prefix}-MAN"
            potential=reach(ship,medium,start)
            must(hold in potential
                 and f"NODE-WASTE-PROC-A-{prefix}" in potential
                 and f"NODE-WASTE-PROC-B-{prefix}" in potential,
                 "hab wet flow not able to use either processor and fixed hold")
            must(hold in reach(ship,medium,start,{a})
                 and hold in reach(ship,medium,start,{b}),
                 "one lost rotary wet crossing should still reach fixed receiver")
            must(hold not in reach(ship,medium,start,{a,b}),
                 "fixed waste receiver mysteriously reached with both unions isolated")
    grey=equip["FIXED-GREY-HOLD"]["attributes"]
    black=equip["FIXED-BLACK-HOLD"]["attributes"]
    must(grey["working_capacity_m3"]==10 and
         black["working_capacity_m3"]==2 and
         grey["reference_greywater_L_day"]==800 and
         black["reference_blackwater_L_day"]==80,
         "finite short-isolation receiver capacities lost")
    generated=inventory["INV-WASTE-RESIDUE"]
    bins=[equip[f"WASTE-RESIDUE-HOLD-{k}"] for k in "AB"]
    must(all(x["space_id"]=="STORE-FLUID-AFT"
             and x["attributes"]["nominal_departure_fill_t"]==0
             for x in bins),
         "dry waste receiver location/departure status unproven")
    capacity=sum(x["attributes"]["capacity_t"] for x in bins)
    must(isclose(capacity,generated["capacity_t"],abs_tol=1e-8)
         and capacity>=waste["solid_sanitary_residue_t_730d_screen"]
         and generated["nominal_mass_t"]==0
         and generated["source_inventory_is_transformed_not_additional"] is True
         and waste["storage_mass_not_additional_departure_mass"] is True,
         "generated waste double counted or receiver physically undersized")
    maintenance=set(x for t in ship["maintenance_tasks"] for x in t["equipment_ids"])
    must(maintenance==set(equip),"installed byproduct equipment unmaintainable")
    return {
       "separate_byproduct_exhausts":4,
       "isolated_gas_vent_valves":8,
       "new_double_isolated_wet_rotary_paths":4,
       "new_wet_rotary_valves":8,
       "generated_solid_residue_storage_capacity_t":capacity,
       "one_rotary_connection_lost":"ALTERNATE_ROUTE_PASS",
       "both_rotary_connections_lost":"FIXED_RECEIVER_UNAVAILABLE_PASS",
       "voyage_reference_kg_hydrogen":round(waste["hydrogen_t_730d_if_vented"]*1000,2),
       "voyage_reference_kg_CO2":round(waste["carbon_dioxide_t_730d_if_vented"]*1000,2)
    }

def negative_tests(ship):
    def reject(mut):
        wrong=deepcopy(ship)
        mut(wrong)
        try:
            validate(wrong)
        except (ValueError,KeyError):
            return
        raise AssertionError("expected damaged waste/byproduct model to fail")
    reject(lambda s: next(e for e in s["service_edges"]
           if e["id"]=="EDGE-BYP-A-H2").update(to_node="NODE-BYP-A-CO2-EXTERIOR"))
    reject(lambda s: next(e for e in s["isolation_points"]
           if e["id"]=="ISO-BYP-B-H2-HULL").update(normal_state="open"))
    reject(lambda s: next(e for e in s["equipment"]
           if e["id"]=="ECLSS-A-CO2-VENT")["attributes"].update(nominal_rate_capacity_kg_day=1))
    reject(lambda s: next(e for e in s["equipment"]
           if e["id"]=="ECLSS-B-H2-VENT")["attributes"].update(temporary_receiver_capacity_kg=999999))
    reject(lambda s: s["service_edges"].remove(next(e for e in s["service_edges"]
           if e["id"]=="EDGE-WET-GREYWATER-A-ROTARY")))
    reject(lambda s: next(e for e in s["isolation_points"]
           if e["id"]=="ISO-WET-BLACKWATER-B-FIXED").update(space_id="HAB-08-COR"))
    reject(lambda s: next(e for e in s["equipment"]
           if e["id"]=="WASTE-RESIDUE-HOLD-A")["attributes"].update(capacity_t=0.1))
    reject(lambda s: next(e for e in s["inventories"]
           if e["id"]=="INV-WASTE-RESIDUE").update(nominal_mass_t=7.3))

if __name__=="__main__":
    ship=load("ox_full_ship_v0.5_candidate.json")
    print(json.dumps(validate(ship),indent=2,sort_keys=True))
    negative_tests(ship)
    print("OX_WASTE_BYPRODUCT_AND_EIGHT_NEGATIVE_TESTS_PASS")
