#!/usr/bin/env python3
"""B-prime spatial/operational mechanics integrity checks (stdlib only).

This independently checks the selected 38-degree *simulation* layout, not
fabrication FEA, certified pressure boundaries or finite-element stresses.

Run: python design/ship/check_bprime_mechanics.py
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from math import cos, hypot, isclose, pi, radians, sin
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MECHANICS = ROOT / "hab_bprime_mechanical_interfaces_v0.5.json"
SHIP = ROOT / "ox_full_ship_v0.5_candidate.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique(records: list[dict], label: str) -> dict:
    index = {record["id"]: record for record in records}
    check(len(index) == len(records), f"duplicated {label} ID")
    return index


def point(theta: float, radius: float) -> tuple[float, float]:
    return radius * cos(radians(theta)), radius * sin(radians(theta))


def tangent(theta: float) -> tuple[float, float]:
    return -sin(radians(theta)), cos(radians(theta))


def head_port(theta: float, sign: int, radius: float) -> tuple[float, float]:
    py, pz = point(theta, radius + 0.75)
    dy, dz = tangent(theta)
    return py + sign * 2.375 * dy, pz + sign * 2.375 * dz


def communities(bridges: list[dict], disabled: set[str]) -> list[set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for i in range(1, 9):
        adj[f"HAB-{i:02d}"]
    for b in bridges:
        if b["id"] in disabled:
            continue
        a, z = b["from_arc_id"], b["to_arc_id"]
        adj[a].add(z)
        adj[z].add(a)
    result = []
    pending = set(adj)
    while pending:
        start = pending.pop()
        seen = {start}
        queue = [start]
        for node in queue:
            for neighbour in adj[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    pending.discard(neighbour)
                    queue.append(neighbour)
        result.append(seen)
    return sorted(result, key=lambda group: sorted(group)[0])


def validate(ship: dict, model: dict) -> dict:
    support = ship["habitation_support_contract"]
    dimensions = model["authoritative_design"]
    check(support["selection"].startswith("B-prime"), "B-prime authority lost")
    check(support["geometry"]["arc_sweep_deg"] ==
          dimensions["span_deg"] == ship["principal"]["hab_tangent_ring_span_deg"] == 38,
          "wrong selected arc sweep")
    check(dimensions["pitch_deg"] == 45 and dimensions["gap_deg"] == 7,
          "wrong pitch/separation")
    check(dimensions["legacy_41_deg_status"].startswith("SUPERSEDED"),
          "old 41-degree trial given design authority")

    arcs = unique(model["arcs"], "arc")
    saddles = unique(model["saddles"], "saddle")
    branches = unique(model["outer_branches"], "outer strut")
    bridges = unique(model["bridges"], "bridge")
    equipment = unique(ship["equipment"], "installed equipment")
    spaces = unique(ship["spaces"], "space")
    tasks = unique(ship["maintenance_tasks"], "maintenance")
    check(len(arcs) == 8 and len(saddles) == 24
          and len(branches) == 48 and len(bridges) == 8,
          "incorrect B-prime subsystem counts")

    registry = support["equipment_realisation"]
    check(len(registry["keyed_centre_ids"]) == 8
          and len(registry["sliding_outer_ids"]) == 16
          and len(registry["bridge_spool_ids"]) == 8,
          "keyed/sliding/bridge installation counts changed")
    check({s["id"] for s in saddles.values() if s["kind"] == "keyed_centre"} ==
          set(registry["keyed_centre_ids"]), "keyed centres not installed")
    check({s["id"] for s in saddles.values() if s["kind"] == "sliding_outer"} ==
          set(registry["sliding_outer_ids"]), "thermal sliding stations not installed")
    check(all(len(a["saddle_ids"]) == 3 for a in arcs.values()),
          "not all arcs have three saddle stations")
    check(all(len(s["branch_ids"]) == 3 for s in saddles.values()
              if s["kind"] == "sliding_outer"), "three outer members absent")

    ring_joints = set()
    for brace in branches.values():
        saddle = saddles[brace["saddle_id"]]
        check(saddle["kind"] == "sliding_outer",
              "outer structural member accidentally mounted at keyed centre")
        check(brace["id"] in saddle["branch_ids"],
              "strut no longer points to parent saddle")
        ring = brace["terminal_joint_id"]
        check(ring not in ring_joints, "multiple supports collapse onto one ring node")
        ring_joints.add(ring)
        root = brace["origin_xyz_m"]
        end = brace["terminal_ring_xyz_m"]
        actual_length = sum((a-b)**2 for a, b in zip(root, end))**0.5
        check(isclose(actual_length, brace["length_m"], abs_tol=0.00001),
              "structural endpoint geometry/length mismatch")
        shell_r = hypot(root[1], root[2])
        section = brace["section_box_outer_m"]
        section_rad = hypot(*section)/2
        real_guard = shell_r - section_rad - 77.92
        check(real_guard > 0.4 and
              isclose(real_guard, brace["radial_guard_clearance_m"], abs_tol=0.00001),
              "B-prime structural beam intersects pressure-shell guard")
    for saddle in saddles.values():
        installed = equipment[saddle["id"]]
        expected_kind = ("hab_keyed_centre_saddle" if saddle["kind"] == "keyed_centre"
                         else "hab_sliding_outer_saddle")
        check(installed["kind"] == expected_kind, "wrong installed saddle type")
        check(installed["space_id"] == "EXT-CENTRAL",
              "cradle work route is not safely exterior")
        if saddle["kind"] == "sliding_outer":
            check(installed["attributes"]["can_clamp_normal_thermal_travel"] is False,
                  "normal shell expansion unlawfully clamped")
            check(set(installed["attributes"]["branch_ids"]) ==
                  set(saddle["branch_ids"]), "installed branch identity mismatch")
        else:
            check(installed["attributes"]["current_purpose"].startswith(
                  "single central circumferential"),
                  "centre/key reference role changed")

    R = 73.15
    for i in range(8):
        a = f"HAB-{i+1:02d}"
        z = f"HAB-{(i+1) % 8 + 1:02d}"
        bid = f"BR-{i+1:02d}"
        bridge = bridges[bid]
        check(bridge["from_arc_id"] == a and bridge["to_arc_id"] == z,
              f"{bid} attaches wrong neighbours")
        theta_a, theta_z = i*45 + 19, i*45 + 26
        end1 = head_port(theta_a, +1, R)
        end2 = head_port(theta_z, -1, R)
        gap = hypot(end1[0]-end2[0], end1[1]-end2[1])
        check(isclose(gap, bridge["port_datum_distance_m"], abs_tol=0.00001),
              f"{bid} bridge endpoints do not match selected 38-degree heads")
        check(3.5 < bridge["central_spool_nominal_length_m"] < 3.7,
              f"{bid} serviceable spool length not viable")
        check(isclose(gap - 2*bridge["collar_projected_length_m_each"],
                      bridge["central_spool_nominal_length_m"], abs_tol=0.00001),
              f"{bid} spool and two collars cannot fit between pressure heads")
        check(bridge["normal_relative_translation_travel_mm"] == 125 and
              bridge["emergency_translation_envelope_mm"] == 450,
              f"{bid} normal/failure bridge motion conflated")
        check(bridge["emergency_mode"].startswith("both end hatches closed"),
              f"{bid} fault movement incorrectly permits open passage")
        check(bridge["independent_pressure_zone_id"] == f"PZ-{bid}",
              f"{bid} independent pressure zone missing")
        item = equipment[bridge["spool_equipment_id"]]
        check(item["space_id"] == bid
              and item["attributes"]["casualty_excursion_permits_transit"] is False,
              f"{bid} pressure bridge not independently serviceable")
        for hid in (bridge["from_hatch_id"], bridge["to_hatch_id"]):
            hatch = equipment[hid]
            check(hatch["kind"] == "arc_end_pressure_hatch",
                  f"{bid}: missing independent arc-end hatch")
            check(hatch["attributes"]["normal_opening"].find("INTO arc") > 0,
                  f"{hid}: wrong opening direction")

    # 41-degree head endpoints leave < 0.5m between port datums; no
    # 3.58m spool could fit. Keep it explicitly superseded, not a choice.
    p41 = head_port(20.5, +1, R)
    q41 = head_port(24.5, -1, R)
    check(hypot(p41[0]-q41[0], p41[1]-q41[1]) < 0.5,
          "41-degree trial geometry no longer distinguished")

    indexers = unique(model["indexers"], "indexer")
    check(set(indexers) == {"IX-A", "IX-B"}, "dual independent indexers lost")
    for indexer in indexers.values():
        id = indexer["id"]
        installed = equipment[f"{id}-CARRIER"]
        check(indexer["carrier_trial_mass_t"] == 30
              and installed["attributes"]["reference_carrier_mass_t"] == 30,
              "B-prime 30-tonne carrier replaced by obsolete 12t trial")
        check(indexer["minimum_bearing_axial_clearance_m"] >= 1.3,
              "indexer encroaches on a HAB support bearing plane")
        check(installed["attributes"]["independent_of_main_hab_rotor"],
              "indexer drive wrongly coupled to main HAB rotor")
        for side in ("FIXED", "ROT"):
            collar = equipment[f"{id}-{side}-COLLAR"]
            check(collar["attributes"]["pressure_equalization_required"],
                  "indexer collar opens without pressure proof")
            check(collar["attributes"]["forced_motion_with_collars_extended_interlocked"],
                  "indexer can rotate with extended collar")

    check(set(registry["main_rotor_bearings"]) ==
          {"HAB-BEARING-FORE", "HAB-BEARING-AFT"},
          "main rotating bearing pair absent")
    check(set(registry["indexer_carriers"]) ==
          {"IX-A-CARRIER", "IX-B-CARRIER"},
          "carrier registry inconsistent")
    check(set(registry["pressure_capture_collars"]) ==
          {f"IX-{i}-{side}-COLLAR" for i in ("A", "B")
           for side in ("FIXED", "ROT")},
          "indexer collar registry incomplete")

    reachable = communities(model["bridges"], set())
    one_out = communities(model["bridges"], {"BR-01"})
    two_out = communities(model["bridges"], {"BR-01", "BR-03"})
    check(len(reachable) == 1 and len(one_out) == 1 and len(two_out) == 2,
          "B-prime circumferential damage-control detour rule broken")
    check(any(g == {"HAB-02", "HAB-03"} for g in two_out),
          "two bridge failures no longer strand a no-refuge arc group")
    check(all("HAB-04" not in g and "HAB-08" not in g
              for g in two_out if g == {"HAB-02", "HAB-03"}),
          "invalid refuge reachability interpretation")

    covered = {e for task in tasks.values() for e in task["equipment_ids"]}
    check(covered == set(equipment), "installed equipment lacks maintenance ownership")
    expected_mass = ship["design_closure_v05"]["habitation_mass_screen_t"]
    allowances = expected_mass["allowance_within_remaining_2895_t"]
    rem = 10500 - 3200 - 4404.9 - sum(allowances.values())
    check(isclose(rem, expected_mass["still_unallocated_hab_misc_services_t"],
                  abs_tol=0.001) and rem > 1500,
          "habitation rough mass screen violates dry-mass envelope")

    return {
        "B_prime_keyed_saddles": 8,
        "thermal_sliding_outer_saddles": 16,
        "physically_distinct_outer_branches": len(branches),
        "isolatable_pressure_bridges": len(bridges),
        "pressure_head_port_gap_m": bridges["BR-01"]["port_datum_distance_m"],
        "bridge_central_spool_m": bridges["BR-01"]["central_spool_nominal_length_m"],
        "independent_30t_carriers": len(indexers),
        "equipment_and_maintenance_coverage": len(covered),
        "single_bridge_out_components": len(one_out),
        "two_bridge_out_components": len(two_out),
    }


def negative_tests(ship: dict, design: dict) -> None:
    mutations = [
        ("keyed centre erased",
         lambda s, d: d["saddles"][1].update(kind="sliding_outer")),
        ("three branches collapse to one ring joint",
         lambda s, d: d["outer_branches"][1].update(
             terminal_joint_id=d["outer_branches"][0]["terminal_joint_id"])),
        ("structural beam guard pierced",
         lambda s, d: d["outer_branches"][0].update(
             radial_guard_clearance_m=-0.1)),
        ("wrong bridge endpoints",
         lambda s, d: d["bridges"][0].update(to_arc_id="HAB-05")),
        ("wrong carrier mass",
         lambda s, d: d["indexers"][0].update(carrier_trial_mass_t=12)),
        ("emergency motion made freely walkable",
         lambda s, d: d["bridges"][0].update(
             emergency_mode="remain open through any translation")),
        ("pressure test bypassed",
         lambda s, d: next(e for e in s["equipment"]
                           if e["id"] == "IX-A-ROT-COLLAR")["attributes"]
                           .update(pressure_equalization_required=False)),
        ("wrong mass balancing",
         lambda s, d: s["design_closure_v05"]["habitation_mass_screen_t"]
                           .update(still_unallocated_hab_misc_services_t=999999)),
    ]
    for title, mutate in mutations:
        s, d = deepcopy(ship), deepcopy(design)
        mutate(s, d)
        try:
            validate(s, d)
        except ValueError:
            continue
        raise AssertionError("negative test unexpectedly passed: " + title)


if __name__ == "__main__":
    ship, model = load(SHIP), load(MECHANICS)
    print(json.dumps(validate(ship, model), indent=2, sort_keys=True))
    negative_tests(ship, model)
    print("OX_BPRIME_38DEG_MECHANICS_AND_EIGHT_NEGATIVE_TESTS_PASS")
