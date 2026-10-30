"""Finite original two-cell welding requires real filler, base parts and arc."""
import copy
import unittest

from world.ship_equipment_repair import (
    initial_repairs, take_parts, validate_repairs,
)
from world.ship_water_recycling import initial_water, validate_water
from world.ship_workshop_fabrication import credit_repair_parts
from world.ship_workshop_welding import (
    WeldError, CELLS, ARC_KW, initial_welding, validate_welding,
    certify_filler, issue_filler, start_weld, step_welds,
    take_slag, deposit_slag, welded_output_confirmed,
)


def prepared():
    w = certify_filler(
        initial_welding(), room="SPARES-CENTRAL",
        kg=2, surveyed_available_kg=2)
    w, stock = issue_filler(
        w, worker="#1", room="SPARES-CENTRAL",
        kg=1, stock_kg=50, surveyed_available_kg=2)
    assert stock == 49
    repairs, new_spares = take_parts(
        initial_repairs(), actor_dbref="#1", kg=3, stock_kg=49)
    assert new_spares == 46
    return start_weld(
        w, repairs, worker="#1", machine="WELD-CELL-A", base_kg=3,
        filler_kg=1, request_id="a"*32)


class OriginalWeldingTests(unittest.TestCase):
    def test_exact_original_two_cells_and_stock_gate(self):
        self.assertEqual(CELLS, frozenset({"WELD-CELL-A","WELD-CELL-B"}))
        with self.assertRaises(WeldError):
            issue_filler(
                initial_welding(), worker="#1", room="SPARES-CENTRAL",
                kg=1, stock_kg=50, surveyed_available_kg=1)
        w = certify_filler(
            initial_welding(), room="SPARES-CENTRAL",
            kg=1, surveyed_available_kg=1)
        with self.assertRaises(WeldError):
            certify_filler(
                w, room="SPARES-CENTRAL", kg=1, surveyed_available_kg=1)
        with self.assertRaises(WeldError):
            issue_filler(
                w, worker="#1", room="SPARES-CENTRAL", kg=2,
                stock_kg=50, surveyed_available_kg=1)

    def test_material_held_by_welder_and_no_remote_or_unpowered_output(self):
        w, repairs = prepared()
        self.assertEqual(w["base_borrowed_kg"], 3)
        self.assertEqual(w["filler_issued_kg"], 1)
        self.assertEqual(repairs["delivered_spares_kg"], 0)
        for kind in ("unpowered", "unattended", "unsafe_air"):
            kwargs = {
                "active": set() if kind == "unpowered" else {"WELD-CELL-A"},
                "present": set() if kind == "unattended" else {"#1"},
                "air_safe": kind != "unsafe_air",
                "capacity": {"#1":12}}
            result, done, arc = step_welds(w, 10, **kwargs)
            self.assertFalse(done)
            self.assertEqual(arc, {})
            self.assertEqual(result["arc_kj"], 0)
            self.assertEqual(result["jobs"]["WELD-CELL-A"]["remaining_s"], 300)

    def test_finite_welded_part_and_actual_slag_reenter_original_ship_stores(self):
        w, repairs = prepared()
        for i in range(30):
            w, result, heat = step_welds(
                w, 10, active={"WELD-CELL-A"}, present={"#1"},
                air_safe=True, capacity={"#1":12})
            self.assertEqual(heat, {"WELD-CELL-A": ARC_KW * 10})
        self.assertEqual(len(result), 1)
        worker, joined, proof = result[0]
        self.assertEqual(worker, "#1")
        self.assertAlmostEqual(joined, 3.85)
        self.assertEqual(proof["request_id"], "a"*32)
        self.assertAlmostEqual(w["slag_shop_kg"], .15)
        self.assertEqual(w["arc_kj"], ARC_KW*300)
        repairs = credit_repair_parts(repairs, actor=worker, kg=joined)
        validate_repairs(repairs)
        self.assertAlmostEqual(repairs["carried_kg"]["#1"], 3.85)
        self.assertAlmostEqual(w["welded_returned_kg"], joined)
        self.assertTrue(validate_welding(w))
        again, no_new, no_arc = step_welds(
            w, 10, active={"WELD-CELL-A"}, present={"#1"},
            air_safe=True, capacity={"#1":12})
        self.assertFalse(no_new)
        self.assertFalse(no_arc)
        self.assertEqual(again["completed"], 1)

        w = take_slag(w, worker="#1", kg=.15)
        stocks = {"normal": 162000.0, "reserve":70000.0,
                  "sanitary":0.0, "industrial":0.0,
                  "hazardous":0.0, "filter":0.0, "spares":46000.0}
        water = initial_water()
        validate_water(water, stocks)
        w, water, stocks = deposit_slag(
            w, water, stocks, worker="#1", kg=.15,
            side="A", receiver_ready=True)
        self.assertAlmostEqual(stocks["industrial"], .15)
        self.assertAlmostEqual(water["cassettes"]["industrial"]["A"], .15)
        self.assertAlmostEqual(w["slag_deposited_kg"], .15)
        self.assertTrue(validate_welding(w))

    def test_live_welding_output_cannot_be_proved_from_old_or_dark_gauge(self):
        machine = {
            "physics_commanded_on": True, "physics_online": True,
            "physics_startup_s": 0,
            "physics_weld_arc_gauge": {
                "last_arc_kj": 150,
                "cumulative_arc_kj": 300,
                "sample_game_time_s": 1010,
            },
        }
        self.assertTrue(welded_output_confirmed(
            "WELD-CELL-A", machine, observed_s=1010, operating=True))
        self.assertFalse(welded_output_confirmed(
            "WELD-CELL-A", machine, observed_s=1020, operating=True))
        self.assertFalse(welded_output_confirmed(
            "WELD-CELL-A", machine, observed_s=1010, operating=False))
        machine["physics_weld_arc_gauge"]["last_arc_kj"] = 0
        self.assertFalse(welded_output_confirmed(
            "WELD-CELL-A", machine, observed_s=1010, operating=True))
        machine["physics_weld_arc_gauge"]["last_arc_kj"] = -10
        with self.assertRaises(WeldError):
            welded_output_confirmed(
                "WELD-CELL-A", machine, observed_s=1010, operating=True)

    def test_two_cells_independent_and_critical_mass_tamper_rejected(self):
        w, repairs = prepared()
        with self.assertRaises(WeldError):
            start_weld(w, repairs, worker="#1", machine="WELD-CELL-B",
                       base_kg=1, filler_kg=1, request_id="b"*32)
        bad = copy.deepcopy(w)
        bad["welded_returned_kg"] = 100
        with self.assertRaises(WeldError):
            validate_welding(bad)
        with self.assertRaises(WeldError):
            step_welds(w, 11, active={"WELD-CELL-A"},
                       present={"#1"}, air_safe=True, capacity={"#1":12})


if __name__ == "__main__":
    unittest.main()
