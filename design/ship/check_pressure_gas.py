#!/usr/bin/env python3
"""Validate B-prime provisional free gas, inventory and physical refill networks.

Runnable standalone (stdlib-only):
    python design/ship/check_pressure_gas.py

Free-volume fractions are authoring/screening assumptions, not surveys and
never a signal that a cell is safe for an unsuited character.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy
from math import isclose
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(filename: str) -> dict:
    return json.loads((HERE / filename).read_text(encoding="utf-8"))


def check(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def unique(rows: list[dict], label: str) -> dict:
    ids = [x["id"] for x in rows]
    check(len(ids) == len(set(ids)), f"{label}: duplicate id")
    return {x["id"]: x for x in rows}


def reachable(graph: dict[str, set[str]], starts: set[str]) -> set[str]:
    visited = set(starts)
    waiting = deque(starts)
    while waiting:
        for other in graph.get(waiting.popleft(), set()):
            if other not in visited:
                visited.add(other)
                waiting.append(other)
    return visited


def gas_graph(ship: dict, excluded: set[str] = frozenset()) -> dict[str, set[str]]:
    """Potential pipe path if authorised valves operate, not current open path."""
    graph: dict[str, set[str]] = defaultdict(set)
    for edge in ship["service_edges"]:
        if edge["network"] != "repressurization_gas" or edge["id"] in excluded:
            continue
        # The cross-tie is a separate normally closed operating decision.
        if edge["id"] == "EDGE-GAS-CROSS-TIE":
            continue
        graph[edge["from_node"]].add(edge["to_node"])
        graph[edge["to_node"]].add(edge["from_node"])
    return graph


def validate(ship: dict, pressure: dict, gas: dict) -> dict:
    check(gas["schema_version"] == "ox.ship.pressure-gas-reference/0.1",
          "wrong pressure gas ledger schema")
    check(ship["model_version"] == gas["ship_model_version"] == "0.5-candidate",
          "wrong ship/cell model version")
    check(gas["pressure_cell_model_version"] == pressure["model_version"],
          "stale pressure cell revision")
    density = pressure["gas_reference"]["calculated_dry_air_density_kg_m3"]
    check(isclose(gas["reference_gas"]["density_kg_m3"], density, rel_tol=1e-8),
          "density must follow original ideal-gas reference")

    spec = unique(pressure["pressure_cells"], "physical pressure cells")
    lines = gas["sized_and_unsized_pressure_cells"]
    check(len(lines) == len(spec) == 133, "missing or invented pressure cells")
    rows = {r["pressure_zone_id"]: r for r in lines}
    check(len(rows) == len(spec), "duplicate gas accounting pressure cell")

    lo_m3 = hi_m3 = lo_kg = hi_kg = 0.
    full_gross = 0.
    sized = 0
    for cell_id, original in spec.items():
        check(cell_id in rows, f"missing gas cell {cell_id}")
        row = rows[cell_id]
        check(row["classification"] == original["classification"],
              f"gas cell class mismatch {cell_id}")
        check(row["source_gross_envelope_m3"] ==
              original["gross_reference_envelope_m3"],
              f"gas cell gross envelope changed {cell_id}")
        check(row["verified_as_installed_free_gas_m3"] is None,
              f"planning assumption falsely marked measured {cell_id}")
        gross = original["gross_reference_envelope_m3"]
        if gross is None:
            check(all(row[k] is None for k in (
                "planning_void_fraction_lower",
                "planning_void_fraction_upper",
                "design_free_gas_lower_m3", "design_free_gas_upper_m3",
                "reference_gas_mass_lower_kg", "reference_gas_mass_upper_kg")),
                f"fabricated unsized volume {cell_id}")
            continue
        sized += 1
        full_gross += gross
        cls = gas.get("cell_void_fraction_overrides", {}).get(cell_id) or gas["void_fraction_policy"][original["classification"]]
        lower, upper = cls["bounds"]
        check(0 < lower < upper <= 1, f"void bound nonphysical {cell_id}")
        check(row["planning_void_fraction_lower"] == lower and
              row["planning_void_fraction_upper"] == upper,
              f"void fraction mismatch {cell_id}")
        check(isclose(row["design_free_gas_lower_m3"],
                      gross*lower, abs_tol=0.002) and
              isclose(row["design_free_gas_upper_m3"],
                      gross*upper, abs_tol=0.002),
              f"free gas volume/mass mismatch {cell_id}")
        check(isclose(row["reference_gas_mass_lower_kg"],
                      gross*lower*density, abs_tol=0.002) and
              isclose(row["reference_gas_mass_upper_kg"],
                      gross*upper*density, abs_tol=0.002),
              f"dry air reference mass inconsistent {cell_id}")
        lo_m3 += gross*lower
        hi_m3 += gross*upper
        lo_kg += gross*lower*density
        hi_kg += gross*upper*density

    check(sized == 96 and len(lines) - sized == 37,
          "gross/geometric data scope altered")
    totals = gas["totals"]
    checks = {
        "sized_gross_m3": full_gross,
        "sized_free_lower_m3": lo_m3,
        "sized_free_upper_m3": hi_m3,
        "dry_air_mass_lower_t": lo_kg/1000,
        "dry_air_mass_upper_t": hi_kg/1000,
    }
    for name, val in checks.items():
        check(isclose(totals[name], val, abs_tol=0.01),
              f"pressure-gas total disagrees {name}")

    room = {x["id"]: x for x in ship["spaces"]}
    unclassified = pressure["unassigned_pressure_zone_space_ids"]
    policies = gas["unclassified_nonbreathable_by_default"]
    check(len(policies) == len(unclassified) == 83 and
          {x["space_id"] for x in policies} == set(unclassified),
          "unclassified cargo/machinery safety policy must cover all 83")
    counts = Counter(x["environment_role"] for x in policies)
    check(counts == {
        "high_energy_industrial_plant": 8,
        "manifest_dependent_cargo_sector": 48,
        "commercial_cargo_portal": 12,
        "bearing_service_annulus": 12,
        "unoccupied_shield_or_trim_bay": 3,
    }, "unsafe default environment role classification")
    for policy in policies:
        check(policy["normal_breathability_unverified"] is True and
              policy["crew_unsuited_access_permitted_by_default"] is False and
              policy["pressure_zone_id"] is None and
              policy["gas_volume_reference_m3"] is None,
              f"unclassified space made breathable by assumption: {policy['space_id']}")
        check(room[policy["space_id"]]["pressure_zone"] is None,
              f"unclassified room silently pressurised: {policy['space_id']}")
    check(totals["pressure_unclassified_spaces"] == len(policies) and
          totals["unsized_pressurized_cells"] == 37,
          "incomplete uncertainty accounting")

    equipment = unique(ship["equipment"], "ship equipment")
    inventory = unique(ship["inventories"], "ship inventory")
    nodes = unique(ship["service_nodes"], "network nodes")
    edges = unique(ship["service_edges"], "network edges")
    isolation = unique(ship["isolation_points"], "isolation points")
    network = "repressurization_gas"
    check(sum(x["id"] == network for x in ship["networks"]) == 1,
          "repressurization gas network must be explicit")
    sub_nodes = [x for x in nodes.values() if x["network"] == network]
    sub_edges = [x for x in edges.values() if x["network"] == network]
    sub_iso = [x for x in isolation.values() if x["network"] == network]
    check((len(sub_nodes),len(sub_edges),len(sub_iso)) == (131,132,143),
          "gas network incomplete")
    check(all(x["id"] in nodes for x in sub_nodes), "network node missing")
    check(all(x["from_node"] in nodes and x["to_node"] in nodes and
              all(i in isolation for i in x["isolator_ids"]) and
              all(location in room for location in x["route_spaces"])
              for x in sub_edges), "unbound gas line or isolation device")
    check(all(x["space_id"] in room for x in sub_iso),
          "valve has no physical access space")

    banks = gas["reserve_gas"]["banks"]
    check(len(banks) == 2 and
          {b["equipment_id"] for b in banks} ==
          {"GAS-REFILL-BANK-A","GAS-REFILL-BANK-B"},
          "independent stores missing")
    total_bank = 0.
    for bank in banks:
        equip = equipment[bank["equipment_id"]]
        supply = inventory[bank["inventory_id"]]
        check(equip["space_id"] == bank["location_id"] and
              supply["location_ids"] == [bank["location_id"]],
              f"gas bank and inventory location diverged: {bank['equipment_id']}")
        check(bank["mass_t"] == supply["nominal_mass_t"] ==
              equip["attributes"]["stored_air_t_nominal"] == 2.75,
              "bank stock and gas receiver mass disagree")
        check(equip["attributes"]["protected_refuge_oxygen_credit_kg"] == 0,
              "backup respiratory oxygen stock double counted")
        check(isolation[f"ISO-GAS-BANK-{bank['equipment_id'][-1]}"]
              ["normal_state"] == "closed",
              "reserve bottle may not normally discharge to whole ship")
        total_bank += bank["mass_t"]
    check(isclose(total_bank,gas["reserve_gas"]["nominal_total_mass_t"],
                  abs_tol=0.0001) and isclose(total_bank,5.5,abs_tol=0.0001),
          "one-arc refill stock changed")
    check(isclose(ship["life_support_contract"]["arc_refill_gas_t"],total_bank,
                  abs_tol=1e-8) and
          ship["life_support_contract"]["protected_oxygen_total_kg"] == 249.2,
          "reservoir gas confused with refuge oxygen")
    check({key for key in inventory if key.startswith("INV-GAS-REFILL-")} ==
          {"INV-GAS-REFILL-A","INV-GAS-REFILL-B"}, "bank inventory missing")

    arcs = [rows[f"PZ-HAB-{n:02d}"] for n in range(1,9)]
    smallest = min(a["reference_gas_mass_lower_kg"] for a in arcs)/1000.
    largest = max(a["reference_gas_mass_upper_kg"] for a in arcs)/1000.
    check(isclose(totals["one_hab_arc_air_lower_t"],smallest,abs_tol=0.002) and
          isclose(totals["one_hab_arc_air_upper_t"],largest,abs_tol=0.002),
          "arc refill mass range incorrect")
    check(2.75 < smallest <= largest < total_bank and 2*smallest > total_bank,
          "replenishment mass must allow one arc but not two or one-bank refill")

    taps = gas["distribution"]["trunk_cell_taps"]
    trunk = [s for s in room.values()
             if s["kind"] in ("personnel_service_trunk","heavy_logistics_trunk")]
    check(len(taps) == len(trunk) == 69 and
          {t["space_id"] for t in taps} == {x["id"] for x in trunk},
          "not every 950 m trunk section has a local gas makeup tap")
    for tap in taps:
        cid = tap["space_id"]
        check(tap["pressure_zone_id"] == room[cid]["pressure_zone"]
              and tap["service_node_id"] in nodes
              and nodes[tap["service_node_id"]]["owner_id"] == cid
              and tap["valve_id"] in isolation
              and isolation[tap["valve_id"]]["space_id"] == cid
              and isolation[tap["valve_id"]]["normal_state"] == "closed",
              f"unsafe or misplaced tap {cid}")
        check(tap["bank_header_id"] in equipment and
              tap["bank_header_id"] in
              ("GAS-REFILL-HEADER-A","GAS-REFILL-HEADER-B"),
              f"missing fixed-spine header for {cid}")
    for n in range(1,9):
        num=f"{n:02d}"
        edge=edges[f"EDGE-GAS-BR-{num}"]
        sleeve=equipment[f"BR-{num}-UTILITY-SLEEVE"]
        check("repressurization_gas" in sleeve["attributes"]["services"],
              f"makeup tube passes through a nonexistent bridge sleeve {num}")
        check(edge["route_spaces"][1]==f"BR-{num}" and
              len(edge["isolator_ids"])==2 and
              all(isolation[iso]["normal_state"]=="closed"
                  for iso in edge["isolator_ids"]),
              f"failed bridge cannot be independently isolated {num}")
    check(edges["EDGE-GAS-CROSS-TIE"]["normal_state"] == "normally_closed"
          and len(edges["EDGE-GAS-CROSS-TIE"]["isolator_ids"])==2,
          "fixed-spine A/B bypass uncontrolled")

    graph=gas_graph(ship)
    banks_set={"NODE-GAS-BANK-A","NODE-GAS-BANK-B"}
    target={f"NODE-GAS-HAB-{n:02d}" for n in range(1,9)}
    check(target <= reachable(graph,banks_set),
          "not all eight arcs have a physical refill path")
    for side in "AB":
        expected={f"NODE-GAS-TAP-{row['space_id']}"
                  for row in taps if row["bank_header_id"].endswith(f"-{side}")}
        check(expected <= reachable(graph,{f"NODE-GAS-BANK-{side}"}),
              f"{side} spine pressure taps not connected to their bank")
    # One failed bridge can be routed around. Two adjacent broken sleeves
    # can isolate an arc without any magical topological gas supply.
    for n in range(1,9):
        broken={f"EDGE-GAS-BR-{n:02d}"}
        check(target <= reachable(gas_graph(ship,broken),banks_set),
              "one bridge loss should not isolate a complete hab segment")
    broken={"EDGE-GAS-BR-06","EDGE-GAS-BR-07"}
    reached=reachable(gas_graph(ship,broken),banks_set)
    check("NODE-GAS-HAB-07" not in reached and
          (target-{"NODE-GAS-HAB-07"}) <= reached,
          "two bridge casualties must isolate HAB-07 makeup path")

    return {
        "pressure_cells":len(rows),"sized_cells":sized,
        "unknown_free_volume_cells":len(rows)-sized,
        "unclassified_cargo_machinery_spaces":len(policies),
        "free_air_m3_lower":round(lo_m3),
        "free_air_m3_upper":round(hi_m3),
        "reference_air_t_lower":round(lo_kg/1000,3),
        "reference_air_t_upper":round(hi_kg/1000,3),
        "makeup_gas_banks":len(banks),
        "makeup_gas_network_nodes":len(sub_nodes),
        "makeup_gas_network_edges":len(sub_edges),
        "makeup_gas_isolation_points":len(sub_iso),
        "fixed_spine_pressure_taps":len(taps),
        "single_broken_bridge_bypass":"PASS",
        "two_adjacent_broken_bridges_isolate_HAB07":"PASS",
    }


def negative_tests(ship:dict, pressure:dict, gas:dict)->None:
    cases=[
        ("reserve mass duplicated",
         lambda s,g: next(i for i in s["inventories"]
                          if i["id"]=="INV-GAS-REFILL-B").update(nominal_mass_t=5.5)),
        ("false as-installed gas measurement",
         lambda s,g: g["sized_and_unsized_pressure_cells"][0]
                    .update(verified_as_installed_free_gas_m3=999)),
        ("fictitious cargo breathability",
         lambda s,g: g["unclassified_nonbreathable_by_default"][0]
                    .update(crew_unsuited_access_permitted_by_default=True)),
        ("open reserve outlet at rest",
         lambda s,g: next(x for x in s["isolation_points"]
                          if x["id"]=="ISO-GAS-BANK-A").update(normal_state="open")),
        ("pressurization tap in wrong pressure cell",
         lambda s,g: g["distribution"]["trunk_cell_taps"][0]
                    .update(pressure_zone_id="PZ-HAB-03")),
        ("lost ring bypass",
         lambda s,g: s["service_edges"].remove(next(x for x in s["service_edges"]
                         if x["id"]=="EDGE-GAS-BR-03"))),
        ("bridge sleeve has no gas service",
         lambda s,g: next(x for x in s["equipment"] if x["id"]=="BR-04-UTILITY-SLEEVE")
                    ["attributes"]["services"].remove("repressurization_gas")),
        ("impossible free fraction",
         lambda s,g: g["void_fraction_policy"]["sectional_heavy_logistics_trunk"]
                    .update(bounds=[0.96,1.08])),
        ("unverified overlapping aft store boxes counted twice",
         lambda s,g: next(r for r in g["sized_and_unsized_pressure_cells"]
                          if r["pressure_zone_id"]=="PZ-AFT-STORES")
                    .update(source_gross_envelope_m3=1051)),
    ]
    for name,mutate in cases:
        s,g=deepcopy(ship),deepcopy(gas)
        mutate(s,g)
        try:
            validate(s,pressure,g)
        except ValueError:
            continue
        raise AssertionError(f"negative pressure-gas regression unexpectedly passed: {name}")


if __name__ == "__main__":
    world=read("ox_full_ship_v0.5_candidate.json")
    pc=read("pressure_zone_topology_v0.5.json")
    gas=read("pressure_gas_recovery_v0.5.json")
    print(json.dumps(validate(world,pc,gas),indent=2,sort_keys=True))
    negative_tests(world,pc,gas)
    print("OX_PRESSURE_GAS_RECOVERY_AND_NINE_NEGATIVE_TESTS_PASS")
