"""Finite local wastewater replacement filters and classified waste handoffs."""
import unittest

from world.ship_water_recycling import (
    WaterError, initial_water, step_water, validate_water,
    water_inventory_total,
)
from world.ship_water_materials import (
    register_source_survey, take_filter, load_filter, local_classified_deposit,
)
from world.tests.test_ship_water_recycling import stock, healthy


def materials():
    result = stock()
    result.update(filter=8000.0, spares=25000.0)
    return result


class PhysicalWasteMaterialsTests(unittest.TestCase):
    def test_filter_moves_from_real_store_through_character_to_purifier(self):
        w, s = initial_water(), materials()
        original = water_inventory_total(w, s)
        w = register_source_survey(
            w, source="INV-DC-CONSUMABLES", room="STORE-CRIT-SPARES",
            verified_kg=1.0, inventory_kg=s["filter"])
        with self.assertRaises(WaterError):
            take_filter(w, actor_dbref="#18", room="HAB-06-ECLSS-A",
                        kg=1.0, stock_kg=s["filter"])
        w, s["filter"] = take_filter(
            w, actor_dbref="#18", room="STORE-CRIT-SPARES",
            kg=1, stock_kg=s["filter"])
        self.assertEqual(w["filter_carried_kg"]["#18"], 1.0)
        self.assertEqual(s["filter"], 7999)
        self.assertAlmostEqual(water_inventory_total(w, s), original)
        with self.assertRaises(WaterError):
            load_filter(w, actor_dbref="#19", side="A", kg=1)
        w = load_filter(w, actor_dbref="#18", side="A", kg=1)
        self.assertEqual(w["filter_carried_kg"]["#18"], 0)
        self.assertEqual(w["filter_staged_kg"]["A"], 1)
        self.assertAlmostEqual(water_inventory_total(w, s), original)
        w["potable_quarantined"] = True
        w["suspected_contamination_kg"] = 1.5
        w["decontaminate"]["A"] = True
        w, s, result = step_water(w, 60, stocks=s, hardware=healthy())
        self.assertAlmostEqual(result["decontaminated_kg"], 1.5)
        self.assertAlmostEqual(s["hazardous"], .003, places=5)
        self.assertAlmostEqual(w["filter_staged_kg"]["A"], .997, places=5)
        self.assertAlmostEqual(water_inventory_total(w, s), original)
        validate_water(w, s)

    def test_source_survey_preserves_unlocated_stock_and_prevents_double_count(self):
        w, s = initial_water(), materials()
        w = register_source_survey(
            w, source="INV-SPARES", room="SPARES-CENTRAL",
            verified_kg=5, inventory_kg=s["spares"])
        w = register_source_survey(
            w, source="INV-SPARES", room="TOOL-CRIB",
            verified_kg=24995, inventory_kg=s["spares"])
        with self.assertRaises(WaterError):
            register_source_survey(
                w, source="INV-SPARES", room="STORE-CRIT-SPARES",
                verified_kg=1, inventory_kg=s["spares"])
        self.assertEqual(w["source_surveys"]["INV-SPARES"]["SPARES-CENTRAL"], 5)
        validate_water(w, s)

    def test_surveyed_spares_convert_to_real_industrial_cassette_and_source_debit(self):
        w, s = initial_water(), materials()
        w = register_source_survey(
            w, source="INV-SPARES", room="SPARES-CENTRAL",
            verified_kg=2, inventory_kg=s["spares"])
        h = {"bins": {"industrial": {"A": True}}}
        w, s = local_classified_deposit(
            w, s, category="industrial", source="INV-SPARES",
            actor_room="SPARES-CENTRAL", target_side="A",
            kg=2, hardware=h)
        self.assertEqual(s["spares"], 24998)
        self.assertEqual(s["industrial"], 2)
        self.assertEqual(w["cassettes"]["industrial"]["A"], 2)
        self.assertEqual(w["source_surveys"]["INV-SPARES"]["SPARES-CENTRAL"], 0)
        validate_water(w, s)
        with self.assertRaises(WaterError):
            local_classified_deposit(
                w, s, category="industrial", source="INV-SPARES",
                actor_room="SPARES-CENTRAL", target_side="A", kg=1,
                hardware=h)

    def test_class_and_isolation_cannot_be_bypassed(self):
        w, s = initial_water(), materials()
        w = register_source_survey(
            w, source="INV-SPARES", room="SPARES-CENTRAL",
            verified_kg=5, inventory_kg=s["spares"])
        bad = (
            ("hazardous", "INV-SPARES", {"hazardous": {"B": True}}),
            ("industrial", "INV-SPARES", {"industrial": {"A": False}}),
        )
        for group, source, bins in bad:
            with self.subTest(group=group, bins=bins):
                with self.assertRaises(WaterError):
                    local_classified_deposit(
                        w, s, category=group, source=source,
                        actor_room="SPARES-CENTRAL", target_side=(
                            "A" if group == "industrial" else "B"),
                        kg=2, hardware={"bins": bins})
        self.assertEqual(s["spares"], 25000)


if __name__ == "__main__":
    unittest.main()
