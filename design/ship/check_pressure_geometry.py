#!/usr/bin/env python3
"""Independent admission checks for pressure cell gross geometry; stdlib only."""
import json
from math import isclose, hypot
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def read(name):
    return json.loads((ROOT/name).read_text())
def require(p,msg):
    if not p: raise ValueError(msg)
def box(s):
    g,l=s.get("geometry") or {},s.get("location") or {}
    if g.get("shape") not in ("box","transfer_lock") or g.get("clear_diameter_m"): return None
    if not isinstance(l.get("x_m"),list):return None
    w=g.get("width_m",g.get("clear_width_m"))
    h=g.get("height_m",g.get("clear_height_m"))
    if w is None or h is None:return None
    return (tuple(l["x_m"]),(l["y_m"]-w/2,l["y_m"]+w/2),(l["z_m"]-h/2,l["z_m"]+h/2))
def intersect(a,b):
    if a is None or b is None:return 0
    v=1
    for k in range(3):v*=max(0,min(a[k][1],b[k][1])-max(a[k][0],b[k][0]))
    return v
def validate(ship,pc,gas,audit):
    rooms={s["id"]:s for s in ship["spaces"]}
    cells={c["id"]:c for c in pc["pressure_cells"]}
    rows={c["pressure_zone_id"]:c for c in gas["sized_and_unsized_pressure_cells"]}
    accepted=set(audit["accepted_zone_ids"])
    require(len(accepted)==11 and len(audit["cells"])==48,"wrong audit population")
    require(len(cells)==133,"unexpected pressure count")
    require(len([c for c in cells.values() if c["gross_reference_envelope_m3"] is not None])==96,"incorrect sized count")
    require(len([c for c in audit["cells"] if c["status"]=="on_hold"])==37,"lost held geometry")
    for entry in audit["cells"]:
        cid=entry["pressure_zone_id"]
        require(cid in cells and entry["space_ids"]==cells[cid]["space_ids"],"lost cell identity")
        if cid not in accepted:
            require(cells[cid]["gross_reference_envelope_m3"] is None and entry["blockers"],"unreviewed volume accepted")
            continue
        ss=[rooms[r] for r in entry["space_ids"]]
        for s in ss:
            require(box(s) is not None and s["geometry"]["shape"] in ("box","transfer_lock"),"invalid accepted envelope")
            require(isclose(s["geometry"]["length_m"],s["location"]["x_m"][1]-s["location"]["x_m"][0],abs_tol=1e-9),"bad axial dimension")
            for other in ship["spaces"]:
                if other["id"]==s["id"] or other.get("pressure_zone") is None:continue
                require(intersect(box(s),box(other))<1e-8,"volume overlaps another room")
                g=other.get("geometry") or {}
                if g.get("shape")=="tube" and other["pressure_zone"]!=cid:
                    a=box(s);t=other["location"]
                    common=max(0,min(a[0][1],t["x_m"][1])-max(a[0][0],t["x_m"][0]))
                    dy=max(a[1][0]-t["y_m"],0,t["y_m"]-a[1][1])
                    dz=max(a[2][0]-t["z_m"],0,t["z_m"]-a[2][1])
                    require(common==0 or hypot(dy,dz)>=g["clear_diameter_m"]/2-1e-8,"tube collision")
        gross=sum(s["geometry"]["length_m"]*(s["geometry"].get("width_m",s["geometry"].get("clear_width_m")))*(s["geometry"].get("height_m",s["geometry"].get("clear_height_m"))) for s in ss)
        require(isclose(gross,cells[cid]["gross_reference_envelope_m3"],abs_tol=1e-7),"gross geometry drift")
        require(isclose(gross,entry["additive_reference_gross_m3"],abs_tol=1e-7),"audit volume drift")
        require(rows[cid]["verified_as_installed_free_gas_m3"] is None,"fabricated survey")
    require(gas["totals"]["unsized_pressurized_cells"]==37,"gas status stale")
    print("OX_PRESSURE_GEOMETRY_11_ACCEPTED_37_HELD_PASS")
if __name__=="__main__":
    validate(*(read(n) for n in ("ox_full_ship_v0.5_candidate.json","pressure_zone_topology_v0.5.json","pressure_gas_recovery_v0.5.json","pressure_geometry_reconciliation_v0.5.json")))
