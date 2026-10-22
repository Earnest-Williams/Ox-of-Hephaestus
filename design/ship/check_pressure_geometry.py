#!/usr/bin/env python3
"""Independently verify nominal pressure volumes and isolation, without Evennia.

This is a physical design ledger, not measured free gas, rated fabrication, or a
simulation of live doors. The eight original arcs contain three NEW separately
isolateable subvolumes; they are not additional gas outside the arc shells.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from math import hypot, isclose, pi
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARC_PHYSICAL_GROSS_M3 = 3663.303551
NEW_SELECTED = {
    "PZ-HAB-04-MED-ISO",
    "PZ-IX-A", "PZ-IX-B",
    "PZ-IX-A-FINAL-LIFT", "PZ-IX-B-FINAL-LIFT",
}

def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))

def need(valid: bool, msg: str) -> None:
    if not valid:
        raise ValueError(msg)

def rect_box(s: dict):
    g, l = s.get("geometry") or {}, s.get("location") or {}
    if g.get("shape") not in ("box", "transfer_lock"):
        return None
    if not isinstance(l.get("x_m"), list):
        return None
    w = g.get("width_m", g.get("clear_width_m"))
    h = g.get("height_m", g.get("clear_height_m"))
    if w is None or h is None or l.get("y_m") is None or l.get("z_m") is None:
        return None
    return ((l["x_m"][0], l["x_m"][1]),
            (l["y_m"]-w/2, l["y_m"]+w/2),
            (l["z_m"]-h/2, l["z_m"]+h/2))

def intersection(a, b) -> float:
    if a is None or b is None:
        return 0.0
    v = 1.0
    for i in range(3):
        v *= max(0.0, min(a[i][1], b[i][1])
                 - max(a[i][0], b[i][0]))
    return v

def new_selected_volume(s: dict) -> float:
    g = s.get("geometry") or {}
    if s["id"] == "HAB-04-MED-ISO":
        need(g.get("shape") == "arc_cabin"
             and g.get("includes_host_arc_gross_envelope") is True,
             "medical isolation omitted from parent arc")
        need(s["net_area_m2"] == 25
             and g.get("tangential_length_m") == 5
             and g.get("axial_width_m") == 5
             and g.get("clear_height_m") == 2.7
             and g.get("radius_m") == 73.15,
             "medical isolation dimensions changed")
        return 25 * 2.7
    if s["id"] in ("IX-A-CAPSULE", "IX-B-CAPSULE"):
        need(g.get("shape") == "capsule"
             and g.get("length_m") == 4.6
             and g.get("diameter_m") == 2.6
             and g.get("nominal_seated_occupants") == 4,
             "indexer capsule altered without envelope review")
        need(g.get("reference_orbit_radius_m") == 10.5
             and g.get("hardware_envelope_x_halfwidth_m") == 3.9
             and g["length_m"]/2 < 3.9
             and 10.5 - 1.3 >= 8.55
             and 10.5 + 1.3 <= 12.5313906484,
             "indexer gas cabin outside moving carrier guard")
        return pi * (g["diameter_m"] / 2) ** 2 * g["length_m"]
    if s["id"] in ("IX-A-FINAL-LIFT", "IX-B-FINAL-LIFT"):
        need(g.get("shape") == "pressure_lift_car"
             and g.get("length_m") == 3
             and g.get("clear_diameter_m") == 2.6
             and g.get("nominal_seated_occupants") == 4
             and g.get("belongs_within_host_arc_gross_envelope") is True,
             "lift not isolated within host habitation pressure shell")
        return pi * (g["clear_diameter_m"]/2) ** 2 * g["length_m"]
    raise ValueError("unknown new gas-space designation: " + s["id"])


DRUM_LOCKS = {f"PZ-DR-{n:02d}-LOCK" for n in range(1, 7)}


def indexed_drum_lock_volume(ship: dict, s: dict) -> float:
    """Screen nominal fixed lock cylinders; ignore unmeasured station necks."""
    q, loc = s["geometry"], s["location"]
    need(s["id"].startswith("DR-") and s["id"].endswith("-SERVICE-LOCK")
         and s["frame"] == "fixed" and q["shape"] == "transfer_lock"
         and q["length_m"] == 5 and q["clear_diameter_m"] == 2.3,
         "indexed service lock envelope or frame altered")
    need(loc["x_m"][1]-loc["x_m"][0] == 5
         and loc["y_m"] == 5.4 and loc["z_m"] == -3.7,
         "unreviewed indexed lock centre position")
    radius = q["clear_diameter_m"]/2
    need(8-hypot(loc["y_m"],loc["z_m"])-radius >= .25,
         "indexed lock intrudes into nominal fixed hull envelope")
    station = s["id"][3:5]
    spaces = {x["id"]: x for x in ship["spaces"]}
    trunk = spaces[f"TRUNK-A-DR-{station}"]
    dist = hypot(loc["y_m"]-trunk["location"]["y_m"],
                 loc["z_m"]-trunk["location"]["z_m"])
    neck = dist-radius-trunk["geometry"]["clear_diameter_m"]/2
    need(.9 <= neck <= 1.4, "inboard station-side connector gap invalid")
    doors = {x["id"]: x for x in ship["access_links"]}
    fixed = doors[f"ACC-DR-{station}-LOCK-FIX"]
    rotary = doors[f"ACC-DR-{station}-LOCK-ROT"]
    need(fixed["from"] == f"TRUNK-A-DR-{station}" and fixed["to"] == s["id"]
         and rotary["from"] == s["id"] and rotary["to"] == f"DR-{station}-HUB"
         and fixed["pressure_boundary"] and rotary["pressure_boundary"]
         and fixed["isolatable"] and rotary["isolatable"]
         and fixed["normal_state"] == rotary["normal_state"] == "closed",
         "indexed lock lacks two normally-shut rated boundaries")
    for other in ship["spaces"]:
        if other["id"] == s["id"] or other.get("pressure_zone") in (None,"VACUUM"):
            continue
        ol, og = other.get("location") or {}, other.get("geometry") or {}
        x = ol.get("x_m")
        if not isinstance(x,list):
            if not isinstance(x,(int,float)) or "length_m" not in og:
                continue
            x = [x-og["length_m"]/2,x+og["length_m"]/2]
        if min(loc["x_m"][1],x[1])-max(loc["x_m"][0],x[0]) <= 0:
            continue
        if "y_m" not in ol or "z_m" not in ol:
            continue # Receiving drum galleries still require their own geometry.
        clear = None
        if og.get("shape") in ("tube","cylinder","capsule") or (
           og.get("shape") == "transfer_lock" and "clear_diameter_m" in og):
            dia = og.get("clear_diameter_m",og.get("diameter_m"))
            if dia is not None:
                clear = hypot(loc["y_m"]-ol["y_m"],loc["z_m"]-ol["z_m"])-radius-dia/2
        elif og.get("shape") == "box" or (
             og.get("shape") == "transfer_lock" and "clear_width_m" in og):
            width=og.get("width_m",og.get("clear_width_m"))
            height=og.get("height_m",og.get("clear_height_m"))
            if width is not None and height is not None:
                dy=max(ol["y_m"]-width/2-loc["y_m"],0,loc["y_m"]-ol["y_m"]-width/2)
                dz=max(ol["z_m"]-height/2-loc["z_m"],0,loc["z_m"]-ol["z_m"]-height/2)
                clear=hypot(dy,dz)-radius
        if clear is not None:
            need(clear >= .20, "indexed service lock overlaps "+other["id"])
    return pi*radius*radius*q["length_m"]

def validate(ship: dict, pressure: dict, gas: dict, audit: dict) -> dict:
    rooms = {x["id"]:x for x in ship["spaces"]}
    cells = {x["id"]:x for x in pressure["pressure_cells"]}
    rows = {x["pressure_zone_id"]:x for x in gas["sized_and_unsized_pressure_cells"]}
    need(len(rooms)==421 and len(cells)==133 and len(rows)==133,
         "lost physical gas zones")
    prior = audit["prior_unsized_pressure_cell_ids"]
    selected = set(audit["accepted_zone_ids"])
    need(len(prior)==48 and len(set(prior))==48
         and len(audit["cells"])==48
         and len(selected)==22
         and selected <= set(prior),
         "geometry audit omits or invents pressure cells")
    need(Counter(x["status"] for x in audit["cells"]) == {
        "accepted_nominal_envelope": 11,
        "selected_internal_pressure_geometry": 5,
        "selected_indexed_service_lock_envelope": 6,
        "on_hold": 26
    }, "unreviewed geometric admission")
    need({x["pressure_zone_id"] for x in audit["cells"]
          if x["status"] == "selected_internal_pressure_geometry"} == NEW_SELECTED,
         "unreviewed passenger/medical sizing")
    for entry in audit["cells"]:
        zid=entry["pressure_zone_id"]
        need(zid in cells and entry["space_ids"]==cells[zid]["space_ids"],
             "pressure-cell members were lost")
        if zid not in selected:
            need(cells[zid]["gross_reference_envelope_m3"] is None
                 and entry["additive_reference_gross_m3"] is None
                 and len(entry["blockers"])>0,
                 "unreconciled geometry counted as spare air: "+zid)
            continue
        constituent=[rooms[k] for k in entry["space_ids"]]
        if zid in DRUM_LOCKS:
            need(len(constituent)==1, "indexed lock contains other rooms")
            volume=indexed_drum_lock_volume(ship,constituent[0])
        elif zid in NEW_SELECTED:
            need(len(constituent)==1, "new passenger cabin has multiple geometries")
            volume=new_selected_volume(constituent[0])
        else:
            volume=0.0
            for s in constituent:
                g=s.get("geometry") or {}
                box=rect_box(s)
                need(box is not None and g.get("shape") in ("box","transfer_lock"),
                     "admitted source box lacks placement")
                need(isclose(g["length_m"],box[0][1]-box[0][0],abs_tol=1e-8),
                     "authored compartment length disagrees with axial interval")
                width=g.get("width_m",g.get("clear_width_m"))
                height=g.get("height_m",g.get("clear_height_m"))
                volume+=g["length_m"]*width*height
                for other in ship["spaces"]:
                    if other["id"]==s["id"] or other.get("pressure_zone") is None:
                        continue
                    need(intersection(box,rect_box(other))<1e-8,
                         "gross envelope overlaps another registered pressure room: "
                         +s["id"]+"/"+other["id"])
                    og=other.get("geometry") or {}
                    if other["pressure_zone"] != zid and og.get("shape")=="tube":
                        al=other.get("location") or {}
                        if not isinstance(al.get("x_m"),list):
                            continue
                        span=max(0.0,min(box[0][1],al["x_m"][1])
                                 -max(box[0][0],al["x_m"][0]))
                        dy=max(box[1][0]-al["y_m"],0,al["y_m"]-box[1][1])
                        dz=max(box[2][0]-al["z_m"],0,al["z_m"]-box[2][1])
                        need(span<=1e-8 or
                             hypot(dy,dz)>=og["clear_diameter_m"]/2-1e-8,
                             "gross box intrudes into pressure trunk: "+s["id"])
        need(isclose(volume,cells[zid]["gross_reference_envelope_m3"],abs_tol=1e-5)
             and isclose(volume,entry["additive_reference_gross_m3"],abs_tol=1e-5),
             "source volume and pressure ledger disagree: "+zid)
        need(rows[zid]["verified_as_installed_free_gas_m3"] is None,
             "design reference misrepresented as measured air")
    for host,children in (
        ("PZ-HAB-04",("PZ-HAB-04-MED-ISO","PZ-IX-A-FINAL-LIFT")),
        ("PZ-HAB-08",("PZ-IX-B-FINAL-LIFT",)),
    ):
        actual=cells[host]["gross_reference_envelope_m3"]
        sub=sum(cells[z]["gross_reference_envelope_m3"] for z in children)
        need(isclose(actual+sub,ARC_PHYSICAL_GROSS_M3,abs_tol=2e-6),
             "nested pressurised room counted twice in host "+host)
    transfers=ship["transit_contract"]["inter_drum_transfer"]
    reference=transfers["freight_lock_reference"]
    need(reference["clear_length_m"]==12 and reference["sled_length_m"]==8
         and reference["fore_and_aft_end_clearance_m_each"]==2,
         "reintroduced eight-metre lock around eight-metre sled")
    for n in range(1,7):
        g=rooms[f"DR-{n:02d}-FREIGHT-LOCK"]["geometry"]
        need(g["length_m"]>=reference["sled_length_m"] +
             2*reference["fore_and_aft_end_clearance_m_each"] and
             g["clear_width_m"]==4.6 and g["clear_height_m"]==4.6,
             "freight lock cannot contain a fully secured sled")
    actual_doors={x["id"] for x in ship["access_links"]
                  if x.get("pressure_boundary")}
    registered={x["id"] for x in pressure["pressure_boundary_doors"]}
    need(len(actual_doors)==len(registered)==208 and actual_doors==registered,
         "pressure boundary registry incomplete")
    for edge in ship["access_links"]:
        a,b=rooms[edge["from"]].get("pressure_zone"),rooms[edge["to"]].get("pressure_zone")
        need(a is None or b is None or a==b or edge["pressure_boundary"],
             "unrated door between independently isolated pressure volumes: "+edge["id"])
    need(sum(c["gross_reference_envelope_m3"] is not None for c in cells.values())==107,
         "incorrect pressure sizing count")
    need(gas["totals"]["unsized_pressurized_cells"]==26
         and pressure["totals"]["pressure_boundary_doors"]==208,
         "gas/boundary totals stale")
    need(all(c["actual_usable_free_air_m3"] is None for c in cells.values()),
         "gas inventory has been falsely represented as measured")
    return {
        "sized_pressure_cells":107, "unsized_pressure_cells":26,
        "rated_pressure_boundaries":208,
        "gross_reference_m3":pressure["totals"]["gross_reference_envelopes_m3"],
        "nested_arc_child_displacements_checked":3,
        "freight_lock_sled_end_clearance_m_each":2
    }

def negative_tests(ship, pressure, gas, audit):
    def reject(edit):
        values=deepcopy((ship,pressure,gas,audit))
        edit(*values)
        try:
            validate(*values)
        except ValueError:
            return
        raise AssertionError("deliberately invalid pressure geometry was accepted")
    reject(lambda s,p,g,a: next(x for x in p["pressure_cells"]
           if x["id"]=="PZ-HAB-04").update(gross_reference_envelope_m3=ARC_PHYSICAL_GROSS_M3))
    reject(lambda s,p,g,a: next(x for x in s["access_links"]
           if x["id"]=="ACC-IX-A-FINAL").update(pressure_boundary=False))
    reject(lambda s,p,g,a: next(x for x in s["access_links"]
           if x["id"]=="ACC-LOGI-F1-BAY").update(pressure_boundary=False))
    reject(lambda s,p,g,a: next(x for x in s["spaces"]
           if x["id"]=="DR-02-FREIGHT-LOCK")["geometry"].update(length_m=8))
    reject(lambda s,p,g,a: next(x for x in s["spaces"]
           if x["id"]=="IX-A-CAPSULE")["geometry"].update(length_m=9))
    reject(lambda s,p,g,a: next(x for x in g["sized_and_unsized_pressure_cells"]
           if x["pressure_zone_id"]=="PZ-HAB-04-MED-ISO").update(verified_as_installed_free_gas_m3=67.5))
    reject(lambda s,p,g,a: next(x for x in a["cells"]
           if x["pressure_zone_id"]=="PZ-AFT-STORES").update(status="accepted_nominal_envelope"))
    reject(lambda s,p,g,a: next(x for x in s["spaces"]
           if x["id"]=="ELEC-FWD")["location"].update(z_m=0))
    reject(lambda s,p,g,a: next(x for x in s["spaces"]
           if x["id"]=="DR-01-SERVICE-LOCK")["location"].update(y_m=4.5,z_m=-1.5))
    reject(lambda s,p,g,a: next(x for x in s["spaces"]
           if x["id"]=="DR-02-SERVICE-LOCK")["geometry"].update(clear_diameter_m=3.8))
    reject(lambda s,p,g,a: next(x for x in s["access_links"]
           if x["id"]=="ACC-DR-03-LOCK-ROT").update(normal_state="open"))
    reject(lambda s,p,g,a: next(x for x in p["pressure_cells"]
           if x["id"]=="PZ-DR-04-LOCK").update(gross_reference_envelope_m3=1))

if __name__=="__main__":
    models=[load(n) for n in (
        "ox_full_ship_v0.5_candidate.json",
        "pressure_zone_topology_v0.5.json",
        "pressure_gas_recovery_v0.5.json",
        "pressure_geometry_reconciliation_v0.5.json"
    )]
    print(json.dumps(validate(*models),sort_keys=True,indent=2))
    negative_tests(*models)
    print("OX_PRESSURE_GEOMETRY_AND_TWELVE_NEGATIVE_TESTS_PASS")
