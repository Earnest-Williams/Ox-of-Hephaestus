#!/usr/bin/env python3
"""Coupled fire, smoke, pressure, ventilation and heat reference trials for Ox v0.5.

Physical identities and connections come from ox_full_ship_v0.5_candidate.json.
Simulation parameters are selected scenario assumptions, not certified ratings,
live Evennia state, crew knowledge, or authority to operate ship machinery.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
import json

from pressure_damage_sim_v05 import (
    PressureDamageTrial, AIR_CP_KJ_KG_K, T_REF_K, positive, require,
    load_model,
)

HERE = Path(__file__).resolve().parent
OXYGEN_PER_KG_CARBON = 32.0 / 12.0
FIRE_HEAT_MJ_PER_KG = 20.0
VENT_MIX_KG_S = 2.0
DUCT_PRESSURE_LEAK_KG_S = 0.12
FILTER_KG_S_PER_TRAIN = 0.02
MIST_COOLING_MJ_PER_KG = 2.2
MIST_BURN_FRACTION = 0.04
TERMINAL_COOLING_MW = 2.0


def read_ship() -> dict:
    return json.loads((HERE / "ox_full_ship_v0.5_candidate.json")
                      .read_text(encoding="utf-8"))


@dataclass
class Fire:
    id: str
    zone: str
    remaining_fuel_kg: float
    reference_burn_kg_s: float
    smoke_yield_fraction: float
    hazard: str
    consumed_fuel_kg: float = 0.0


class FireSmokeThermalTrial(PressureDamageTrial):
    """Design-only physical casualty trial, never a live handler permission system."""

    def __init__(self, topology: dict, gas: dict, environmental: dict,
                 ship: dict, *, volume_basis: str = "midpoint",
                 suppression_water_kg: float = 150.0,
                 filter_capacity_kg: float = 10.0):
        super().__init__(topology, gas, environmental, volume_basis=volume_basis)
        require(ship["model_version"] == "0.5-candidate", "wrong source ship")
        require(len(ship["spaces"]) == 421 and len(ship["access_links"]) == 517
                and len(ship["equipment"]) == 808, "source ship identities shifted")
        self.ship = ship
        self.space = {x["id"]: x for x in ship["spaces"]}
        self.equipment = {x["id"]: x for x in ship["equipment"]}
        self.node = {x["id"]: x for x in ship["service_nodes"]}
        self.isolator = {x["id"]: x for x in ship["isolation_points"]}
        require(len(self.space) == 421 and len(self.equipment) == 808,
                "source entity identity duplicated")

        expected = {"atmosphere": (212, 213, 221),
                    "fire_main": (68, 73, 73),
                    "lt_cooling": (78, 79, 87)}
        self.edges: dict[str, list[dict]] = {}
        self.valves: dict[str, dict[str, str]] = {}
        for network, counts in expected.items():
            nodes = [x for x in ship["service_nodes"] if x["network"] == network]
            edges = [x for x in ship["service_edges"] if x["network"] == network]
            isolators = [x for x in ship["isolation_points"] if x["network"] == network]
            require((len(nodes), len(edges), len(isolators)) == counts,
                    "changed service topology for " + network)
            require(len({x["id"] for x in nodes}) == len(nodes)
                    and len({x["id"] for x in edges}) == len(edges)
                    and len({x["id"] for x in isolators}) == len(isolators),
                    "duplicate service IDs in " + network)
            ids = {x["id"] for x in nodes}
            valves = {x["id"]: x for x in isolators}
            for edge in edges:
                require(edge["from_node"] in ids and edge["to_node"] in ids
                        and all(id in valves for id in edge["isolator_ids"]),
                        "unregistered service node/valve " + edge["id"])
            self.edges[network] = sorted(edges, key=lambda r: r["id"])
            # Cold-case starting settings use *authored normal* valve states,
            # explicitly not the current installation or verified indicators.
            self.valves[network] = {
                x["id"]: {"state": x["normal_state"], "fault": "working"}
                for x in isolators
            }
            require(all(v["state"] in ("open", "closed")
                        for v in self.valves[network].values()),
                    "unsupported normal valve state")
        self.air_terminal_edge = {
            e["id"]: (self._node_zone(e["from_node"]),
                       self._node_zone(e["to_node"]))
            for e in self.edges["atmosphere"]}
        require(all(a in self.cells and b in self.cells
                    for a, b in self.air_terminal_edge.values()),
                "unclassified cargo unexpectedly shares protected circulation")

        self.fans_online = True
        self.filters_on = False
        self.eclss_processors = {"ECLSS-A": True, "ECLSS-B": True}
        self.filter_available_kg = positive(
            filter_capacity_kg, "smoke filter allocation", allow_zero=True)
        self.captured_smoke_kg = 0.0
        self.water_remaining_kg = positive(
            suppression_water_kg, "allocated firewater", allow_zero=True)
        # Selected small allocation inside the existing 162 t normal
        # makeup water, not a new stock, mass entry, or extra equipment.
        require(self.water_remaining_kg <= 162000,
                "firewater exceeds existing voyage-water account")
        require(self.filter_available_kg <= 8000,
                "DC filters exceed the existing eight-tonne DC consumables")
        self.water_used_kg = 0.0
        self.mist_kg_s: dict[str, float] = {}
        self.fire_pumps = {"FIRE-PUMP-FWD": True, "FIRE-PUMP-AFT": True}
        self.fires: dict[str, Fire] = {}
        self.lost_oxygen_in_combustion_kg = 0.0
        self.heat_generated_MJ = 0.0
        self.heat_removed_MJ = 0.0

        self.radiator_capacity_MW = {
            id: positive(self.equipment[id]["attributes"]["nominal_total_MW_share"],
                         "radiator nameplate capacity")
            for id in ("RAD-LT-1", "RAD-LT-2", "RAD-LT-3", "RAD-LT-4")
        }
        self.radiators_online = {id: True for id in self.radiator_capacity_MW}
        self.lt_plant_MW = positive(
            self.equipment["LT-PLANT"]["attributes"]["nominal_rejection_MW"],
            "LT plant rating")
        require(isclose(self.lt_plant_MW, 3.75)
                and isclose(sum(self.radiator_capacity_MW.values()), 3.75),
                "baseline radiator budget disagrees with ship equipment")
        self.background_heat_MW: dict[str, float] = defaultdict(float)
        self.fixture_heat_capacity_kJ_K: dict[str, float] = {
            id: (30000 if id.startswith("PZ-HAB-") and
                 id.count("-") == 2 else 5000)
            for id in self.cells
        }
        self.cooling_commanded = True

    def _node_zone(self, node_id: str) -> str | None:
        n = self.node[node_id]
        if n["owner_type"] == "space":
            space_id = n["owner_id"]
        else:
            require(n["owner_type"] == "equipment"
                    and n["owner_id"] in self.equipment,
                    "service node has no physical owner")
            space_id = self.equipment[n["owner_id"]]["space_id"]
        require(space_id in self.space, "service owner not a real ship room")
        return self.space[space_id]["pressure_zone"]

    def _active(self, network: str, edge: dict) -> bool:
        return all(self.valves[network][id]["state"] == "open"
                   for id in edge["isolator_ids"])

    def _adjacency(self, network: str) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges[network]:
            if self._active(network, edge):
                a, b = edge["from_node"], edge["to_node"]
                graph[a].add(b)
                graph[b].add(a)
        return graph

    def _reachable(self, network: str, starts: list[str]) -> set[str]:
        graph = self._adjacency(network)
        found = set(starts)
        pending = deque(sorted(found))
        while pending:
            for other in sorted(graph[pending.popleft()]):
                if other not in found:
                    found.add(other)
                    pending.append(other)
        return found

    def change_valve(self, network: str, valve_id: str, state: str,
                     *, local_authority: bool, control_mode: str = "remote") -> bool:
        require(network in self.valves and valve_id in self.valves[network],
                "unregistered valve or wrong service network")
        require(state in ("open", "closed") and local_authority is True,
                "missing operator authorization for valve control")
        require(control_mode in ("remote", "manual"),
                "unrecognized remote/manual service operation")
        hardware = self.isolator[valve_id]
        if (control_mode == "remote" and hardware["remote_operable"] is not True
                or control_mode == "manual" and hardware["manual_operation"] is not True):
            self.event("valve_control_not_fitted", valve=valve_id,
                       control_mode=control_mode)
            return False
        valve = self.valves[network][valve_id]
        if valve["fault"] != "working":
            self.event("valve_move_failed", valve=valve_id, fault=valve["fault"])
            return False
        valve["state"] = state
        self.event("service_valve_moved", network=network, valve=valve_id,
                   state=state)
        return True

    def fail_valve(self, network: str, valve_id: str, stuck_state: str) -> None:
        require(network in self.valves and valve_id in self.valves[network],
                "unregistered service valve")
        require(stuck_state in ("open", "closed"),
                "invalid valve fault")
        valve = self.valves[network][valve_id]
        valve["state"] = stuck_state
        valve["fault"] = "stuck_" + stuck_state
        self.event("valve_jam", network=network, valve=valve_id,
                   stuck_state=stuck_state)

    def isolate_ventilation(self, zone: str, *,
                            local_authority: bool) -> dict:
        require(zone in self.cells and local_authority is True,
                "cannot isolate unknown zone without authority")
        targets = set()
        for edge in self.edges["atmosphere"]:
            a, b = self.air_terminal_edge[edge["id"]]
            if a != b and zone in (a, b):
                targets.update(edge["isolator_ids"])
        closed, failed = [], []
        for id in sorted(targets):
            if self.change_valve("atmosphere", id, "closed",
                                 local_authority=True):
                closed.append(id)
            else:
                failed.append(id)
        self.event("ventilation_zone_isolation", zone=zone,
                   shut=len(closed), failed=failed)
        return {"closed": closed, "failed": failed}

    def configure_fan(self, online: bool, *, local_authority: bool) -> None:
        require(type(online) is bool and local_authority is True,
                "fan command lacks proof or authority")
        self.fans_online = online
        self.event("ventilation_fan_command", online=online)

    def configure_smoke_cleanup(self, on: bool, *, local_authority: bool) -> None:
        require(type(on) is bool and local_authority is True,
                "ECLSS smoke-cleanup command lacks authority")
        self.filters_on = on
        self.event("smoke_cleanup_command", on=on)

    def configure_processor(self, id: str, online: bool,
                            *, local_authority: bool) -> None:
        require(id in self.eclss_processors and type(online) is bool
                and local_authority is True, "unknown or unauthorized ECLSS train")
        self.eclss_processors[id] = online
        self.event("ECLSS_processor_state", processor=id, online=online)

    def configure_pump(self, id: str, online: bool,
                       *, local_authority: bool) -> None:
        require(id in self.fire_pumps and type(online) is bool
                and local_authority is True, "unknown or unauthorized fire pump")
        self.fire_pumps[id] = online
        self.event("fire_pump_state", pump=id, online=online)

    def _firewater_reaches(self, zone: str) -> bool:
        if not zone.startswith("PZ-HAB-") or zone.count("-") != 2:
            return False
        name = zone.replace("PZ-", "")
        outlet = "NODE-" + name + "-FIRE-MIST"
        pumps = ["NODE-FIRE-PUMP-" + id.rsplit("-", 1)[1]
                 for id, on in self.fire_pumps.items() if on]
        return bool(pumps) and outlet in self._reachable("fire_main", pumps)

    def ignite(self, fire_id: str, zone: str, *, fuel_kg: float,
               burn_kg_s: float, smoke_yield_fraction: float = 0.12,
               hazard: str = "ordinary_combustible") -> None:
        require(fire_id not in self.fires and zone in self.cells,
                "duplicate fire or unregistered pressure cell")
        require(hazard in ("ordinary_combustible", "energized_electrical"),
                "unsupported fire hazard")
        amount = positive(fuel_kg, "fire finite fuel")
        rate = positive(burn_kg_s, "reference fuel burn rate")
        require(isinstance(smoke_yield_fraction, (int, float))
                and not isinstance(smoke_yield_fraction, bool)
                and isfinite(smoke_yield_fraction)
                and 0 <= smoke_yield_fraction <= 1,
                "nonphysical particulate tracer allocation")
        self.fires[fire_id] = Fire(fire_id, zone, amount, rate,
                                   float(smoke_yield_fraction), hazard)
        # C is a finite existing-material scenario stock; account for all of
        # it until converted to gas-products or subsequently vented/filtered.
        self.initial_system_gas_kg += amount
        self.event("fire_started", fire=fire_id, zone=zone, fuel_kg=amount)

    def start_mist(self, zone: str, *, kg_s: float,
                   local_authority: bool, compatible_agent: bool,
                   energy_isolated: bool = False) -> bool:
        require(zone in self.cells and local_authority is True
                and type(compatible_agent) is bool
                and type(energy_isolated) is bool,
                "unauthorized, incompatible or unregistered mist command")
        rate = positive(kg_s, "mist reference discharge flow")
        require(rate <= 2.0, "suppression reference exceeds single-outlet screen")
        active = [f for f in self.fires.values()
                  if f.zone == zone and f.remaining_fuel_kg > 0]
        if (not active or not compatible_agent
            or any(f.hazard == "energized_electrical" for f in active)
               and not energy_isolated
            or self.water_remaining_kg <= 0
            or not self._firewater_reaches(zone)):
            self.event("mist_activation_denied", zone=zone,
                       reason="unproven_agent_energy_stock_or_fire_main")
            return False
        self.mist_kg_s[zone] = rate
        self.event("mist_started", zone=zone, rate_kg_s=rate)
        return True

    def stop_mist(self, zone: str, *, local_authority: bool) -> None:
        require(zone in self.cells and local_authority is True,
                "unauthorized stop command")
        self.mist_kg_s.pop(zone, None)
        self.event("mist_stopped", zone=zone)

    def configure_radiator(self, id: str, online: bool,
                           *, local_authority: bool) -> None:
        require(id in self.radiators_online and type(online) is bool
                and local_authority is True, "unverified radiator control")
        self.radiators_online[id] = online
        self.event("radiator_state", radiator=id, online=online)

    def command_cooling(self, on: bool, *, local_authority: bool) -> None:
        require(type(on) is bool and local_authority is True,
                "unauthorized cooling command")
        self.cooling_commanded = on
        self.event("cooling_command", on=on)

    def set_background_heat(self, zone: str, MW: float, *,
                            local_authority: bool) -> None:
        require(zone in self.cells and local_authority is True,
                "unknown or unverified heat load")
        value = positive(MW, "local heat load", allow_zero=True)
        require(value <= 1.0, "selected per-cell reference load exceeded")
        self.background_heat_MW[zone] = value
        self.event("workload_heat_setting", zone=zone, MW=value)

    def _connected_to_cooling(self, zone: str) -> bool:
        if not self.cooling_commanded:
            return False
        # Source plant and local HAB manifolds are authentic equipment.
        reached = self._reachable("lt_cooling", ["NODE-LT-PLANT"])
        if zone.startswith("PZ-HAB-") and zone.count("-") == 2:
            return "NODE-" + zone[3:] + "-LT-COOLING-MAN" in reached
        # No invented cooling service for pressurised spaces without
        # an independently modelled terminal in their pressure cell.
        return any(self._node_zone(node) == zone for node in reached
                   if node in self.node and
                   self.node[node]["network"] == "lt_cooling"
                   and self.node[node]["kind"] == "load")

    def _total_cooling_MW(self) -> float:
        if not self.cooling_commanded:
            return 0.0
        live = sum(cap for id, cap in self.radiator_capacity_MW.items()
                   if self.radiators_online[id])
        return min(self.lt_plant_MW, live)

    def vent_to_known_vacuum(self, zone: str, gate_id: str, *,
                             local_authority: bool,
                             evacuated_and_isolated: bool) -> None:
        require(zone in self.cells and gate_id in self.gates
                and local_authority is True and
                evacuated_and_isolated is True, "unsafe emergency vent request")
        gate = self.gates[gate_id]
        require({gate.a, gate.b} == {zone, "VACUUM"}
                and self.cells[zone].crew == 0
                and self.open_pressure_component(zone) == {zone}
                and gate.state == "closed",
                "requested vent lacks rated local exterior hatch or safe isolation")
        gate.state = "open"
        self.event("deliberate_airlock_vent", zone=zone, gate=gate_id)

    def _vent_step(self, dt: float) -> None:
        # Physical open duct may bypass an otherwise closed pressure hatch.
        # Fans add COMPOSITION EXCHANGE, never magically generate air mass.
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
                    donor.pressure_kpa, receiver.pressure_kpa,
                    DUCT_PRESSURE_LEAK_KG_S, dt)
                self._move_mass(donor, receiver,
                                min(max(0.0, ceiling), pressure_flow))
            if self.fans_online:
                self._exchange_constituents(a, b, VENT_MIX_KG_S * dt)

    def _fire_step(self, dt: float) -> dict[str, float]:
        heat_MJ = defaultdict(float)
        water_by_zone = defaultdict(float)
        active_mist = {}
        for zone, rate in sorted(self.mist_kg_s.items()):
            if not self._firewater_reaches(zone) or self.water_remaining_kg <= 0:
                self.event("mist_delivery_lost", zone=zone)
                continue
            used = min(self.water_remaining_kg, rate * dt)
            self.water_remaining_kg -= used
            self.water_used_kg += used
            water_by_zone[zone] += used
            if used > 0:
                active_mist[zone] = True
        for fire_id in sorted(self.fires):
            fire = self.fires[fire_id]
            if fire.remaining_fuel_kg <= 0:
                continue
            cell = self.cells[fire.zone]
            oxygen_fraction = (cell.oxygen_partial_kpa / 20.0)
            if cell.oxygen_partial_kpa <= 5.0:
                continue  # oxygen-starved; fuel remains for reignition
            burn = min(fire.remaining_fuel_kg, fire.reference_burn_kg_s * dt
                       * (MIST_BURN_FRACTION if active_mist.get(fire.zone) else 1.0)
                       * min(1.0, max(0.0, oxygen_fraction)),
                       cell.oxygen_kg / OXYGEN_PER_KG_CARBON)
            if burn <= 0:
                continue
            fire.remaining_fuel_kg -= burn
            fire.consumed_fuel_kg += burn
            consumed_o2 = OXYGEN_PER_KG_CARBON * burn
            cell.oxygen_kg -= consumed_o2
            # Carbon-fuel products add their carbon mass to the atmospheric
            # reference ledger; O2 is converted to other products, not lost.
            cell.gas_kg += burn
            cell.trace_kg += fire.smoke_yield_fraction * burn
            self.lost_oxygen_in_combustion_kg += consumed_o2
            heat_MJ[fire.zone] += FIRE_HEAT_MJ_PER_KG * burn
            self.heat_generated_MJ += FIRE_HEAT_MJ_PER_KG * burn
        for zone, amount in water_by_zone.items():
            heat_MJ[zone] -= amount * MIST_COOLING_MJ_PER_KG
            self.heat_removed_MJ += amount * MIST_COOLING_MJ_PER_KG
        return heat_MJ

    def _scrub_step(self, dt: float) -> None:
        if not self.filters_on or not self.fans_online or self.filter_available_kg <= 0:
            return
        # Remote reachability is NOT filtration throughput. Scrubbed smoke
        # must first travel via modeled ducts to one of the REAL processing
        # plants (HAB-06 ECLSS-A or HAB-08 ECLSS-B). The processor's own
        # air inlet damper must also be open. No source-side instant cleanup.
        for train in ("ECLSS-A", "ECLSS-B"):
            if not self.eclss_processors[train] or self.filter_available_kg <= 0:
                continue
            inlet = next(e for e in self.edges["atmosphere"]
                         if e["id"] == "EDGE-" + train + "-AIR")
            if not self._active("atmosphere", inlet):
                continue
            zone = self._node_zone("NODE-" + train + "-AIR")
            cell = self.cells[zone]
            if cell.unknown_exposure:
                continue
            caught = min(self.filter_available_kg,
                         FILTER_KG_S_PER_TRAIN * dt, cell.trace_kg)
            if caught <= 0:
                continue
            cell.gas_kg -= caught
            cell.trace_kg -= caught
            self.captured_smoke_kg += caught
            self.filter_available_kg -= caught

    def _thermal_step(self, dt: float, fire_heat_MJ: dict) -> None:
        # LT rejection is SHARED across connected zones and constrained by
        # the actual four radiator equipment ratings. Stored excess heat
        # seeks a finite 600-second recovery, rather than instantly vanishing
        # when a radiator or valve is restored.
        demand, generation = {}, {}
        for zone, cell in self.cells.items():
            generation[zone] = (self.background_heat_MW[zone]
                                + fire_heat_MJ.get(zone, 0.0) / dt)
            capacity_kJ_K = (max(cell.gas_kg, 0.0) * AIR_CP_KJ_KG_K
                             + self.fixture_heat_capacity_kJ_K[zone])
            stored_excess_MJ = max(0.0, cell.temperature_K - T_REF_K) * (
                capacity_kJ_K / 1000)
            cooldown_MW = min(0.6, stored_excess_MJ / 600.0)
            wanted = max(0.0, generation[zone]) + cooldown_MW
            if wanted > 0:
                demand[zone] = wanted
        connected = {z for z in demand if self._connected_to_cooling(z)}
        total_demand = sum(demand[z] for z in connected)
        available = self._total_cooling_MW()
        for zone, wanted in demand.items():
            removed_MW = 0.0
            if zone in connected and total_demand > 0:
                removed_MW = min(wanted, TERMINAL_COOLING_MW,
                                 available * demand[zone] / total_demand)
            cell = self.cells[zone]
            capacity_kJ_K = (max(cell.gas_kg, 0) * AIR_CP_KJ_KG_K
                             + self.fixture_heat_capacity_kJ_K[zone])
            energy_MJ = (generation[zone] - removed_MW) * dt
            cell.temperature_K = max(
                T_REF_K, cell.temperature_K + energy_MJ * 1000
                / capacity_kJ_K)
            self.heat_removed_MJ += removed_MW * dt
            require(isfinite(cell.temperature_K) and cell.temperature_K > 0,
                    "nonphysical fire/thermal energy state")

    def _step(self, dt: float) -> None:
        before = {zone: c.crew_unsafe_seconds for zone, c in self.cells.items()}
        super()._step(dt)  # pressure/hatches/vacuum first
        heat = self._fire_step(dt)
        self._vent_step(dt)
        self._scrub_step(dt)
        self._thermal_step(dt, heat)
        for zone, cell in self.cells.items():
            # Crew danger is evaluated after smoke/heat transport as well as
            # pressure: no one is double counted by two sequential solvers.
            cell.crew_unsafe_seconds = before[zone] + (
                cell.crew * dt if not cell.modeled_unsuited_air_safe() else 0)
        require(self.mass_balance_error_kg() < 1e-5,
                "combustion/smoke transport manufactured or destroyed mass")

    def accounted_mass_kg(self) -> float:
        # Includes finite unburned carbon and captured particulate;
        # allocated suppression water is accounted separately, not new ship
        # atmosphere, and never doubles the 162-tonne water inventory.
        baseline = super().accounted_mass_kg()
        return (baseline + sum(f.remaining_fuel_kg for f in
                               getattr(self, "fires", {}).values())
                + getattr(self, "captured_smoke_kg", 0.0))

    def fire_summary(self, zones: list[str]) -> dict:
        summary = self.summary(zones)
        summary["fires"] = {
            id: {"fuel_remaining_kg": round(f.remaining_fuel_kg, 4),
                 "fuel_burned_kg": round(f.consumed_fuel_kg, 4),
                 "hazard": f.hazard}
            for id, f in sorted(self.fires.items())}
        summary["smoke_trace_kg"] = {
            id: round(self.cells[id].trace_kg, 5) for id in zones}
        summary["water_used_kg"] = round(self.water_used_kg, 4)
        summary["water_remaining_kg"] = round(self.water_remaining_kg, 4)
        summary["smoke_captured_by_filters_kg"] = round(self.captured_smoke_kg, 4)
        summary["filter_remaining_kg"] = round(self.filter_available_kg, 4)
        summary["combustion_oxygen_consumed_kg"] = round(
            self.lost_oxygen_in_combustion_kg, 4)
        summary["heat_generated_MJ"] = round(self.heat_generated_MJ, 3)
        summary["heat_removed_MJ"] = round(self.heat_removed_MJ, 3)
        summary["available_LT_radiator_MW"] = round(self._total_cooling_MW(), 4)
        return summary


def new_trial(*, volume_basis="midpoint", water_kg=150.0, filters_kg=10.0):
    topology, gas, environmental = load_model()
    return FireSmokeThermalTrial(
        topology, gas, environmental, read_ship(),
        volume_basis=volume_basis, suppression_water_kg=water_kg,
        filter_capacity_kg=filters_kg)
