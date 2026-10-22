#!/usr/bin/env python3
"""Check v0.5 physically isolatable pressure cells and gas-envelope accounting.

The outputs are geometrical upper envelopes, not calibrated free-air volume
or live Evennia atmospheric state. No external library or Evennia is required.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from math import isclose, pi
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATE = ROOT / "ox_full_ship_v0.5_candidate.json"
CELLS = ROOT / "pressure_zone_topology_v0.5.json"


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def validate(ship: dict, ledger: dict) -> dict:
    space = {s["id"]: s for s in ship["spaces"]}
    require(len(space) == len(ship["spaces"]) == 421, "space IDs duplicated/lost")
    pressure = {x["id"]: x for x in ledger["pressure_cells"]}
    require(len(pressure) == len(ledger["pressure_cells"]) == 133,
            "expected 133 separate pressure cells")
    volume_by_space: dict[str, list[str]] = defaultdict(list)
    vacuum, unknown = set(), set()
    for s in ship["spaces"]:
        zone = s.get("pressure_zone")
        if zone == "VACUUM":
            vacuum.add(s["id"])
        elif zone is None:
            unknown.add(s["id"])
        else:
            require(zone in pressure, f"unregistered real pressure volume {zone}")
            volume_by_space[zone].append(s["id"])
    require(vacuum == set(ledger["vacuum_space_ids"]) and len(vacuum) == 26,
            "vacuum equipment or exterior spaces incorrectly labelled")
    require(unknown == set(ledger["unassigned_pressure_zone_space_ids"])
            and len(unknown) == 83, "unresolved pressurization records silently invented")
    for id, group in pressure.items():
        require(sorted(group["space_ids"]) == sorted(volume_by_space[id]),
                f"pressure volume identity disagrees with world space: {id}")
        require(group["actual_usable_free_air_m3"] is None,
                f"gross envelope falsely represented as measured free gas: {id}")
        if group["classification"] == "sectional_personnel_trunk":
            require(len(group["space_ids"]) == 1 and
                    group["space_ids"][0].startswith(("TRUNK-A-", "TRUNK-B-")),
                    f"sectional crew trunk accidentally shared across segments: {id}")
            require(group["gross_reference_envelope_m3"] is not None,
                    f"missing crew tube gross volume: {id}")

    a = [x for x in pressure.values() if x["classification"] ==
         "sectional_personnel_trunk" and x["id"].startswith("PZ-TRUNK-A-")]
    b = [x for x in pressure.values() if x["classification"] ==
         "sectional_personnel_trunk" and x["id"].startswith("PZ-TRUNK-B-")]
    logi = [x for x in pressure.values() if x["classification"] ==
            "sectional_heavy_logistics_trunk"]
    arcs = [x for x in pressure.values() if x["classification"] ==
            "habitation_arc_with_two_ellipsoidal_halfheads"]
    bridges = [x for x in pressure.values() if x["classification"] ==
               "independent_interarc_pressure_bridge"]
    require((len(a), len(b), len(logi), len(arcs), len(bridges)) ==
            (23, 23, 23, 8, 8), "wrong tube/arc/bridge cell counts")

    # Each trunk is exactly one unbroken set of sealed axial intervals
    # covering x0..950 when doors are open, but never one huge gas cell.
    for physical in (a, b):
        segments = sorted(physical, key=lambda cell:
                          space[cell["space_ids"][0]]["location"]["x_m"][0])
        last = 0.0
        for row in segments:
            source = space[row["space_ids"][0]]
            x0, x1 = source["location"]["x_m"]
            require(isclose(x0, last, abs_tol=1e-7) and x1 > x0,
                    "trunk axial sections overlap or leave gaps")
            gross = pi * (3 / 2)**2 * (x1 - x0)
            require(isclose(gross, row["gross_reference_envelope_m3"],
                            abs_tol=1e-5),
                    "trunk gross cylindrical gas envelope inconsistent")
            last = x1
        require(isclose(last, 950.0, abs_tol=1e-7), "personnel trunk not 950m")

    # Every world pressure boundary must be a recorded inter-cell door.
    actual_doors = {door["id"]: door for door in ship["access_links"]
                    if door.get("pressure_boundary")}
    projected = {door["id"]: door for door in ledger["pressure_boundary_doors"]}
    require(len(actual_doors) == len(projected) == 208,
            "pressure-boundary count/reference mismatch")
    for id, door in actual_doors.items():
        record = projected[id]
        from_zone = space[door["from"]].get("pressure_zone")
        to_zone = space[door["to"]].get("pressure_zone")
        require(from_zone != to_zone and
                record["from_pressure_zone_id"] == from_zone and
                record["to_pressure_zone_id"] == to_zone,
                f"pressure-rated hatch has no actual isolation boundary: {id}")


    # A separate pressure zone requires an actual rated isolation closure;
    # this includes the nominally vacuum F1/F2 machinery enclosures.
    for door in ship["access_links"]:
        za = space[door["from"]].get("pressure_zone")
        zb = space[door["to"]].get("pressure_zone")
        if za is not None and zb is not None and za != zb:
            require(door.get("pressure_boundary") is True,
                    f"unrated door between pressure zones: {door['id']}")

    # Emergency refuge capacity occupies entire pressure arc, not cupboard.
    refuge = ship["life_support_contract"]["refuge_occupancy_contract"]
    require(refuge["whole_arc_used_for_people"] and
            refuge["protected_refuge_zone_ids"] == ["PZ-HAB-04", "PZ-HAB-08"],
            "refuge volume cannot hold the intended 40 people")
    require(all(space[s]["kind"] == "refuge_store" and
                space[s]["pressure_zone"] in refuge["protected_refuge_zone_ids"]
                for s in refuge["equipment_cupboard_space_ids"]),
            "small life-support equipment cupboard incorrectly used as separate refuge")
    for id in ("HAB-04-MED-ISO", "IX-A-FINAL-LIFT", "IX-B-FINAL-LIFT"):
        require(space[id]["pressure_zone"] == "PZ-" + id,
                f"independent protected pressure transition not isolateable: {id}")
    require(all(space[id]["pressure_zone"] == "VACUUM"
                for id in ("F1-BAY", "F2-BAY")),
            "flywheel machinery airlocks do not open to a defined vacuum compartment")

    gross = sum(cell["gross_reference_envelope_m3"] for cell in
                pressure.values() if cell["gross_reference_envelope_m3"] is not None)
    require(isclose(gross, ledger["totals"]["gross_reference_envelopes_m3"],
                    abs_tol=1e-4) and 68185 < gross < 68187,
            "gross geometric atmosphere envelope mass/volume mismatch")
    density = (ledger["gas_reference"]["pressure_Pa"] *
               ledger["gas_reference"]["gas_molar_mass_kg_mol"] /
               (8.314462618 * ledger["gas_reference"]["temperature_K"]))
    require(isclose(density,
                    ledger["gas_reference"]["calculated_dry_air_density_kg_m3"],
                    abs_tol=1e-6),
            "reference atmosphere ideal gas density inconsistent")
    require(isclose(gross * density,
                    ledger["totals"]["full_gross_reference_air_kg_20C"],
                    abs_tol=1e-3),
            "gas-envelope mass calculation inconsistent")
    require(len([c for c in pressure.values()
                 if c["gross_reference_envelope_m3"] is not None]) == 101,
            "unaccounted numerical gross-envelope sections")
    return {
        "distinct_pressure_cells": len(pressure),
        "pressure_rated_links": len(actual_doors),
        "crew_trunk_cells": len(a) + len(b),
        "logistics_cells": len(logi),
        "Bprime_arcs": len(arcs),
        "isolatable_interarc_bridges": len(bridges),
        "full_gross_envelope_m3_not_net": round(gross, 2),
        "gross_air_tonnes_at_20C_not_stored_reserve": round(gross * density / 1000, 3),
        "vacuum_rooms": len(vacuum),
        "pressure_status_unclassified_rooms": len(unknown),
    }


def negative_tests(ship: dict, design: dict) -> None:
    tests = [
        ("collapse two tube sections", lambda s, d:
         next(r for r in s["spaces"] if r["id"] == "TRUNK-A-DR-01")
         .update(pressure_zone="PZ-TRUNK-A-BOW")),
        ("medical room reconnects to main arc", lambda s, d:
         next(r for r in s["spaces"] if r["id"] == "HAB-04-MED-ISO")
         .update(pressure_zone="PZ-HAB-04")),
        ("bridge pressure identity altered", lambda s, d:
         next(r for r in s["spaces"] if r["id"] == "BR-01")
         .update(pressure_zone="PZ-HAB-01")),
        ("flywheel vacuum erased", lambda s, d:
         next(r for r in s["spaces"] if r["id"] == "F1-BAY")
         .update(pressure_zone=None)),
        ("gross volume misdeclared", lambda s, d:
         d["totals"].update(gross_reference_envelopes_m3=1)),
        ("fake measured net gas inventory", lambda s, d:
         d["pressure_cells"][0].update(actual_usable_free_air_m3=999)),
    ]
    for name, mutation in tests:
        s, d = deepcopy(ship), deepcopy(design)
        mutation(s, d)
        try:
            validate(s, d)
        except ValueError:
            continue
        raise AssertionError("pressure-cell negative regression wrongly accepted: " + name)


if __name__ == "__main__":
    s = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    g = json.loads(CELLS.read_text(encoding="utf-8"))
    print(json.dumps(validate(s, g), indent=2, sort_keys=True))
    negative_tests(s, g)
    print("OX_PRESSURE_CELL_MODEL_AND_SIX_NEGATIVE_TESTS_PASS")
