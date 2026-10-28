"""G19 finite shop machining, actual spindle witnesses and mass conservation."""
import copy
import unittest

from world.ship_equipment_repair import initial_repairs, begin_repair, move_toolkit, validate_repairs
from world.ship_water_recycling import initial_water, validate_water
from world.ship_workshop_fabrication import (
    FabricationError, initial_fabrication, validate_fabrication,
    certify_blanks, pick_blank, start_batch, step_batches,
    credit_repair_parts, take_offcuts, deposit_offcuts,
)


def prepared():
    fab = certify_blanks(
        initial_fabrication(), room="SPARES-CENTRAL", kg=8,
        surveyed_available_kg=8)
    fab, stock = pick_blank(
        fab, actor="#1", room="SPARES-CENTRAL",
        kg=4, stock_kg=50, surveyed_available_kg=8)
    assert stock == 46
    return start_batch(
        fab, actor="#1", machine="SHOP-CNC-MILL",
        kg=4, request_id="1" * 32,
        previous_output=0, current_repair_kg=0)


def stocks():
    return {"normal": 162000.0, "reserve": 70000.0,
            "sanitary": 0.0, "industrial": 0.0, "hazardous": 0.0,
            "filter": 0.0, "spares": 46000.0}


class FabricationTests(unittest.TestCase):
    def test_no_unsurveyed_free_material_or_duplicate_classification(self):
        empty = initial_fabrication()
        with self.assertRaises(FabricationError):
            pick_blank(empty, actor="#1", room="SPARES-CENTRAL",
                       kg=4, stock_kg=50, surveyed_available_kg=8)
        good = certify_blanks(empty, room="SPARES-CENTRAL", kg=4,
                              surveyed_available_kg=5)
        with self.assertRaises(FabricationError):
            certify_blanks(good, room="SPARES-CENTRAL", kg=4,
                           surveyed_available_kg=5)
        with self.assertRaises(FabricationError):
            pick_blank(good, actor="#1", room="SPARES-CENTRAL",
                       kg=8, stock_kg=50, surveyed_available_kg=5)

    def test_real_mechanical_output_and_worker_presence_are_required(self):
        fab = prepared()
        for i in range(30):
            fab, completed = step_batches(
                fab, 10, observed={"SHOP-CNC-MILL": {
                    "operating": False, "cumulative_output": (i+1) * 100}},
                present={"#1"}, free_part_kg={"#1":12})
            self.assertFalse(completed)
        self.assertEqual(fab["jobs"]["SHOP-CNC-MILL"]["remaining_s"], 360)
        fab, completed = step_batches(
            fab, 10, observed={"SHOP-CNC-MILL": {
                "operating": True, "cumulative_output": 3200}},
            present=set(), free_part_kg={"#1":12})
        self.assertFalse(completed)
        self.assertEqual(fab["jobs"]["SHOP-CNC-MILL"]["remaining_s"], 360)
        fab, completed = step_batches(
            fab, 10, observed={"SHOP-CNC-MILL": {
                "operating": True, "cumulative_output": 3200}},
            present={"#1"}, free_part_kg={"#1":12})
        self.assertFalse(completed)
        self.assertEqual(fab["jobs"]["SHOP-CNC-MILL"]["remaining_s"], 360)

    def test_4kg_workpiece_becomes_3kg_real_repair_part_plus_1kg_chips(self):
        fab = prepared()
        repairs = initial_repairs()
        for i in range(36):
            fab, completed = step_batches(
                fab, 10, observed={"SHOP-CNC-MILL": {
                    "operating": True, "cumulative_output": (i+1) * 100}},
                present={"#1"}, free_part_kg={"#1": 12})
        self.assertEqual(len(completed), 1)
        worker, mass, provenance = completed[0]
        self.assertEqual(provenance["request_id"], "1" * 32)
        self.assertEqual((worker, mass), ("#1", 3))
        repairs = credit_repair_parts(repairs, actor=worker, kg=mass)
        self.assertTrue(validate_repairs(repairs))
        self.assertEqual(repairs["carried_kg"]["#1"], 3)
        self.assertEqual(fab["finished_kg"], 3)
        self.assertEqual(fab["shop_offcuts_kg"], 1)
        self.assertEqual(fab["drawn_kg"], 4)
        self.assertEqual(fab["completed"], 1)
        self.assertTrue(validate_fabrication(fab))
        with self.assertRaises(FabricationError):
            step_batches(fab, 10, observed={"SHOP-CNC-MILL": {
                "operating": True, "cumulative_output": -1}},
                present={"#1"}, free_part_kg={"#1": 12})
        repairs = move_toolkit(repairs, actor_dbref="#1", verb="pickup_toolkit")
        repairs = begin_repair(
            repairs, target="equipment:WATER-PROC-A",
            room="HAB-06-ECLSS-A", actor_dbref="#1", condition="failed")
        self.assertEqual(repairs["jobs"]["equipment:WATER-PROC-A"]["staged_kg"], 3)

        fab = take_offcuts(fab, actor="#1", kg=1)
        wet, ledger = initial_water(), stocks()
        validate_water(wet, ledger)
        fab, wet, ledger = deposit_offcuts(
            fab, wet, ledger, actor="#1", kg=1,
            side="A", receiver_ready=True)
        self.assertEqual(wet["cassettes"]["industrial"]["A"], 1)
        self.assertEqual(ledger["industrial"], 1)
        self.assertEqual(wet["cumulative"]["industrial_waste_kg"], 1)
        self.assertEqual(fab["offcuts_deposited_kg"], 1)
        self.assertTrue(validate_fabrication(fab))

    def test_finish_pauses_if_hands_full_and_cannot_replay_old_output(self):
        fab = prepared()
        for i in range(35):
            fab, _ = step_batches(
                fab, 10, observed={"SHOP-CNC-MILL": {
                    "operating": True, "cumulative_output": (i+1)*100}},
                present={"#1"}, free_part_kg={"#1":0})
        fab, finished = step_batches(
            fab, 10, observed={"SHOP-CNC-MILL": {
                "operating": True, "cumulative_output": 3600}},
            present={"#1"}, free_part_kg={"#1": 0})
        self.assertFalse(finished)
        self.assertEqual(fab["jobs"]["SHOP-CNC-MILL"]["remaining_s"], 10)
        # Credit only a later, genuinely fresh physical machining sample.
        fab, finished = step_batches(
            fab, 10, observed={"SHOP-CNC-MILL": {
                "operating": True, "cumulative_output": 3700}},
            present={"#1"}, free_part_kg={"#1":3})
        self.assertEqual(len(finished), 1)

    def test_no_scrap_teleportation_or_false_cassette_capacity(self):
        fab = prepared()
        with self.assertRaises(FabricationError):
            take_offcuts(fab, actor="#1", kg=1)
        broken = copy.deepcopy(fab)
        broken["drawn_kg"] += 2
        with self.assertRaises(FabricationError):
            validate_fabrication(broken)
        # An unsurveyed industrial receiver is not a disposal sink.
        with self.assertRaises(FabricationError):
            deposit_offcuts(
                initial_fabrication(), initial_water(), stocks(),
                actor="#1", kg=1, side="A", receiver_ready=False)


if __name__ == "__main__":
    unittest.main()
