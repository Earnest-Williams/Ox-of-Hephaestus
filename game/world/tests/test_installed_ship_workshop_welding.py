"""Real WELD-CELL-A produces a finite joined part, heat and sealed slag."""
from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, state,
)
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water,
    commission_g19_repairs, commission_g19_welding,
    survey_g19_water_material, survey_g19_welding_filler,
    crew_physical_action, local_physics_readout, tick_continuous_physics,
)
from world.models import CanonicalShipState, WorkReceipt


class InstalledWelding(EvenniaTestCase):
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
        commission_g19_welding(operator_approved=True)
        self.assertFalse(commission_g19_welding(operator_approved=True)["commissioned"])
        self.now, self.serial = 1000, 0
        self.lineup("NODE-LP-SHOP-WELD")
        self.lineup("NODE-HAB-03-FIRE-DETECT")

    def lineup(self, destination):
        set_isolator("ISO-GEN-M", "closed", operator=True)
        graph = defaultdict(list)
        for edge in CanonicalShipState.objects.filter(
                category="edge", reference__network="power"):
            if (edge.setting != "available" or
                    edge.condition in {"faulted","failed","severed","jammed","destroyed"}):
                continue
            a,b = edge.reference["from_node"],edge.reference["to_node"]
            graph[a].append((b,edge))
            if edge.reference["kind"] in {"bridge_feeder","cross_tie"}:
                graph[b].append((a,edge))
        q, seen, previous = deque(["NODE-GEN-M"]), {"NODE-GEN-M"}, {}
        while q and destination not in seen:
            for nxt, edge in graph[q.popleft()]:
                if nxt not in seen:
                    seen.add(nxt)
                    previous[nxt] = (edge,edge.reference["from_node"],
                                      edge.reference["to_node"])
                    q.append(nxt)
        self.assertIn(destination, seen, "No original conductive source route")
        node = destination
        while node != "NODE-GEN-M":
            edge,a,b = previous[node]
            for iso in edge.reference["isolator_ids"]:
                if state("isolator",iso).setting != "closed":
                    set_isolator(iso,"closed",operator=True)
            node = a if node == b else b

    def at(self, room):
        self.assertTrue(self.worker.move_to(find_ship_space(room), quiet=True))

    def action(self, action, target, value, request=None):
        self.serial += 1
        return crew_physical_action(
            self.worker, request or f"{self.serial:032x}",
            action, target, value)

    def tick(self, seconds):
        while seconds:
            dt = min(60,seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def prepare(self):
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="SPARES-CENTRAL", verified_kg=4)
        survey_g19_welding_filler(
            operator_approved=True, room_id="SPARES-CENTRAL", verified_kg=1)
        self.at("SPARES-CENTRAL")
        stock_before = state("inventory","INV-SPARES").quantity
        source = self.action("weld","filler","pickup:1")
        self.assertEqual(
            source, self.action("weld","filler","pickup:1",
                                request=source["request_id"]))
        self.action("repair","INV-SPARES","pickup:3")
        self.assertAlmostEqual(
            state("inventory","INV-SPARES").quantity,
            stock_before - 0.004, places=7)
        self.at("SHOP-WELD")
        self.action("plant","WELD-CELL-A","on")
        self.tick(20)
        self.assertTrue(local_physics_readout(
            self.worker,"WELD-CELL-A")["operating"])

    def test_actual_arc_returns_joined_part_and_sealed_slag(self):
        self.prepare()
        start = self.action("weld","WELD-CELL-A","start:3:1")
        self.assertEqual(start,self.action(
            "weld","WELD-CELL-A","start:3:1",
            request=start["request_id"]))
        self.assertEqual(_clock().details["repairs"]["carried_kg"][
            self.worker.dbref],0)
        self.tick(10)
        live = local_physics_readout(self.worker, "WELD-CELL-A")
        self.assertTrue(live["output_proven_at_site"], live)
        self.assertGreater(live["workshop_arc_output"]["last_arc_kj"], 0)
        self.tick(290)
        welding = _clock().details["welding"]
        self.assertEqual(welding["completed"],1)
        self.assertFalse(welding["jobs"])
        self.assertAlmostEqual(welding["welded_returned_kg"],3.85)
        self.assertAlmostEqual(welding["slag_shop_kg"],.15)
        self.assertAlmostEqual(
            _clock().details["repairs"]["carried_kg"][self.worker.dbref],3.85)
        gauge = state("equipment","WELD-CELL-A").details["physics_weld_arc_gauge"]
        self.assertGreater(gauge["cumulative_arc_kj"],4000)
        self.assertEqual(WorkReceipt.objects.filter(
            operation="weld").count(),2)
        self.action("weld","slag","pickup:0.15")
        self.at("SPARES-CENTRAL")
        self.action("weld","IND-SCRAP-HOLD-A","deposit:0.15")
        self.assertAlmostEqual(
            _clock().details["water"]["cassettes"]["industrial"]["A"],.15)
        self.assertAlmostEqual(
            state("inventory","INV-INDUSTRIAL-SCRAP").quantity,.00015)
        self.assertEqual(_clock().details["welding"]["completed"],1)

    def test_unattended_arc_and_live_feeder_loss_pause_weld(self):
        self.prepare()
        self.action("weld","WELD-CELL-A","start:3:1")
        self.tick(20)
        before = _clock().details["welding"]["jobs"][
            "WELD-CELL-A"]["remaining_s"]
        self.at("SPARES-CENTRAL")
        self.tick(40)
        self.assertEqual(_clock().details["welding"]["jobs"][
            "WELD-CELL-A"]["remaining_s"],before)
        self.at("SHOP-WELD")
        set_isolator("ISO-G19-SVC-WELD-CELL-A","open",operator=True)
        self.tick(40)
        self.assertEqual(_clock().details["welding"]["jobs"][
            "WELD-CELL-A"]["remaining_s"],before)
        self.assertEqual(
            state("equipment","WELD-CELL-A").details[
                "physics_weld_arc_gauge"]["last_arc_kj"],0)
        self.assertEqual(_clock().details["welding"]["completed"],0)


if __name__ == "__main__":
    import unittest
    unittest.main()
