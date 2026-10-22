#!/usr/bin/env python3
"""Focused, stdlib-only integrity and physical-envelope checks for Ox v0.5.

Run from repository root:
    python design/ship/check_v05_candidate.py

This is a *design* validator, not an Evennia simulator, structural FEA pass,
pressure qualification, or proof that all fictional equipment is functional.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from math import hypot, isclose, pi, sin
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "ox_full_ship.json"
CANDIDATE = HERE / "ox_full_ship_v0.5_candidate.json"


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def ident_map(records: list[dict], kind: str) -> dict:
    ids = [record["id"] for record in records]
    require(len(ids) == len(set(ids)), f"{kind}: repeated id")
    return {record["id"]: record for record in records}


def validate(candidate: dict, baseline: dict) -> dict:
    require(candidate["schema_version"] == baseline["schema_version"] == "ox.ship-world/0.1",
            "world schema drift")
    require(candidate["model_version"] == "0.5-candidate", "candidate identity changed")
    require(candidate["status"] == "DESIGN_CANDIDATE_NOT_RUNTIME_AUTHORITY",
            "candidate promoted without review")
    require(len(candidate["spaces"]) == len(baseline["spaces"]) == 421,
            "spatial count changed")
    require(len(candidate["access_links"]) == len(baseline["access_links"]) == 517,
            "physical-link count changed")
    require(len(candidate["equipment"]) == len(baseline["equipment"]) + 72 == 764,
            "expected v0.5 equipment including Bprime structure/indexers/bridges")
    require(len(candidate["maintenance_tasks"]) == 39, "maintenance package count changed")

    spaces = ident_map(candidate["spaces"], "spaces")
    equips = ident_map(candidate["equipment"], "equipment")
    links = ident_map(candidate["access_links"], "access links")
    nodes = ident_map(candidate["service_nodes"], "service nodes")
    edges = ident_map(candidate["service_edges"], "service edges")
    isos = ident_map(candidate["isolation_points"], "isolators")
    era = ident_map(candidate["eras"], "refit eras")
    tasks = ident_map(candidate["maintenance_tasks"], "maintenance tasks")

    for section in ("service_nodes", "isolation_points"):
        require(candidate[section] == baseline[section], f"unexpected {section} mutation")
    # Only the explicitly justified pressure-cell corrections may alter the
    # 421 installed space records. Physical geometry and room IDs stay fixed.
    expected_spaces = deepcopy(baseline["spaces"])
    protected_cells = {
        "HAB-04-MED-ISO": "PZ-HAB-04-MED-ISO",
        "IX-A-FINAL-LIFT": "PZ-IX-A-FINAL-LIFT",
        "IX-B-FINAL-LIFT": "PZ-IX-B-FINAL-LIFT",
    }
    for base_space in expected_spaces:
        sid = base_space["id"]
        if base_space["kind"] == "personnel_service_trunk":
            base_space["pressure_zone"] = "PZ-" + sid
        elif sid in protected_cells:
            base_space["pressure_zone"] = protected_cells[sid]
            base_space["tags"] = [*base_space.get("tags", []),
                                  "independent_pressure_cell"]
        elif sid in {"F1-BAY", "F2-BAY"}:
            base_space["pressure_zone"] = "VACUUM"
            base_space["tags"] = [
                *base_space.get("tags", []),
                "unpressurised_machinery", "flywheel_safety_enclosure"
            ]
            base_space["notes"] = [
                *base_space.get("notes", []),
                "F1/F2 fixed flywheel equipment bay normally vacuum/unpressurised; service through pressure airlock with rotor isolation and suited entry."
            ]
    require(candidate["spaces"] == expected_spaces,
            "unauthorised spatial mutation outside reviewed pressure-cell corrections")
    zone_of = {room["id"]: room["pressure_zone"] for room in candidate["spaces"]}
    trunk = [room for room in candidate["spaces"]
             if room["kind"] == "personnel_service_trunk"]
    require(len(trunk) == 46 and
            len({room["pressure_zone"] for room in trunk}) == 46,
            "A/B personnel trunks must have 23 independently sealable pressure sections each")
    trunk_enddoors = [
        edge for edge in candidate["access_links"]
        if edge["from"] in {r["id"] for r in trunk}
        and edge["to"] in {r["id"] for r in trunk}
    ]
    require(len(trunk_enddoors) == 44 and
            all(edge["pressure_boundary"] for edge in trunk_enddoors),
            "pressure doors missing between 46 A/B trunk segments")
    require(all(zone_of[edge["from"]] != zone_of[edge["to"]]
                for edge in candidate["access_links"]
                if edge["pressure_boundary"]
                and zone_of[edge["from"]] is not None
                and zone_of[edge["to"]] is not None),
            "a rated pressure boundary cannot connect two rooms of one elementary gas cell")
    refuge = candidate["life_support_contract"]["refuge_occupancy_contract"]
    require(refuge["protected_refuge_zone_ids"] == ["PZ-HAB-04", "PZ-HAB-08"]
            and refuge["whole_arc_used_for_people"]
            and refuge["cupboards_are_not_forty_person_habitable_refuges"],
            "refuge equipment cupboard mistaken for forty-person pressure refuge")
    require(zone_of["F1-BAY"] == zone_of["F2-BAY"] == "VACUUM",
            "main flywheel airlocks must isolate vacuum machinery");

    require(candidate["inventories"][:len(baseline["inventories"])] == baseline["inventories"],
            "v0.4 inventory stock unexpectedly rewritten")
    require(len(candidate["inventories"]) == len(baseline["inventories"]) + 1,
            "missing or duplicated new food stock")
    food = next((i for i in candidate["inventories"]
                 if i["id"] == "INV-FOOD-LONG-LEG"), None)
    require(food is not None and food["nominal_mass_t"] == 32 and
            all(room in spaces for room in food["location_ids"]),
            "missing or misplaced 32 t long-leg provisions")
    require(40 * 0.85 * 730 / 1000 <= food["nominal_mass_t"],
            "food stock cannot support reference edible provision demand")
    for row in baseline["access_links"]:
        other = links[row["id"]]
        require((row["from"], row["to"], row["kind"]) ==
                (other["from"], other["to"], other["kind"]),
                f"access connectivity changed: {row['id']}")
    for row in candidate["modifications"]:
        require(row["era"] in era, f"unrecognised modification era: {row['id']}")
    for row in candidate["current_configuration_notes"]:
        require(row["subject_id"] in spaces or row["subject_id"] in equips,
                f"unknown as-found note target: {row['subject_id']}")
    for item in candidate["equipment"]:
        require(item["space_id"] in spaces, f"equipment location unknown: {item['id']}")
    for link in candidate["access_links"]:
        require(link["from"] in spaces and link["to"] in spaces,
                f"access endpoint unknown: {link['id']}")
    for node in candidate["service_nodes"]:
        if node["owner_type"] == "space":
            require(node["owner_id"] in spaces, f"service space lost: {node['id']}")
        if node["owner_type"] == "equipment":
            require(node["owner_id"] in equips, f"service equipment lost: {node['id']}")
    for edge in candidate["service_edges"]:
        require(edge["from_node"] in nodes and edge["to_node"] in nodes,
                f"service endpoint unknown: {edge['id']}")
        require(all(space in spaces for space in edge["route_spaces"]),
                f"service route uses non-space id: {edge['id']}")
        require(all(i in isos for i in edge["isolator_ids"]),
                f"service isolator missing: {edge['id']}")
    for iso in candidate["isolation_points"]:
        require(iso["space_id"] in spaces, f"isolator room missing: {iso['id']}")

    covered: set[str] = set()
    for task in tasks.values():
        for equipment_id in task["equipment_ids"]:
            require(equipment_id in equips,
                    f"{task['id']} targets missing equipment {equipment_id}")
            covered.add(equipment_id)
        require(task["verification"], f"unverifiable task: {task['id']}")
    require(covered == set(equips), "equipment without assigned maintenance task")

    diameter = candidate["transit_contract"]["heavy_logistics_trunk"]["clear_diameter_m"]
    width, height, length = candidate["transit_contract"]["heavy_logistics_trunk"]["sled_envelope_m"]
    corner_radius = hypot(width / 2.0, height / 2.0)
    clearance = diameter / 2.0 - corner_radius
    require(length <= 8.0 and length > 0 and clearance >= 0.18,
            "heavy sled exceeds 5.5 m clear tube or has insufficient corner clearance")
    require(candidate["transit_contract"]["inter_drum_transfer"]["sled_envelope_m"]
            == [width, height, length],
            "drum load envelope and trunk sled box differ")
    require(isclose(clearance,
                    candidate["design_closure_v05"]["capacity_checks"]["radius_clearance_m"],
                    abs_tol=0.001),
            "recorded sled clearance inconsistent")

    arc_refs = ["HAB-01", "HAB-03", "HAB-05", "HAB-07"]
    cabins = [item for item in candidate["spaces"] if item["kind"] == "cabin"]
    require(len(cabins) == 40, "40-bed residential requirement lost")
    require(all(sum(s["id"].startswith(f"{arc}-CAB-") for s in cabins) == 10
                for arc in arc_refs),
            "residential arc berth allocation changed")

    hull_hatches = [e for e in equips.values() if e["kind"] == "arc_end_pressure_hatch"]
    sleeves = [e for e in equips.values() if e["kind"] == "bridge_utility_sleeve"]
    require(len(hull_hatches) == 16, "wrong arc-end hatch count")
    require(len(sleeves) == 8, "wrong bridge utility sleeve count")
    hatch_edges = {
        x["id"] for x in links.values()
        if x["kind"] == "pressure_hatch"
        and (x["from"].startswith("BR-") or x["to"].startswith("BR-"))
    }
    require({e["attributes"]["access_link_id"] for e in hull_hatches} == hatch_edges,
            "not every end hatch has exactly one associated physical access link")
    for h in hull_hatches:
        require(h["attributes"]["latch_dogs"] == 16
                and h["attributes"]["dual_replaceable_seals"]
                and h["attributes"]["pressure_equalization_required"]
                and h["attributes"]["fails_secure_under_differential"],
                f"pressure hatch operating rule lost: {h['id']}")

    require({e["space_id"] for e in sleeves} ==
            {f"BR-{n:02d}" for n in range(1, 9)},
            "bridge sleeve installed in wrong pressure zone")
    require(set(tasks["MT-BRIDGE-SLEEVE"]["equipment_ids"]) ==
            {e["id"] for e in sleeves},
            "bridge maintenance still targets a room rather than equipment")
    require(all(not any(token == f"HAB-{n:02d}" for token in edge["route_spaces"]
                        for n in range(1, 9))
                for edge in edges.values()),
            "unresolved habitation-group placeholder in utility route")

    ls = candidate["life_support_contract"]
    require(ls["protected_people_per_train"] == 40
            and set(ls["train_ids"]) == {"ECLSS-A", "ECLSS-B"},
            "forty-person full-train redundancy lost")
    reserve = [e for e in equips.values() if e["kind"] == "oxygen_bank"]
    reserve_kg = sum(e["attributes"]["oxygen_kg"] for e in reserve)
    require(len(reserve) == 10 and isclose(reserve_kg, 249.2, abs_tol=0.001)
            and isclose(reserve_kg, ls["protected_oxygen_total_kg"], abs_tol=0.001),
            "protected O2 stock double-counted or deficient")
    refuge = [e for e in equips.values() if e["kind"] == "emergency_life_support"]
    require(len(refuge) == 2 and all(e["attributes"]["people"] == 40
            and e["attributes"]["duration_h"] == 72 for e in refuge),
            "forty-person refuge plan changed")
    craft = [e for e in equips.values() if e["kind"] == "survival_craft_life_support"]
    require(len(craft) == 2 and all(e["attributes"]["people"] == 40
            and e["attributes"]["duration_days"] == 30 for e in craft),
            "deep survival-craft layer changed")

    # The operating ECLSS trains own two different processes:
    # oxygen must actually be replaced and captured CO2 must have a
    # regeneration/disposal path. These are not duplicates of bottled O2.
    o2 = [e for e in equips.values() if e["kind"] == "oxygen_generation_skid"]
    co2 = [e for e in equips.values() if e["kind"] == "carbon_dioxide_recovery_skid"]
    require(len(o2) == len(co2) == 2, "normal gas production/removal absent")
    require({e["attributes"]["host_train_id"] for e in o2} ==
            {"ECLSS-A", "ECLSS-B"}, "oxygen unit misassigned")
    require({e["attributes"]["host_train_id"] for e in co2} ==
            {"ECLSS-A", "ECLSS-B"}, "CO2 scrubber unit misassigned")
    require(all(e["attributes"]["oxygen_capacity_kg_day"] >= 35.6
                and e["attributes"]["requires_oxygen_purity_proof"]
                and e["attributes"]["requires_hydrogen_byproduct_safe_path"]
                for e in o2),
            "normal oxygen replacement insufficient or unverified")
    require(all(e["attributes"]["carbon_dioxide_capacity_kg_day"] >= 43.2
                and e["attributes"]["requires_regeneration_or_receiving_route"]
                for e in co2),
            "CO2 regeneration/disposal insufficient or unverified")
    water_budget = ls["makeup_water_730day_planning_split_t"]
    require(isclose(sum(water_budget.values()), 162.0, abs_tol=0.002),
            "normal 162 t makeup water allocations do not balance")
    require(isclose(water_budget["domestic_unrecovered_t"], 73,
                    abs_tol=0.001),
            "domestic water recovery math lost")
    require(isclose(water_budget["oxygen_electrolysis_feed_t"],
                    (40 * 0.89 * 730 / 1000 * 18/16),
                    abs_tol=0.002),
            "O2 electrolysis water feed inconsistent")
    mass = candidate["mass"]
    require(sum(mass["dry_allocations_t"].values()) == mass["dry_t"],
            "dry mass allocation lost reconciliation")
    expected_departure = (
        mass["dry_t"] + mass["commercial_cargo_t"] +
        mass["FTL_fuel_t"] + mass["sublight_reaction_mass_t"] +
        mass["mission_and_nonpropulsive_fluids_t"]
    )
    require(expected_departure == mass["reference_departure_t"],
            "departure mass no longer balanced")
    require(candidate["principal"]["hab_tangent_ring_span_deg"] == 38,
            "B-prime selected 38-degree arc geometry was changed")
    hab = candidate.get("habitation_support_contract", {})
    require(hab.get("selection", "").startswith("B-prime"),
            "selected B-prime support architecture missing")
    geometry = hab.get("geometry", {})
    require(geometry.get("arc_count") == 8
            and geometry.get("arc_sweep_deg") == 38
            and geometry.get("arc_pitch_deg") == 45
            and geometry.get("angular_gap_deg") == 7,
            "B-prime requires eight independent 38-degree arcs at 45-degree pitch")
    support = hab.get("load_path", {})
    require(support.get("saddles_per_arc") == 3
            and support.get("total_saddles") == 24
            and support.get("keyed_centre_saddles") == 8
            and support.get("sliding_outer_saddles") == 16
            and support.get("outer_branches_per_saddle") == 3
            and support.get("total_outer_branches") == 48,
            "B-prime keyed centre / sliding multi-branch support count changed")
    equipment_registry = hab.get("equipment_realisation", {})
    require(len(equipment_registry.get("keyed_centre_ids", [])) == 8
            and len(equipment_registry.get("sliding_outer_ids", [])) == 16
            and len(equipment_registry.get("bridge_spool_ids", [])) == 8
            and len(equipment_registry.get("indexer_carriers", [])) == 2
            and len(equipment_registry.get("pressure_capture_collars", [])) == 4,
            "B-prime installed equipment registry incomplete")
    require(all(e in equips for ids in equipment_registry.values()
                for e in ids), "B-prime registry points to missing equipment")
    require(candidate["design_closure_v05"]["maintenance_coverage"]
            ["equipment_with_at_least_one_task"] == len(equips),
            "B-prime maintenance coverage record does not match installed equipment")
    require(isclose(geometry.get("head_pressure_port_to_port_distance_m", 0),
                    4.281834, abs_tol=0.01)
            and isclose(geometry.get("replaceable_bridge_spool_length_m", 0),
                        3.581834, abs_tol=0.01),
            "B-prime 38-degree bridge-head mechanical datums inconsistent")
    require("non-clamping" in support.get("retainer_rule", ""),
            "B-prime outer retainers must not clamp ordinary thermal motion")
    head = hab.get("arc_end", {})
    require(head.get("leaf_opens", "").startswith("inward")
            and head.get("dog_count") == 16
            and head.get("seal", "").startswith("fitted")
            and head.get("opening_motions") == [
                "withdraw inward 0.120 m", "swing leaf inward through 90 degrees"
            ], "B-prime pressure-seated inward hatch operating rule lost")
    bridges = hab.get("interarc_bridges", {})
    require(bridges.get("number") == 8
            and bridges.get("independent_pressurised_bridge_volumes")
            and bridges.get("normal_relative_service_travel_mm") == 125
            and bridges.get("emergency_translation_envelope_mm") == 450,
            "independent pressure bridge and failure travel boundaries lost")
    require(hab.get("transfers", {}).get("habitation_indexer_count") == 2,
            "dual independent habitation indexers missing")
    require(isclose(geometry.get("gap_chord_m", 0),
                    2*geometry["centreline_radius_m"] *
                    sin(geometry["angular_gap_deg"]*pi/360),
                    abs_tol=0.01),
            "B-prime bridge geometric gap inconsistent")
    radius = candidate["principal"]["hab_shell_centreline_radius_m"]
    d_inner = candidate["principal"]["hab_pressure_section_internal_diameter_m"]
    arc_angle = candidate["principal"]["hab_tangent_ring_span_deg"]
    arc_volume = 8 * pi * (d_inner / 2)**2 * (2*pi*radius*arc_angle/360)
    tubes = 950*pi/4*(5.5**2+2*3**2)
    record = candidate["design_closure_v05"]["capacity_checks"]
    require(abs(record["combined_gross_tube_envelopes_m3"] -
                (arc_volume+tubes)) < 1.0,
            "geometric pressure-volume reference does not balance")
    require(abs(record["bridge_centerline_gap_m"] -
                2*radius*sin((45-arc_angle)*pi/360)) < 0.01,
            "bridge gap reference inconsistent")
    require("UNRESOLVED" in record["net_gas_volume_status"],
            "gross tube geometry misrepresented as pressure gas inventory")

    return {
        "habitation_support": "B-prime 38deg",
        "outer_saddle_branches": 48,
        "food_departure_t": food["nominal_mass_t"],
        "normal_oxygen_generators": len(o2),
        "normal_CO2_regenerators": len(co2),
        "spaces": len(spaces), "physical_links": len(links),
        "equipment": len(equips), "maintenance_groups": len(tasks),
        "maintained_equipment": len(covered),
        "service_edges": len(edges), "isolation_points": len(isos),
        "sled_radial_clearance_m": round(clearance, 3),
        "gross_tube_envelopes_m3": round(arc_volume+tubes),
        "protected_O2_kg": reserve_kg,
    }


def negative_regressions(base: dict, source: dict) -> None:
    cases = [
        ("oversize sled", lambda m: m["transit_contract"]["heavy_logistics_trunk"]
         .update(sled_envelope_m=[4.2, 4.2, 8])),
        ("lost service route", lambda m: m["service_edges"][0]
         .update(route_spaces=["HAB-01"])),
        ("missing work target", lambda m: m["maintenance_tasks"][0]
         .update(equipment_ids=["SOMETHING-THAT-IS-NOT-EQUIPMENT"])),
        ("invalid refit era", lambda m: m["modifications"][0]
         .update(era="ERA-LIFE-EXTENSION")),
        ("wrong oxygen", lambda m: m["equipment"][next(i for i, e in
         enumerate(m["equipment"]) if e["id"] == "HAB-04-REFUGE-O2")]
         ["attributes"].update(oxygen_kg=1)),
        ("removed hatch", lambda m: m["equipment"].remove(next(
         e for e in m["equipment"] if e["kind"] == "arc_end_pressure_hatch"))),
        ("missing food stores", lambda m: m["inventories"].pop()),
        ("undersized oxygen production", lambda m: m["equipment"][next(
         i for i, e in enumerate(m["equipment"])
         if e["id"] == "ECLSS-A-O2-GEN")]["attributes"]
         .update(oxygen_capacity_kg_day=20)),
        ("unbalanced water budget", lambda m: m["life_support_contract"]
         ["makeup_water_730day_planning_split_t"].update(
         cultivation_and_food_process_t=999)),
        ("wrong arc selection", lambda m: m["habitation_support_contract"]
         ["geometry"].update(arc_sweep_deg=41)),
        ("lost redundant outer branches", lambda m: m["habitation_support_contract"]
         ["load_path"].update(outer_branches_per_saddle=1)),
        ("trunk zones collapsed", lambda m: m["spaces"][next(i for i, space
         in enumerate(m["spaces"]) if space["id"] == "TRUNK-A-DR-01")]
         .update(pressure_zone="PZ-TRUNK-A-BOW")),
        ("refuge cupboard mistaken for refuge", lambda m: m["life_support_contract"]
         ["refuge_occupancy_contract"].update(whole_arc_used_for_people=False)),
        ("wrong pressure-hatch opening", lambda m: m["habitation_support_contract"]
         ["arc_end"].update(leaf_opens="outward")),
    ]
    for title, inject in cases:
        mutated = deepcopy(base)
        inject(mutated)
        try:
            validate(mutated, source)
        except ValueError:
            continue
        raise AssertionError(f"negative regression wrongly accepted: {title}")


if __name__ == "__main__":
    source = load(SOURCE)
    candidate = load(CANDIDATE)
    print(json.dumps(validate(candidate, source), indent=2, sort_keys=True))
    negative_regressions(candidate, source)
    print("OX_V05_DESIGN_CANDIDATE_AND_FOURTEEN_NEGATIVE_REGRESSIONS_PASS")
