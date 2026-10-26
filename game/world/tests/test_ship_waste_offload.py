"""Conservation and casualty regressions for real sealed-solid port custody."""
import unittest

from world.ship_water_recycling import (
    WaterError, initial_water, validate_water, water_inventory_total)
from world.ship_waste_offload import (
    accept_berth, approve_route, prepare, command, step_offload, RECEIVERS)
from world.tests.test_ship_water_recycling import stock


class WastePortContractTests(unittest.TestCase):
    def setUp(self):
        self.w = initial_water()
        self.s = stock()
        self.cat = "sanitary"
        self.receiver = "WASTE-RESIDUE-HOLD-A"
        self.w["cassettes"][self.cat]["A"] = 1200.0
        self.s[self.cat] = 1200.0
        self.w = accept_berth(
            self.w, acceptance_id="YARD-A-1", portal_id="DR-01-P1",
            berth_id="YARD-A", category=self.cat, limit_kg=1800)
        self.route = ["ACC-STORE-FLUID-AFT", "ACC-DR-01-FREIGHT-LOCK-LOGI"]
        self.w = approve_route(
            self.w, receiver=self.receiver,
            portal_id="DR-01-P1", route=self.route)
        validate_water(self.w, self.s)

    def _stage(self):
        self.w = prepare(
            self.w, receiver=self.receiver, acceptance_id="YARD-A-1",
            route=self.route)

    def _step(self, dt, freight=(), port=()):
        self.w, stocks, report = step_offload(
            self.w, dt, freight_ready=set(freight),
            port_ready=set(port), stocks={
                k: self.s[k] for k in ("sanitary", "industrial", "hazardous")})
        self.s.update(stocks)
        validate_water(self.w, self.s)
        return report

    def test_full_sealed_cassette_has_finite_haul_port_and_return(self):
        departure = water_inventory_total(self.w, self.s)
        self._stage()
        self.w = command(self.w, receiver=self.receiver, verb="haul")
        self._step(60, freight=(self.receiver,))
        self._step(60, freight=())
        self.assertEqual(self.w["cassettes"]["sanitary"]["A"], 1200)
        for _ in range(3):
            self._step(60, freight=(self.receiver,))
        self.assertEqual(
            self.w["waste_offload"]["jobs"][self.receiver]["phase"],
            "port_ready")
        self.assertEqual(self.w["cassettes"]["sanitary"]["A"], 0)
        self.assertEqual(self.s["sanitary"], 1200)
        self.assertAlmostEqual(water_inventory_total(self.w, self.s), departure)
        self.w = command(self.w, receiver=self.receiver, verb="offload")
        self._step(60, port=(self.receiver,))
        self.assertEqual(self.s["sanitary"], 1200)
        first = self._step(5, port=(self.receiver,))
        self.assertEqual(first["exported_kg"], 400)
        self.assertEqual(self.s["sanitary"], 800)
        with self.assertRaises(WaterError):
            command(self.w, receiver=self.receiver, verb="abort")
        self._step(10, port=(self.receiver,))
        self.assertEqual(self.s["sanitary"], 0)
        self.assertEqual(self.w["waste_offload"]["delivered_kg"]["sanitary"], 1200)
        self.assertEqual(self.w["waste_offload"]["jobs"][self.receiver]["phase"], "return_ready")
        self.assertAlmostEqual(
            water_inventory_total(self.w, self.s), departure - 1200)
        self.w = command(self.w, receiver=self.receiver, verb="return")
        for _ in range(4):
            self._step(60, freight=(self.receiver,))
        self.assertFalse(self.w["waste_offload"]["jobs"])
        self.assertEqual(self.w["cassettes"]["sanitary"]["A"], 0)
        self.assertEqual(self.w["waste_offload"]["acceptances"]["YARD-A-1"]["accepted_kg"], 1200)

    def test_abort_while_hauling_returns_same_source_mass(self):
        self._stage()
        self.w = command(self.w, receiver=self.receiver, verb="haul")
        self._step(60, freight=(self.receiver,))
        self.w = command(self.w, receiver=self.receiver, verb="abort")
        for _ in range(4):
            self._step(60, freight=(self.receiver,))
        self.assertFalse(self.w["waste_offload"]["jobs"])
        self.assertEqual(self.w["cassettes"]["sanitary"]["A"], 1200)
        self.assertEqual(self.s["sanitary"], 1200)
        self.assertEqual(self.w["waste_offload"]["delivered_kg"]["sanitary"], 0)

    def test_external_class_quota_and_berth_cannot_be_swapped(self):
        self.w = accept_berth(
            self.w, acceptance_id="TOX-1", portal_id="DR-02-P1",
            berth_id="TOX-BERTH", category="hazardous", limit_kg=500)
        with self.assertRaises(WaterError):
            prepare(self.w, receiver=self.receiver, acceptance_id="TOX-1",
                    route=self.route)
        self.w["waste_offload"]["acceptances"]["YARD-A-1"]["limit_kg"] = 1000
        with self.assertRaises(WaterError):
            prepare(self.w, receiver=self.receiver, acceptance_id="YARD-A-1",
                    route=self.route)
        self.w["waste_offload"]["acceptances"]["YARD-A-1"]["limit_kg"] = 1800
        self._stage()
        with self.assertRaises(WaterError):
            prepare(self.w, receiver=self.receiver, acceptance_id="YARD-A-1",
                    route=self.route)
        with self.assertRaises(WaterError):
            approve_route(self.w, receiver="INVALID",
                          portal_id="DR-01-P1", route=self.route)

    def test_corrupt_port_ledger_and_missing_inboard_mass_are_rejected(self):
        import copy
        self._stage()
        self.w = command(self.w, receiver=self.receiver, verb="haul")
        for _ in range(4):
            self._step(60, freight=(self.receiver,))
        altered = copy.deepcopy(self.w)
        altered["waste_offload"]["jobs"][self.receiver]["aboard_kg"] -= 1
        with self.assertRaises(WaterError):
            validate_water(altered, self.s)
        altered = copy.deepcopy(self.w)
        altered["waste_offload"]["acceptances"]["YARD-A-1"]["accepted_kg"] = 1
        with self.assertRaises(WaterError):
            validate_water(altered, self.s)
        altered = copy.deepcopy(self.w)
        altered["waste_offload"]["jobs"][self.receiver]["paused"] = "yes"
        with self.assertRaises(WaterError):
            validate_water(altered, self.s)

    def test_unsealed_or_empty_receiver_cannot_be_exported(self):
        self.w["cassette_sealed"]["sanitary"]["A"] = False
        with self.assertRaises(WaterError):
            prepare(self.w, receiver=self.receiver,
                    acceptance_id="YARD-A-1", route=self.route)
        self.w["cassette_sealed"]["sanitary"]["A"] = True
        self.w["cassettes"]["sanitary"]["A"] = 0
        self.s["sanitary"] = 0
        with self.assertRaises(WaterError):
            prepare(self.w, receiver=self.receiver,
                    acceptance_id="YARD-A-1", route=self.route)

    def test_per_tick_finite_offload_is_deterministic_and_zero_power_pauses(self):
        self._stage()
        self.w = command(self.w, receiver=self.receiver, verb="haul")
        for _ in range(4):
            self._step(60, freight=(self.receiver,))
        self.w = command(self.w, receiver=self.receiver, verb="offload")
        self._step(60, port=())
        self.assertEqual(self.s["sanitary"], 1200)
        self._step(60, port=(self.receiver,))
        self.assertEqual(self.s["sanitary"], 1200)
        import copy
        initial = copy.deepcopy(self.w)
        stocks = {k: self.s[k] for k in ("sanitary","industrial","hazardous")}
        a = step_offload(initial, 5, freight_ready=set(),
                         port_ready={self.receiver}, stocks=stocks)
        b = step_offload(initial, 5, freight_ready=set(),
                         port_ready={self.receiver}, stocks=stocks)
        self.assertEqual(a, b)
        self.assertEqual(a[2]["exported_kg"], 400)
        with self.assertRaises(WaterError):
            step_offload(initial, 90, freight_ready=set(),
                         port_ready={self.receiver}, stocks=stocks)


if __name__ == "__main__":
    unittest.main()
