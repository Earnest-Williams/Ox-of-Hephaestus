"""G19 as-installed fire suppression and drinking-water recovery under casualties.

A healthy suit profile flag is *not* physical protection. This tests a
finite-oxygen issued suit, real HAB fire-main water, one actual fire-pump
fuse, contaminated water with a loaded finite filter, and continuing
original cargo-shell leakage in one durable Evennia world.
"""
from __future__ import annotations

import copy
from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state, set_isolator,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_world import (
    ensure_canonical_ship, find_ship_space, find_world_entity,
)
from world.ship_crew_access import traverse_canonical_exit
from world.ship_unclassified_spaces import SECTORS
from world.ship_process_outputs import FIELD
from world.continuous_ship_physics import (
    PhysicsError, _clock, _reachable, _topology, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water, commission_g19_repairs,
    commission_g19_eva, commission_g19_crew_physiology,
    commission_g19_unclassified_spaces, commission_g19_instrumentation,
    configure_scenario_casualty, configure_water_casualty,
    survey_cargo_lot, survey_g19_cargo_sector,
    witness_g19_cargo_sector_leak, survey_g19_water_material,
    crew_physical_action, tick_continuous_physics,
)


class InstalledAttendedFireWaterRecovery(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        self.worker.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        # Line up the original three wet networks. Fresh installations
        # leave these individual valves isolated by default.
        for row in CanonicalShipState.objects.filter(category="isolator"):
            if (row.reference.get("network") in {
                    "potable_water", "greywater", "blackwater"}
                    and row.condition in {"serviceable", "degraded"}):
                set_isolator(row.source_id, "open", operator=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.worker.dbref])
        commission_g19_unclassified_spaces(operator_approved=True)
        commission_g19_instrumentation(operator_approved=True)
        self.counter = 94000

    def at(self, room):
        location = find_ship_space(room)
        self.assertIsNotNone(location, room)
        self.assertTrue(self.worker.move_to(location, quiet=True))

    def action(self, kind, target, value, *, request_id=None):
        if request_id is None:
            self.counter += 1
            request_id = f"{self.counter:032x}"
        return crew_physical_action(
            self.worker, request_id, kind, target, value)

    def _energise_authored_forward_fire_pump(self):
        """Line up the existing B generator and independently fused pump."""
        edges = list(CanonicalShipState.objects.filter(category="edge",
                             reference__network="power"))
        graph = defaultdict(list)
        for edge in edges:
            if edge.setting != "available" or edge.condition in {
                    "faulted", "failed", "severed", "destroyed", "jammed"}:
                continue
            spec = edge.reference
            graph[spec["from_node"]].append((spec["to_node"], edge))
            if spec["kind"] in {"bridge_feeder", "cross_tie"}:
                graph[spec["to_node"]].append((spec["from_node"], edge))
        for start, destination in (
                ("NODE-GEN-B", "NODE-LP-WATER-FWD"),
                ("NODE-GEN-B", "NODE-HAB-06-ECLSS-A-LP"),
                ("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")):
            # The purifier's own A-side panel and motors are electrically
            # independent of the forward fire pump. Powering one does not
            # magically energise the other.
            queue, visited, previous = deque([start]), {start}, {}
            while queue and destination not in visited:
                for nxt, edge in graph[queue.popleft()]:
                    if nxt not in visited:
                        visited.add(nxt)
                        previous[nxt] = (
                            edge, edge.reference["from_node"],
                            edge.reference["to_node"])
                        queue.append(nxt)
            self.assertIn(destination, visited, "Fitted motor lacks source")
            position = destination
            while position != start:
                edge, a, b = previous[position]
                for ident in edge.reference["isolator_ids"]:
                    if state("isolator", ident).setting != "closed":
                        set_isolator(ident, "closed", operator=True)
                position = a if position == b else b
        for name in ("WATER-PROC-A", "WASTE-PROC-A"):
            set_isolator(
                "ISO-G19-MOTOR-" + name, "closed", operator=True)

        # A single observable source: no second fire-pump output can mask
        # an absent discharge from the fitted forward pump.
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-AFT", "open", operator=True)
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-FWD", "closed", operator=True)
        fire_edges = [
            edge for edge in CanonicalShipState.objects.filter(category="edge")
            if edge.reference.get("network") == "fire_main"
        ]
        self.assertTrue(fire_edges)
        for edge in fire_edges:
            for ident in edge.reference["isolator_ids"]:
                kind = state("isolator", ident).reference["kind"].lower()
                setting = ("open" if "valve" in kind or "damper" in kind
                           else "closed")
                set_isolator(ident, setting, operator=True)
        fire_switches = {
            row.source_id: row for row in
            CanonicalShipState.objects.filter(category="isolator")
        }
        reachable = _reachable(
            fire_edges, fire_switches, "fire_main", ["NODE-FIRE-PUMP-FWD"])
        mist_nodes = sorted(
            node for node in reachable
            if node.startswith("NODE-HAB-") and node.endswith("-FIRE-MIST"))
        self.assertTrue(mist_nodes, "No as-fitted HAB mist route")
        zone = "PZ-" + mist_nodes[0][5:-10]
        rooms = sorted(
            room for room, pressure_zone in _topology()[0].items()
            if pressure_zone == zone and find_ship_space(room) is not None)
        self.assertTrue(rooms, "No actual room in mist pressure cell")
        return zone, rooms[0]

    def _issue_real_suit(self):
        """Pass through original forward pressure hatch to check out gear."""
        self.at("ENG-LOCKER")
        self.assertEqual(self.action(
            "eva", "INV-DC-CONSUMABLES", "stage:0.75")["status"],
            "succeeded")
        self.at("TRUNK-B-BOW")
        self.assertEqual(self.action(
            "eva", "EVA-FWD", "inner_open")["status"], "succeeded")
        forward = find_world_entity("access:ACC-EVA-FWD:forward")
        self.assertIsNotNone(forward)
        self.assertEqual(traverse_canonical_exit(
            self.worker, forward, forward.destination,
            request_id=f"{self.counter + 100:032x}")["status"], "succeeded")
        self.assertEqual(self.action(
            "eva", "EVA-FWD", "inner_close")["status"], "succeeded")
        self.assertEqual(self.action(
            "eva", "EVA-FWD", "checkout")["status"], "succeeded")
        self.assertEqual(self.action(
            "eva", "EVA-FWD", "inner_open")["status"], "succeeded")
        reverse = find_world_entity("access:ACC-EVA-FWD:reverse")
        self.assertIsNotNone(reverse)
        self.assertEqual(traverse_canonical_exit(
            self.worker, reverse, reverse.destination,
            request_id=f"{self.counter + 101:032x}")["status"], "succeeded")
        self.assertEqual(self.action(
            "eva", "EVA-FWD", "inner_close")["status"], "succeeded")
        self.assertEqual(self.worker.location.db.ox_space_id, "TRUNK-B-BOW")

    def _survey_breached_cargo(self):
        drum, sector = "DR-03", "DR-03-SEC-05"
        survey_cargo_lot(
            operator_approved=True, operation="verify", drum=drum)
        for name in (x for x in SECTORS if x.startswith(drum + "-")):
            survey_g19_cargo_sector(
                operator_approved=True, sector=name,
                free_volume_m3=50, pressure_pa=101000,
                temperature_k=293.15, oxygen_mass_fraction=.232,
                co2_mass_fraction=.0004, smoke_mass_fraction=0,
                cargo_class="empty", lot_ids=[])
        witness_g19_cargo_sector_leak(
            operator_approved=True, sector=sector, leak_kg_s=.02)
        return sector

    def test_real_issued_suit_proves_mist_and_potable_recovery(self):
        zone, fire_room = self._energise_authored_forward_fire_pump()
        sector = self._survey_breached_cargo()
        configure_scenario_casualty(
            zone, operator=True, fire_fuel_kg=8, fire_burn_kg_s=.05)
        configure_water_casualty(operator=True, contaminated_kg=1.5)

        # The obsolete flag cannot supply oxygen or authorize a live mist.
        self.at(fire_room)
        self.worker.db.ox_suit_verified = True
        self.counter += 1
        denied_id = f"{self.counter:032x}"
        with self.assertRaises(PermissionError):
            self.action("mist", zone, "start", request_id=denied_id)
        self.assertFalse(WorkReceipt.objects.filter(pk=denied_id).exists())
        self.assertEqual(state("pressure", zone).details["physics_mist_kg_s"], 0)

        self._issue_real_suit()
        # Issued EVA custody, not an old character flag, authorizes mist.
        self.worker.db.ox_suit_verified = False
        self.at(fire_room)
        source_kg = state("inventory", "INV-WATER-NORMAL").quantity * 1000
        self.counter += 1
        command_id = f"{self.counter:032x}"
        started = self.action(
            "mist", zone, "start", request_id=command_id)
        self.assertEqual(started["status"], "succeeded")
        self.assertEqual(
            self.action("mist", zone, "start", request_id=command_id), started)
        self.assertEqual(state("pressure", zone).details["physics_mist_kg_s"], .5)
        first = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(first["advanced"])
        delivered = state("equipment", "FIRE-PUMP-FWD").details[FIELD]["amount"]
        self.assertGreater(delivered, 0, "HAB mist requires real pump water")
        self.assertGreaterEqual(
            source_kg - state("inventory", "INV-WATER-NORMAL").quantity * 1000,
            delivered)
        self.assertLessEqual(_clock().details["burned_fuel_kg"], .15 * .05 * 10 + 1e-6)
        self.assertTrue(_clock().details["water"]["potable_quarantined"])

        # Real fuse isolation stops pump output even though the mist
        # command and burning fuel have not disappeared.
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-FWD", "open", operator=True)
        burned_before = _clock().details["burned_fuel_kg"]
        second = tick_continuous_physics(now_game_time=1020)
        self.assertTrue(second["advanced"])
        self.assertEqual(
            state("equipment", "FIRE-PUMP-FWD").details[FIELD]["amount"], 0)
        self.assertAlmostEqual(
            _clock().details["burned_fuel_kg"] - burned_before, .05 * 10,
            delta=1e-6)
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-FWD", "closed", operator=True)
        third = tick_continuous_physics(now_game_time=1030)
        self.assertTrue(third["advanced"])
        self.assertGreater(
            state("equipment", "FIRE-PUMP-FWD").details[FIELD]["amount"], 0)
        self.assertGreater(_clock().details[
            "unclassified_spaces"]["sectors"][sector]["lost_kg"], 0)

        # Water quality has a completely different recovery path. One
        # measured, finite chemistry filter is carried and physically
        # loaded at a real water processor; the operator cannot clear
        # quarantine until it has actually scrubbed the contamination.
        self.at("WATER-FWD")
        self.assertEqual(self.action(
            "water", "POTABLE-TANK-MAIN", "sample")["status"], "succeeded")
        with self.assertRaises(PhysicsError):
            self.action("water", "POTABLE-TANK-MAIN", "clear")
        before_filter = state("inventory", "INV-DC-CONSUMABLES").quantity
        survey_g19_water_material(
            operator_approved=True, source="INV-DC-CONSUMABLES",
            room_id="STORE-CRIT-SPARES", verified_kg=1)
        self.at("STORE-CRIT-SPARES")
        self.assertEqual(self.action(
            "water", "INV-DC-CONSUMABLES", "pickup_filter:1")["status"],
            "succeeded")
        self.assertLess(
            state("inventory", "INV-DC-CONSUMABLES").quantity, before_filter)
        self.at("HAB-06-ECLSS-A")
        self.assertEqual(self.action(
            "water", "WATER-PROC-A", "load_filter:1")["status"], "succeeded")
        self.assertEqual(self.action(
            "water", "WATER-PROC-A", "decontaminate")["status"], "succeeded")
        recovery = tick_continuous_physics(now_game_time=1090)
        self.assertTrue(recovery["advanced"])
        self.assertGreater(
            recovery["water"]["last_step"]["decontaminated_kg"], 0)
        self.assertGreater(
            state("inventory", "INV-HAZARDOUS-RESIDUE").quantity, 0)
        self.at("WATER-FWD")
        self.assertEqual(self.action(
            "water", "POTABLE-TANK-MAIN", "sample")["status"], "succeeded")
        self.assertEqual(self.action(
            "water", "POTABLE-TANK-MAIN", "clear")["status"], "succeeded")
        self.assertFalse(_clock().details["water"]["potable_quarantined"])

        # Clearing potable quarantine cannot undo the fire, repair an
        # exterior cargo breach, or restore already escaped breathing gas.
        cargo = _clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertGreater(cargo["lost_kg"], 0)
        self.assertAlmostEqual(
            cargo["gas"]["mass_kg"] + cargo["lost_kg"]
            - cargo["gallery_net_kg"], cargo["initial_kg"], delta=1e-5)
        self.assertGreater(
            state("pressure", zone).details["physics_smoke_kg"], 0)
        self.assertEqual(
            state("pressure", zone).details["physics_mist_kg_s"], .5)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1090)["advanced"])
        self.assertEqual(WorkReceipt.objects.filter(
            pk=command_id).count(), 1)
        self.at(fire_room)
        self.assertEqual(self.action(
            "mist", zone, "stop")["status"], "succeeded")
        self.assertEqual(
            state("pressure", zone).details["physics_mist_kg_s"], 0)
