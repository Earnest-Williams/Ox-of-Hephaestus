#!/usr/bin/env python3
"""Adversarial 40 independently staged Ox crew aboard one physical ship.

Reference comparison: containment-first vs rescue-first vs jammed-open
pressure boundary. These are deterministic *policies*, not 40 LLMs or a
live Evennia execution. Only the existing 421 rooms, 517 access links,
133 pressure cells, utilities and previously bounded stores are used.
"""
from __future__ import annotations

from collections import Counter
import json
from math import isclose

from whole_ship_crew_casualty_v05 import (
    FortyCrewVoyage, comparative_trials, reference_roster,
    CASUALTY_ZONE, REFUGE_ZONE, TARGET_HORIZON_S,
    EXITS, VENT_DAMPERS,
)


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def acceptance():
    scenarios = comparative_trials()
    c = scenarios["containment_first"]
    r = scenarios["rescue_first"]
    j = scenarios["containment_jammed_open"]
    records = {}
    for name, report in scenarios.items():
        ids = [p["id"] for p in report["individual_crew"]]
        require(len(ids) == len(set(ids)) == 40,
                name + ": manifest not 40 unique people")
        require(report["actual_people"] == 40
                and report["distinct_starting_rooms"] == 40
                and report["occupied_pressure_cells"] >= 18,
                name + ": crew not distributed across real ship")
        require(isclose(report["reference_horizon_s"],
                        TARGET_HORIZON_S, abs_tol=1e-6),
                name + ": unequal comparison time")
        require(report["sensor_contradiction"] == {
            "HAB03_remote_fire_panel": "silent",
            "crew_witness_local": "odor_and_visible_smoke",
        }, name + ": detector lie and eyewitness discrepancy lost")
        require(all(p["observations"] >= 1
                    and p["orders_and_actions"] >= 1
                    and p["initial_space"] and p["final_space"]
                    for p in report["individual_crew"]),
                name + ": missing individual observation, decision or room")
        require(report["air_reserve_banks_kg"] == {
            "INV-GAS-REFILL-A": 2750.0,
            "INV-GAS-REFILL-B": 2750.0},
                name + ": emergency response conjured or spent unused reserve")
        require(0 < report["water_used_kg"] <= 150.0
                and 0 <= report["remaining_water_kg"] <= 150.0
                and isclose(report["remaining_water_kg"] +
                            report["water_used_kg"], 150.0,
                            abs_tol=1e-5)
                and report["gas_mass_balance_error_kg"] < 1e-5,
                name + ": finite ship resource/material accounting broken")
        require(0 < report["fire_fuel_consumed_kg"] <= 28.0
                and report["total_person_unsafe_seconds"] > 0,
                name + ": oxygen/fuel/individual worksite exposure absent")
        require(all(p["unsafe_person_seconds"] <= 240
                    for p in report["individual_crew"]),
                name + ": one actor exposed for more than scenario duration")
        require(any(p["initial_space"] == "CMD-PRIMARY"
                    for p in report["individual_crew"])
                and any(p["initial_space"] == "CMD-EMERG"
                        for p in report["individual_crew"])
                and any(p["initial_space"] == "SHOP-MECH"
                        for p in report["individual_crew"])
                and any(p["initial_space"] == "TRUNK-A-AFT"
                        for p in report["individual_crew"])
                and any(p["initial_space"] == "BR-03"
                        for p in report["individual_crew"]),
                name + ": 'whole ship' roster actually only HAB extras")
        require(any(e["actor"] == "CREW-033"
                    and e["action"] == "received_fire_panel_indication"
                    for e in report["timeline"])
                and any(e["actor"] == "CREW-009"
                        and e["action"] == "witnessed_local_air_condition"
                        for e in report["timeline"])
                and any(e["actor"] == "CREW-034"
                        and e["action"] == "electrical_source_B_isolated"
                        for e in report["timeline"]),
                name + ": work has no named owner and fallible evidence")
        require(all(e["actor"] in ids for e in report["timeline"]),
                name + ": an invented worker performed world action")
        records[name] = {
            "evacuated": len(report["evacuated_people"]),
            "HAB04_smoke_kg": report["HAB04_smoke_trace_kg"],
            "BR03_smoke_kg": report["BR03_smoke_trace_kg"],
            "burned_fuel_kg": report["fire_fuel_consumed_kg"],
            "suppression_at_s": report["suppression_started_s"],
            "water_used_kg": report["water_used_kg"],
            "person_unsafe_seconds": report["total_person_unsafe_seconds"],
            "command_receipts": sum(
                1 for e in report["timeline"] if "command" in e["action"]
                or "ordered" in e["action"]),
            "individual_work_records": len(report["timeline"]),
        }

    # The whole point of this counterfactual test: exactly the same
    # installed ship, two initially open pressure hatches, a false-silent
    # alarm, and the same 40 posts yield opposing defensible outcomes.
    require(c["evacuated_people"] == [],
            "containment policy secretly teleported CAB03 occupants")
    require(r["evacuated_people"] == ["CREW-007", "CREW-008"],
            "rescue policy could not physically move both named sleepers")
    require(all(p["final_space"] == "HAB-04-COR"
                for p in r["individual_crew"]
                if p["id"] in r["evacuated_people"]),
            "Evacuation result does not match individual ship locations")
    require(r["HAB04_smoke_trace_kg"]
            > c["HAB04_smoke_trace_kg"] + 1e-4,
            "rescue-first's longer open bridge fails to expose HAB04")
    require(r["fire_fuel_consumed_kg"]
            > c["fire_fuel_consumed_kg"] + 0.5,
            "rescue-first suppression delay has no combustion cost")
    require(r["suppression_started_s"]
            > c["suppression_started_s"] + 40.0,
            "contrasting priorities did not cost real response time")
    require(j["failed_pressure_gate_closures"] == [EXITS[0]]
            and not c["failed_pressure_gate_closures"]
            and not r["failed_pressure_gate_closures"],
            "jammed pressure hatch misreported as positive seal")
    require(j["BR03_smoke_trace_kg"] >
            c["BR03_smoke_trace_kg"] + 1e-4,
            "jammed-open casualty does not expose bridge air differently")
    require(j["evacuated_people"] == [],
            "jammed pressure bulkhead gave out phantom evacuation credit")
    require(set(p["id"] for p in c["individual_crew"]) ==
            set(p["id"] for p in r["individual_crew"]) ==
            set(p["id"] for p in j["individual_crew"]),
            "policies changed the people instead of their choices")

    # Finite PPE is credited to exactly two named sleepers. A delayed
    # rescue uses a different amount of that same limited protection.
    preissued = {p["id"] for p in r["individual_crew"]
                 if p["gear_breathing_preissued"]}
    require(preissued == {"CREW-007", "CREW-008"},
            "smoke sets materialized for additional unregistered people")
    require(len([p for p in c["individual_crew"] if p["has_portable_light"]])
            == 2,
            "scarce portable lighting duplicated")
    require(any(x["action"] == "physically_traversed_link"
                and x["actor"] == "CREW-007" and
                x["access_link_id"] == EXITS[0]
                for x in r["timeline"]),
            "evacuated character skipped real physical pressure hatch")
    require(any(x["action"] == "physically_traversed_link"
                and x["actor"] == "CREW-008" and
                x["access_link_id"] == EXITS[1]
                for x in r["timeline"]),
            "second evacuated character skipped remaining pressure hatch")
    for inc in (c, r, j):
        require(all(name in
                    {e.get("valve_id") for e in inc["timeline"]
                     if e["action"] == "ordered_ventilation_partition"}
                    for name in VENT_DAMPERS),
                "HAB03 other ring duct forgotten during smoke isolation")
    records["comparisons_passed"] = {
        "rescue_saves_two_real_individuals": True,
        "rescue_costs_adjacent_arc_smoke_and_delays_mist": True,
        "failed_first_hatch_does_not_create_a_seal": True,
        "actor_roster_and_physical_receipts_conserved": True,
    }
    return scenarios, records


def negative_tests():
    checks = [
        lambda: FortyCrewVoyage(response="NASA_certification"),
        lambda: FortyCrewVoyage(response="rescue_first",
                                jam_hab03_hatch=1),
        lambda: FortyCrewVoyage(response="contained"),
    ]
    for i, bad in enumerate(checks, start=1):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("invalid campaign configuration accepted " + str(i))

    roster = reference_roster()
    require(len(roster) == 40
            and len({p.initial_space for p in roster}) == 40,
            "unsupported repeated initial crew positions")

    trial = FortyCrewVoyage(response="containment_first")
    try:
        trial.emit("PERSON-41", "phantom_override")
    except ValueError:
        pass
    else:
        raise AssertionError("event log allowed forty-first phantom author")

    # Neither warning-only detector nor a vanished communications route
    # is allowed to synthesize a human fire report at command.
    trial.sim.fault_control_link(False, local_authority=True)
    trial.sim.advance(12)
    try:
        trial._station_command_report()
    except RuntimeError:
        pass
    else:
        raise AssertionError("disconnected command magically read the local watch")

    independent = FortyCrewVoyage(response="containment_first")
    independent.personnel["CREW-009"].current_space = "CMD-PRIMARY"
    independent.sim.advance(12)
    try:
        independent._crew_local_smoke_evidence()
    except AssertionError:
        pass
    else:
        raise AssertionError("person outside HAB03 claimed local smell")

    wrong = FortyCrewVoyage(response="containment_first")
    wrong.personnel["CREW-007"].current_space = "TRUNK-A-BOW"
    try:
        wrong.outcome()
    except AssertionError:
        pass
    else:
        raise AssertionError("character teleportation evaded manifest accounting")

    expired = FortyCrewVoyage(response="rescue_first")
    expired_person = expired.personnel["CREW-007"]
    expired_person.wearing_from_s = -179.0
    require(not expired._route_person("CREW-007")
            and expired_person.current_space == "HAB-03-CAB-01",
            "expired finite mask permitted a real smoke evacuation")

    blocked = FortyCrewVoyage(response="rescue_first")
    blocked.sim.close_gate(EXITS[0])
    require(not blocked._route_person("CREW-007")
            and blocked.personnel["CREW-007"].current_space
                == "HAB-03-CAB-01",
            "closed rated bridge hatch crossed by a route planner")

    forty_one = FortyCrewVoyage(response="containment_first")
    try:
        forty_one.sim.stage_crew("HAB-01-CAB-03", 1)
    except ValueError:
        pass
    else:
        raise AssertionError("41st physical crew person admitted to manifest")
    return 10


if __name__ == "__main__":
    scenarios, summary = acceptance()
    summary["invalid_cases_rejected"] = negative_tests()
    # Full 40 distinct actor placements, physical locations, observation
    # counts, per-person exposure and action traces are available in the
    # raw returned records. Print a short CI-readable accounting digest.
    summary["roster_sample"] = [
        {k: p[k] for k in ("id", "role", "initial_space", "final_space",
                          "unsafe_person_seconds", "observations",
                          "orders_and_actions")}
        for p in scenarios["rescue_first"]["individual_crew"]
    ]
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("OX_40_DISTINCT_CREW_MATCHED_CASUALTY_AND_TEN_NEGATIVE_TESTS_PASS")
