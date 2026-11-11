"""First segment gateway: measured electricity and versioned read-only telemetry.

The mixed-generation drum-3 adapter has no actuation entry point. Its raw
register vocabulary is a simulation contract, verified separately from the
physical cable and supply. No firmware or live player principal is implied.
"""

from __future__ import annotations

import copy
import math

from world.ship_mind_power import MindPowerError
from world.ship_mind_support import BROKEN, SCHEMA

PROFILE = "ox.drum3.mixed-telemetry/1"
GATEWAY = "GW-LCS-DR-03"
SOURCES = ("equipment:DR-03-CARGO-HX", "equipment:DR-03-CARGO-GAS", "isolator:ISO-DR-03-LT-IF")


def _require(ok, message):
    """Reject an unverified source, measurement or protocol transition."""
    if not ok:
        raise MindPowerError(message)


def _number(value):
    """Accept nonnegative finite physical quantities only."""
    _require(
        type(value) in (int, float) and math.isfinite(value) and value >= 0,
        "Invalid gateway energy or time",
    )
    return float(value)


def gateway_power_rows(support, ship):
    """Fit local fused power and a conductive mount into an actual trunk cell."""
    gateway = support["gateway_candidates"][0]
    _require(gateway["id"] == GATEWAY, "Unknown gateway supply")
    feed = gateway.get("power_connection")
    _require(
        isinstance(feed, dict)
        and feed
        == {
            "panel_node": "NODE-LP-BE-05-SVC",
            "terminal_node": "NODE-PWR-GW-LCS-DR-03",
            "edge": "EDGE-PWR-GW-LCS-DR-03",
            "isolator": "ISO-PWR-GW-LCS-DR-03",
            "load_kw": 0.05,
            "route_spaces": ["BE-05-SVC"],
        },
        "Gateway supply is not the separately fused local 50 W circuit",
    )
    nodes = {n["id"]: n for n in ship["service_nodes"]}
    equipment = {e["id"]: e for e in ship["equipment"]}
    panel = nodes[feed["panel_node"]]
    _require(
        panel["network"] == "power"
        and panel["owner_id"] == "LP-BE-05-SVC"
        and equipment[panel["owner_id"]]["space_id"] == gateway["room"],
        "Original local gateway supply panel is missing or misplaced",
    )
    heat = gateway.get("thermal_connection")
    _require(
        heat
        == {
            "id": "THERM-GW-LCS-DR-03",
            "sink_room": "TRUNK-B-DR-03",
            "route_spaces": ["BE-05-SVC", "TRUNK-B-DR-03"],
            "rated_kw": 0.05,
        },
        "Gateway has no separately fitted local thermal mount",
    )
    spaces = {s["id"]: s for s in ship["spaces"]}
    _require(
        spaces[gateway["room"]].get("pressure_zone") is None
        and spaces[heat["sink_room"]].get("pressure_zone") is not None
        and any(
            {link["from"], link["to"]} == set(heat["route_spaces"]) for link in ship["access_links"]
        ),
        "Gateway heat route does not join its unpressurised host to a real trunk cell",
    )
    result = {}
    for category, name, setting, reference in (
        (
            "node",
            feed["terminal_node"],
            "unverified",
            {
                "id": feed["terminal_node"],
                "network": "ship_gateway_power",
                "kind": "gateway_power_terminal",
                "owner_type": "equipment",
                "owner_id": GATEWAY,
            },
        ),
        (
            "edge",
            feed["edge"],
            "available",
            {
                "id": feed["edge"],
                "network": "ship_gateway_power",
                "kind": "local_fused_feeder",
                "from_node": feed["panel_node"],
                "to_node": feed["terminal_node"],
                "isolator_ids": [feed["isolator"]],
                "route_spaces": feed["route_spaces"],
            },
        ),
        (
            "isolator",
            feed["isolator"],
            "closed",
            {
                "id": feed["isolator"],
                "network": "ship_gateway_power",
                "kind": "breaker",
                "manual_operation": True,
                "remote_operable": False,
            },
        ),
        (
            "edge",
            heat["id"],
            "available",
            {
                "id": heat["id"],
                "network": "ship_gateway_thermal",
                "kind": "conductive_mounting_strap",
                "from_room": gateway["room"],
                "to_room": heat["sink_room"],
                "route_spaces": heat["route_spaces"],
                "rated_kw": heat["rated_kw"],
                "isolator_ids": [],
            },
        ),
    ):
        key = category + ":" + name
        result[key] = {
            "key": key,
            "category": category,
            "source_id": name,
            "source_model": SCHEMA,
            "space_id": gateway["room"],
            "condition": "serviceable",
            "setting": setting,
            "reference": reference,
            "details": {},
        }
    return result


def fitted_gateway_power(world_state, support, ship, *, install=False):
    """Read exact circuit identity; optional fitting never repairs existing rows."""
    expected = gateway_power_rows(support, ship)
    created = 0
    if install:
        for key, spec in expected.items():
            _, added = world_state.objects.get_or_create(key=key, defaults=spec)
            created += int(added)
    found = {r.key: r for r in world_state.objects.filter(key__in=list(expected))}
    _require(set(found) == set(expected), "Fitted gateway power circuit disappeared")
    for key, spec in expected.items():
        _require(
            all(
                getattr(found[key], field) == spec[field]
                for field in ("source_model", "category", "source_id", "space_id", "reference")
            ),
            "Gateway circuit provenance changed: " + key,
        )
    original_keys = set(SOURCES) | {"equipment:LCS-DR-03", "equipment:LP-BE-05-SVC"}
    originals = {r.key: r for r in world_state.objects.filter(key__in=sorted(original_keys))}
    validate_gateway_sources(originals, ship)
    return found, created


def validate_gateway_sources(rows, ship):
    """Reject relabelled, moved or substituted original local-controller sources."""
    expected = {
        category + ":" + r["id"]: r
        for section, category in (("equipment", "equipment"), ("isolation_points", "isolator"))
        for r in ship[section]
    }
    keys = set(SOURCES) | {"equipment:LCS-DR-03", "equipment:LP-BE-05-SVC"}
    _require(keys <= set(rows), "Original gateway host, panel or telemetry source disappeared")
    for key in sorted(keys):
        row, ref = rows[key], expected[key]
        category, name = key.split(":", 1)
        _require(
            row.source_model == ship["model_version"]
            and row.category == category
            and row.source_id == name
            and row.space_id == ref["space_id"]
            and row.reference == ref,
            "Gateway source provenance changed: " + key,
        )
    return True


def initial_gateway():
    """No measured power or understood registers on first installation."""
    return {
        "version": 1,
        "power_survey": None,
        "mapping_revision": 0,
        "profile": None,
        "served_kwh": 0.0,
        "elapsed_s": 0.0,
        "last": {},
    }


def validate_gateway(account):
    """Bound electricity and mapping state; remote command authority is absent."""
    _require(
        isinstance(account, dict)
        and set(account)
        == {
            "version",
            "power_survey",
            "mapping_revision",
            "profile",
            "served_kwh",
            "elapsed_s",
            "last",
        }
        and type(account["version"]) is int
        and account["version"] == 1,
        "Unknown world gateway ledger",
    )
    revision = account["mapping_revision"]
    _require(
        type(revision) is int
        and revision >= 0
        and account["profile"] == (None if revision == 0 else PROFILE),
        "Unverified gateway vocabulary revision",
    )
    elapsed = _number(account["elapsed_s"])
    delivered = _number(account["served_kwh"])
    _require(
        delivered <= 0.05 * elapsed / 3600 + 1e-9, "Gateway drew more than its rated local circuit"
    )
    survey = account["power_survey"]
    if survey is not None:
        _require(
            isinstance(survey, dict)
            and set(survey)
            == {"measured_kw", "component_revisions", "evidence_id", "thermal_path_verified"}
            and _number(survey["measured_kw"]) == 0.05
            and isinstance(survey["component_revisions"], dict)
            and len(survey["component_revisions"]) == 4
            and survey["thermal_path_verified"] is True
            and all(type(r) is int and r >= 0 for r in survey["component_revisions"].values())
            and isinstance(survey["evidence_id"], str)
            and 0 < len(survey["evidence_id"]) <= 128,
            "Unmeasured or altered gateway power survey",
        )
    else:
        _require(delivered == 0 and revision == 0, "Unsupplied gateway has energy or mappings")
    last = account["last"]
    _require(isinstance(last, dict), "Malformed last gateway observation")
    if last:
        _require(
            set(last)
            == {
                "observed_s",
                "powered",
                "connected",
                "raw_samples",
                "readings",
                "mapping_revision",
                "remote_commands_enabled",
            }
            and last["remote_commands_enabled"] is False
            and type(last["powered"]) is bool
            and type(last["connected"]) is bool
            and isinstance(last["raw_samples"], dict)
            and set(last["raw_samples"]) <= set(SOURCES)
            and isinstance(last["readings"], dict)
            and set(last["readings"]) <= set(SOURCES)
            and type(last["mapping_revision"]) is int
            and 0 <= last["mapping_revision"] <= revision,
            "Unknown gateway frame or attempted remote-authority grant",
        )
        _number(last["observed_s"])
    return True


def survey_gateway_power(account, rows, *, measured_kw, evidence_id, thermal_path_verified=False):
    """Attest a live supply or verified repair without resetting energy meters."""
    validate_gateway(account)
    _require(
        _number(measured_kw) == 0.05
        and isinstance(evidence_id, str)
        and 0 < len(evidence_id) <= 128
        and len(rows) == 4
        and thermal_path_verified is True
        and all(r.condition not in BROKEN for r in rows.values()),
        "No intact measured gateway feeder",
    )
    _require(
        all(r.category != "isolator" or r.setting == "closed" for r in rows.values()),
        "Gateway's dedicated fuse is open",
    )
    result = copy.deepcopy(account)
    result["power_survey"] = {
        "measured_kw": float(measured_kw),
        "component_revisions": {r.key: r.revision for r in rows.values()},
        "evidence_id": evidence_id,
        "thermal_path_verified": True,
    }
    validate_gateway(result)
    return result


def raw_gateway_samples(rows, *, now_s, operating_machines=None):
    """Read only three actual controller registers, preserving bad/unknown states."""
    samples = {}
    for key in SOURCES:
        row = rows.get(key)
        _require(row is not None, "Original drum-3 telemetry source disappeared")
        valve = key.startswith("isolator:")
        term = "VLV_POS" if valve else "RUN_FB"
        raw = (
            {"open": "O", "closed": "C"}.get(row.setting)
            if valve
            else (
                int(key.split(":", 1)[1] in operating_machines)
                if isinstance(operating_machines, (set, frozenset))
                else None
            )
        )
        quality = "unavailable" if row.condition in BROKEN or raw is None else "good"
        samples[key] = {
            "source_id": key,
            "source_revision": row.revision,
            "source_time": now_s,
            "raw_term": term,
            "raw_value": raw,
            "quality": quality,
        }
    return samples


def translate_gateway_samples(samples, *, mapping_revision):
    """Decode the fixed mixed-generation vocabulary without promoting output claims."""
    _require(set(samples) == set(SOURCES), "Missing or foreign gateway register")
    readings = {}
    for key, sample in samples.items():
        valve = key.startswith("isolator:")
        _require(
            sample["source_id"] == key and sample["raw_term"] == ("VLV_POS" if valve else "RUN_FB"),
            "Wrong source or raw gateway term",
        )
        raw = sample["raw_value"]
        decoded = (
            {"O": "open", "C": "closed"}.get(raw)
            if valve and type(raw) is str
            else bool(raw) if not valve and type(raw) is int and raw in (0, 1) else None
        )
        quality = "good" if sample["quality"] == "good" and decoded is not None else "unavailable"
        readings[key] = dict(
            sample,
            mapping_revision=mapping_revision,
            unit="position" if valve else "state",
            meaning="valve_position" if valve else "running_feedback",
            value=decoded if quality == "good" else None,
            quality=quality,
        )
    return readings


def verify_gateway_protocol(account, *, profile, confirmations, observed_s):
    """Verify translations against this tick's actual powered source samples."""
    validate_gateway(account)
    last = account["last"]
    _require(
        profile == PROFILE and last.get("powered") is True and last.get("observed_s") == observed_s,
        "Protocol verification requires fresh powered local samples",
    )
    revision = account["mapping_revision"] + 1
    readings = translate_gateway_samples(last["raw_samples"], mapping_revision=revision)
    expected = {
        key: {"value": row["value"], "unit": row["unit"], "meaning": row["meaning"]}
        for key, row in readings.items()
    }
    _require(
        all(row["quality"] == "good" for row in readings.values()) and confirmations == expected,
        "Observed raw vocabulary does not match its proposed translation",
    )
    result = copy.deepcopy(account)
    result.update(profile=PROFILE, mapping_revision=revision)
    validate_gateway(result)
    return result


def step_gateway(
    account,
    *,
    rows,
    support_rows,
    source_rows,
    power,
    connected,
    seconds,
    now_s,
    heat_sink_available,
    operating_machines,
):
    """Bill the live feeder, then sample registers; command authority stays false."""
    validate_gateway(account)
    dt, now = _number(seconds), _number(now_s)
    _require(
        0 < dt <= 10 and (not account["last"] or now >= account["last"]["observed_s"] + dt - 1e-7),
        "Gateway clock replay or unbounded step",
    )
    survey = account["power_survey"]
    powered = bool(
        survey
        and heat_sink_available is True
        and all(r.condition not in BROKEN for r in rows.values())
        and all(r.category != "isolator" or r.setting == "closed" for r in rows.values())
        and all(r.category != "edge" or r.setting == "available" for r in rows.values())
        and survey["component_revisions"] == {r.key: r.revision for r in rows.values()}
        and support_rows["equipment:" + GATEWAY].condition not in BROKEN
        and source_rows["equipment:LCS-DR-03"].condition not in BROKEN
        and "NODE-LP-BE-05-SVC" in power["nodes"]
        and power["essential_assured"]
        and power["available_mw"] - power["requested_mw"] >= 0.00005 - 1e-10
    )
    result = copy.deepcopy(account)
    result["elapsed_s"] += dt
    served_kw = 0.05 if powered else 0.0
    result["served_kwh"] += served_kw * dt / 3600
    samples = (
        raw_gateway_samples(source_rows, now_s=now, operating_machines=operating_machines)
        if powered
        else {}
    )
    readings = (
        translate_gateway_samples(samples, mapping_revision=account["mapping_revision"])
        if powered and connected and account["mapping_revision"] > 0
        else {}
    )
    result["last"] = {
        "observed_s": now,
        "powered": powered,
        "connected": bool(connected and powered),
        "raw_samples": samples,
        "readings": readings,
        "mapping_revision": account["mapping_revision"],
        "remote_commands_enabled": False,
    }
    validate_gateway(result)
    return result, served_kw / 1000
