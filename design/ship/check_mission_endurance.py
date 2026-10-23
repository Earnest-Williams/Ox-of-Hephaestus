#!/usr/bin/env python3
"""B-prime 40-crew/730-day physical stores and power reconciliation.

Design-reference arithmetic and causal routing, NOT as-installed measurements
or permission for a game character to operate inaccessible valves.
Run: python design/ship/check_mission_endurance.py
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from math import isclose
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent


def demand(ok, why):
    if not ok:
        raise ValueError(why)


def unique(rows, kind):
    by = {x["id"]: x for x in rows}
    demand(len(by) == len(rows), "duplicate " + kind)
    return by


def reachable(edges, start, *, crossfeed=False):
    graph = defaultdict(set)
    for edge in edges:
        if edge["network"] != "inert_makeup":
            continue
        if edge["id"] == "EDGE-INERT-CROSS-TIE" and not crossfeed:
            continue
        graph[edge["from_node"]].add(edge["to_node"])
        graph[edge["to_node"]].add(edge["from_node"])
    q = deque([start])
    found = {start}
    while q:
        for nxt in graph[q.popleft()]:
            if nxt not in found:
                found.add(nxt)
                q.append(nxt)
    return found


def validate(ship):
    demand(ship["model_version"] == "0.5-candidate",
           "not the designed ship candidate")
    rooms = unique(ship["spaces"], "rooms")
    equips = unique(ship["equipment"], "equipment")
    inventory = unique(ship["inventories"], "inventory")
    nets = unique(ship["networks"], "networks")
    nodes = unique(ship["service_nodes"], "nodes")
    edges = unique(ship["service_edges"], "edges")
    valves = unique(ship["isolation_points"], "valves")
    life = ship["life_support_contract"]
    food = life["long_leg_food"]
    water = life["makeup_water_730day_planning_split_t"]
    leakage = life["atmospheric_leakage_reference"]
    power = ship["power_contract"]
    mass = ship["mass"]

    # The full-leg contingency is *dehydrated mass*, not all combined stored
    # food, and is not another secretly added physical reserve.
    f = inventory["INV-FOOD-LONG-LEG"]
    demand(f["nominal_mass_t"] == food["departure_stock_t"] == 56.79
           and sum(f["location_allocations_t"].values()) == 56.79
           and set(f["location_allocations_t"]) == set(f["location_ids"]),
           "food departure store differs from actual split locations")
    demand(all(room in rooms for room in f["location_ids"])
           and f["dehydrated_fallback_stock_t"] == 24.82
           and f["conventional_stock_t"] == 31.97
           and isclose(24.82 + 31.97, 56.79, abs_tol=1e-9),
           "dehydrated full-leg reserve and conventional material double-counted")
    demand(food["design_population"] == 40 and food["leg_days"] == 730
           and food["reference_calories_per_person_day"] == 2550,
           "40-person 730-day diet changed")
    shares = food["normal_diet_calorie_fractions"]
    demand(shares == {"hydroponic": 0.25, "dehydrated": 0.25,
                      "conventional": 0.5}, "B-prime diet fractions lost")
    kcal = 40 * 730 * 2550
    dry_kcal_per_kg = food["dehydrated_energy_density_kcal_kg"]
    demand(isclose(24.82 * 1000 * dry_kcal_per_kg, kcal, abs_tol=1),
           "departure dehydrated mass cannot supply 100% of 730-day calories")
    nominal_dry_t = .25 * kcal / dry_kcal_per_kg / 1000
    crop_t = .25 * kcal / food["hydroponic_staple_energy_density_kcal_kg_reference"] / 1000
    conventional_kcal = 31.97 * 1000 * food["conventional_energy_density_kcal_kg_reference"]
    demand(isclose(food["nominal_dehydrated_consumed_t_730d"], nominal_dry_t, abs_tol=.001)
           and isclose(food["nominal_hydroponic_edible_t_730d"], crop_t, abs_tol=.001)
           and isclose(conventional_kcal, kcal * .5, abs_tol=20),
           "normal diet does not supply the prescribed calories by source")
    demand(food["dehydrated_stock_can_cover_entire_leg_at_departure"] is True
           and food["dehydrated_can_substitute_failed_crops_or_conventional"] is True
           and food["hydroponic_calorie_credit_normal_operation"] is True
           and food["hydroponic_calorie_credit_required_for_survival"] is False,
           "failed-crop contingency cannot substitute finite stored dry food")
    grow = food["growing_area_m2_by_room"]
    demand(len(grow) == 3 and sum(grow.values()) == 450
           and all(r in rooms and r.endswith("-GROW") for r in grow),
           "450 m2 staple area not situated in three real rooms")
    demand(food["productive_growing_area_m2"] == 450
           and food["normal_crop_power_kW_total"] == 90,
           "wrong hydroponic bed/power size")
    for n, room in enumerate(grow, 1):
        # The three source rooms were already part of the B-prime arcs.
        ctrl, nutrient = equips[f"GROW-{n}-CTRL"], equips[f"GROW-{n}-NUTRIENT"]
        demand(ctrl["space_id"] == room and nutrient["space_id"] == room
               and ctrl["attributes"]["productive_bed_area_m2"] == grow[room]
               and ctrl["attributes"]["normal_power_kW_share"] == 30
               and nutrient["attributes"]["failed_crop_is_not_free_replacement_food"],
               "crop output/power incorrectly attributed to absent machinery")
    # On a nominal voyage the backup stock is drawn at 25% of total calories.
    # At ANY elapsed point it must still exceed the whole remaining demand
    # if conventional food and crops both become unusable.
    for elapsed in (0, 1, 182, 365, 729, 730):
        remaining_dry = 24.82 - nominal_dry_t * elapsed / 730
        full_remaining = 24.82 * (730 - elapsed) / 730
        demand(remaining_dry >= full_remaining - 1e-8,
               "nominal dry ration use erases promised remaining-voyage fallback")

    demand(isclose(sum(water.values()), 162, abs_tol=.001)
           and water["domestic_unrecovered_t"] == 73
           and water["cultivation_and_food_process_t"] == 35
           and isclose(water["dehydrated_rehydration_process_t"], .74, abs_tol=.001),
           "162 t normal water allocation does not cover the food plan")
    ordinary_o2 = life["normal_oxygen_generation"]["reference_consumption_kg_day"]
    demand(isclose(ordinary_o2, 40 * life["oxygen_kg_person_day"], abs_tol=1e-8)
           and isclose(water["oxygen_electrolysis_feed_t"],
                       ordinary_o2 * 730 / 1000 * 18/16, abs_tol=.002),
           "baseline electrolysis feed does not close")
    # The external review's 4.45-5.95 t is the inert component; 5.79-7.74 t
    # is the total lost gas. Treating these as competing estimates is wrong.
    gas_lo, gas_hi = leakage["nominal_total_dry_gas_t_range"]
    fraction = leakage["daily_fraction_of_fitted_dry_gas"]
    days = leakage["reference_days"]
    demand(days == 730 and isclose(fraction, .0001, abs_tol=1e-12)
           and 79.26 < gas_lo < 79.28 and 105.98 < gas_hi < 106,
           "leakage calculation uses wrong cells or 0.01 percent per day")
    gross = [gas_lo * fraction * days, gas_hi * fraction * days]
    inert = [x * leakage["inert_mass_fraction_assumption"] for x in gross]
    oxygen = [x * leakage["reference_oxygen_mass_fraction"] for x in gross]
    demand(isclose(leakage["inert_mass_fraction_assumption"]
                   + leakage["reference_oxygen_mass_fraction"], 1.0, abs_tol=1e-9),
           "oxygen/inert split not mass conserving")
    for key, check in (("gross_lost_mixed_air_t_range", gross),
                       ("lost_inert_t_range", inert),
                       ("lost_oxygen_t_range", oxygen)):
        demand(all(isclose(a, b, abs_tol=.001) for a, b in zip(leakage[key], check)),
               "leakage accounting mismatch: " + key)
    demand(leakage["no_routine_use_of_refill_reserve"] is True
           and leakage["metered_only_at_eclss_mixer"] is True,
           "routine leaking gas wrongly consumes breach reserve or enters cabins")
    demand(isclose(leakage["independent_inert_stock_t"], 7, abs_tol=1e-9)
           and 7 > max(inert),
           "inert gas store cannot sustain the reference leg")
    oxygen_water_needed = max(oxygen) * 18 / 16
    demand(water["leak_replacement_oxygen_electrolysis_feed_t"] >= oxygen_water_needed
           and isclose(leakage["gross_electrolysis_water_t_budget_for_loss"],
                       water["leak_replacement_oxygen_electrolysis_feed_t"], abs_tol=1e-9),
           "ECLSS lost oxygen restoration not paid from voyage water")
    o2_day_max = ordinary_o2 + 1000 * max(oxygen) / 730
    demand(all(equips[x]["attributes"]["oxygen_capacity_kg_day"] >= o2_day_max
               for x in ("ECLSS-A-O2-GEN", "ECLSS-B-O2-GEN")),
           "a single healthy ECLSS train cannot replace metabolic plus leak oxygen")

    demand(nets["inert_makeup"]["medium"].endswith("NON-BREATHABLE"),
           "unsafe gas described as breathable")
    demand(len([x for x in nodes.values() if x["network"] == "inert_makeup"]) == 6
           and len([x for x in edges.values() if x["network"] == "inert_makeup"]) == 5
           and len([x for x in valves.values() if x["network"] == "inert_makeup"]) == 5,
           "routine make-up network missing boundaries")
    for side, bank_room, train_room in (("A", "ENV-FWD", "HAB-06-ECLSS-A"),
                                        ("B", "ENV-AFT", "HAB-08-ECLSS-B")):
        id = f"INV-INERT-MAKEUP-{side}"
        bank, regulator, mixer = (equips[f"GAS-INERT-BANK-{side}"],
                                  equips[f"GAS-INERT-REG-{side}"],
                                  equips[f"ECLSS-{side}-INERT-MIX"])
        demand(inventory[id]["nominal_mass_t"] == 3.5
               and inventory[id]["location_ids"] == [bank_room]
               and bank["space_id"] == regulator["space_id"] == bank_room
               and mixer["space_id"] == train_room,
               "inert stores not physically independent / not near their regulators")
        demand(bank["attributes"]["inventory_id"] == id
               and bank["attributes"]["not_casualty_reserve"] is True
               and mixer["attributes"]["host_train_id"] == "ECLSS-" + side
               and mixer["attributes"]["no_direct_inert_cabin_feed"] is True
               and mixer["attributes"]["interlock_oxygen_partial_pressure"] is True
               and mixer["attributes"]["interlock_gas_purity"] is True
               and mixer["attributes"]["atmosphere_return_node_id"] ==
                    "NODE-ECLSS-" + side + "-AIR",
               "inert added without independent oxygen-controlled mixer")
        for suffix in ("OUTLET", "INJECT"):
            valve = valves[f"ISO-INERT-{side}-{suffix}"]
            demand(valve["normal_state"] == valve["current_state"] == "closed",
                   "routine inert branch unintentionally open")
        outgoing = edges[f"EDGE-INERT-{side}-TO-MIX"]
        demand(outgoing["from_node"] == f"NODE-INERT-REG-{side}"
               and outgoing["to_node"] == f"NODE-INERT-MIX-{side}"
               and len(outgoing["route_spaces"]) >= 12
               and outgoing["route_spaces"][0] == bank_room
               and outgoing["route_spaces"][-1] == train_room
               and all(p in rooms for p in outgoing["route_spaces"])
               and f"ROTARY-UTIL-{side}" in outgoing["route_spaces"],
               "inert trunk/rotary branch has no real physical route")
        # Each source reaches its own ECLSS with crossfeed shut. A failed
        # outlet, feed, mixer, interlock or rotary passage can prevent flow.
        demand(f"NODE-INERT-MIX-{side}" in reachable(ship["service_edges"],
                f"NODE-INERT-BANK-{side}"),
               "inert bank disconnected from its assigned ECLSS")
        opposite = "B" if side == "A" else "A"
        demand(f"NODE-INERT-MIX-{opposite}" not in reachable(ship["service_edges"],
                f"NODE-INERT-BANK-{side}"),
               "routine banks are cross-connected by default")
        demand(f"NODE-INERT-MIX-{opposite}" in reachable(ship["service_edges"],
                f"NODE-INERT-BANK-{side}", crossfeed=True),
               "no controlled recovery if one ECLSS train or bank is unavailable")
    cross = edges["EDGE-INERT-CROSS-TIE"]
    demand(cross["normal_state"] == "closed"
           and cross["isolator_ids"] == ["ISO-INERT-CROSS-TIE"]
           and valves["ISO-INERT-CROSS-TIE"]["normal_state"] == "closed"
           and valves["ISO-INERT-CROSS-TIE"]["manual_operation"] is True,
           "unprotected contamination-prone routine crossfeed")
    demand(set(leakage["inert_bank_inventory_ids"]) ==
           {"INV-INERT-MAKEUP-A", "INV-INERT-MAKEUP-B"}
           and set(life["repressurization_reserve"]["inventory_ids"]) ==
           {"INV-GAS-REFILL-A", "INV-GAS-REFILL-B"}
           and isclose(sum(inventory[id]["nominal_mass_t"]
                           for id in life["repressurization_reserve"]["inventory_ids"]),
                       5.5, abs_tol=1e-9),
           "emergency and normal gas reservoirs conflated")

    allocation = power["normal_reference_allocation_kW"]
    demand(isclose(power["normal_MW"], 1.35, abs_tol=1e-9)
           and allocation["hydroponic_staple_production"] == 90
           and allocation["normal_unallocated_operating_margin"] == 97
           and sum(allocation.values()) == 1350
           and power["protected_MW"] == .75
           and power["single_aux_MW"] == .65,
           "normal/essential electrical basis inconsistent with B-prime")
    cartridge = inventory["INV-GEN-CART"]["nominal_mass_t"]
    needed = power["normal_MW"] * 24 * 730 * power["cartridge_kg_per_electrical_MWh"] / 1000
    demand(needed < cartridge and isclose(needed, 106.434, abs_tol=.01),
           "generator cartridge fuel cannot cover normal 730-day electrical load")
    mission = sum(x["nominal_mass_t"] for key, x in inventory.items()
                  if key not in ("INV-FTL-FUEL", "INV-REACTION"))
    demand(mission < mass["mission_and_nonpropulsive_fluids_t"] == 1500
           and mass["reference_departure_t"] == 1187500,
           "duplicated mission provisioning exceeds unchanged departure mass")
    return {
        "status": "BPRIME_ISSUE13_MISSION_ENDURANCE_CONSISTENT",
        "crew": 40, "days": 730,
        "food_departure_t": f["nominal_mass_t"],
        "dehydrated_full_leg_standalone_t": f["dehydrated_fallback_stock_t"],
        "crop_area_m2": food["productive_growing_area_m2"],
        "crop_power_kW": food["normal_crop_power_kW_total"],
        "normal_power_MW": power["normal_MW"],
        "generator_cartridges_730day_t": round(needed, 3),
        "routine_gas_inert_stock_t": 7,
        "mixed_air_lost_t_730d": [round(x, 3) for x in gross],
        "inert_loss_t_730d": [round(x, 3) for x in inert],
        "oxygen_loss_t_730d": [round(x, 3) for x in oxygen],
        "extra_electrolysis_water_budget_t": water["leak_replacement_oxygen_electrolysis_feed_t"],
        "emergency_refill_still_protected_t": 5.5,
        "normal_water_budget_t": sum(water.values()),
        "mission_inventory_upper_bound_t": round(mission, 3),
        "equipment_units": len(equips),
        "validated_separate_inert_paths": 2,
    }


def negative_controls(ship):
    cases = [
        ("rations missing", lambda x: x["inventories"][next(i for i, row in
           enumerate(x["inventories"]) if row["id"] == "INV-FOOD-LONG-LEG")].update(nominal_mass_t=32)),
        ("crop power not provided", lambda x: x["power_contract"]["normal_reference_allocation_kW"].update(hydroponic_staple_production=0)),
        ("oxygen water not funded", lambda x: x["life_support_contract"]["makeup_water_730day_planning_split_t"].update(leak_replacement_oxygen_electrolysis_feed_t=0)),
        ("routine inert gas depleted", lambda x: x["inventories"][next(i for i, row in enumerate(x["inventories"]) if row["id"] == "INV-INERT-MAKEUP-A")].update(nominal_mass_t=0)),
        ("reserve double spent", lambda x: x["life_support_contract"]["atmospheric_leakage_reference"].update(no_routine_use_of_refill_reserve=False)),
        ("inert released direct", lambda x: x["equipment"][next(i for i, row in enumerate(x["equipment"]) if row["id"] == "ECLSS-A-INERT-MIX")]["attributes"].update(no_direct_inert_cabin_feed=False)),
        ("lost side B supply", lambda x: x["service_edges"].remove(next(e for e in x["service_edges"] if e["id"] == "EDGE-INERT-B-TO-MIX"))),
        ("contaminating open crossfeed", lambda x: x["service_edges"][next(i for i, e in enumerate(x["service_edges"]) if e["id"] == "EDGE-INERT-CROSS-TIE")].update(normal_state="available")),
        ("insufficient hydroponic area", lambda x: x["life_support_contract"]["long_leg_food"]["growing_area_m2_by_room"].update({"HAB-06-GROW":0})),
    ]
    for title, damage in cases:
        broken = deepcopy(ship)
        damage(broken)
        try:
            validate(broken)
        except (ValueError, KeyError, TypeError):
            continue
        raise AssertionError("damaged mission ledger passed: " + title)
    return len(cases)


def main():
    ship = json.loads((HERE / "ox_full_ship_v0.5_candidate.json").read_text(encoding="utf-8"))
    report = validate(ship)
    report["deliberate_negative_controls"] = negative_controls(ship)
    print(json.dumps(report, indent=2, sort_keys=True))
    print("OX_BPRIME_730_DAY_MISSION_ENDURANCE_PASS")


if __name__ == "__main__":
    main()
