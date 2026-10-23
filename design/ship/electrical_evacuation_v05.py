#!/usr/bin/env python3
"""Design-reference power, control failures and crew routing on the real Ox graph.

All source/switch states, operator locations, probes and protective equipment
are explicit scenario assumptions. This is NOT the live Evennia or AI handler.
"""
from __future__ import annotations

from collections import defaultdict, deque
from heapq import heappop, heappush
from math import ceil, isclose, isfinite

from fire_smoke_thermal_v05 import (
    FireSmokeThermalTrial, new_trial as base_trial, read_ship,
)
from pressure_damage_sim_v05 import load_model, positive, require

GENERATOR_MW = {"GEN-M": 3.0, "GEN-A": 0.65, "GEN-B": 0.65}
SHIP_CONTINUOUS_MW = 3.3
NORMAL_DEMAND_MW = 1.55
MAX_CREW = 40
BATCH_WALKERS = 4  # explicit scenario screen, NOT a rated corridor throughput
POWER_SOURCE_IDS = {
    "GEN-M": "NODE-GEN-M",
    "GEN-A": "NODE-GEN-A",
    "GEN-B": "NODE-GEN-B",
}
EXCLUDED_POWER_SOURCES = ("SHORE-PWR", "BAT-COMMON-OPS", "BAT-COMMON-PROT")


class ElectricalEvacuationTrial(FireSmokeThermalTrial):
    """Reference coupling across source power graph, control and occupied routes."""

    def __init__(self, topology, gas, environmental, ship, *,
                 volume_basis="midpoint", suppression_water_kg=150.0,
                 filter_capacity_kg=10.0, reference_breathing_sets=4,
                 reference_portable_lights=2):
        super().__init__(topology, gas, environmental, ship,
                         volume_basis=volume_basis,
                         suppression_water_kg=suppression_water_kg,
                         filter_capacity_kg=filter_capacity_kg)
        power_nodes = [x for x in ship["service_nodes"]
                       if x["network"] == "power"]
        power_edges = [x for x in ship["service_edges"]
                       if x["network"] == "power"]
        power_isolators = [x for x in ship["isolation_points"]
                           if x["network"] == "power"]
        require((len(power_nodes), len(power_edges), len(power_isolators))
                == (438, 450, 466), "authored power topology has changed")
        require(len({x["id"] for x in power_nodes}) == 438
                and len({x["id"] for x in power_edges}) == 450
                and len({x["id"] for x in power_isolators}) == 466,
                "duplicate power connection or breaker")
        known_nodes = {x["id"] for x in power_nodes}
        known_breakers = {x["id"] for x in power_isolators}
        for edge in power_edges:
            require(edge["from_node"] in known_nodes
                    and edge["to_node"] in known_nodes
                    and all(id in known_breakers for id in edge["isolator_ids"]),
                    "invented power bus, feeder or breaker: " + edge["id"])
        self.edges["power"] = sorted(power_edges, key=lambda x: x["id"])
        self.valves["power"] = {
            x["id"]: {"state": x["normal_state"], "fault": "working"}
            for x in power_isolators
        }
        self.power_edge_selected = {
            x["id"]: x["normal_state"] != "standby" for x in power_edges
        }
        self._cached_power_nodes = None
        self.generators_online = {"GEN-M": True, "GEN-A": False, "GEN-B": True}
        self.requested_load_MW = NORMAL_DEMAND_MW
        self.unrated_sources_not_dispatchable = EXCLUDED_POWER_SOURCES
        self.control_link_online = True
        self.control_indication_faults = {}
        self.reported_switches = {}
        self.pending_commands = []
        self.last_command_number = 0

        self.access = {x["id"]: x for x in ship["access_links"]}
        require(len(self.access) == len(ship["access_links"]) == 517,
                "access passage duplicated or removed")
        for a in self.access.values():
            require(a["from"] in self.space and a["to"] in self.space,
                    "access passage ends in invented room: " + a["id"])
            require(a["pressure_boundary"] == (a["id"] in self.gates),
                    "pressure-boundary ID does not reconcile: " + a["id"])
            require(isinstance(a["traverse_time_s"], (int, float))
                    and not isinstance(a["traverse_time_s"], bool)
                    and 0 < a["traverse_time_s"] <= 10000,
                    "unsupported traversal time: " + a["id"])
        require(len(self.gates) == 339, "pressure boundary mapping failed")
        self.access_blocked = set()
        self.workers = defaultdict(int)
        self.crew_by_space = defaultdict(int)
        self.reference_breathing_sets = self._count_stock(
            reference_breathing_sets, "breathing sets")
        self.reference_portable_lights = self._count_stock(
            reference_portable_lights, "portable lights")
        self.issued_breathing_sets = 0
        self.issued_portable_lights = 0
        self.detector_faults = {}
        self.electrical_fire_load_nodes = {}
        self.thermal_power_witness = True
        self.fire_pump_power_witness = {
            "FIRE-PUMP-FWD": True, "FIRE-PUMP-AFT": True}
        self.event("electrical_reference_initialized",
                   power_sources=["GEN-M", "GEN-B"],
                   demand_MW=NORMAL_DEMAND_MW,
                   unqualified_sources=list(EXCLUDED_POWER_SOURCES))

    @staticmethod
    def _count_stock(n, what):
        require(type(n) is int and 0 <= n <= MAX_CREW,
                "unqualified scenario allocation: " + what)
        return n

    def _edge_live(self, edge):
        return (self.power_edge_selected[edge["id"]]
                and self._active("power", edge)
                and edge["current_condition"] == "serviceable")

    def change_valve(self, network, valve_id, state, *,
                     local_authority, control_mode="remote"):
        # This low-level physical intervention API is for scenario setup.
        # Crew-issued orders must use queue_valve_command(), where manual
        # worker presence, sensor knowledge and actuator delay are checked.
        moved = super().change_valve(
            network, valve_id, state, local_authority=local_authority,
            control_mode=control_mode)
        if moved and network == "power":
            self._cached_power_nodes = None
        return moved

    def fail_valve(self, network, valve_id, stuck_state):
        super().fail_valve(network, valve_id, stuck_state)
        if network == "power":
            self._cached_power_nodes = None

    def power_reachability(self):
        """Directed feeds, bidirectional only where actual ring/tie can backfeed.

        In particular, the protected bus and its batteries cannot energize
        main boards by wrongly reversing a protected source-selection feed.
        """
        if self._cached_power_nodes is not None:
            return self._cached_power_nodes
        graph = defaultdict(set)
        for e in self.edges["power"]:
            if not self._edge_live(e):
                continue
            a, b = e["from_node"], e["to_node"]
            graph[a].add(b)
            if e["kind"] in ("bridge_feeder", "cross_tie"):
                graph[b].add(a)
        starts = sorted(POWER_SOURCE_IDS[id]
                        for id, online in self.generators_online.items()
                        if online and self._generator_connected(id))
        reached = set(starts)
        q = deque(starts)
        while q:
            for adj in sorted(graph[q.popleft()]):
                if adj not in reached:
                    reached.add(adj)
                    q.append(adj)
        self._cached_power_nodes = frozenset(reached)
        return self._cached_power_nodes

    def _generator_connected(self, id):
        # Physically open feeder breaker means generator does not deliver,
        # regardless of generator ON_LOAD indication.
        route = next(e for e in self.edges["power"]
                     if e["id"] == "EDGE-" + id)
        return self._edge_live(route)

    def available_MW(self):
        connected = {id: rating for id, rating in GENERATOR_MW.items()
                     if self.generators_online[id]
                     and self._generator_connected(id)}
        return min(SHIP_CONTINUOUS_MW, sum(connected.values()))

    def power_budget_ok(self):
        return self.requested_load_MW <= self.available_MW() + 1e-9

    def has_power_path(self, node_id):
        require(node_id in self.node and
                self.node[node_id]["network"] == "power",
                "not an actual registered electrical node")
        return node_id in self.power_reachability()

    def assured_power(self, node_id):
        # A copper path with overloaded generation is NOT proof of
        # functional service: explicit load shedding is required.
        return self.power_budget_ok() and self.has_power_path(node_id)

    def electrical_summary(self):
        critical = ["PWR-MSB-A", "PWR-MSB-B", "PWR-PROT",
                    "NODE-HAB-03-PDB-A", "NODE-HAB-03-PDB-B",
                    "NODE-HAB-03-FIRE-DETECT",
                    "NODE-HAB-03-EMERGENCY-LIGHT",
                    "NODE-HAB-06-ECLSS-A-LP",
                    "NODE-HAB-08-ECLSS-B-LP"]
        return {
            "available_dispatch_MW": round(self.available_MW(), 3),
            "requested_schedule_MW": round(self.requested_load_MW, 3),
            "schedule_within_dispatch_budget": self.power_budget_ok(),
            "source_dispatch": dict(sorted(self.generators_online.items())),
            "power_connections": len(self.edges["power"]),
            "breakers": len(self.valves["power"]),
            "outcomes": {id: {"physical_path": self.has_power_path(id),
                               "assured_under_selected_load":
                                   self.assured_power(id)}
                         for id in critical},
            "backup_battery_and_shore_endurance":
                "UNKNOWN_not_credited_as_unbounded_generation",
        }

    def set_generator(self, id, online, *, local_authority):
        require(id in GENERATOR_MW and type(online) is bool
                and local_authority is True,
                "unverified generator status or unauthorized dispatch")
        self.generators_online[id] = online
        self._cached_power_nodes = None
        self.event("generator_state", id=id, on_load=online)

    def shed_load(self, new_MW, *, local_authority,
                  load_plan_verified):
        requested = positive(new_MW, "selected ship electrical demand")
        require(requested <= SHIP_CONTINUOUS_MW and
                local_authority is True and load_plan_verified is True,
                "invalid or unverified load-shed schedule")
        self.requested_load_MW = requested
        self.event("load_schedule_selected", demand_MW=requested)

    def select_protected_feed(self, hab_arc, bus, *,
                              local_authority, transfer_verified):
        require(type(hab_arc) is int and 1 <= hab_arc <= 8
                and bus in ("A", "B") and local_authority is True
                and transfer_verified is True,
                "unverified protected-source selection")
        head = "EDGE-HAB-%02d-PROT-" % hab_arc
        require(head + "A" in self.power_edge_selected
                and head + "B" in self.power_edge_selected,
                "missing real two-feed protected panel")
        self.power_edge_selected[head + "A"] = bus == "A"
        self.power_edge_selected[head + "B"] = bus == "B"
        self._cached_power_nodes = None
        self.event("protected_feed_transfer", arc=hab_arc, selected_bus=bus)

    def select_main_protected_feed(self, bus, *,
                                   local_authority, transfer_verified):
        require(bus in ("A", "B") and local_authority is True
                and transfer_verified is True,
                "unverified primary protected-bus source transfer")
        for side in ("A", "B"):
            edge = "EDGE-PWR-MSB-" + side + "-PROT"
            require(edge in self.power_edge_selected,
                    "missing existing main protected feeder")
            self.power_edge_selected[edge] = (side == bus)
        self._cached_power_nodes = None
        self.event("main_protected_source_transfer", selected_bus=bus)

    def change_power_tie(self, enabled, *,
                         local_authority, synchronisation_verified):
        require(type(enabled) is bool and local_authority is True
                and (not enabled or synchronisation_verified is True),
                "unsafe unsynchronized main bus tie operation")
        self.power_edge_selected["EDGE-MSB-XTIE"] = enabled
        self._cached_power_nodes = None
        self.event("main_bus_tie_selection", enabled=enabled)

    def _zone_auxiliary_power(self, zone):
        if zone.startswith("PZ-HAB-") and zone.count("-") == 2:
            arc = zone.replace("PZ-", "")
            return (self.assured_power("NODE-" + arc + "-PDB-A")
                    or self.assured_power("NODE-" + arc + "-PDB-B"))
        return self.assured_power("PWR-PROT")

    def _firewater_reaches(self, zone):
        if not self.assured_power("PWR-PROT"):
            return False
        # Exact fire-pump motor feeder is not independently mapped in the
        # authored power graph. This separately asserted local witness is
        # required; a working pump does not arise from a guessed branch.
        backed_up = self.fire_pumps.copy()
        try:
            for id in backed_up:
                self.fire_pumps[id] = (backed_up[id]
                                       and self.fire_pump_power_witness[id])
            return super()._firewater_reaches(zone)
        finally:
            self.fire_pumps.update(backed_up)

    def _connected_to_cooling(self, zone):
        return (self.thermal_power_witness
                and self.assured_power("PWR-PROT")
                and super()._connected_to_cooling(zone))

    def ignite(self, fire_id, zone, *, fuel_kg, burn_kg_s,
               smoke_yield_fraction=0.12,
               hazard="ordinary_combustible",
               energized_load_node=None):
        if hazard == "energized_electrical":
            require(energized_load_node in self.node
                    and self.node[energized_load_node]["network"] == "power"
                    and self.node[energized_load_node]["kind"] == "load"
                    and self._node_zone(energized_load_node) == zone,
                    "electrical fire needs a real load circuit in its pressure cell")
        else:
            require(energized_load_node is None,
                    "non-electrical fire cannot be assigned a live-load fixture")
        super().ignite(fire_id, zone, fuel_kg=fuel_kg,
                       burn_kg_s=burn_kg_s,
                       smoke_yield_fraction=smoke_yield_fraction,
                       hazard=hazard)
        if energized_load_node is not None:
            self.electrical_fire_load_nodes[fire_id] = energized_load_node
        self.event("fire_hazard_electrical_identity", fire=fire_id,
                   load_node=energized_load_node)

    def start_mist(self, zone, *, kg_s, local_authority, compatible_agent,
                   energy_isolated=False):
        active_electrical = [f for f in self.fires.values()
                             if f.zone == zone and f.hazard == "energized_electrical"
                             and f.remaining_fuel_kg > 0]
        if active_electrical:
            # A yes/no work permit is insufficient while the actual machine
            # branch still has an energized copper path. This especially
            # catches the patched HAB-03 cabin 07 fan-coil/SG2 exception.
            if not energy_isolated or any(
                self.has_power_path(self.electrical_fire_load_nodes[f.id])
                for f in active_electrical
            ):
                self.event("mist_activation_denied", zone=zone,
                           reason="real_live_electrical_load_or_unverified_lockout")
                return False
        return super().start_mist(
            zone, kg_s=kg_s, local_authority=local_authority,
            compatible_agent=compatible_agent,
            energy_isolated=energy_isolated)

    def _vent_step(self, dt):
        # The original coolant/duct topology is preserved. Pressure leakage
        # through OPEN dampers remains possible with failed electric fans;
        # active 2 kg/s mixing requires an energized endpoint fan at BOTH
        # supply arcs and an enabled fan command.
        for edge in self.edges["atmosphere"]:
            if not self._active("atmosphere", edge):
                continue
            a_id, b_id = self.air_terminal_edge[edge["id"]]
            if a_id == b_id:
                continue
            a, b = self.cells[a_id], self.cells[b_id]
            if a.unknown_exposure or b.unknown_exposure:
                a.unknown_exposure = b.unknown_exposure = True
                continue
            if a.pressure_kpa > b.pressure_kpa:
                donor, receiver = a, b
            elif b.pressure_kpa > a.pressure_kpa:
                donor, receiver = b, a
            else:
                donor = receiver = None
            if donor is not None:
                ceiling = (
                    donor.gas_kg * donor.temperature_K * receiver.free_volume_m3
                    - receiver.gas_kg * receiver.temperature_K * donor.free_volume_m3
                ) / (donor.temperature_K
                     * (donor.free_volume_m3 + receiver.free_volume_m3))
                pressure_flow = self._flow_kg(
                    donor.pressure_kpa, receiver.pressure_kpa, 0.12, dt)
                self._move_mass(donor, receiver,
                                min(max(0, ceiling), pressure_flow))
            if (self.fans_online and self._zone_auxiliary_power(a_id)
                    and self._zone_auxiliary_power(b_id)):
                self._exchange_constituents(a, b, 2.0 * dt)

    def _scrub_step(self, dt):
        old = self.eclss_processors.copy()
        try:
            for id in sorted(old):
                panel = ("NODE-HAB-06-ECLSS-A-LP" if id == "ECLSS-A"
                         else "NODE-HAB-08-ECLSS-B-LP")
                self.eclss_processors[id] = (
                    old[id] and self.assured_power(panel))
            super()._scrub_step(dt)
        finally:
            self.eclss_processors.update(old)

    def _step(self, dt):
        self._execute_pending_commands()
        super()._step(dt)

    def fault_control_link(self, online, *, local_authority):
        require(type(online) is bool and local_authority is True,
                "control network fault/repair unverified")
        self.control_link_online = online
        self.event("remote_control_transport", online=online)

    def fault_indication(self, network, valve_id, stuck_reading):
        require(network in self.valves
                and valve_id in self.valves[network]
                and stuck_reading in ("open", "closed", "unknown"),
                "unrecognized panel indication fault")
        self.control_indication_faults[(network, valve_id)] = stuck_reading
        self.event("telemetry_fault", network=network, valve=valve_id)

    def observe_switch(self, network, valve_id):
        require(network in self.valves and valve_id in self.valves[network],
                "unregistered control indication request")
        if not self.control_link_online or not self.assured_power("PWR-PROT"):
            return {"reading": "unavailable", "sampled_at_s": None,
                    "verified_physical_state": False}
        fault = self.control_indication_faults.get((network, valve_id))
        if fault:
            return {"reading": fault, "sampled_at_s": round(self.time_s, 3),
                    "verified_physical_state": False}
        # Panel command acknowledgement alone is not a local limit switch.
        observed = self.reported_switches.get((network, valve_id))
        if observed is None:
            return {"reading": "unknown", "sampled_at_s": None,
                    "verified_physical_state": False}
        return {"reading": observed[0], "sampled_at_s": observed[1],
                "verified_physical_state": False}

    def stage_worker(self, space_id, count=1):
        require(space_id in self.space and
                self.space[space_id]["pressure_zone"] in self.cells
                and self.space[space_id]["access_class"] in ("crew", "engineering"),
                "cannot conjure local technician in unknown receiver")
        zone = self.space[space_id]["pressure_zone"]
        require(self.may_enter_unsuited(zone),
                "worker location unsafe or has no recent local sample")
        require(type(count) is int and 1 <= count <= MAX_CREW
                and sum(self.crew_by_space.values()) + count <= MAX_CREW,
                "worker would exceed 40-person manifest")
        self.workers[space_id] += count
        self.crew_by_space[space_id] += count
        self.cells[zone].crew += count
        self.event("qualified_worker_present", space=space_id, count=count)

    def queue_valve_command(self, network, valve_id, desired, *,
                            control_mode, local_authority,
                            worker_space=None, delay_s=2.0):
        require(network in self.valves and valve_id in self.valves[network]
                and desired in ("open", "closed") and
                control_mode in ("remote", "manual")
                and local_authority is True,
                "unverified control order or nonexistent device")
        delay = positive(delay_s, "operation time")
        require(delay <= 120, "operation time exceeds design control screen")
        hw = self.isolator[valve_id]
        if control_mode == "manual":
            require(hw["manual_operation"] is True
                    and worker_space == hw["space_id"]
                    and self.workers[worker_space] >= 1
                    and self.space[worker_space]["pressure_zone"] in self.cells
                    and self.may_enter_unsuited(
                        self.space[worker_space]["pressure_zone"]),
                    "manual operation requires a safe worker at actual valve")
        else:
            require(hw["remote_operable"] is True
                    and self.control_link_online
                    and self.assured_power("PWR-PROT"),
                    "remote actuator/power/communication unavailable")
        self.last_command_number += 1
        serial = "DC-CMD-%04d" % self.last_command_number
        self.pending_commands.append({
            "id": serial, "network": network, "valve": valve_id,
            "desired": desired, "mode": control_mode, "site": worker_space,
            "due_at_s": self.time_s + delay})
        self.event("command_sent_not_yet_verified", id=serial,
                   network=network, valve=valve_id, desired=desired)
        return serial

    def _execute_pending_commands(self):
        due = [c for c in self.pending_commands
               if c["due_at_s"] <= self.time_s + 1e-6]
        self.pending_commands = [c for c in self.pending_commands
                                 if c not in due]
        for c in sorted(due, key=lambda x: x["id"]):
            hw = self.isolator[c["valve"]]
            if c["mode"] == "remote":
                valid = (self.control_link_online
                         and self.assured_power("PWR-PROT")
                         and hw["remote_operable"])
            else:
                valid = (hw["manual_operation"]
                         and c["site"] == hw["space_id"]
                         and self.workers[c["site"]] >= 1
                         and self.space[c["site"]]["pressure_zone"] in self.cells
                         and self.may_enter_unsuited(
                            self.space[c["site"]]["pressure_zone"]))
            moved = False
            if valid:
                moved = super().change_valve(
                    c["network"], c["valve"], c["desired"],
                    local_authority=True, control_mode=c["mode"])
            if moved:
                if c["network"] == "power":
                    self._cached_power_nodes = None
                self.reported_switches[(c["network"], c["valve"])] = (
                    c["desired"], round(self.time_s, 3))
            self.event("control_order_result", id=c["id"],
                       accepted_and_moved=moved,
                       reason=("control_path_or_local_presence_lost"
                               if not valid else
                               "mechanical_movement_or_fault"))

    def fire_detector_report(self, hab_arc):
        require(type(hab_arc) is int and 1 <= hab_arc <= 8,
                "unregistered habitation detector")
        equipment = "HAB-%02d-FIRE-DETECT" % hab_arc
        node = "NODE-" + equipment
        if not self.assured_power(node):
            return {"report": "unavailable", "credible_fire_truth": False}
        fault = self.detector_faults.get(equipment, "none")
        if fault in ("silent", "false_alarm"):
            return {"report": "silent" if fault == "silent" else "alarm",
                    "credible_fire_truth": False}
        zone = "PZ-HAB-%02d" % hab_arc
        active = any(f.zone == zone and f.remaining_fuel_kg > 0
                     for f in self.fires.values())
        return {"report": "alarm" if active else "silent",
                "credible_fire_truth": False}

    def fault_detector(self, id, fault):
        require(id in self.equipment and id.endswith("-FIRE-DETECT")
                and fault in ("none", "silent", "false_alarm"),
                "invalid detector fault target")
        self.detector_faults[id] = fault
        self.event("detector_fault", equipment=id, mode=fault)

    def light_powered(self, zone):
        if zone.startswith("PZ-HAB-") and zone.count("-") == 2:
            node = "NODE-" + zone[3:] + "-EMERGENCY-LIGHT"
            return self.assured_power(node)
        # Bridge sectors lack an independently asserted luminaire
        # in the power graph. Do not invent one; require portable
        # lighting for bridge transits unless a separate witness exists.
        return False

    def reserve_crew_gear(self, *, breathing_sets=0, portable_lights=0,
                          allocation_verified):
        require(type(breathing_sets) is int and type(portable_lights) is int
                and breathing_sets >= 0 and portable_lights >= 0
                and allocation_verified is True
                and self.issued_breathing_sets + breathing_sets
                    <= self.reference_breathing_sets
                and self.issued_portable_lights + portable_lights
                    <= self.reference_portable_lights,
                "unavailable or unverified finite damage-control gear")
        self.issued_breathing_sets += breathing_sets
        self.issued_portable_lights += portable_lights
        self.event("DC_gear_issued", breathing_sets=breathing_sets,
                   portable_lights=portable_lights)

    def set_access_fault(self, access_id, *, impassable):
        require(access_id in self.access and type(impassable) is bool,
                "unregistered damaged crew passage")
        if impassable:
            self.access_blocked.add(access_id)
        else:
            self.access_blocked.discard(access_id)
        self.event("access_fault", passage=access_id, blocked=impassable)

    def _can_occupy_space(self, space_id, *, breathing_set):
        row = self.space[space_id]
        zone_id = row["pressure_zone"]
        if zone_id not in self.cells or row["access_class"] in ("cargo", "eva"):
            return False
        c = self.cells[zone_id]
        if c.unknown_exposure or not c.fresh_observation(self.time_s):
            return False
        if not breathing_set:
            return c.modeled_unsuited_air_safe()
        return (70.0 <= c.pressure_kpa <= 120.0
                and c.temperature_K <= 323.15)
        # A smoke breathing set is NOT a vacuum-rated spacesuit.

    def plan_crew_route(self, start_space, destination_space, *,
                        crew_count=1, breathing_sets=False,
                        portable_lighting=False, role="crew"):
        require(start_space in self.space and destination_space in self.space,
                "route starts or ends outside the original room graph")
        require(type(crew_count) is int and 1 <= crew_count <= MAX_CREW
                and role in ("crew", "engineering"),
                "unsupported crew group or security classification")
        require(type(breathing_sets) is bool and
                type(portable_lighting) is bool,
                "equipment must be deliberately allocated")
        if breathing_sets and crew_count > self.issued_breathing_sets:
            return None
        if portable_lighting and self.issued_portable_lights == 0:
            return None
        if not self._can_occupy_space(start_space, breathing_set=breathing_sets):
            return None
        if not self._can_occupy_space(destination_space,
                                      breathing_set=breathing_sets):
            return None
        graph = defaultdict(list)
        for a in self.access.values():
            if a["id"] in self.access_blocked:
                continue
            if a["kind"] in ("eva_rail", "eva_work_platform_transfer",
                             "freight_handling_route", "freight_gate",
                             "freight_door", "freight_pressure_shutter",
                             "freight_branch_tunnel", "indexed_freight_transfer",
                             "cargo_service_door", "cargo_portal_inner",
                             "heavy_rotor_freight_lock"):
                continue
            if a["pressure_boundary"]:
                gate = self.gates[a["id"]]
                if not gate.is_open():
                    continue
            elif a["restrictions"]:
                # Non-boundary restricted transfers need a specific separate
                # permit/sequence; their restrictions are NOT free text to
                # waive by mere graph connectivity.
                continue
            for x, y in ((a["from"], a["to"]), (a["to"], a["from"])):
                zone_x = self.space[x]["pressure_zone"]
                zone_y = self.space[y]["pressure_zone"]
                if zone_x not in self.cells or zone_y not in self.cells:
                    continue
                if role == "crew" and self.space[y]["access_class"] != "crew":
                    continue
                if self.space[y]["access_class"] in ("cargo", "eva"):
                    continue
                graph[x].append((y, a))
        best = {start_space: 0.0}
        queue = [(0.0, start_space)]
        previous = {}
        while queue:
            elapsed, room = heappop(queue)
            if elapsed != best[room]:
                continue
            if room == destination_space:
                break
            for other, link in sorted(graph[room], key=lambda z: z[1]["id"]):
                if not self._can_occupy_space(other,
                                               breathing_set=breathing_sets):
                    continue
                if (not portable_lighting
                    and not self.light_powered(
                        self.space[other]["pressure_zone"])):
                    continue
                seconds = float(link["traverse_time_s"]) * ceil(
                    crew_count / BATCH_WALKERS)
                if not self.light_powered(self.space[other]["pressure_zone"]):
                    seconds *= 1.5  # explicitly slow/limited portable lighting
                new = elapsed + seconds
                if new < best.get(other, float("inf")):
                    best[other] = new
                    previous[other] = (room, link["id"], seconds)
                    heappush(queue, (new, other))
        if destination_space not in best:
            return None
        links = []
        rooms = [destination_space]
        node = destination_space
        while node != start_space:
            parent, id, duration = previous[node]
            links.append({"access_link_id": id, "from": parent,
                          "to": node, "duration_reference_s": duration})
            node = parent
            rooms.append(node)
        links.reverse()
        rooms.reverse()
        return {
            "start": start_space, "destination": destination_space,
            "personnel": crew_count,
            "reference_duration_s": round(best[destination_space], 2),
            "requires_breathing_set": breathing_sets,
            "requires_portable_light": portable_lighting,
            "rooms": rooms, "legs": links,
            "scope": "sampled_now_route_not_automatic_traversal_or_world_permission",
        }

    def stage_crew(self, space_id, count):
        require(space_id in self.space and type(count) is int
                and 1 <= count <= MAX_CREW
                and self._can_occupy_space(space_id, breathing_set=False),
                "unverified crew starting room or dangerous pressure")
        total = sum(self.crew_by_space.values())
        require(total + count <= MAX_CREW,
                "cannot spawn more than 40 verified ship crew")
        zone_id = self.space[space_id]["pressure_zone"]
        self.crew_by_space[space_id] += count
        self.cells[zone_id].crew += count
        self.event("crew_staged_in_real_space", room=space_id, people=count)

    def evacuate_group(self, route, *, qualified_threshold_probes):
        """Time-advancing transit, not a teleport or automatic command.

        Each leg re-samples its receiving pressure cell through explicit
        qualified observation. On failure, crew remain where they reached.
        """
        require(route is not None and
                qualified_threshold_probes is True,
                "evacuation requires a positive validated plan and sensors")
        count = route["personnel"]
        current = route["start"]
        require(self.crew_by_space[current] >= count,
                "unplaced crew cannot leave an invented location")
        departed = 0
        for leg in route["legs"]:
            require(leg["from"] == current and
                    leg["access_link_id"] in self.access,
                    "route changed after plan was constructed")
            link = self.access[leg["access_link_id"]]
            if link["id"] in self.access_blocked:
                break
            if link["pressure_boundary"] and not self.gates[link["id"]].is_open():
                break
            self.advance(leg["duration_reference_s"])
            destination = leg["to"]
            z = self.space[destination]["pressure_zone"]
            if z in self.cells and not self.cells[z].unknown_exposure:
                # Simulated new physical probe at each reached threshold; no
                # assumption that previous 10-second sample is still valid.
                self.sample_local(z, qualified_local_probe=True)
            if not self._can_occupy_space(
                destination, breathing_set=route["requires_breathing_set"]):
                break
            start_zone = self.space[current]["pressure_zone"]
            self.crew_by_space[current] -= count
            self.crew_by_space[destination] += count
            # A worker is a manifested person, not a second independently
            # spawned occupant. Their on-site capability moves with them.
            relocating_workers = min(count, self.workers[current])
            self.workers[current] -= relocating_workers
            self.workers[destination] += relocating_workers
            if z != start_zone:
                self.cells[start_zone].crew -= count
                self.cells[z].crew += count
            departed += 1
            current = destination
        success = current == route["destination"]
        self.event("crew_group_transit_finished", reached=current,
                   arrived=success, traversed_legs=departed, people=count)
        return {"arrived": success, "reached": current,
                "people": count, "legs_completed": departed,
                "elapsed_ship_time_s": round(self.time_s, 3)}


def new_trial(*, volume_basis="midpoint", water_kg=150.0,
              filters_kg=10.0, breathing_sets=4, portable_lights=2):
    topology, gas, env = load_model()
    return ElectricalEvacuationTrial(
        topology, gas, env, read_ship(), volume_basis=volume_basis,
        suppression_water_kg=water_kg, filter_capacity_kg=filters_kg,
        reference_breathing_sets=breathing_sets,
        reference_portable_lights=portable_lights)
