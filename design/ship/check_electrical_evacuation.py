#!/usr/bin/env python3
"""Adversarial electrical, fallible control and real-ship crew-access trials.

Execute: python design/ship/check_electrical_evacuation.py
Pure design reference, no live ship truth, crew AI or Evennia mutations.
"""
from __future__ import annotations

from copy import deepcopy
import json
from math import isclose

from electrical_evacuation_v05 import (
    ElectricalEvacuationTrial, new_trial, load_model, read_ship,
)


def insist(value, why):
    if not value:
        raise AssertionError(why)


def validate():
    report = {}
    new = new_trial()
    initial = new.electrical_summary()
    insist((initial["power_connections"], initial["breakers"]) == (450, 466)
           and len(new.access) == 517 and len(new.gates) == 339,
           "actual electrical/access/pressure topology was changed")
    insist(isclose(initial["available_dispatch_MW"], 3.3)
           and isclose(initial["requested_schedule_MW"], 1.55),
           "initial scenario power dispatch contrary to ship contract")
    insist(initial["schedule_within_dispatch_budget"]
           and new.assured_power("PWR-MSB-A")
           and new.assured_power("PWR-MSB-B")
           and new.assured_power("NODE-HAB-03-FIRE-DETECT"),
           "main and auxiliary cannot power protected observed circuit")
    insist(new.fire_detector_report(3)["report"] == "silent",
           "fresh non-burning HAB falsely alarms")
    insist(new._firewater_reaches("PZ-HAB-03"),
           "healthy initial electrical/fire-main interface is unpowered")
    report["ship_power_and_access"] = {
        "power_nodes": 438, "power_edges": 450, "power_breakers": 466,
        "passage_links": 517, "pressure_hatches": 339,
        "initial_generators_MW": initial["available_dispatch_MW"],
        "normal_load_MW": initial["requested_schedule_MW"],
    }

    # Main generator OFF does NOT close remote breakers or magically
    # energize the isolated A distribution from protected battery.
    trip = new_trial()
    trip.set_generator("GEN-M", False, local_authority=True)
    insist(isclose(trip.available_MW(), 0.65)
           and not trip.power_budget_ok()
           and trip.has_power_path("NODE-HAB-03-PDB-B")
           and not trip.assured_power("NODE-HAB-03-PDB-B"),
           "single auxiliary overstated beyond essential reference schedule")
    insist(not trip.has_power_path("PWR-MSB-A"),
           "B auxiliary back-fed A main bus through forbidden protected bus")
    insist(not trip.has_power_path("PWR-PROT")
           and trip.fire_detector_report(3)["report"] == "unavailable"
           and not trip._firewater_reaches("PZ-HAB-03"),
           "tripped generator still runs protected controls and suppression")
    insist(set(trip.unrated_sources_not_dispatchable)
           == {"SHORE-PWR", "BAT-COMMON-OPS", "BAT-COMMON-PROT"},
           "unqualified shore/battery stock credited as endless power")
    trip.shed_load(0.60, local_authority=True, load_plan_verified=True)
    insist(trip.power_budget_ok() and
           trip.assured_power("NODE-HAB-03-PDB-B"),
           "explicit essential load shed does not restore B service")
    insist(not trip.assured_power("NODE-HAB-03-FIRE-DETECT"),
           "protected A-to-B transfer occurred without operation")
    trip.select_protected_feed(3, "B", local_authority=True,
                             transfer_verified=True)
    insist(trip.assured_power("NODE-HAB-03-FIRE-DETECT")
           and trip.assured_power("NODE-HAB-03-EMERGENCY-LIGHT"),
           "local protected supply cannot select surviving B")
    trip.select_main_protected_feed("B", local_authority=True,
                                   transfer_verified=True)
    insist(trip.assured_power("PWR-PROT")
           and trip._firewater_reaches("PZ-HAB-03"),
           "surviving B auxiliary cannot restore selected 0.60 MW protected load")
    insist(not trip.has_power_path("PWR-MSB-A"),
           "selected central protected bus wrongly backfeeds MSB-A")
    report["generator_trip_and_recovery"] = {
        "GEN_B_sole_MW": 0.65,
        "normal_1_55_MW_unmet": True,
        "essential_0_60_MW_served_after_shed": True,
        "HAB03_protected_B_manually_selected": True,
        "central_PROT_B_manually_selected": True,
    }

    # A physical cross-tie requires synchronisation evidence. Selection
    # alone without an actual available B generator will not create output.
    tie = new_trial()
    tie.set_generator("GEN-M", False, local_authority=True)
    tie.shed_load(0.6, local_authority=True, load_plan_verified=True)
    try:
        tie.change_power_tie(True, local_authority=True,
                             synchronisation_verified=False)
    except ValueError:
        pass
    else:
        raise AssertionError("unsynchronised MSB bus-tie accepted")
    insist(not tie.has_power_path("PWR-MSB-A"),
           "rejected bus-tie silently energized A")
    tie.change_power_tie(True, local_authority=True,
                         synchronisation_verified=True)
    insist(tie.has_power_path("PWR-MSB-A"),
           "real synchronized cross-tie fails to backfeed A main bus")
    tie.change_power_tie(False, local_authority=True,
                         synchronisation_verified=False)
    insist(not tie.has_power_path("PWR-MSB-A"),
           "opening central tie fails to re-isolate electrical bus")

    # Refit exception: HAB-03 cabin 07 fan-coil is NOT on its cabin panel.
    # A false model would black out both together and mask the service-group
    # workaround installed during the ship's long life.
    refit = new_trial()
    panel = "NODE-HAB-03-CAB-07-LP"
    fan = "NODE-PWR-HAB-03-CAB-07-FANCOIL"
    insist(refit.has_power_path(panel) and refit.has_power_path(fan),
           "real cabin electrical paths unavailable")
    refit.sample_local("PZ-HAB-03", qualified_local_probe=True)
    refit.stage_worker("HAB-03-CAB-07")
    try:
        refit.queue_valve_command("power", "ISO-HAB-03-CAB-07-LP", "closed",
                                  control_mode="remote", local_authority=True)
    except ValueError:
        pass
    else:
        raise AssertionError("refit manual-only cabin panel obeyed remote actuation")
    refit.queue_valve_command("power", "ISO-HAB-03-CAB-07-LP", "closed",
                              control_mode="manual", local_authority=True,
                              worker_space="HAB-03-CAB-07", delay_s=2)
    refit.advance(3)
    insist(not refit.has_power_path(panel) and refit.has_power_path(fan),
           "patched cabin 07 fan-coil circuit incorrectly on cabin panel")
    refit.sample_local("PZ-HAB-03", qualified_local_probe=True)
    refit.stage_worker("HAB-03-SG2-CUPBOARD")
    refit.queue_valve_command("power", "ISO-HAB-03-SG2-DB", "closed",
                              control_mode="manual", local_authority=True,
                              worker_space="HAB-03-SG2-CUPBOARD", delay_s=2)
    refit.advance(3)
    insist(not refit.has_power_path(fan),
           "refit corridor service-group breaker fails to disconnect fan coil")
    report["ship_of_theseus_wiring"] = {
        "cabin07_panel_dark": True,
        "fan_coil_survives_cabin07_panel_trip": True,
        "fan_coil_requires_SG2_group_board": True,
    }

    # A generic "energy isolated" form cannot make an electrical fire
    # safe for water mist if the actual branch still has a live feed.
    # Deliberately exercise CAB-07's inherited corridor-fed fan coil.
    elect_fire = new_trial()
    load = "NODE-PWR-HAB-03-CAB-07-FANCOIL"
    # A misleading "cabin electrically isolated" condition exists before
    # the subsequent fire: the cabin panel is off, but its patched
    # corridor-supplied fan coil is still live.
    elect_fire.sample_local("PZ-HAB-03", qualified_local_probe=True)
    elect_fire.stage_worker("HAB-03-CAB-07")
    elect_fire.queue_valve_command(
        "power", "ISO-HAB-03-CAB-07-LP", "closed",
        control_mode="manual", local_authority=True,
        worker_space="HAB-03-CAB-07", delay_s=1)
    elect_fire.advance(3)
    insist(not elect_fire.has_power_path("NODE-HAB-03-CAB-07-LP")
           and elect_fire.has_power_path(load),
           "pre-existing CAB-07 panel isolation failed to leave patched fan live")
    elect_fire.ignite("F-COIL", "PZ-HAB-03", fuel_kg=10,
                      burn_kg_s=0.04, smoke_yield_fraction=0.10,
                      hazard="energized_electrical", energized_load_node=load)
    insist(not elect_fire.start_mist(
        "PZ-HAB-03", kg_s=0.5, local_authority=True,
        compatible_agent=True, energy_isolated=True),
        "a false work permit and unrelated cabin panel bypassed live-coil interlock")
    elect_fire.sample_local("PZ-HAB-03", qualified_local_probe=True)
    elect_fire.queue_valve_command(
        "power", "ISO-PWR-HAB-03-CAB-07-FANCOIL", "closed",
        control_mode="manual", local_authority=True,
        worker_space="HAB-03-CAB-07", delay_s=1)
    elect_fire.advance(2)
    insist(elect_fire.has_power_path(load)
           and any(e["kind"] == "control_order_result"
                   and not e["accepted_and_moved"]
                   for e in elect_fire.events),
           "stale smoke-affected worksite sensor falsely allowed local breaker work")
    # This old cabin circuit cannot be remotely broken and the worker
    # has already lost reliable local atmosphere evidence. The costly
    # alternative is isolating the actual upstream B generator/feed.
    elect_fire.set_generator("GEN-B", False, local_authority=True)
    insist(not elect_fire.has_power_path(load)
           and elect_fire.assured_power("PWR-PROT"),
           "upstream B source trip failed to isolate fan or preserved A power")
    insist(elect_fire.start_mist(
        "PZ-HAB-03", kg_s=0.5, local_authority=True,
        compatible_agent=True, energy_isolated=True),
        "verified upstream B isolation failed to enable compatible water mist")
    report["energized_refit_circuit_mist_interlock"] = {
        "false_work_permit_alone_denied": True,
        "cabin_panel_off_fan_coil_still_live": True,
        "local_breaker_work_denied_after_smoke_sample_staled": True,
        "real_upstream_B_feed_isolated_and_verified": True,
    }

    # Smoke between HAB-03 and HAB-04 through air ducts requires fans
    # and powered local distribution. Unpowered fans do not instantly
    # change the physical states of the 221 mechanical dampers.
    vent_live, vent_dark = new_trial(), new_trial()
    for x in (vent_live, vent_dark):
        x.mark_contaminated("PZ-HAB-03", 0.8)
    vent_dark.set_generator("GEN-M", False, local_authority=True)
    vent_dark.set_generator("GEN-B", False, local_authority=True)
    vent_live.advance(120)
    vent_dark.advance(120)
    insist(vent_live.cells["PZ-HAB-04"].trace_kg > 1e-5
           and isclose(vent_dark.cells["PZ-HAB-04"].trace_kg, 0,
                       abs_tol=1e-7),
           "powered mixing persists through total electric failure")
    insist(all(v["state"] == "open"
               for v in vent_dark.valves["atmosphere"].values()),
           "power loss magically closed physical ventilation dampers")
    report["ventilation_power_dependency"] = {
        "HAB04_smoke_tracer_kg_live": round(
            vent_live.cells["PZ-HAB-04"].trace_kg, 5),
        "HAB04_smoke_tracer_kg_blackout": round(
            vent_dark.cells["PZ-HAB-04"].trace_kg, 5),
        "passive_open_ducts_remain": True,
    }

    # Remote actuation can be queued under healthy conditions and then
    # fail when the electrical/control chain is lost before execution.
    remote = new_trial()
    valve = "ISO-AIR-BR-03-HAB-03"
    serial = remote.queue_valve_command(
        "atmosphere", valve, "closed",
        control_mode="remote", local_authority=True, delay_s=2)
    insist(serial.startswith("DC-CMD-") and
           remote.valves["atmosphere"][valve]["state"] == "open",
           "queued operator command asserted success without actuator motion")
    remote.set_generator("GEN-M", False, local_authority=True)
    remote.advance(3)
    insist(remote.valves["atmosphere"][valve]["state"] == "open"
           and remote.observe_switch("atmosphere", valve)["reading"]
               == "unavailable",
           "queued valve silently moved after protected-power interruption")
    remote.sample_local("PZ-HAB-03", qualified_local_probe=True)
    remote.stage_worker("HAB-03-VEST-CW")
    remote.queue_valve_command(
        "atmosphere", valve, "closed", control_mode="manual",
        local_authority=True, worker_space="HAB-03-VEST-CW", delay_s=2)
    remote.advance(3)
    insist(remote.valves["atmosphere"][valve]["state"] == "closed",
           "worker on site cannot close powerless but mechanical damper")
    remote.shed_load(0.6, local_authority=True, load_plan_verified=True)
    remote.select_main_protected_feed(
        "B", local_authority=True, transfer_verified=True)
    remote.fault_indication("atmosphere", valve, "open")
    reading = remote.observe_switch("atmosphere", valve)
    insist(reading["reading"] == "open"
           and reading["verified_physical_state"] is False
           and remote.valves["atmosphere"][valve]["state"] == "closed",
           "false panel indication mistaken for actual breaker condition")
    report["control_command_fallibility"] = {
        "remote_pending_command_survived_until_power_loss": True,
        "remote_order_failed_without_actuation": True,
        "local_worker_closed_real_valve": True,
        "stuck_telemetry_lies_without_overwriting_physical_state": True,
    }

    transport = new_trial()
    transport.queue_valve_command("atmosphere", valve, "closed",
                                  control_mode="remote",
                                  local_authority=True, delay_s=3)
    transport.fault_control_link(False, local_authority=True)
    transport.advance(4)
    insist(transport.valves["atmosphere"][valve]["state"] == "open",
           "disconnected remote command magically actuated")
    manual_only = new_trial()
    manual_only.sample_local("PZ-HAB-06", qualified_local_probe=True)
    device = "ISO-lt_cooling-BR-06-HAB-06"
    insist(not manual_only.isolator[device]["remote_operable"],
           "old BR-06 repair-era manual-only contract forgotten")
    try:
        manual_only.queue_valve_command(
            "lt_cooling", device, "closed", control_mode="remote",
            local_authority=True)
    except ValueError:
        pass
    else:
        raise AssertionError("patched manual-only BR06 coolant valve obeyed remote")
    manual_only.stage_worker("HAB-06-VEST-CW")
    manual_only.queue_valve_command(
        "lt_cooling", device, "closed", control_mode="manual",
        local_authority=True, worker_space="HAB-06-VEST-CW", delay_s=2)
    manual_only.advance(3)
    insist(manual_only.valves["lt_cooling"][device]["state"] == "closed",
           "patched BR-06 manual actuation fails on-site")

    # An actual engineer already standing at the real damper can lose
    # safe chemistry evidence while a five-second manual close is queued.
    # This both aborts the action and counts the technician as exposed crew.
    endangered = new_trial()
    endangered.sample_local("PZ-HAB-03", qualified_local_probe=True)
    endangered.stage_worker("HAB-03-VEST-CW")
    endangered.queue_valve_command(
        "atmosphere", valve, "closed", control_mode="manual",
        local_authority=True, worker_space="HAB-03-VEST-CW", delay_s=5)
    endangered.ignite("WORKSITE-FIRE", "PZ-HAB-03",
                      fuel_kg=20, burn_kg_s=0.12,
                      smoke_yield_fraction=0.5)
    endangered.advance(6)
    insist(endangered.valves["atmosphere"][valve]["state"] == "open"
           and endangered.cells["PZ-HAB-03"].crew_unsafe_seconds > 0
           and endangered.crew_by_space["HAB-03-VEST-CW"] == 1,
           "unsafe manual worksite was wrongly ignored or worker disappeared")
    endangered.queue_valve_command(
        "atmosphere", valve, "closed", control_mode="remote",
        local_authority=True, delay_s=2)
    endangered.advance(3)
    insist(endangered.valves["atmosphere"][valve]["state"] == "closed",
           "surviving powered remote alternative cannot isolate smoky worksite")
    report["worksite_unsafe_before_manual_control"] = {
        "local_job_aborted_when_sensor_stale": True,
        "on_site_engineer_counted_in_exposure": True,
        "verified_remote_backup_actuated": True,
    }

    # Alarms, physical fire truth and power are separate. A dark sensor
    # cannot prove that no fire exists; false alarms and stuck-silent
    # detector must not mutate the actual combustion event.
    indication = new_trial()
    indication.ignite("REAL-FIRE", "PZ-HAB-03", fuel_kg=20,
                      burn_kg_s=0.08, smoke_yield_fraction=0.25)
    insist(indication.fire_detector_report(3)["report"] == "alarm",
           "healthy powered detector does not indicate fire")
    indication.fault_detector("HAB-03-FIRE-DETECT", "silent")
    insist(indication.fire_detector_report(3)["report"] == "silent"
           and indication.fires["REAL-FIRE"].remaining_fuel_kg == 20,
           "faulted detector illegitimately erases real fire")
    indication.fault_detector("HAB-03-FIRE-DETECT", "false_alarm")
    insist(indication.fire_detector_report(3)["report"] == "alarm"
           and indication.fire_detector_report(3)["credible_fire_truth"] is False,
           "panel readout incorrectly supplies certain world-hidden truth")
    detector_panel = new_trial()
    detector_panel.sample_local("PZ-HAB-03", qualified_local_probe=True)
    detector_panel.stage_worker("HAB-03-COR")
    detector_panel.queue_valve_command(
        "power", "ISO-HAB-03-FIRE-DETECT", "closed", control_mode="manual",
        local_authority=True, worker_space="HAB-03-COR", delay_s=1)
    detector_panel.advance(3)
    insist(detector_panel.valves["power"]["ISO-HAB-03-FIRE-DETECT"]["state"]
           == "closed"
           and detector_panel.fire_detector_report(3)["report"] == "unavailable"
           and detector_panel.assured_power("NODE-HAB-03-EMERGENCY-LIGHT"),
           "independently controlled fire-detector breaker not correctly isolated")
    report["alarm_trust_boundary"] = "powered reading, false report and dark sensor remain distinct"

    # Real cargo zones remain unverified; no hull access path may silently
    # promote a cargo sector to a safe destination. Nor may a closed,
    # rated pressure hatch be treated as walkable based only on graph edges.
    evac = new_trial(breathing_sets=3, portable_lights=1)
    for id in ("PZ-HAB-03", "PZ-BR-03", "PZ-HAB-04"):
        evac.sample_local(id, qualified_local_probe=True)
    insist(evac.plan_crew_route("HAB-03-CAB-03", "HAB-04-COR",
                                portable_lighting=False) is None,
           "closed rated hab bridge counted as available physical route")
    insist(evac.plan_crew_route("HAB-03-CAB-03", "GEN-M-ROOM") is None,
           "unverified industrial machinery location treated safe refuge")
    evac.stage_crew("HAB-03-CAB-03", 2)
    evac.reserve_crew_gear(breathing_sets=2, portable_lights=1,
                           allocation_verified=True)
    insist(evac.open_gate("ACC-BR-03-HAB-03", local_authority=True)
           and evac.open_gate("ACC-BR-03-HAB-04", local_authority=True),
           "positive protected hab bridge access proof not honored")
    evac.ignite("HAB03-FIRE", "PZ-HAB-03", fuel_kg=40,
                burn_kg_s=0.08, smoke_yield_fraction=0.3)
    evac.advance(20)
    for id in ("PZ-HAB-03", "PZ-BR-03", "PZ-HAB-04"):
        evac.sample_local(id, qualified_local_probe=True)
    insist(not evac.cells["PZ-HAB-03"].modeled_unsuited_air_safe(),
           "simulated smoke has no breathing hazard")
    insist(evac.plan_crew_route(
        "HAB-03-CAB-03", "HAB-04-COR",
        crew_count=2, breathing_sets=False,
        portable_lighting=True) is None,
        "smoky HAB route allowed without allocated breathing gear")
    insist(evac.plan_crew_route(
        "HAB-03-CAB-03", "HAB-04-COR",
        crew_count=2, breathing_sets=True,
        portable_lighting=False) is None,
        "unverified bridge lights conjured without portable unit")
    route = evac.plan_crew_route(
        "HAB-03-CAB-03", "HAB-04-COR",
        crew_count=2, breathing_sets=True, portable_lighting=True)
    insist(route is not None
           and "ACC-BR-03-HAB-03" in
                [leg["access_link_id"] for leg in route["legs"]]
           and "ACC-BR-03-HAB-04" in
                [leg["access_link_id"] for leg in route["legs"]],
           "crew route failed to use real bridge hatch IDs")
    original_mass = evac.mass_balance_error_kg()
    moved = evac.evacuate_group(route, qualified_threshold_probes=True)
    insist(moved["arrived"] and moved["reached"] == "HAB-04-COR"
           and evac.crew_by_space["HAB-03-CAB-03"] == 0
           and evac.crew_by_space["HAB-04-COR"] == 2
           and sum(evac.crew_by_space.values()) == 2
           and evac.mass_balance_error_kg() < 1e-5,
           "crew transit teleported, duplicated, or lost material accounting")
    report["real_cabin_to_hab04_evacuated"] = {
        "personnel": 2,
        "route_ids": [leg["access_link_id"] for leg in route["legs"]],
        "walk_reference_seconds": route["reference_duration_s"],
        "arrival_after_time_s": moved["elapsed_ship_time_s"],
        "smoke_breathing_sets_required": True,
        "unknown_cargo_not_routeable": True,
    }

    # Damage/locked bridge immediately removes the route regardless of
    # what the unmodified architectural graph says. Power loss can make
    # unsuited routes fail due to unavailable/emergency lighting.
    locked = new_trial(portable_lights=0)
    for zone in ("PZ-HAB-03", "PZ-BR-03", "PZ-HAB-04"):
        locked.sample_local(zone, qualified_local_probe=True)
    locked.open_gate("ACC-BR-03-HAB-03", local_authority=True)
    locked.open_gate("ACC-BR-03-HAB-04", local_authority=True)
    locked.set_access_fault("ACC-BR-03-HAB-04", impassable=True)
    insist(locked.plan_crew_route("HAB-03-COR", "HAB-04-COR",
                                 portable_lighting=False) is None,
           "known blocked pressure passage still assumed traversable")
    dark = new_trial(portable_lights=1)
    dark.sample_local("PZ-HAB-03", qualified_local_probe=True)
    dark.set_generator("GEN-M", False, local_authority=True)
    dark.set_generator("GEN-B", False, local_authority=True)
    insist(dark.plan_crew_route("HAB-03-CAB-01", "HAB-03-COR",
                               portable_lighting=False) is None,
           "unpowered passage magically illuminated itself")
    dark.reserve_crew_gear(portable_lights=1, allocation_verified=True)
    insist(dark.plan_crew_route("HAB-03-CAB-01", "HAB-03-COR",
                               portable_lighting=True) is not None,
           "verified portable light cannot substitute for failed arc lighting")

    # A worker is one of the forty real bodies. Do not create a separate
    # 40-person cargo-like "engineer population" atop the crew manifest.
    staffing = new_trial()
    staffing.sample_local("PZ-HAB-03", qualified_local_probe=True)
    staffing.stage_worker("HAB-03-VEST-CW")
    staffing.stage_crew("HAB-03-COR", 39)
    insist(sum(staffing.crew_by_space.values()) == 40
           and staffing.cells["PZ-HAB-03"].crew == 40,
           "maintenance worker not charged to real crew occupancy")
    try:
        staffing.stage_crew("HAB-03-COR", 1)
    except ValueError:
        pass
    else:
        raise AssertionError("forty plus one phantom worker accepted")

    reloc = new_trial()
    reloc.sample_local("PZ-HAB-03", qualified_local_probe=True)
    reloc.stage_worker("HAB-03-COR")
    relocation = reloc.plan_crew_route("HAB-03-COR", "HAB-03-VEST-CW")
    insist(relocation is not None, "legitimate technician intra-arc route denied")
    moved_worker = reloc.evacuate_group(
        relocation, qualified_threshold_probes=True)
    insist(moved_worker["arrived"]
           and reloc.workers["HAB-03-COR"] == 0
           and reloc.workers["HAB-03-VEST-CW"] == 1
           and sum(reloc.crew_by_space.values()) == 1,
           "qualified technician teleported, multiplied or left behind")

    # 40-character passage under finite physical link traversal; the
    # published MUD remains untouched and no occupant may multiply.
    full = new_trial()
    full.sample_local("PZ-HAB-03", qualified_local_probe=True)
    full.stage_crew("HAB-03-COR", 40)
    full_route = full.plan_crew_route(
        "HAB-03-COR", "HAB-03-VEST-CW", crew_count=40)
    insist(full_route is not None and
           isclose(full_route["reference_duration_s"], 80),
           "forty-person group incorrectly assigned single-person travel time")
    done = full.evacuate_group(full_route, qualified_threshold_probes=True)
    insist(done["arrived"] and full.crew_by_space["HAB-03-VEST-CW"] == 40
           and sum(full.crew_by_space.values()) == 40,
           "forty-person physical passage lost/duplicated occupants")
    report["forty_person_casualty_transit"] = {
        "people": 40, "reference_passage_s": full_route["reference_duration_s"],
        "crew_count_conserved": True,
    }

    return report


def negative_tests():
    bad = [
        lambda t: t.set_generator("SHORE-PWR", True, local_authority=True),
        lambda t: t.set_generator("GEN-A", 1, local_authority=True),
        lambda t: t.shed_load(4.0, local_authority=True,
                             load_plan_verified=True),
        lambda t: t.shed_load(0.6, local_authority=True,
                             load_plan_verified=False),
        lambda t: t.change_power_tie(True, local_authority=True,
                                     synchronisation_verified=False),
        lambda t: t.select_protected_feed(9, "B", local_authority=True,
                                         transfer_verified=True),
        lambda t: t.select_protected_feed(3, "B", local_authority=True,
                                         transfer_verified=False),
        lambda t: t.select_main_protected_feed(
            "X", local_authority=True, transfer_verified=True),
        lambda t: t.queue_valve_command(
            "power", "ISO-NOT-REGISTERED", "closed",
            control_mode="remote", local_authority=True),
        lambda t: t.queue_valve_command(
            "power", "ISO-GEN-M", "closed",
            control_mode="magic", local_authority=True),
        lambda t: t.queue_valve_command(
            "power", "ISO-GEN-M", "closed",
            control_mode="remote", local_authority=False),
        lambda t: t.stage_crew("GEN-M-ROOM", 1),
        lambda t: t.stage_crew("HAB-03-COR", 41),
        lambda t: t.reserve_crew_gear(breathing_sets=5,
                                     allocation_verified=True),
        lambda t: t.reserve_crew_gear(portable_lights=4,
                                     allocation_verified=True),
        lambda t: t.plan_crew_route("HAB-03-COR", "ROOM-INVENTED"),
        lambda t: t.plan_crew_route("HAB-03-COR", "HAB-04-COR",
                                   crew_count=41),
        lambda t: t.set_access_fault("ACC-INVENTED", impassable=True),
        lambda t: t.fault_indication("power", "ISO-MISSING", "open"),
        lambda t: t.fault_detector("HAB-03-AHU", "silent"),
        lambda t: t.ignite("F-UNBOUND", "PZ-HAB-03",
                            fuel_kg=2, burn_kg_s=0.1,
                            hazard="energized_electrical"),
        lambda t: t.ignite("F-WRONG", "PZ-HAB-03",
                            fuel_kg=2, burn_kg_s=0.1,
                            hazard="energized_electrical",
                            energized_load_node="NODE-HAB-03-FIRE-DETECTOR-GHOST"),
        lambda t: t.has_power_path("NODE-GHOST"),
        lambda t: t.queue_valve_command("atmosphere",
                "ISO-lt_cooling-BR-06-HAB-06", "closed",
                control_mode="remote", local_authority=True),
    ]
    passed = 0
    for i, mutate in enumerate(bad, 1):
        trial = new_trial()
        try:
            mutate(trial)
        except (ValueError, KeyError):
            passed += 1
            continue
        raise AssertionError("invalid electrical/evacuation mutation accepted: "
                             + str(i))
    topo, gas, env = load_model()
    ship = read_ship()
    corrupt_cases = [
        ("missing_power_breaker", lambda s: s["isolation_points"].remove(
            next(v for v in s["isolation_points"] if v["id"] ==
                 "ISO-HAB-03-CAB-07-LP"))),
        ("missing_door", lambda s: s["access_links"].remove(
            next(v for v in s["access_links"] if v["id"] ==
                 "ACC-BR-03-HAB-03"))),
        ("invented_power_feed", lambda s: next(
            v for v in s["service_edges"] if v["id"] ==
            "EDGE-PWR-A-BR-03").update(to_node="NODE-GHOST")),
        ("pressure_boundary_lied", lambda s: next(
            v for v in s["access_links"] if v["id"] ==
            "ACC-BR-03-HAB-03").update(pressure_boundary=False)),
    ]
    for name, mutate in corrupt_cases:
        bad_ship = deepcopy(ship)
        mutate(bad_ship)
        try:
            ElectricalEvacuationTrial(topo, gas, env, bad_ship)
        except (ValueError, KeyError):
            passed += 1
            continue
        raise AssertionError("corrupt actual graph silently accepted: " + name)
    return passed


if __name__ == "__main__":
    results = validate()
    results["invalid_cases_rejected"] = negative_tests()
    print(json.dumps(results, indent=2, sort_keys=True))
    print("OX_ELECTRICAL_CONTROL_AND_REAL_ACCESS_CASUALTY_PASS")
