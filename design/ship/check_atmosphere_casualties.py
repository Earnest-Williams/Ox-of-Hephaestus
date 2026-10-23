#!/usr/bin/env python3
"""Design-reference gas casualty accounting; no live atmosphere/actuator authority."""
from __future__ import annotations
from copy import deepcopy
import json
from math import isclose, isfinite
from pathlib import Path

HERE=Path(__file__).resolve().parent

def read(name):
    return json.loads((HERE/name).read_text(encoding="utf-8"))

def require(value, message):
    if not value:
        raise ValueError(message)

def evaluate(gas, zone_id, lost_fraction, available_bank_ids, route_proven,
             leak_repaired, receiver_verified, max_flow_kg_h=None):
    rows={r["pressure_zone_id"]:r for r in gas["sized_and_unsized_pressure_cells"]}
    require(zone_id in rows,"unregistered pressure cell")
    row=rows[zone_id]
    require(isinstance(lost_fraction,(int,float)) and not isinstance(lost_fraction,bool)
            and isfinite(lost_fraction) and 0<=lost_fraction<=1,
            "nonphysical atmosphere lost fraction")
    require(row["verified_as_installed_free_gas_m3"] is None,
            "planning ledger cannot represent live measured compartment")
    require(row["reference_gas_mass_lower_kg"] is not None,
            "unsized cell cannot receive numerical refill estimate")
    banks={b["inventory_id"]:b["mass_t"]*1000 for b in gas["reserve_gas"]["banks"]}
    require(isinstance(available_bank_ids,(tuple,list,set)) and
            len(set(available_bank_ids))==len(available_bank_ids) and
            set(available_bank_ids)<=set(banks),"invalid/double credited gas banks")
    require(all(isinstance(v,bool) for v in
                (route_proven,leak_repaired,receiver_verified)),
            "unverified casualty precondition")
    max_flow=gas["reserve_gas"]["maximum_simultaneous_controlled_flow_kg_h_from_two_banks"]
    flow=max_flow if max_flow_kg_h is None else max_flow_kg_h
    require(isinstance(flow,(int,float)) and not isinstance(flow,bool)
            and isfinite(flow) and 0<flow<=max_flow,
            "invalid/magically increased flow allowance")
    required_lower=row["reference_gas_mass_lower_kg"]*lost_fraction
    required_upper=row["reference_gas_mass_upper_kg"]*lost_fraction
    available=sum(banks[x] for x in available_bank_ids)
    allowed=route_proven and leak_repaired and receiver_verified
    return {
        "zone_id":zone_id,
        "lost_fraction":lost_fraction,
        "required_lower_kg":round(required_lower,3),
        "required_upper_kg":round(required_upper,3),
        "available_reserve_kg":round(available,3),
        "reserve_covers_upper_reference":available>=required_upper,
        "reserve_covers_lower_reference":available>=required_lower,
        "minimum_flow_time_lower_h":round(required_lower/flow,3),
        "minimum_flow_time_upper_h":round(required_upper/flow,3),
        "authorised_to_start_refill":allowed and available>=required_upper,
        "gas_exhausted_kg_if_upper_reference":round(min(available,required_upper),3)
            if allowed else 0,
        "remaining_reserve_kg_if_upper_reference":
            round(max(0,available-required_upper),3) if allowed and available>=required_upper else None,
        "limitations":"reference estimate, not live pressure, actual cell free volume, leak rate, route control or executable permission",
    }

def validate(gas):
    banks=[b["inventory_id"] for b in gas["reserve_gas"]["banks"]]
    require(len(banks)==2 and len(set(banks))==2 and
            isclose(sum(b["mass_t"] for b in gas["reserve_gas"]["banks"]),5.5),
            "reserve stock not two independent 2.75 t banks")
    hab="PZ-HAB-03"
    scenarios={
        "one_arc_both_banks":evaluate(gas,hab,1,banks,True,True,True),
        "one_arc_single_bank":evaluate(gas,hab,1,banks[:1],True,True,True),
        "one_arc_unrepaired_leak":evaluate(gas,hab,1,banks,True,False,True),
        "one_arc_no_verified_route":evaluate(gas,hab,1,banks,False,True,True),
        "one_arc_receiver_unverified":evaluate(gas,hab,1,banks,True,True,False),
        "two_arcs_sequential":None,
    }
    first=scenarios["one_arc_both_banks"]
    next_arc=evaluate(gas,"PZ-HAB-07",1,banks,True,True,True)
    scenarios["two_arcs_sequential"]={
        "combined_lower_kg":round(first["required_lower_kg"]+next_arc["required_lower_kg"],3),
        "combined_upper_kg":round(first["required_upper_kg"]+next_arc["required_upper_kg"],3),
        "combined_fits_reserve_lower":first["required_lower_kg"]+next_arc["required_lower_kg"]<=5500,
        "note":"Sequential refill does not recreate gas. Actual loss and valve supply must be measured.",
    }
    require(first["authorised_to_start_refill"] and first["reserve_covers_upper_reference"],
            "two banks cannot refill one selected reference arc")
    require(15<first["minimum_flow_time_lower_h"]<19 and
            15<first["minimum_flow_time_upper_h"]<19,
            "nominal maximum refill flow/time inconsistent")
    require(not scenarios["one_arc_single_bank"]["reserve_covers_lower_reference"],
            "one bank unexpectedly covers a fully lost reference arc")
    require(all(not scenarios[x]["authorised_to_start_refill"] and
                scenarios[x]["gas_exhausted_kg_if_upper_reference"]==0
                for x in ("one_arc_unrepaired_leak",
                          "one_arc_no_verified_route","one_arc_receiver_unverified")),
            "unsafe refill allowed without complete casualty proof")
    require(not scenarios["two_arcs_sequential"]["combined_fits_reserve_lower"],
            "two whole habitation arcs unexpectedly refilled from 5.5 t")
    require(gas["totals"]["sized_pressure_cells"]==133
            and gas["totals"]["unsized_pressurized_cells"]==0,
            "incomplete nominal cell envelope")
    return scenarios

def negative_tests(gas):
    banks=[b["inventory_id"] for b in gas["reserve_gas"]["banks"]]
    bad_cases=[
        lambda: evaluate(gas,"PZ-HAB-03",1.1,banks,True,True,True),
        lambda: evaluate(gas,"PZ-HAB-03",-0.1,banks,True,True,True),
        lambda: evaluate(gas,"PZ-HAB-03",float("nan"),banks,True,True,True),
        lambda: evaluate(gas,"PZ-HAB-03",1,banks+banks[:1],True,True,True),
        lambda: evaluate(gas,"PZ-HAB-03",1,["INV-GAS-BOGUS"],True,True,True),
        lambda: evaluate(gas,"PZ-HAB-03",1,banks,True,True,True,400),
        lambda: evaluate(gas,"PZ-HAB-03",1,banks,True,True,True,0),
        lambda: evaluate(gas,"PZ-HAB-03",1,banks,1,True,True),
        lambda: evaluate(gas,"PZ-MISSING",1,banks,True,True,True),
    ]
    for i, bad in enumerate(bad_cases,1):
        try:
            bad()
        except (ValueError,KeyError,TypeError):
            continue
        raise AssertionError(f"casualty negative test {i} incorrectly accepted")
    false_measure=deepcopy(gas)
    next(r for r in false_measure["sized_and_unsized_pressure_cells"]
         if r["pressure_zone_id"]=="PZ-HAB-03")["verified_as_installed_free_gas_m3"]=10
    try:
        evaluate(false_measure,"PZ-HAB-03",1,banks,True,True,True)
    except ValueError:
        pass
    else:
        raise AssertionError("fabricated measurement accepted")

if __name__=="__main__":
    data=read("pressure_gas_recovery_v0.5.json")
    print(json.dumps(validate(data),indent=2,sort_keys=True))
    negative_tests(data)
    print("OX_GAS_CASUALTY_REFERENCE_AND_TEN_NEGATIVE_TESTS_PASS")
