#!/usr/bin/env python3
"""Forty-person whole-ship design-casualty exercise for the fictional Ox.

The ship model, powers, valves, pressures and passage IDs come from the
candidate design. Named crew, initial stations, imperfect reported evidence,
policies, times, casualty and PPE capacity are explicit test assumptions.
NOT an Evennia crew implementation, Concordia run or real-world certification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose

from electrical_evacuation_v05 import (
    ElectricalEvacuationTrial, new_trial as create_trial,
)

TARGET_HORIZON_S = 240.0
BREATHING_SET_REFERENCE_S = 180.0
LOCAL_SMOKE_OBSERVATION_KG = 0.005
CASUALTY_ZONE = "PZ-HAB-03"
REFUGE_ZONE = "PZ-HAB-04"
PRIMARY_CASUALTY_LOAD = "NODE-PWR-HAB-03-CAB-07-FANCOIL"
EXITS = ("ACC-BR-03-HAB-03", "ACC-BR-03-HAB-04")
VENT_DAMPERS = ("ISO-AIR-BR-02-HAB-03", "ISO-AIR-BR-03-HAB-03")


@dataclass
class Crew:
    id: str
    role: str
    initial_space: str
    current_space: str
    experience: str
    observations: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    gear_breathing: bool = False
    gear_light: bool = False
    wearing_from_s: float | None = None
    unsafe_person_seconds: float = 0.0


def reference_roster() -> list[Crew]:
    """The same 40 distinct positions, jobs and knowledge in every replay."""
    crew = []
    for n in range(1, 9):
        tag = "HAB-%02d" % n
        crew.extend((
            Crew("CREW-%03d" % (3*n-2), "off_duty",
                 tag+"-CAB-01", tag+"-CAB-01", "basic_safety"),
            Crew("CREW-%03d" % (3*n-1), "utility_rating",
                 tag+"-CAB-02", tag+"-CAB-02", "basic_safety"),
            Crew("CREW-%03d" % (3*n), "sector_watch",
                 tag+"-COR", tag+"-COR", "damage_control"),
        ))
    for n in range(1, 9):
        room = "BR-%02d" % n
        crew.append(Crew("CREW-%03d" % (24+n), "bridge_technician",
                         room, room, "pressure_doors"))
    axial = (
        ("CMD-PRIMARY", "captain", "incident_command"),
        ("CMD-EMERG", "electrical_officer", "source_isolation"),
        ("SHOP-MECH", "mechanic", "work_rotor_repair"),
        ("SPARES-CENTRAL", "stores_specialist", "inventory"),
        ("TRUNK-A-BOW", "bow_watch", "trunk_isolation"),
        ("TRUNK-A-DR-01", "freight_technician", "cargo_station"),
        ("TRUNK-A-AFT", "aft_watch", "generator_plant"),
        ("TRUNK-B-AFT", "damage_control_officer", "a_b_spine_mains"),
    )
    for i, (room, role, training) in enumerate(axial, start=33):
        crew.append(Crew("CREW-%03d" % i, role, room, room, training))
    assert len(crew) == 40 and len({c.id for c in crew}) == 40
    assert len({c.current_space for c in crew}) == 40
    return crew


class CrewIncidentPhysics(ElectricalEvacuationTrial):
    """Account individual exposure per timestep, including persons in transit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.individuals: dict[str, Crew] = {}

    def _step(self, dt):
        super()._step(dt)
        for person in self.individuals.values():
            zone = self.space[person.current_space]["pressure_zone"]
            cell = self.cells[zone]
            gear_protects = (
                person.gear_breathing
                and person.wearing_from_s is not None
                and self.time_s <= person.wearing_from_s
                    + BREATHING_SET_REFERENCE_S
                and not cell.unknown_exposure
                and 70.0 <= cell.pressure_kpa <= 120.0
                and cell.temperature_K <= 323.15
            )
            if not gear_protects and not cell.modeled_unsuited_air_safe():
                person.unsafe_person_seconds += dt


def new_physics() -> CrewIncidentPhysics:
    from pressure_damage_sim_v05 import load_model
    from fire_smoke_thermal_v05 import read_ship
    topology, gas, environmental = load_model()
    return CrewIncidentPhysics(
        topology, gas, environmental, read_ship(),
        suppression_water_kg=150.0, filter_capacity_kg=1.0,
        reference_breathing_sets=2,
        reference_portable_lights=2)


class FortyCrewVoyage:
    def __init__(self, *, response: str, jam_hab03_hatch: bool = False):
        if response not in ("containment_first", "rescue_first"):
            raise ValueError("unknown casualty response policy")
        if type(jam_hab03_hatch) is not bool:
            raise ValueError("invalid mechanical failure selection")
        self.response = response
        self.sim = new_physics()
        self.personnel = {p.id: p for p in reference_roster()}
        self.sim.individuals = self.personnel
        self.jam_hab03_hatch = jam_hab03_hatch
        self.events: list[dict] = []
        self.evacuated: list[str] = []
        self.bridge_closure_failed: list[str] = []
        self.reported_alarm = None
        self.local_smoke_report = None
        self.actual_damper_states_after_response: dict[str, str] = {}
        self.suppression_started_s: float | None = None
        self._setup()

    def emit(self, actor: str, action: str, *, observed=None, **detail):
        if actor not in self.personnel:
            raise ValueError("phantom incident responder")
        row = {"at_s": round(self.sim.time_s, 3),
               "actor": actor, "action": action, **detail}
        self.events.append(row)
        if observed is not None:
            self.personnel[actor].observations.append({
                "at_s": row["at_s"], "evidence": observed,
                "source": action})
        else:
            self.personnel[actor].orders.append(row)

    def _setup(self):
        # All nominated spaces have actual authored pressure-zone identities.
        # Explicit assumption: qualified startup readings exist for every
        # pressure cell occupied; there is NO all-ship omniscient sensor.
        sampled = set()
        for p in self.personnel.values():
            row = self.sim.space.get(p.initial_space)
            if row is None:
                raise ValueError("crew placed in invented room")
            zone = row["pressure_zone"]
            if (zone not in self.sim.cells or
                    row["access_class"] != "crew" or
                    p.initial_space in
                    (s.initial_space for s in self.personnel.values()
                     if s.id != p.id)):
                raise ValueError("unverified or duplicated initial crew station")
            if zone not in sampled:
                self.sim.sample_local(zone, qualified_local_probe=True)
                sampled.add(zone)
            self.sim.stage_crew(p.initial_space, 1)
            self.emit(p.id, "startup_station_check",
                      observed={"space": p.initial_space,
                                "pressure_zone": zone,
                                "reference_pressure_kPa":
                                    round(self.sim.cells[zone].pressure_kpa, 3),
                                "scope": "local_startup_instrument_only"})
            self.emit(p.id, "remain_at_actual_initial_station",
                      physical_room=p.initial_space, reason="standing_shift_order")
        if sum(self.sim.crew_by_space.values()) != 40:
            raise AssertionError("forty-person manifest not staged")

        # Explicit reference: two suits and two lamps were issued to two
        # HAB03 cabin sleepers BEFORE the casualty, not teleported out of
        # a service locker after smoke blocks access.
        self.sim.reserve_crew_gear(
            breathing_sets=2, portable_lights=2, allocation_verified=True)
        for person_id in ("CREW-007", "CREW-008"):
            p = self.personnel[person_id]
            if p.initial_space not in ("HAB-03-CAB-01", "HAB-03-CAB-02"):
                raise AssertionError("PPE issued to wrong station")
            p.gear_breathing = True
            p.gear_light = True
            self.emit(person_id, "personal_emergency_gear_prepositioned",
                      stock_debited=True, no_remote_delivery=True)

        # Authored real BR03 hatches happen to be open during this specific
        # working shift; they are deliberately NOT assumed open by default.
        door_operator = self.personnel["CREW-027"]
        if door_operator.current_space != "BR-03":
            raise AssertionError("bridge operator not physically there")
        for gate in EXITS:
            if not self.sim.open_gate(gate, local_authority=True):
                raise AssertionError("authored healthy startup bridge cannot open")
            self.emit(door_operator.id, "locally_confirmed_open_pressure_gate",
                      access_link_id=gate)

        if self.jam_hab03_hatch:
            # The failure is introduced after startup opening, at the
            # common casualty time origin in every replay.
            self.sim.fail_gate_open(EXITS[0])
            self.emit("CREW-027", "observed_jammed_open",
                      access_link_id=EXITS[0])

        # The physical source is a real energized replacement-era fan-coil,
        # not a hypothetical 'HAB03 equipment' with invented wiring.
        self.sim.ignite(
            "INCIDENT-FANCOIL-03-07", CASUALTY_ZONE,
            fuel_kg=28.0, burn_kg_s=0.07,
            smoke_yield_fraction=0.3,
            hazard="energized_electrical",
            energized_load_node=PRIMARY_CASUALTY_LOAD)
        self.sim.fault_detector("HAB-03-FIRE-DETECT", "silent")

    def _crew_local_smoke_evidence(self) -> str:
        # This is an OBSERVATION by a person actually inside HAB-03,
        # with a finite phenomenological detection threshold. It is not
        # reading the hidden fire object to tell the captain its cause.
        observer = self.personnel["CREW-009"]
        if self.sim.space[observer.current_space]["pressure_zone"] != CASUALTY_ZONE:
            raise AssertionError("remote crew given local smoke smell")
        air = self.sim.cells[CASUALTY_ZONE]
        evidence = ("odor_and_visible_smoke" if
                    air.trace_kg >= LOCAL_SMOKE_OBSERVATION_KG
                    else "no_local_smoke_observed")
        self.emit(observer.id, "witnessed_local_air_condition",
                  observed=evidence)
        return evidence

    def _station_command_report(self):
        # Stuck-silent fire panel and human witness can contradict.
        captain = self.personnel["CREW-033"]
        if captain.current_space != "CMD-PRIMARY":
            raise AssertionError("commander not at known command position")
        reading = self.sim.fire_detector_report(3)
        self.reported_alarm = reading["report"]
        self.emit(captain.id, "received_fire_panel_indication",
                  observed=reading)
        if (not self.sim.control_link_online
                or not self.sim.assured_power("NODE-HAB-03-COMMS-NODE")
                or not self.sim.assured_power("PWR-PROT")):
            self.local_smoke_report = "COMMS_UNAVAILABLE"
        else:
            self.local_smoke_report = self._crew_local_smoke_evidence()
            self.emit(captain.id, "received_HAB03_witness_report",
                      observed=self.local_smoke_report)
        if self.local_smoke_report != "odor_and_visible_smoke":
            raise RuntimeError("evidence did not justify either response")

    def _shutdown_hab03_outlets(self):
        commander = self.personnel["CREW-033"]
        if not self.sim.assured_power("PWR-PROT"):
            raise AssertionError("no actual protected remote control service")
        for valve in VENT_DAMPERS:
            cmd = self.sim.queue_valve_command(
                "atmosphere", valve, "closed",
                control_mode="remote", local_authority=True, delay_s=2)
            self.emit(commander.id, "ordered_ventilation_partition",
                      valve_id=valve, order_receipt=cmd)
        self.sim.advance(3)
        self.actual_damper_states_after_response = {
            id: self.sim.valves["atmosphere"][id]["state"]
            for id in VENT_DAMPERS}
        # Readbacks are fallible; actual states belong only in private
        # evaluator outcomes, never a character's 'observed' payload.
        for valve in VENT_DAMPERS:
            reported = self.sim.observe_switch("atmosphere", valve)
            self.emit(commander.id, "remote_damper_panel_readback",
                      observed={"device": valve, **reported})

    def _close_pressure_transfer(self):
        operator = self.personnel["CREW-027"]
        if operator.current_space != "BR-03":
            raise AssertionError("bridge threshold closure has no local witness")
        for gate in EXITS:
            # Even a local positive-close command takes time. A jam will
            # fail physically and is separately reported; never conjure seal.
            self.sim.advance(2)
            success = self.sim.close_gate(gate)
            self.emit(operator.id, "bridge_pressure_boundary_close_attempt",
                      access_link_id=gate, physically_shut=success)
            if not success:
                self.bridge_closure_failed.append(gate)

    def _deenergize_and_suppress(self):
        engineer = self.personnel["CREW-034"]
        if engineer.current_space != "CMD-EMERG":
            raise AssertionError("generator isolation ordered by absent officer")
        self.sim.advance(4)
        self.sim.set_generator("GEN-B", False, local_authority=True)
        self.emit(engineer.id, "electrical_source_B_isolated",
                  actual_generator_id="GEN-B",
                  consequence="B_distribution_lost_protected_A_retained")
        if self.sim.has_power_path(PRIMARY_CASUALTY_LOAD):
            raise AssertionError("electrical source isolation failed to cut real load")
        commander = self.personnel["CREW-033"]
        if not self.sim.start_mist(
            CASUALTY_ZONE, kg_s=0.6,
            local_authority=True, compatible_agent=True,
            energy_isolated=True):
            raise AssertionError("suppression denied after verified load isolation")
        self.suppression_started_s = self.sim.time_s
        self.emit(commander.id, "fire_main_mist_admitted",
                  delivery_reference_kg_s=0.6,
                  verified_power_path="protected_A",
                  finite_water_allocation=True)

    def _route_person(self, person_id: str) -> bool:
        p = self.personnel[person_id]
        if not p.gear_breathing or not p.gear_light:
            raise ValueError("missing individually assigned evacuation protection")
        if p.wearing_from_s is None:
            p.wearing_from_s = self.sim.time_s
            self.emit(p.id, "donned_allocated_smoke_mask",
                      expires_after_reference_s=BREATHING_SET_REFERENCE_S)
        # Qualified staffed receivers in the actual two next HAB pressure
        # compartments provide fresh admission readings at route-planning
        # time; the executing helper refreshes each threshold on arrival.
        for zone in (CASUALTY_ZONE, "PZ-BR-03", REFUGE_ZONE):
            self.sim.sample_local(zone, qualified_local_probe=True)
        route = self.sim.plan_crew_route(
            p.current_space, "HAB-04-COR", crew_count=1,
            breathing_sets=True, portable_lighting=True)
        if route is None:
            self.emit(p.id, "evacuation_route_rejected",
                      reason="current_access_or_atmosphere_unverified")
            return False
        self.emit(p.id, "individual_route_selected",
                  passage_ids=[leg["access_link_id"] for leg in route["legs"]],
                  walk_reference_s=route["reference_duration_s"])
        for leg in route["legs"]:
            if self.sim.time_s > p.wearing_from_s + BREATHING_SET_REFERENCE_S:
                self.emit(p.id, "smoke_mask_reference_endurance_expired")
                return False
            one = {
                "personnel": 1,
                "start": leg["from"],
                "destination": leg["to"],
                "requires_breathing_set": True,
                "requires_portable_light": True,
                "legs": [leg],
            }
            result = self.sim.evacuate_group(
                one, qualified_threshold_probes=True)
            # Even a failed passage consumes time. Do not change a
            # character's position until the ship physically reports arrival.
            if not result["arrived"]:
                self.emit(p.id, "individual_evacuate_blocked",
                          attempted_link=leg["access_link_id"],
                          final_room=result["reached"])
                return False
            p.current_space = result["reached"]
            self.emit(p.id, "physically_traversed_link",
                      access_link_id=leg["access_link_id"],
                      reached=p.current_space)
        if p.current_space != "HAB-04-COR":
            raise AssertionError("claimed rescue without arriving at actual refuge")
        self.evacuated.append(p.id)
        self.emit(p.id, "reached_neighbouring_HAB04",
                  survival="reference_route_completed_not_health_guarantee")
        return True

    def run(self):
        # Fixed matched incident and roster. The sole early decision is
        # whether to prioritize closing/open-air exposure boundaries or
        # keep this route available to move its occupants first.
        if self.sim.time_s < 12:
            self.sim.advance(12 - self.sim.time_s)
        self._station_command_report()
        for p in self.personnel.values():
            if p.id not in ("CREW-007", "CREW-008", "CREW-027",
                            "CREW-033", "CREW-034"):
                self.emit(p.id, "received_incident_shift_order",
                          disposition=("hold_and_report"
                                       if p.role != "sector_watch"
                                       else "monitor_local_atmosphere"),
                          assigned_at_actual_room=p.current_space)
        if self.response == "containment_first":
            self._close_pressure_transfer()
            self._shutdown_hab03_outlets()
            self._deenergize_and_suppress()
            for id in ("CREW-007", "CREW-008"):
                p = self.personnel[id]
                p.wearing_from_s = self.sim.time_s
                self.emit(id, "remained_in_isolated_arc_with_smoke_set",
                          decision="contain_and_wait_for_checked_access")
        else:
            for id in ("CREW-007", "CREW-008"):
                self._route_person(id)
            self._close_pressure_transfer()
            self._shutdown_hab03_outlets()
            self._deenergize_and_suppress()
        if self.sim.time_s >= TARGET_HORIZON_S:
            raise AssertionError("casualty response exceeded fixed horizon")
        self.sim.advance(TARGET_HORIZON_S - self.sim.time_s)
        return self.outcome()

    def outcome(self):
        people = sorted(self.personnel.values(), key=lambda x: x.id)
        # No technician, off-duty occupant or bridge watch may vanish,
        # multiply, or be credited twice in the physics model.
        if (len(people) != 40 or
            len({p.id for p in people}) != 40 or
            sum(self.sim.crew_by_space.values()) != 40 or
            sum(c.crew for c in self.sim.cells.values()) != 40 or
            any(self.sim.crew_by_space[p.current_space] <= 0
                for p in people)):
            raise AssertionError("forty-crew physical accounting violated")
        locations = {}
        for p in people:
            locations[p.current_space] = locations.get(p.current_space, 0)+1
        if dict(locations) != {k:v for k,v in
                              self.sim.crew_by_space.items() if v > 0}:
            raise AssertionError("person identities no longer match occupied rooms")
        if self.sim.mass_balance_error_kg() >= 1e-5:
            raise AssertionError("forty-crew trial violates ship material balance")
        if any(not p.observations or not p.orders for p in people):
            raise AssertionError("nominal crew lacks own observation or disposition")
        return {
            "policy": self.response,
            "hatch_fault": ("HAB03_BR03_end_jammed_open"
                            if self.jam_hab03_hatch else "none"),
            "reference_horizon_s": round(self.sim.time_s, 3),
            "actual_people": len(people),
            "distinct_starting_rooms": len({p.initial_space for p in people}),
            "occupied_pressure_cells": len({
                self.sim.space[p.initial_space]["pressure_zone"] for p in people}),
            "sensor_contradiction": {
                "HAB03_remote_fire_panel": self.reported_alarm,
                "crew_witness_local": self.local_smoke_report,
            },
            "evacuated_people": sorted(self.evacuated),
            "failed_pressure_gate_closures": sorted(self.bridge_closure_failed),
            "HAB04_smoke_trace_kg": round(
                self.sim.cells[REFUGE_ZONE].trace_kg, 6),
            "BR03_smoke_trace_kg": round(
                self.sim.cells["PZ-BR-03"].trace_kg, 6),
            "fire_fuel_consumed_kg": round(
                self.sim.fires["INCIDENT-FANCOIL-03-07"].consumed_fuel_kg, 5),
            "suppression_started_s": round(self.suppression_started_s, 3),
            "water_used_kg": round(self.sim.water_used_kg, 4),
            "remaining_water_kg": round(self.sim.water_remaining_kg, 4),
            "air_reserve_banks_kg": {
                id: round(value, 3) for id, value
                in self.sim.bank_kg.items()},
            "total_person_unsafe_seconds": round(sum(
                p.unsafe_person_seconds for p in people), 3),
            "individual_crew": [
                {"id": p.id, "role": p.role,
                 "initial_space": p.initial_space,
                 "final_space": p.current_space,
                 "gear_breathing_preissued": p.gear_breathing,
                 "has_portable_light": p.gear_light,
                 "unsafe_person_seconds": round(p.unsafe_person_seconds, 3),
                 "observations": len(p.observations),
                 "orders_and_actions": len(p.orders)}
                for p in people],
            "timeline": list(self.events),
            "gas_mass_balance_error_kg": round(
                self.sim.mass_balance_error_kg(), 9),
            "limitations": ("design_only_assumed_staff_stations_gear_sensor_samples_"
                             "rates_and_response_policy_not_Evennia_or_live_AI"),
        }


def comparative_trials() -> dict:
    scenarios = {}
    for name, policy, failure in (
        ("containment_first", "containment_first", False),
        ("rescue_first", "rescue_first", False),
        ("containment_jammed_open", "containment_first", True),
    ):
        scenarios[name] = FortyCrewVoyage(
            response=policy, jam_hab03_hatch=failure).run()
    return scenarios
