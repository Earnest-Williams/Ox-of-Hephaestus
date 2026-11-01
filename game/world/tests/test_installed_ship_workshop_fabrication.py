"""Installed original machine-shop, real CNC output and physical repair stock."""
from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.models import CanonicalShipState, WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    commission_g19_water, commission_g19_repairs,
    commission_g19_fabrication, survey_g19_water_material,
    survey_g19_fabrication_blanks, tick_continuous_physics,
    crew_physical_action, local_physics_readout, _clock,
)


class InstalledMachiningTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_fabrication(operator_approved=True)
        self.assertFalse(commission_g19_fabrication(operator_approved=True)["commissioned"])
        self.now = 1000
        self.serial = 100
        self.energize("NODE-LP-SHOP-MECH")
        self.energize("NODE-HAB-03-FIRE-DETECT")

    def at(self, room):
        self.assertTrue(self.worker.move_to(find_ship_space(room), quiet=True))

    def action(self, command, target, value, request_id=None):
        self.serial += 1
        return crew_physical_action(
            self.worker, request_id or f"{self.serial:032x}",
            command, target, value)

    def tick(self, seconds):
        while seconds:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def energize(self, destination):
        set_isolator("ISO-GEN-M", "closed", operator=True)
        edges = CanonicalShipState.objects.filter(
            category="edge", reference__network="power")
        graph = defaultdict(list)
        for edge in edges:
            if edge.setting != "available" or edge.condition in {
                    "faulted", "failed", "jammed", "severed", "destroyed"}:
                continue
            left, right = edge.reference["from_node"], edge.reference["to_node"]
            graph[left].append((right, edge))
            if edge.reference["kind"] in {"bridge_feeder", "cross_tie"}:
                graph[right].append((left, edge))
        q, seen, previous = deque(["NODE-GEN-M"]), {"NODE-GEN-M"}, {}
        while q and destination not in seen:
            for nxt, edge in graph[q.popleft()]:
                if nxt not in seen:
                    seen.add(nxt)
                    previous[nxt] = (edge, edge.reference["from_node"],
                                     edge.reference["to_node"])
                    q.append(nxt)
        self.assertIn(destination, seen)
        node = destination
        while node != "NODE-GEN-M":
            edge, a, b = previous[node]
            for iso in edge.reference["isolator_ids"]:
                if state("isolator", iso).setting != "closed":
                    set_isolator(iso, "closed", operator=True)
            node = a if node == b else b

    def prepare(self):
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="SPARES-CENTRAL", verified_kg=8)
        survey_g19_fabrication_blanks(
            operator_approved=True, room_id="SPARES-CENTRAL",
            verified_kg=8)
        self.at("SPARES-CENTRAL")
        existing = state("inventory", "INV-SPARES").quantity
        first = self.action("fabricate", "blank", "pickup:4")
        self.assertEqual(first, self.action(
            "fabricate", "blank", "pickup:4",
            request_id=first["request_id"]))
        self.assertAlmostEqual(
            state("inventory", "INV-SPARES").quantity, existing - .004,
            places=7)
        self.at("SHOP-MECH")
        self.action("plant", "SHOP-CNC-MILL", "on")
        self.tick(20)
        site = local_physics_readout(self.worker, "SHOP-CNC-MILL")
        self.assertTrue(site["output_proven_at_site"], site)

    def test_live_machining_to_real_part_and_final_installed_repair(self):
        self.prepare()
        self.action("fabricate", "SHOP-CNC-MILL", "start:4")
        self.assertIn("SHOP-CNC-MILL", _clock().details["fabrication"]["jobs"])
        self.tick(360)
        fab = _clock().details["fabrication"]
        self.assertEqual(fab["completed"], 1)
        self.assertFalse(fab["jobs"])
        self.assertEqual(fab["finished_kg"], 3)
        self.assertEqual(fab["shop_offcuts_kg"], 1)
        self.assertEqual(_clock().details["repairs"]["carried_kg"][
            self.worker.dbref], 3)
        self.assertEqual(_clock().details["repairs"]["delivered_spares_kg"], 3)
        self.assertEqual(fab["receipts"][0]["machine"], "SHOP-CNC-MILL")
        self.assertEqual(WorkReceipt.objects.filter(
            operation="fabricate").count(), 2)

        # Chips cannot be emptied remotely; take the real chip tray contents
        # back to one original sealed industrial receiver.
        self.action("fabricate", "offcuts", "pickup:1")
        self.at("SPARES-CENTRAL")
        self.action("fabricate", "IND-SCRAP-HOLD-A", "deposit:1")
        self.assertEqual(_clock().details["water"]["cassettes"][
            "industrial"]["A"], 1)
        self.assertEqual(state("inventory", "INV-INDUSTRIAL-SCRAP").quantity,
                         .001)

        # This manufactured part enters the SAME proven finite-spares path
        # as a previously stocked replacement; no "repair all" shortcut.
        self.at("TOOL-CRIB")
        self.action("repair", "TOOL-CRIB", "pickup_toolkit")
        self.at("HAB-06-ECLSS-A")
        self.action("water", "WATER-PROC-A", "off")
        set_component_condition(
            "equipment", "WATER-PROC-A", "failed", operator=True)
        self.action("repair", "equipment:WATER-PROC-A", "start")
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["staged_kg"], 3)
        self.tick(600)
        self.assertEqual(state("equipment", "WATER-PROC-A").condition,
                         "serviceable")
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 3)
        self.assertEqual(_clock().details["repairs"]["completed"], 1)

    def test_machining_suspends_without_present_crew_and_real_power(self):
        self.prepare()
        self.action("fabricate", "SHOP-CNC-MILL", "start:4")
        self.tick(30)
        remaining = _clock().details["fabrication"]["jobs"][
            "SHOP-CNC-MILL"]["remaining_s"]
        self.at("SPARES-CENTRAL")
        self.tick(40)
        self.assertEqual(_clock().details["fabrication"]["jobs"][
            "SHOP-CNC-MILL"]["remaining_s"], remaining)
        self.at("SHOP-MECH")
        set_isolator("ISO-G19-SVC-SHOP-CNC-MILL", "open", operator=True)
        self.tick(40)
        self.assertEqual(_clock().details["fabrication"]["jobs"][
            "SHOP-CNC-MILL"]["remaining_s"], remaining)
        self.assertEqual(_clock().details["repairs"]["delivered_spares_kg"], 0)
        self.assertEqual(_clock().details["fabrication"]["finished_kg"], 0)
        with self.assertRaises(PermissionError):
            self.at("SPARES-CENTRAL")
            self.action("fabricate", "SHOP-CNC-MILL", "start:1")


if __name__ == "__main__":
    import unittest
    unittest.main()
