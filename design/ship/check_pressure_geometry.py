#!/usr/bin/env python3
"""Ox v0.5 physical gross-envelope and complete fixed/rotary geometry closure.

Design-screen geometry, not as-installed measured free air or fabrication FEA.
All 133 distinct pressure cells get an independently recomputed reference.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from math import hypot, isclose, pi
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ARC_SHELL_M3 = 3663.303551
ORIGINAL_SELECTED = {
    "PZ-BOW-SVC",
    *(f"PZ-DR-{i:02d}-FREIGHT" for i in range(1, 7)),
    "PZ-XCON-GAP-12", "PZ-XCON-GAP-23",
    "PZ-XCON-GAP-45", "PZ-XCON-GAP-56",
}
DRUM_LOCKS = {f"PZ-DR-{i:02d}-LOCK" for i in range(1, 7)}
MEDICAL_AND_INDEXERS = {
    "PZ-HAB-04-MED-ISO", "PZ-IX-A", "PZ-IX-B",
    "PZ-IX-A-FINAL-LIFT", "PZ-IX-B-FINAL-LIFT",
}
EXPECTED_STATUS = {
    "accepted_nominal_envelope": 11,
    "selected_internal_pressure_geometry": 5,
    "selected_indexed_service_lock_envelope": 6,
    "selected_collision_screened_fixed_room_boxes": 11,
    "selected_rotating_drum_pressure_annuli": 6,
    "selected_wr_annular_hub": 1,
    "selected_wr_indexer_capsule": 1,
    "selected_distinct_rotor_pods": 2,
    "selected_bounded_telescopic_gas_passage": 2,
    "selected_external_over_spine_connector": 3,
}


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def need(condition, description):
    if not condition:
        raise ValueError(description)


def close(a, b, tolerance=1e-5) -> bool:
    return isclose(a, b, rel_tol=0, abs_tol=tolerance)


def rectangle(room):
    g, l = room.get("geometry") or {}, room.get("location") or {}
    if g.get("shape") not in ("box", "transfer_lock") or not isinstance(l.get("x_m"), list):
        return None
    w, h = g.get("width_m", g.get("clear_width_m")), g.get("height_m", g.get("clear_height_m"))
    if w is None or h is None or not all(k in l for k in ("y_m", "z_m")):
        return None
    need(close(l["x_m"][1]-l["x_m"][0], g["length_m"]),
         "room axial extent does not match dimensions: " + room["id"])
    return (l["x_m"], (l["y_m"]-w/2, l["y_m"]+w/2),
            (l["z_m"]-h/2, l["z_m"]+h/2))


def tube(room):
    g, l = room.get("geometry") or {}, room.get("location") or {}
    if g.get("shape") not in ("tube", "transfer_lock") or not isinstance(l.get("x_m"), list):
        return None
    d = g.get("clear_diameter_m")
    if d is None or not all(k in l for k in ("y_m", "z_m")):
        return None
    need(close(l["x_m"][1]-l["x_m"][0], g["length_m"]),
         "pressure-tube axial mismatch: " + room["id"])
    return (l["x_m"], l["y_m"], l["z_m"], d/2)


def transverse_penetration(a, b):
    # a and b are (kind, space, source id) triples.
    if min(a[1][0][1], b[1][0][1]) <= max(a[1][0][0], b[1][0][0]):
        return 0
    if a[0] == b[0] == "box":
        ay, az, by, bz = a[1][1], a[1][2], b[1][1], b[1][2]
        return min(min(ay[1], by[1])-max(ay[0], by[0]),
                   min(az[1], bz[1])-max(az[0], bz[0]))
    if a[0] == b[0] == "tube":
        return a[1][3]+b[1][3]-hypot(a[1][1]-b[1][1], a[1][2]-b[1][2])
    t, x = (a, b) if a[0] == "tube" else (b, a)
    dy = max(x[1][1][0]-t[1][1], t[1][1]-x[1][1][1], 0)
    dz = max(x[1][2][0]-t[1][2], t[1][2]-x[1][2][1], 0)
    return t[1][3]-hypot(dy, dz)


def check_fixed_spine(room_list):
    # Static solids only. Rail-stop operational sweeps and penetrating shield
    # collars are not second gas cells/boxes; explicit types guard the exception.
    shapes = []
    for s in room_list:
        g = s.get("geometry") or {}
        if s["id"].startswith("LOGI-STOP-"):
            need(g.get("shape") == "rail_stop_activity"
                 and g.get("activity_only_no_additive_volume") is True
                 and g.get("complete_sled_envelope_m") == [3.8, 3.4, 8],
                 "logistics stop misrepresented as a separate pressure box")
        if s["id"] == "BOW-SHIELD-FOREPEAK":
            need(g.get("shape") == "penetrated_forepeak_shield"
                 and len(g.get("service_bores", [])) == 3,
                 "shield reintroduces obstruction of through transit")
        box, circle = rectangle(s), tube(s)
        if box:
            shapes.append(("box", box, s["id"]))
            if s["frame"] == "fixed" and not (
                s["id"].endswith("-FREIGHT-LOCK")
                or s["id"] in {
                   "STORES-LONGLIFE", "STORE-FOOD-AFT",
                   "STORE-FLUID-AFT", "STORE-CRIT-SPARES",
                   "CMD-EMERG", "COMMS-AFT", "RESCUE-AFT"
                }):
                maxr = max(hypot(y, z) for y in box[1] for z in box[2])
                need(maxr <= 8.05,
                     "fixed compartment outside 16m nominal spine: " + s["id"])
        if circle:
            shapes.append(("tube", circle, s["id"]))
    for i, one in enumerate(shapes):
        for two in shapes[i+1:]:
            need(transverse_penetration(one, two) <= 1e-6,
                 "physical overlap: " + one[2] + " / " + two[2])
    return len(shapes)


def regular_box_volume(s):
    b = rectangle(s)
    need(b is not None, "fixed pressure room is not a placed box: " + s["id"])
    return (b[0][1]-b[0][0])*(b[1][1]-b[1][0])*(b[2][1]-b[2][0])


def selected_new_cell(zid, s):
    g = s.get("geometry") or {}
    if zid == "PZ-HAB-04-MED-ISO":
        need(g.get("shape") == "arc_cabin"
             and g.get("includes_host_arc_gross_envelope") is True
             and g.get("axial_width_m") == g.get("tangential_length_m") == 5
             and g.get("clear_height_m") == 2.7,
             "medical daughter cabin geometry unsound")
        return 67.5
    if zid in ("PZ-IX-A", "PZ-IX-B"):
        need(g.get("shape") == "capsule"
             and g.get("length_m") == 4.6
             and g.get("diameter_m") == 2.6
             and g.get("reference_orbit_radius_m") == 10.5,
             "main indexer chamber displaced from known capture ring")
        return pi*1.3**2*4.6
    need(zid in ("PZ-IX-A-FINAL-LIFT", "PZ-IX-B-FINAL-LIFT")
         and g.get("shape") == "pressure_lift_car"
         and g.get("belongs_within_host_arc_gross_envelope") is True
         and g.get("length_m") == 3
         and g.get("clear_diameter_m") == 2.6,
         "final isolation lift mis-sized")
    return pi*1.3**2*3


def indexed_drum_lock(ship, s):
    g, l = s["geometry"], s["location"]
    number = s["id"][3:5]
    cargo = next(r for r in ship["spaces"] if r["id"] == f"DR-{number}-FREIGHT-LOCK")
    middle = sum(cargo["location"]["x_m"])/2
    need(g.get("shape") == "transfer_lock" and g.get("length_m") == 5
         and g.get("clear_diameter_m") == 2.3
         and l["x_m"] == [middle+15.5, middle+20.5]
         and l["y_m"] == 5.4 and l["z_m"] == -3.7
         and 8-hypot(l["y_m"],l["z_m"])-1.15 > .25,
         "indexed personnel station occupies freight swept axial interval or fixed hull")
    trunk = next(r for r in ship["spaces"] if r["id"] == f"TRUNK-A-DR-{number}")
    neck = hypot(l["y_m"]-trunk["location"]["y_m"],
                 l["z_m"]-trunk["location"]["z_m"])-1.15-1.5
    need(.9 <= neck <= 1.4, "indexed lock cannot reach crew trunk from outboard position")
    doors = {d["id"]: d for d in ship["access_links"]}
    fixed, rotor = doors[f"ACC-DR-{number}-LOCK-FIX"], doors[f"ACC-DR-{number}-LOCK-ROT"]
    need(fixed["from"] == trunk["id"] and fixed["to"] == s["id"]
         and rotor["from"] == s["id"] and rotor["to"] == f"DR-{number}-HUB"
         and all(d["pressure_boundary"] and d["isolatable"]
                 and d["normal_state"] == "closed" for d in (fixed, rotor)),
         "indexed lock lacks both independent rated gates")
    return pi*1.15**2*5


def rotating_drum_zone(ship, members):
    byid = {s["id"]: s for s in members}
    prefix = members[0]["id"][:5]
    need(set(byid) == {f"{prefix}-HUB", f"{prefix}-GALLERY", f"{prefix}-FREIGHT-HUB"},
         "drum pressure zone lost separate hub/gallery/berth identities")
    hub, gallery, berth = [byid[f"{prefix}-{name}"] for name in (
        "HUB", "GALLERY", "FREIGHT-HUB")]
    h, o, b = hub["geometry"], gallery["geometry"], berth["geometry"]
    need(h.get("shape") == "rotating_hub_composite"
         and h.get("annular_inner_radius_m") == 11.85
         and h.get("annular_outer_radius_m") == 13.65
         and h.get("freight_ring_axial_length_m") == 6
         and h.get("crew_ring_axial_length_m") == 5
         and h.get("crew_indexer_axial_station_offset_m") == 18
         and h.get("connecting_rotor_tube_clear_diameter_m") == 1.6
         and h.get("connecting_rotor_tube_clear_length_m") == 12.5
         and h.get("pressurised_components_disjoint") is True,
         "drum annular components are incomplete or multiply counted")
    need(o.get("shape") == "rotating_annular_band"
         and o.get("inner_radius_m") == 13.65
         and o.get("outer_radius_m") == 16.5
         and o.get("axial_length_m") == 4
         and b.get("shape") == "nested_handling_bay"
         and b.get("volume_additive") is False
         and b.get("parent_room_id") == gallery["id"],
         "drum gallery/berth is not properly nested")
    freight = next(s for s in ship["spaces"]
                   if s["id"] == f"{prefix}-FREIGHT-LOCK")
    middle = sum(freight["location"]["x_m"])/2
    need(close(hub["location"]["x_m"],middle+9)
         and close(gallery["location"]["x_m"],middle)
         and close(berth["location"]["x_m"],middle)
         and close(hub["location"]["x_m"]+9,middle+18),
         "rotor pressure rings do not serve axially separated stations")
    fixed_corner = hypot(freight["location"]["y_m"]+freight["geometry"]["clear_width_m"]/2,
                         freight["geometry"]["clear_height_m"]/2)
    need(h["annular_inner_radius_m"]-fixed_corner >= .5,
         "rotating hub will hit stationary full freight lock")
    person = ship["transit_contract"]["indexed_drum_personnel_transfer"]
    need(person["selected_axial_offset_from_freight_station_m"] == 18
         and person["internal_moving_carrier_radial_envelope_m"] == [8.55, 11.55]
         and person["swept_collar_retract_before_freight_handling"] is True,
         "indexed personnel shuttle intersects cargo or lacks a retract interlock")
    return (pi*(13.65**2-11.85**2)*(6+5)
            + pi*.8**2*12.5
            + pi*(16.5**2-13.65**2)*4)


def wr_zone(zid, members, ship):
    s = {x["id"]: x for x in members}
    def annulus(r1, r2, length):
        return pi*(r2*r2-r1*r1)*length
    if zid == "PZ-WR-HUB":
        g = s["WR-HUB"]["geometry"]
        need(g.get("shape") == "rotating_annular_band"
             and g.get("inner_radius_m") == 8.8
             and g.get("outer_radius_m") == 12.8
             and g.get("axial_length_m") == 10
             and g.get("stationary_spine_radial_guard_m") == .8,
             "WR spinning hub would intersect fixed spine")
        return annulus(8.8,12.8,10)
    if zid == "PZ-WR-IX":
        c = s["WR-IX-CAPSULE"]
        g, l = c["geometry"], c["location"]
        need(g.get("shape") == "capsule" and g.get("diameter_m") == 2.6
             and g.get("length_m") == 4
             and g.get("reference_orbit_radius_m") == 10.5
             and l.get("radius_m") == 10.5 and l.get("x_m") == 480
             and g.get("swept_radial_min_m") == 9.2
             and g.get("swept_radial_max_m") == 11.8,
             "WR indexer overlaps fixed axis or WR hub station")
        return pi*1.3**2*4
    if zid in ("PZ-WR-SHOP", "PZ-WR-STORES"):
        if zid == "PZ-WR-SHOP":
            ordered = [("PARTS-WASH",476,8,0),("SHOP-MECH",489,18,0),
                       ("SHOP-WELD",503,10,0)]
            nested = "SHOP-IMMEDIATE-STOCK"
            parent = "SHOP-MECH"
        else:
            ordered = [("MATERIAL-STOCK",477,12,180),
                       ("SPARES-CENTRAL",489,12,180),
                       ("TOOL-CRIB",499,8,180)]
            nested = None
        volume = 0
        segments = []
        for name, x, length, az in ordered:
            room = s[name]
            q, l = room["geometry"], room["location"]
            need(q.get("shape") == "pod" and q.get("length_m") == length
                 and l.get("x_m") == x and l.get("theta_deg") == az
                 and l.get("radius_m") == (60 if az == 0 else 20),
                 "rotating workshop/store pod has no distinct place: "+name)
            segments.append((x-length/2,x+length/2))
            volume += length*q["tangential_width_m"]*q["radial_depth_m"]
        need(all(segments[i][1] <= segments[i+1][0]
                 for i in range(len(segments)-1)),
             "rotating workshop/store machine rooms overlap axially")
        if nested:
            g = s[nested]["geometry"]
            need(g.get("shape") == "nested_locker_bank"
                 and g.get("volume_additive") is False
                 and g.get("parent_room_id") == parent,
                 "workshop immediate locker double counted")
        return volume
    need(zid in ("PZ-WR-SHOP-PASS","PZ-WR-STORES-PASS"),
         "unknown workshop geometric pressure zone")
    room = members[0]
    g = room["geometry"]
    want = (12.8,54,41.2,0) if zid.endswith("SHOP-PASS") else (12.8,15,2.2,180)
    inner, outer, length, az = want
    need(g.get("shape") == "sealed_telescoping_pressure_passage"
         and g.get("radial_inner_m") == inner
         and g.get("radial_outer_m") == outer
         and close(g.get("reference_deployed_length_m",0),length)
         and g.get("clear_diameter_m") == 3
         and room["location"]["theta_deg"] == az
         and g.get("pressure_makeup_required_when_extending") is True
         and g.get("working_seals") == "paired monitored sliding seals",
         "variable passage cannot preserve pressure during telescoping")
    bounds=g.get("variable_extension_length_bounds_m")
    need(len(bounds)==2 and 0 < bounds[0] <= length <= bounds[1],
         "invalid telescoping passage gas-volume bounds")
    return pi*1.5**2*length


def external_cross_bypass(zid, members):
    need(len(members)==1, "cross-trunk bypass has multiple unknown hulls")
    s = members[0]
    g, l = s["geometry"], s["location"]
    need(g.get("shape")=="external_pressure_bypass"
         and g.get("clear_diameter_m")==2.5
         and g.get("arch_centerline_radius_m")==9.6
         and g.get("arc_span_deg")==180
         and g.get("station_necks_each_m")==3.5
         and g.get("pressure_cell_independent") is True
         and g.get("arch_centerline_radius_m")-g["clear_diameter_m"]/2 >= 8.3,
         "external crossconnector obstructs fixed heavy logistics spine")
    expected_x = [866,869] if zid=="PZ-XCON-AFT" else (
       [43.5,46.5] if zid=="PZ-XCON-BOW" else [453.5,456.5])
    need(l.get("x_m")==expected_x, "crossconnector bypass not clear of other stations")
    # HAB indexers occupy 441.1..448.9 and 461.1..468.9;
    # central crossconnector must be in the genuine axial gap.
    return pi*1.25**2*(pi*9.6+2*3.5)


def admission_volume(ship, row, members):
    zid,status=row["pressure_zone_id"],row["status"]
    if status == "selected_internal_pressure_geometry":
        need(zid in MEDICAL_AND_INDEXERS and len(members)==1,
             "undocumented internal child selection")
        return selected_new_cell(zid,members[0])
    if status == "selected_indexed_service_lock_envelope":
        need(zid in DRUM_LOCKS and len(members)==1,
             "indexed service lock outside reviewed drum group")
        return indexed_drum_lock(ship,members[0])
    if status in ("accepted_nominal_envelope",
                  "selected_collision_screened_fixed_room_boxes"):
        need((zid in ORIGINAL_SELECTED) ==
             (status == "accepted_nominal_envelope"),
             "fixed box wrongly described as earlier accepted region")
        return sum(regular_box_volume(s) for s in members)
    if status == "selected_rotating_drum_pressure_annuli":
        need(zid.startswith("PZ-DR-") and zid.endswith("-SVC"),
             "incorrect drum pressure group")
        return rotating_drum_zone(ship,members)
    if status in ("selected_wr_annular_hub","selected_wr_indexer_capsule",
                  "selected_distinct_rotor_pods",
                  "selected_bounded_telescopic_gas_passage"):
        return wr_zone(zid,members,ship)
    if status=="selected_external_over_spine_connector":
        return external_cross_bypass(zid,members)
    raise ValueError("unapproved geometry status for "+zid+": "+status)


def validate(ship, pressure, gas, audit):
    rooms={s["id"]:s for s in ship["spaces"]}
    cells={c["id"]:c for c in pressure["pressure_cells"]}
    gasrows={c["pressure_zone_id"]:c for c in gas["sized_and_unsized_pressure_cells"]}
    need(len(rooms)==len(ship["spaces"])==421
         and len(cells)==len(pressure["pressure_cells"])==133
         and len(gasrows)==len(gas["sized_and_unsized_pressure_cells"])==133,
         "physical cell or room identity changed")
    expected=set(audit["prior_unsized_pressure_cell_ids"])
    chosen=set(audit["accepted_zone_ids"])
    need(len(expected)==len(chosen)==len(audit["cells"])==48
         and expected==chosen
         and Counter(x["status"] for x in audit["cells"])==EXPECTED_STATUS,
         "pressure-room geometry audit not complete")
    static_count=check_fixed_spine(ship["spaces"])
    need(static_count>=140,"static geometry checker did not examine all fixed spaces")
    computed={}
    for row in audit["cells"]:
        zid=row["pressure_zone_id"]
        need(zid in expected and row["space_ids"]==cells[zid]["space_ids"],
             "pressure cell/room membership drift: "+zid)
        v=admission_volume(ship,row,[rooms[k] for k in row["space_ids"]])
        cell,gr=cells[zid],gasrows[zid]
        need(close(v,cell["gross_reference_envelope_m3"])
             and close(v,row["additive_reference_gross_m3"])
             and close(v,gr["source_gross_envelope_m3"]),
             "wrong independent gross pressure envelope: "+zid)
        need(gr["verified_as_installed_free_gas_m3"] is None
             and cell["actual_usable_free_air_m3"] is None,
             "nominal gas reference falsely claimed as measured")
        need(row["blockers"]==[], "unclosed physical pressure reference: "+zid)
        computed[zid]=v
    for host, children in (
        ("PZ-HAB-04",("PZ-HAB-04-MED-ISO","PZ-IX-A-FINAL-LIFT")),
        ("PZ-HAB-08",("PZ-IX-B-FINAL-LIFT",))):
        need(close(cells[host]["gross_reference_envelope_m3"] +
                   sum(cells[k]["gross_reference_envelope_m3"] for k in children),
                   ARC_SHELL_M3,2e-5), "habitation daughter volume counted twice")
    total=sum(c["gross_reference_envelope_m3"] for c in cells.values())
    need(all(c["gross_reference_envelope_m3"] is not None
             and c["actual_usable_free_air_m3"] is None for c in cells.values()),
         "unmeasured or omitted pressure cell")
    need(100772 < total < 100774
         and close(total,pressure["totals"]["gross_reference_envelopes_m3"],1e-4)
         and pressure["totals"]["sized_geometric_cells"] == 133
         and gas["totals"]["sized_pressure_cells"]==133
         and gas["totals"]["unsized_pressurized_cells"]==0
         and audit["totals"]["still_unsized"]==0,
         "whole-ship pressure geometry tally disagrees")
    doors={d["id"] for d in ship["access_links"] if d.get("pressure_boundary")}
    recorded={d["id"] for d in pressure["pressure_boundary_doors"]}
    need(len(doors)==len(recorded)==339 and doors==recorded,
         "independent rated pressure boundary missing")
    for edge in ship["access_links"]:
        ra,rb=rooms[edge["from"]]["pressure_zone"],rooms[edge["to"]]["pressure_zone"]
        need(ra==rb or edge["pressure_boundary"],
             "unrated independent pressure-zone door: "+edge["id"])
    ref=ship["transit_contract"]["inter_drum_transfer"]["freight_lock_reference"]
    need(ref["clear_length_m"]==12 and ref["sled_length_m"]==8
         and ref["fore_and_aft_end_clearance_m_each"]==2,
         "sled does not fit six fixed freight chambers")
    return {"sized_pressure_cells":133,"unsized_pressure_cells":0,
            "rated_pressure_boundaries":339,"checked_static_box_tube_envelopes":static_count,
            "gross_reference_m3":round(total,3),
            "newly_sized_in_this_increment":26,
            "drum_annulus_axially_separated":6,
            "verified_as_installed_free_gas":"NONE"}


def negative_tests(ship,pressure,gas,audit):
    def fail(mutator):
        inputs=deepcopy((ship,pressure,gas,audit))
        mutator(*inputs)
        try:
            validate(*inputs)
        except (ValueError,KeyError,TypeError):
            return
        raise AssertionError("invalid ship physical geometry accepted")
    def room(s,id):
        return next(r for r in s["spaces"] if r["id"]==id)
    def cell(p,id):
        return next(r for r in p["pressure_cells"] if r["id"]==id)
    fail(lambda s,p,g,a: room(s,"DR-01-SERVICE-LOCK")["location"].update(x_m=[125,130]))
    fail(lambda s,p,g,a: room(s,"DR-02-SERVICE-LOCK")["geometry"].update(clear_diameter_m=4))
    fail(lambda s,p,g,a: next(x for x in s["access_links"]
         if x["id"]=="ACC-DR-03-LOCK-ROT").update(normal_state="open"))
    fail(lambda s,p,g,a: room(s,"STORE-FOOD-AFT")["location"].update(y_m=8.9))
    fail(lambda s,p,g,a: room(s,"BOW-SHIELD-FOREPEAK")["geometry"].update(shape="box"))
    fail(lambda s,p,g,a: room(s,"LOGI-STOP-AFT")["geometry"].update(shape="box"))
    fail(lambda s,p,g,a: room(s,"XCON-AFT")["geometry"].update(arch_centerline_radius_m=7.6))
    fail(lambda s,p,g,a: room(s,"WR-HUB")["geometry"].update(inner_radius_m=7))
    fail(lambda s,p,g,a: room(s,"DR-04-HUB")["geometry"].update(crew_ring_axial_length_m=3))
    fail(lambda s,p,g,a: room(s,"SHOP-WELD")["location"].update(x_m=497))
    fail(lambda s,p,g,a: room(s,"WR-PASS-SHOP")["geometry"].update(reference_deployed_length_m=100))
    fail(lambda s,p,g,a: cell(p,"PZ-WR-HUB").update(gross_reference_envelope_m3=1))
    fail(lambda s,p,g,a: next(x for x in s["access_links"]
         if x["id"]=="ACC-IX-A-FINAL").update(pressure_boundary=False))
    fail(lambda s,p,g,a: next(x for x in g["sized_and_unsized_pressure_cells"]
         if x["pressure_zone_id"]=="PZ-AFT-STORES").update(verified_as_installed_free_gas_m3=100))
    fail(lambda s,p,g,a: room(s,"BE-12-SVC")["location"].update(z_m=-3.35))
    fail(lambda s,p,g,a: next(e for e in s["access_links"]
         if e["id"]=="ACC-DR-01-SEC-01").update(pressure_boundary=False))
    fail(lambda s,p,g,a: next(e for e in s["access_links"]
         if e["id"]=="ACC-GEN-M-ROOM").update(pressure_boundary=False))
    fail(lambda s,p,g,a: next(e for e in s["access_links"]
         if e["id"]=="ACC-DR-06-FREIGHT-SEC-08").update(pressure_boundary=False))


if __name__=="__main__":
    data=[read(n) for n in (
        "ox_full_ship_v0.5_candidate.json",
        "pressure_zone_topology_v0.5.json",
        "pressure_gas_recovery_v0.5.json",
        "pressure_geometry_reconciliation_v0.5.json",
    )]
    print(json.dumps(validate(*data),sort_keys=True,indent=2))
    negative_tests(*data)
    print("OX_COMPLETE_PRESSURE_GEOMETRY_AND_EIGHTEEN_NEGATIVE_TESTS_PASS")
