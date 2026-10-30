"""G19 finite sealed-cassette port custody, using installed cargo handling.

Pure transition library. An operator attests berth acceptance and the actual
freight route; crew must prepare a sealed physical cassette, run the internal
freight transfer and then use the already installed external cargo portal.
Each intermediate state belongs to the water clock; no hidden offship sink.
"""
from __future__ import annotations

import copy
import math

from world.ship_water_recycling import WaterError, _quantity, CASSETTE_KG

HAUL_SECONDS = 240.0
RETURN_SECONDS = 240.0
PORT_START_SECONDS = 60.0
WASTE_PORT_RATE_KG_S = 80.0
WASTE_PORT_AUX_MW = 0.18

RECEIVERS = {
    **{f"WASTE-RESIDUE-HOLD-{s}": ("sanitary", s) for s in "AB"},
    **{f"IND-SCRAP-HOLD-{s}": ("industrial", s) for s in "AB"},
    **{f"HAZ-ISO-HOLD-{s}": ("hazardous", s) for s in "AB"},
}
STOCK_KEYS = {
    "sanitary": "sanitary",
    "industrial": "industrial",
    "hazardous": "hazardous",
}


def debit_ship_mass_for_waste(motion, exported):
    """Charge true external waste against the original material mass family.

    Stabilised sanitary solids originate in mission water/food flows; sorted
    scrap and cartridge refuse come from the pre-existing dry equipment and
    spare stores. The whole-ship inertial sum falls by precisely the actual
    delivered mass, without treating wet residue as structural dry hull.
    """
    if not isinstance(exported, dict) or set(exported) != set(CASSETTE_KG):
        raise WaterError("Missing or unknown externally delivered waste class")
    out = dict(motion)
    charges = {"dry_mass_kg": 0.0, "mission_fluids_kg": 0.0}
    for category in CASSETTE_KG:
        mass = _quantity(exported[category])
        account = ("mission_fluids_kg" if category == "sanitary"
                   else "dry_mass_kg")
        charges[account] += mass
    for account, debit in charges.items():
        original = _quantity(out[account])
        if original + 1e-7 < debit:
            raise WaterError("External waste exceeds actual finite shipboard mass")
        out[account] = max(0.0, original - debit)
    return out


def initial_offload():
    return {"acceptances": {}, "routes": {}, "jobs": {}, "delivered_kg": {
        k: 0.0 for k in CASSETTE_KG}}


def validate_offload(water, stocks):
    off = water["waste_offload"]
    if not isinstance(off, dict) or set(off) != {
            "acceptances", "routes", "jobs", "delivered_kg"}:
        raise WaterError("Invalid external waste custody state")
    for category in CASSETTE_KG:
        _quantity(off["delivered_kg"][category])
    # External acceptance ledgers and the per-class cumulative delivery
    # gauges must reconcile. One cannot erase previously exported matter
    # by editing only a job, a receipt, or a berth balance.
    delivered = {category: 0.0 for category in CASSETTE_KG}
    if not isinstance(off["routes"], dict):
        raise WaterError("Missing installed waste freight-route evidence")
    reserved = {}
    occupied_drums = set()
    for key, entry in off["acceptances"].items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise WaterError("Invalid external disposal authorization")
        if entry.get("category") not in CASSETTE_KG:
            raise WaterError("Unclassified external disposal authorization")
        if (not isinstance(entry.get("berth_id"), str)
                or not entry["berth_id"]):
            raise WaterError("Unidentified waste accepting berth")
        accepted = _quantity(entry["accepted_kg"])
        limit = _quantity(entry["limit_kg"])
        if limit <= 0 or accepted > limit + 1e-7:
            raise WaterError("External berth accepted more than its finite limit")
        delivered[entry["category"]] += accepted
    for category in CASSETTE_KG:
        if not math.isclose(delivered[category], off["delivered_kg"][category],
                            abs_tol=1e-6, rel_tol=1e-10):
            raise WaterError("External waste acceptance and delivery ledgers differ")
    for receiver, job in off["jobs"].items():
        if receiver not in RECEIVERS:
            raise WaterError("Unknown waste cassette in custody")
        category, side = RECEIVERS[receiver]
        if job["category"] != category or job["side"] != side:
            raise WaterError("Waste custody class or serial mismatch")
        if job["phase"] not in {
                "prepared", "hauling", "port_ready", "offloading",
                "return_ready", "returning", "aborting"}:
            raise WaterError("Invalid physical custody stage")
        portal = job["portal_id"]
        if (not isinstance(portal, str) or
                not portal.startswith("DR-") or
                portal[:5] in occupied_drums):
            raise WaterError("Same drum freight handling rail is double-booked")
        occupied_drums.add(portal[:5])
        mass = _quantity(job["aboard_kg"])
        original = _quantity(job["original_kg"])
        exported = _quantity(job["offship_kg"])
        wait = _quantity(job["remaining_s"])
        if (original <= 0 or mass + exported > original + 1e-6
                or wait > 240 + 1e-7 or not isinstance(job.get("paused"), bool)):
            raise WaterError("Invalid cassette cargo custody, wait or pause state")
        if (job["phase"] in {"port_ready", "offloading", "return_ready",
                             "returning"} and
                not math.isclose(mass + exported, original,
                                 abs_tol=1e-6, rel_tol=1e-10)):
            raise WaterError("Outbound cassette lost unexported physical material")
        if (job["phase"] in {"prepared", "hauling", "aborting"}
                and (mass > 1e-7 or exported > 1e-7)):
            raise WaterError("Waste moved before physical freight capture completed")
        if (job["phase"] in {"port_ready", "offloading",
                           "return_ready", "returning"} and
                water["cassettes"][category][side] > 1e-7):
            raise WaterError("Same cassette exists in source and cargo custody")
        if not isinstance(job["route"], list) or not job["route"]:
            raise WaterError("Missing surveyed material freight path")
        acceptance = off["acceptances"].get(job["acceptance_id"])
        if (acceptance is None or acceptance["category"] != category
                or acceptance["portal_id"] != portal
                or acceptance["berth_id"] != job["berth_id"]):
            raise WaterError("Job has no appropriate external waste acceptance")
        reserved[category] = reserved.get(category, 0.0) + mass
    for cat in CASSETTE_KG:
        physical = sum(water["cassettes"][cat].values()) + reserved.get(cat, 0.0)
        if not math.isclose(physical, stocks[STOCK_KEYS[cat]],
                            abs_tol=1e-5, rel_tol=1e-10):
            raise WaterError("Waste inventory differs from sealed or in-transit mass")


def accept_berth(water, *, acceptance_id, portal_id, berth_id, category, limit_kg):
    if (not isinstance(acceptance_id, str) or
            len(acceptance_id) > 64 or not acceptance_id):
        raise WaterError("Waste disposal acceptance requires a stable ID")
    if category not in CASSETTE_KG or not isinstance(portal_id, str):
        raise WaterError("Waste class or commercial port not accepted")
    if not isinstance(berth_id, str) or not berth_id:
        raise WaterError("External berth provenance missing")
    qty = _quantity(limit_kg)
    if qty <= 0:
        raise WaterError("Cannot authorize zero waste capacity")
    w = copy.deepcopy(water)
    off = w["waste_offload"]
    if acceptance_id in off["acceptances"]:
        raise WaterError("Duplicate external waste acceptance")
    off["acceptances"][acceptance_id] = {
        "portal_id": portal_id, "berth_id": berth_id,
        "category": category, "limit_kg": qty, "accepted_kg": 0.0}
    return w


def approve_route(water, *, receiver, portal_id, route):
    if (receiver not in RECEIVERS or not isinstance(portal_id, str)
            or not isinstance(route, list) or not 0 < len(route) <= 64
            or len(set(route)) != len(route)
            or not all(isinstance(link, str) and link.startswith("ACC-")
                       for link in route)):
        raise WaterError("No verified bounded installed waste haul route")
    w = copy.deepcopy(water)
    key = receiver + ":" + portal_id
    if any(job["portal_id"] == portal_id and job["route"] != route
           for job in w["waste_offload"]["jobs"].values()):
        raise WaterError("Cannot alter the route of a live waste offload")
    w["waste_offload"]["routes"][key] = list(route)
    return w


def prepare(water, *, receiver, acceptance_id, route):
    if receiver not in RECEIVERS:
        raise WaterError("Not a removable installed waste receiver")
    if not isinstance(route, list) or not route or len(route) > 64:
        raise WaterError("Physical waste route was not surveyed")
    w = copy.deepcopy(water)
    category, side = RECEIVERS[receiver]
    permit = w["waste_offload"]["acceptances"].get(acceptance_id)
    if not permit or w["waste_offload"]["routes"].get(
            receiver + ":" + permit["portal_id"]) != route:
        raise WaterError("Physical route has not been explicitly surveyed")
    if not w["cassette_sealed"][category][side]:
        raise WaterError("A loaded waste receiver must be positively sealed")
    if receiver in w["waste_offload"]["jobs"]:
        raise WaterError("Waste receiver already assigned to a haul")
    permit = w["waste_offload"]["acceptances"].get(acceptance_id)
    if permit is None or permit["category"] != category:
        raise WaterError("Port facility cannot receive this classified waste")
    if any(x["portal_id"][:5] == permit["portal_id"][:5]
           for x in w["waste_offload"]["jobs"].values()):
        raise WaterError("Radial waste transporter already occupied")
    amount = _quantity(w["cassettes"][category][side])
    if amount <= 0 or amount > CASSETTE_KG[category][side]:
        raise WaterError("No finite sealed material to offload")
    allocated = sum(x["original_kg"] - x["offship_kg"]
                    for x in w["waste_offload"]["jobs"].values()
                    if x["acceptance_id"] == acceptance_id)
    if permit["accepted_kg"] + amount + allocated > permit["limit_kg"] + 1e-7:
        raise WaterError("External facility acceptance would be exceeded")
    w["waste_offload"]["jobs"][receiver] = {
        "category": category, "side": side,
        "portal_id": permit["portal_id"], "berth_id": permit["berth_id"],
        "acceptance_id": acceptance_id, "route": list(route),
        "phase": "prepared", "remaining_s": 0.0,
        "original_kg": amount, "aboard_kg": 0.0, "offship_kg": 0.0,
        "paused": False}
    return w


def command(water, *, receiver, verb):
    w = copy.deepcopy(water)
    job = w["waste_offload"]["jobs"].get(receiver)
    if job is None:
        raise WaterError("No active sealed waste haul")
    stage = job["phase"]
    if verb == "pause":
        job["paused"] = True
    elif verb == "resume":
        job["paused"] = False
    elif verb == "haul" and stage == "prepared":
        job["phase"] = "hauling"
        job["remaining_s"] = HAUL_SECONDS
        job["paused"] = False
    elif verb == "offload" and stage == "port_ready":
        job["phase"] = "offloading"
        job["remaining_s"] = PORT_START_SECONDS
        job["paused"] = False
    elif verb == "return" and stage == "return_ready":
        job["phase"] = "returning"
        job["remaining_s"] = RETURN_SECONDS
        job["paused"] = False
    elif verb == "abort" and stage in {"prepared", "hauling"}:
        job["phase"] = "aborting"
        job["remaining_s"] = RETURN_SECONDS
        job["paused"] = False
    elif verb == "abort" and stage in {"port_ready", "offloading"}:
        # A partly exported hazardous consignment cannot be recalled from
        # the outside station by a mere switch. Finish the registered
        # delivery first; until then it remains safely under berth custody.
        if job["offship_kg"] > 1e-7:
            raise WaterError("Partial export requires completion, not magical reversal")
        job["phase"] = "return_ready"
        job["paused"] = False
    else:
        raise WaterError("Incompatible physical waste movement instruction")
    return w


def step_offload(water, seconds, *, freight_ready, port_ready,
                 stocks, return_ready=None):
    if (isinstance(seconds, bool) or not isinstance(seconds, (float, int))
            or not math.isfinite(seconds) or not 0 <= seconds <= 60):
        raise WaterError("Unbounded cassette handling step")
    import copy
    w = copy.deepcopy(water)
    updated = {k: _quantity(v) for k, v in stocks.items()}
    report = {"exported_kg": 0.0, "exported": {
        k: 0.0 for k in CASSETTE_KG}, "completed": []}
    for receiver, job in list(sorted(w["waste_offload"]["jobs"].items())):
        if job["paused"]:
            continue
        phase = job["phase"]
        can_freight = receiver in freight_ready
        can_port = receiver in port_ready
        if phase in {"hauling", "aborting", "returning"}:
            if not can_freight:
                continue
            work = min(seconds, job["remaining_s"])
            job["remaining_s"] -= work
            if job["remaining_s"] > 1e-7:
                continue
            if phase == "hauling":
                category, side = job["category"], job["side"]
                job["aboard_kg"] = w["cassettes"][category][side]
                w["cassettes"][category][side] = 0.0
                job["phase"] = "port_ready"
            elif phase == "aborting":
                del w["waste_offload"]["jobs"][receiver]
                report["completed"].append((receiver, "recovered_at_source"))
            else:
                # Return the physically unexported fraction. The previously
                # exported portion is NOT magically recovered from the berth.
                w["cassettes"][job["category"]][job["side"]] = job["aboard_kg"]
                del w["waste_offload"]["jobs"][receiver]
                report["completed"].append((receiver, "returned_to_source"))
        elif phase == "offloading" and can_port:
            startup = min(seconds, job["remaining_s"])
            job["remaining_s"] -= startup
            load_s = seconds - startup
            permit = w["waste_offload"]["acceptances"][job["acceptance_id"]]
            amount = min(
                job["aboard_kg"], max(0.0, load_s * WASTE_PORT_RATE_KG_S),
                max(0.0, permit["limit_kg"] - permit["accepted_kg"]))
            category = job["category"]
            if updated[category] + 1e-7 < amount:
                raise WaterError("Port would discharge more material than ship owns")
            job["aboard_kg"] -= amount
            job["offship_kg"] += amount
            updated[category] -= amount
            permit["accepted_kg"] += amount
            w["waste_offload"]["delivered_kg"][category] += amount
            report["exported_kg"] += amount
            report["exported"][category] += amount
            if job["aboard_kg"] <= 1e-7:
                job["aboard_kg"] = 0.0
                job["phase"] = "return_ready"
                report["completed"].append((receiver, "delivered_to_berth"))
    validate_offload(w, updated)
    return w, updated, report
