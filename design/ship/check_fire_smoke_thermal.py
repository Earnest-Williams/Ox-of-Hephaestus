#!/usr/bin/env python3
"""Real Ox ship fire/smoke/ventilation/cooling casualty and mutation tests.

Run: python design/ship/check_fire_smoke_thermal.py
No world mutation, Evennia state, handler cognition or live machinery commands.
"""
from __future__ import annotations

from copy import deepcopy
from math import isclose

from fire_smoke_thermal_v05 import (
    FireSmokeThermalTrial, new_trial, load_model, read_ship,
)

import json


def insist(condition, reason):
    if not condition:
        raise AssertionError(reason)


def hab_fire(trial, *, hazard="ordinary_combustible"):
    trial.ignite("F-HAB-03", "PZ-HAB-03", fuel_kg=100.0,
                 burn_kg_s=0.08, smoke_yield_fraction=0.30,
                 hazard=hazard)


def run_reference_tests():
    report = {}
    cold = new_trial()
    insist(len(cold.cells) == 133 and len(cold.gates) == 339
           and len(cold.unknown_gate_ids) == 131, "pressure register altered")
    insist(tuple(len(cold.edges[n]) for n in
                 ("atmosphere", "fire_main", "lt_cooling")) ==
           (213, 73, 79), "service network not original v0.5")
    insist(isclose(cold._total_cooling_MW(), 3.75),
           "radiator contract changed")
    insist(all(g.state == "closed" for g in cold.gates.values()),
           "cold reference trial invents open access hatches")
    insist(cold.mass_balance_error_kg() < 1e-5,
           "initial design gas ledger invalid")
    report["ship_interfaces"] = {
        "pressure_cells": 133, "rated_boundaries": 339,
        "unclassified_environment_thresholds": 131,
        "atmosphere_ducts": 213, "fire_main_edges": 73,
        "low_temperature_cooling_edges": 79,
    }

    # Design reference oxygen and fire fuel must be finite. Carbon products
    # join the actual gas ledger; atmospheric O2 is chemically consumed.
    burning = new_trial()
    burning.set_crew("PZ-HAB-03", 3)
    burning.command_cooling(False, local_authority=True)
    original_o2 = burning.cells["PZ-HAB-03"].oxygen_kg
    original_mass = burning.cells["PZ-HAB-03"].gas_kg
    hab_fire(burning)
    burning.advance(140)
    fire = burning.fires["F-HAB-03"]
    insist(0 < fire.consumed_fuel_kg < 100 and
           isclose(fire.consumed_fuel_kg + fire.remaining_fuel_kg,
                   100, abs_tol=1e-6),
           "finite physical combustion fuel lost")
    insist(burning.cells["PZ-HAB-03"].oxygen_kg < original_o2 - 10,
           "fire did not consume real finite oxygen")
    insist(burning.cells["PZ-HAB-03"].gas_kg > original_mass,
           "gas species/combustion carbon source not recorded")
    insist(burning.cells["PZ-HAB-03"].temperature_K > 296.0
           and burning.cells["PZ-HAB-03"].pressure_kpa > 101.5,
           "fire heat does not couple into actual reference pressure")
    insist(burning.cells["PZ-HAB-03"].crew_unsafe_seconds > 0,
           "smoke/heat/oxygen consequences do not affect crew exposure")
    insist(burning.mass_balance_error_kg() < 1e-5,
           "combustion created gas from nowhere")
    report["fire_and_crew"] = burning.fire_summary(
        ["PZ-HAB-03", "PZ-HAB-04"])

    # Every physical HAB pressure gate stays shut. The intact separate
    # ventilation ducts nevertheless move smoke into HAB-04, unless their
    # real dampers are shut early.
    circulating = new_trial()
    isolated = new_trial()
    delayed = new_trial()
    for trial in (circulating, isolated, delayed):
        hab_fire(trial)
    early = isolated.isolate_ventilation("PZ-HAB-03",
                                         local_authority=True)
    insist(early["closed"] and not early["failed"],
           "healthy HAB-03 ventilation dampers did not isolate")
    insist(isolated._firewater_reaches("PZ-HAB-03")
           and isolated._connected_to_cooling("PZ-HAB-03"),
           "closing ventilation incorrectly also closes fire main or LT cooling")
    circulating.advance(360)
    isolated.advance(360)
    delayed.advance(140)
    delayed.isolate_ventilation("PZ-HAB-03", local_authority=True)
    delayed.advance(220)
    smoke_open = circulating.cells["PZ-HAB-04"].trace_kg
    smoke_late = delayed.cells["PZ-HAB-04"].trace_kg
    smoke_shut = isolated.cells["PZ-HAB-04"].trace_kg
    insist(smoke_open > smoke_late > smoke_shut + 1e-5,
           "timed duct isolation does not change neighboring smoke exposure")
    insist(smoke_shut < 1e-7 and
           isolated.cells["PZ-HAB-03"].trace_kg >
           circulating.cells["PZ-HAB-03"].trace_kg,
           "isolated ventilation fails to retain smoke in the affected arc")
    insist(not circulating.cells["PZ-HAB-04"].modeled_unsuited_air_safe(),
           "smoky adjoining HAB incorrectly treated breathable")
    insist(all(t.mass_balance_error_kg() < 1e-5
               for t in (circulating, isolated, delayed)),
           "smoke ventilation manufactured carbon/air")
    report["ventilation_vs_pressure_hatches"] = {
        "physical_access_hatches_all_closed": True,
        "HAB04_smoke_kg_unisolated": round(smoke_open, 5),
        "HAB04_smoke_kg_isolated_140s": round(smoke_late, 5),
        "HAB04_smoke_kg_isolated_0s": round(smoke_shut, 5),
    }

    # A single failed-open damper can be defeated by closing the other
    # end. Two independently stuck-open dampers on the BR-03 duct defeat
    # the local isolation effort and restore contamination propagation.
    one_stuck = new_trial()
    both_stuck = new_trial()
    for trial in (one_stuck, both_stuck):
        hab_fire(trial)
        trial.fail_valve("atmosphere", "ISO-AIR-BR-03-HAB-03", "open")
    both_stuck.fail_valve("atmosphere", "ISO-AIR-BR-03-HAB-04", "open")
    one_report = one_stuck.isolate_ventilation(
        "PZ-HAB-03", local_authority=True)
    both_report = both_stuck.isolate_ventilation(
        "PZ-HAB-03", local_authority=True)
    insist(len(one_report["failed"]) == 1 and len(both_report["failed"]) == 2,
           "faulted independent dampers not explicitly reported")
    one_stuck.advance(240)
    both_stuck.advance(240)
    insist(one_stuck.cells["PZ-HAB-04"].trace_kg < 1e-7
           and both_stuck.cells["PZ-HAB-04"].trace_kg > 1e-5,
           "two-sided bridge damper redundancy has no physical effect")
    report["two_end_damper_casualty"] = {
        "single_jam_contained": True,
        "both_end_jam_spreads_smoke": True,
    }

    # A fire hatch isn't opened by an ECLSS configuration change, and a
    # healthy duct across a SHUT pressure hatch can also carry depressurizing
    # flow. Only real damper isolation arrests that bypass path.
    open_duct = new_trial()
    shut_duct = new_trial()
    shut_duct.isolate_ventilation("PZ-HAB-03", local_authority=True)
    for trial in (open_duct, shut_duct):
        trial.breach("HAB-03-LEAK", "PZ-HAB-03", 7)
        trial.advance(180)
    insist(open_duct.cells["PZ-HAB-04"].pressure_kpa <
           shut_duct.cells["PZ-HAB-04"].pressure_kpa - 0.001,
           "shut pressure door wrongly seals independently open HVAC duct")
    insist(isclose(shut_duct.cells["PZ-HAB-04"].pressure_kpa, 101.325,
                   abs_tol=1e-5),
           "ventilation isolation leaked into a closed unaffected HAB")
    report["duct_pressure_bypass"] = {
        "unisolated_HAB04_kPa": round(
            open_duct.cells["PZ-HAB-04"].pressure_kpa, 5),
        "isolated_HAB04_kPa": round(
            shut_duct.cells["PZ-HAB-04"].pressure_kpa, 5),
    }

    # Two independent connected ECLSS trains, actual damper topology,
    # finite filter allocation; no scrubber works through a blocked duct
    # or an unpowered fan.
    filtered = new_trial(filters_kg=0.4)
    blocked = new_trial(filters_kg=0.4)
    for trial in (filtered, blocked):
        hab_fire(trial)
        trial.configure_smoke_cleanup(True, local_authority=True)
    blocked.isolate_ventilation("PZ-HAB-03", local_authority=True)
    filtered.advance(300)
    blocked.advance(300)
    insist(filtered.captured_smoke_kg > 0.0
           and filtered.captured_smoke_kg <= 0.40000001
           and isclose(filtered.filter_available_kg
                       + filtered.captured_smoke_kg, 0.4, abs_tol=1e-7),
           "smoke cleanup consumes fictitious/infinite filters")
    insist(blocked.captured_smoke_kg <
           filtered.captured_smoke_kg - 1e-5,
           "closed ducts allow remote processor to clean isolated HAB-03")
    fanless = new_trial(filters_kg=0.4)
    hab_fire(fanless)
    fanless.configure_smoke_cleanup(True, local_authority=True)
    fanless.configure_fan(False, local_authority=True)
    fanless.advance(180)
    insist(isclose(fanless.captured_smoke_kg, 0, abs_tol=1e-7),
           "disabled circulation magically powers remote smoke scrubber")
    report["finite_filtration"] = {
        "connected_filters_captured_kg": round(filtered.captured_smoke_kg, 5),
        "isolated_filters_captured_kg": round(blocked.captured_smoke_kg, 5),
        "disabled_fan_capture_kg": round(fanless.captured_smoke_kg, 5),
    }

    # Fire suppression needs a REAL route across source pumps, two rotary
    # interfaces, and the sector valve. Mist water comes from a finite
    # allocation within normal voyage water, never a new mass source.
    wet = new_trial(water_kg=22)
    dry = new_trial(water_kg=22)
    for trial in (wet, dry):
        hab_fire(trial)
    insist(wet._firewater_reaches("PZ-HAB-03"),
           "authentic A/B fire-main network cannot reach HAB03")
    insist(wet.start_mist("PZ-HAB-03", kg_s=1.0, local_authority=True,
                          compatible_agent=True),
           "fire-main available but verified ordinary fire cannot be misted")
    wet.advance(120)
    dry.advance(120)
    insist(isclose(wet.water_used_kg, 22, abs_tol=1e-6)
           and isclose(wet.water_remaining_kg, 0, abs_tol=1e-6),
           "depleted mist stock never exhausts or leaks through allocation")
    insist(wet.fires["F-HAB-03"].consumed_fuel_kg <
           dry.fires["F-HAB-03"].consumed_fuel_kg,
           "real mist delivery does not reduce burning fuel")
    insist(wet.mass_balance_error_kg() < 1e-5,
           "suppressant incorrectly creates atmospheric mass")
    empty_route = new_trial()
    hab_fire(empty_route)
    empty_route.change_valve("fire_main", "ISO-HAB-03-FIRE-MIST", "closed",
                             local_authority=True)
    insist(not empty_route.start_mist(
        "PZ-HAB-03", kg_s=0.8, local_authority=True, compatible_agent=True),
        "isolation valve closed but local fire station still gets water")
    no_pumps = new_trial()
    hab_fire(no_pumps)
    for pump in ("FIRE-PUMP-FWD", "FIRE-PUMP-AFT"):
        no_pumps.configure_pump(pump, False, local_authority=True)
    insist(not no_pumps.start_mist(
        "PZ-HAB-03", kg_s=0.8, local_authority=True, compatible_agent=True),
        "both real fire pumps off but firefighting still fed")
    electrical = new_trial()
    hab_fire(electrical, hazard="energized_electrical")
    insist(not electrical.start_mist(
        "PZ-HAB-03", kg_s=0.6, local_authority=True, compatible_agent=True),
        "live electrical equipment inexplicably sprayed with water")
    insist(electrical.start_mist(
        "PZ-HAB-03", kg_s=0.6, local_authority=True,
        compatible_agent=True, energy_isolated=True),
        "locally isolated electrical fire cannot receive verified suppression")
    report["suppression"] = {
        "mist_water_used_kg": round(wet.water_used_kg, 3),
        "fuel_burned_without_mist_kg": round(
            dry.fires["F-HAB-03"].consumed_fuel_kg, 3),
        "fuel_burned_with_mist_kg": round(
            wet.fires["F-HAB-03"].consumed_fuel_kg, 3),
        "closed_station_valve_and_failed_pumps_block_supply": True,
    }

    # Radiators are real 0.9375 MW equipment units sharing the 3.75 MW
    # LT heat-rejection system. An overloaded single remaining radiator
    # cannot dissipate the ship's work merely because the coolant valve
    # remains open. Load shedding creates genuine recovery headroom.
    healthy = new_trial()
    degraded = new_trial()
    for trial in (healthy, degraded):
        for n in range(1, 9):
            trial.set_background_heat("PZ-HAB-%02d" % n, 0.45,
                                      local_authority=True)
    for id in ("RAD-LT-1", "RAD-LT-2"):
        degraded.configure_radiator(id, False, local_authority=True)
    healthy.advance(300)
    degraded.advance(300)
    t_healthy = healthy.cells["PZ-HAB-03"].temperature_K
    t_degraded = degraded.cells["PZ-HAB-03"].temperature_K
    insist(t_degraded > t_healthy + 0.5,
           "failed radiator capacity does not cause compartment heating")
    before_shedding = degraded.cells["PZ-HAB-03"].temperature_K
    for n in range(1, 9):
        degraded.set_background_heat("PZ-HAB-%02d" % n, 0.10,
                                     local_authority=True)
    degraded.advance(300)
    insist(degraded.cells["PZ-HAB-03"].temperature_K < before_shedding,
           "load shed never restores thermal recovery capacity")
    isolated_coolant = new_trial()
    isolated_coolant.set_background_heat("PZ-HAB-03", 0.5,
                                        local_authority=True)
    isolated_coolant.change_valve(
        "lt_cooling", "ISO-LT-ROT-A", "closed", local_authority=True)
    isolated_coolant.change_valve(
        "lt_cooling", "ISO-LT-ROT-B", "closed", local_authority=True)
    insist(not isolated_coolant._connected_to_cooling("PZ-HAB-03"),
           "two isolated rotary LT feeds still magically cool HAB")
    isolated_coolant.advance(240)
    insist(isolated_coolant.cells["PZ-HAB-03"].temperature_K > T_HEAT_THRESHOLD(),
           "lost local LT flow has no heat consequence")
    report["thermal_capacity_and_shedding"] = {
        "four_radiators_300s_HAB03_C": round(t_healthy - 273.15, 4),
        "two_radiators_300s_HAB03_C": round(t_degraded - 273.15, 4),
        "after_load_shedding_HAB03_C": round(
            degraded.cells["PZ-HAB-03"].temperature_K - 273.15, 4),
        "both_LT_rotary_valves_closed": True,
    }

    # A small airlock can be deliberately vented under real local procedure
    # but an imaginary direct HAB-03-to-space hatch is not allowed.
    vent = new_trial()
    try:
        vent.vent_to_known_vacuum("PZ-HAB-03", "ACC-EVA-FWD-EXT",
                                 local_authority=True,
                                 evacuated_and_isolated=True)
    except ValueError:
        pass
    else:
        raise AssertionError("fire response fabricated an exterior HAB hatch")
    vent.set_crew("PZ-BOW-EVA", 1)
    try:
        vent.vent_to_known_vacuum("PZ-BOW-EVA", "ACC-EVA-FWD-EXT",
                                 local_authority=True,
                                 evacuated_and_isolated=True)
    except ValueError:
        pass
    else:
        raise AssertionError("unprotected crew deliberately dumped into vacuum")
    vent.set_crew("PZ-BOW-EVA", 0)
    vent.vent_to_known_vacuum("PZ-BOW-EVA", "ACC-EVA-FWD-EXT",
                             local_authority=True, evacuated_and_isolated=True)
    vent.advance(20)
    insist(vent.lost_to_vacuum_kg > 0
           and vent.mass_balance_error_kg() < 1e-5
           and vent.gates["ACC-EVA-FWD-EXT"].state == "open",
           "deliberate rated EVA vent neither loses gas nor records hatch state")

    # Unknown cargo remains quantitatively UNKNOWN after breach/fire,
    # never interpreted as vacuum or breathable simply because we have
    # a sophisticated smoke and temperature reference solver.
    unknown = new_trial()
    unknown.fail_gate_open("ACC-DR-01-SEC-01")
    unknown.advance(8)
    insist(unknown.cells["PZ-DR-01-SVC"].unknown_exposure
           and unknown.summary(["PZ-DR-01-SVC"])["cells"][
               "PZ-DR-01-SVC"]["pressure_reference_kpa"] is None,
           "unverified cargo receiving atmosphere fabricated by HVAC model")

    # Exactly reproducible sample IDs and more than one starting reference
    # free-gas assumption; no carbon/gas material imbalance.
    stress = []
    for basis in ("lower", "midpoint", "upper"):
        trial = new_trial(volume_basis=basis, filters_kg=0.25)
        hab_fire(trial)
        trial.configure_smoke_cleanup(True, local_authority=True)
        trial.advance(120)
        insist(trial.mass_balance_error_kg() < 1e-5
               and all(c.gas_kg >= 0 and c.oxygen_kg >= 0
                       and c.trace_kg >= 0 for c in trial.cells.values()),
               "reference gas bounds yield nonphysical fuel/air ledger")
        stress.append(round(trial.cells["PZ-HAB-03"].pressure_kpa, 4))
    insist(len(set(stress)) == 3,
           "geometry volume uncertainty does not affect thermal/gas casualty")
    report["volume_basis_pressure_reference_kPa"] = dict(zip(
        ("lower", "midpoint", "upper"), stress))
    report["deliberate_vent_and_unknown_cargo"] = "rated vacuum-only vent, cargo remains unquantified"

    return report


def T_HEAT_THRESHOLD():
    return 294.0


def negative_tests():
    bad = [
        lambda t: t.ignite("X", "PZ-HAB-03", fuel_kg=-1, burn_kg_s=0.1),
        lambda t: t.ignite("X", "PZ-HAB-03", fuel_kg=1, burn_kg_s=0),
        lambda t: t.ignite("X", "PZ-NONE", fuel_kg=1, burn_kg_s=0.1),
        lambda t: t.ignite("X", "PZ-HAB-03", fuel_kg=1, burn_kg_s=0.1,
                           smoke_yield_fraction=1.2),
        lambda t: t.change_valve("atmosphere", "ISO-NONE", "closed",
                                 local_authority=True),
        lambda t: t.change_valve("atmosphere", "ISO-AIR-BR-03-HAB-03", "broken",
                                 local_authority=True),
        lambda t: t.fail_valve("fire_main", "ISO-NONE", "open"),
        lambda t: t.isolate_ventilation("PZ-HAB-03", local_authority=False),
        lambda t: t.configure_radiator("RAD-LT-NONE", False,
                                      local_authority=True),
        lambda t: t.set_background_heat("PZ-HAB-03", -1,
                                       local_authority=True),
        lambda t: t.set_background_heat("PZ-HAB-03", 2.2,
                                       local_authority=True),
        lambda t: t.start_mist("PZ-HAB-03", kg_s=-1, local_authority=True,
                               compatible_agent=True),
        lambda t: t.vent_to_known_vacuum("PZ-BOW-EVA", "ACC-EVA-FWD-EXT",
                                        local_authority=False,
                                        evacuated_and_isolated=True),
        lambda t: t.configure_smoke_cleanup("on", local_authority=True),
    ]
    for i, mutate in enumerate(bad, 1):
        trial = new_trial()
        try:
            mutate(trial)
        except (KeyError, ValueError):
            continue
        raise AssertionError("hazardous fire/thermal input accepted: " + str(i))

    topology, gas, environmental = load_model()
    ship = read_ship()
    corrupt = deepcopy(ship)
    next(x for x in corrupt["service_edges"]
         if x["id"] == "EDGE-AIR-BR-03")["isolator_ids"] = ["ISO-INVENTED"]
    try:
        FireSmokeThermalTrial(topology, gas, environmental, corrupt)
    except ValueError:
        pass
    else:
        raise AssertionError("invented bridge damper tolerated")

    for case in ("wrong_fire_main", "duplicate_atmosphere", "wrong_radiator"):
        mutated = deepcopy(ship)
        if case == "wrong_fire_main":
            mutated["service_edges"] = [x for x in mutated["service_edges"]
                                         if x["id"] != "EDGE-FIRE-BR-03"]
        elif case == "duplicate_atmosphere":
            e = next(x for x in mutated["service_edges"]
                     if x["id"] == "EDGE-AIR-BR-03")
            mutated["service_edges"].append(deepcopy(e))
        else:
            next(x for x in mutated["equipment"]
                 if x["id"] == "RAD-LT-1")["attributes"][
                    "nominal_total_MW_share"] = 99
        try:
            FireSmokeThermalTrial(topology, gas, environmental, mutated)
        except ValueError:
            pass
        else:
            raise AssertionError("broken real-world network accepted: " + case)
    return len(bad) + 1 + 3


if __name__ == "__main__":
    output = run_reference_tests()
    output["negative_regressions_rejected"] = negative_tests()
    print(json.dumps(output, indent=2, sort_keys=True))
    print("OX_FIRE_SMOKE_THERMAL_AND_EIGHTEEN_NEGATIVE_TESTS_PASS")
