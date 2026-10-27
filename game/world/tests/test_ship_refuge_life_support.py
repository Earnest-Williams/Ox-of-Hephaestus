"""Pure G19 independent HAB refuge CO2 sorbent and power accounting tests."""
import copy
import unittest
from types import SimpleNamespace as Row

from world.ship_refuge_life_support import (
    REFUGE_PACKS, NOMINAL_CAPTURE_KG, CAPTURE_RATE_KG_S,
    RefugeAirError, initial_refuge_scrubbers, validate_refuge_scrubbers,
    survey_refuge_scrubber, step_refuge_scrubbers,
)


def fixture():
    equipment = {
        pack: Row(space_id=room, condition="serviceable")
        for pack, (room, battery) in REFUGE_PACKS.items()
    }
    rooms = {
        "HAB-04-REFUGE": "PZ-HAB-04",
        "HAB-08-REFUGE": "PZ-HAB-08",
    }
    cells = {}
    for zone in rooms.values():
        mass, cap, temp, volume = 100.0, 30000.0, 293.15, 100.0
        cells[zone] = {
            "mass": mass, "co2": 2.0, "oxygen": 25.0,
            "energy": (cap + mass) * temp,
            "temperature": temp, "capacity": cap, "volume": volume,
        }
    return equipment, rooms, cells


class RefugeAirContracts(unittest.TestCase):
    def test_neither_unsurveyed_media_nor_open_power_mints_scrubbing(self):
        equipment, rooms, cells = fixture()
        initial = initial_refuge_scrubbers()
        result, updated = step_refuge_scrubbers(
            initial, 10, powered_consumers={"HAB-04-REFUGE-AIR"},
            equipment=equipment, room_zones=rooms, cells=cells)
        self.assertEqual(result["meter"]["captured_kg"], 0)
        self.assertEqual(updated, cells)
        surveyed = survey_refuge_scrubber(
            initial, "HAB-04-REFUGE-AIR", remaining_capacity_kg=2.0)
        off, no_power = step_refuge_scrubbers(
            surveyed, 10, powered_consumers=set(),
            equipment=equipment, room_zones=rooms, cells=cells)
        self.assertEqual(off["meter"]["captured_kg"], 0)
        self.assertEqual(no_power, cells)
        self.assertEqual(initial, initial_refuge_scrubbers())

    def test_finite_capture_preserves_all_physical_gas_mass_and_other_arc(self):
        equipment, rooms, cells = fixture()
        ledger = survey_refuge_scrubber(
            initial_refuge_scrubbers(), "HAB-04-REFUGE-AIR",
            remaining_capacity_kg=0.006)
        gas0 = copy.deepcopy(cells)
        before = sum(cell["mass"] for cell in gas0.values())
        for expected in (0.004, 0.006, 0.006):
            ledger, cells = step_refuge_scrubbers(
                ledger, 10, powered_consumers={"HAB-04-REFUGE-AIR"},
                equipment=equipment, room_zones=rooms, cells=cells)
            self.assertAlmostEqual(
                ledger["meter"]["captured_kg"], expected, places=9)
            self.assertAlmostEqual(
                sum(c["mass"] for c in cells.values()) +
                ledger["meter"]["captured_kg"], before, places=9)
            self.assertEqual(cells["PZ-HAB-08"], gas0["PZ-HAB-08"])
        self.assertAlmostEqual(ledger["units"]["HAB-04-REFUGE-AIR"][
            "captured_kg"], 0.006)
        self.assertEqual(
            ledger["last"]["blocked"]["HAB-04-REFUGE-AIR"],
            "sorbent_exhausted")
        self.assertTrue(validate_refuge_scrubbers(ledger))

    def test_failed_appliance_bad_pressure_and_other_source_do_not_crossfeed(self):
        equipment, rooms, cells = fixture()
        bank = survey_refuge_scrubber(
            initial_refuge_scrubbers(), "HAB-04-REFUGE-AIR",
            remaining_capacity_kg=1.0)
        equipment["HAB-04-REFUGE-AIR"].condition = "failed"
        disabled, gas = step_refuge_scrubbers(
            bank, 10, powered_consumers={"HAB-04-REFUGE-AIR"},
            equipment=equipment, room_zones=rooms, cells=cells)
        self.assertEqual(gas, cells)
        equipment["HAB-04-REFUGE-AIR"].condition = "serviceable"
        vacuum = copy.deepcopy(cells)
        vacuum["PZ-HAB-04"]["volume"] *= 10
        disabled, gas = step_refuge_scrubbers(
            bank, 10, powered_consumers={"HAB-04-REFUGE-AIR"},
            equipment=equipment, room_zones=rooms, cells=vacuum)
        self.assertEqual(gas, vacuum)
        self.assertEqual(disabled["last"]["blocked"]["HAB-04-REFUGE-AIR"],
                         "unpressurised_refuge")
        # Installed packages must not substitute electricity for one another.
        other, gas = step_refuge_scrubbers(
            bank, 10, powered_consumers={"HAB-08-REFUGE-AIR"},
            equipment=equipment, room_zones=rooms, cells=cells)
        self.assertEqual(other["meter"]["captured_kg"], 0)
        self.assertEqual(gas, cells)

    def test_operator_survey_is_finite_and_cannot_restock_spent_medium(self):
        first = survey_refuge_scrubber(
            initial_refuge_scrubbers(), "HAB-04-REFUGE-AIR",
            remaining_capacity_kg=NOMINAL_CAPTURE_KG)
        self.assertGreater(NOMINAL_CAPTURE_KG, 100)
        self.assertAlmostEqual(CAPTURE_RATE_KG_S * 72 * 3600,
                               NOMINAL_CAPTURE_KG)
        for name, capacity in (
            ("HAB-04-REFUGE-AIR", 1.0),
            ("HAB-08-REFUGE-AIR", NOMINAL_CAPTURE_KG + 1),
            ("UNKNOWN-AIR", 1.0),
        ):
            with self.assertRaises(RefugeAirError):
                survey_refuge_scrubber(
                    first, name, remaining_capacity_kg=capacity)
        damaged = copy.deepcopy(first)
        damaged["meter"]["captured_kg"] = 99
        with self.assertRaises(RefugeAirError):
            validate_refuge_scrubbers(damaged)
        equipment, rooms, cells = fixture()
        with self.assertRaises(RefugeAirError):
            step_refuge_scrubbers(
                first, 60, powered_consumers=set(),
                equipment=equipment, room_zones=rooms, cells=cells)
