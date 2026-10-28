"""G19 original three-bay finite cultivation regression (no crew voyage)."""
import unittest

from world.ship_food_cultivation import (
    DAY, CultivationError, GROW_BAYS, initial_cultivation,
    survey_existing_nutrients, plan_irrigation, step_cultivation,
    harvest_cultivation, validate_cultivation, NOMINAL_WATER_KG_DAY,
    migrate_cultivation_v1,
)
from world.ship_water_recycling import initial_water, step_water


class CultivationTests(unittest.TestCase):
    def setUp(self):
        self.beds = initial_cultivation()
        for number in GROW_BAYS:
            self.beds = survey_existing_nutrients(
                self.beds, bay=number, charge_kg=10.0)

    def test_survey_is_bounded_and_cannot_mint_replacement_charge(self):
        self.assertTrue(validate_cultivation(self.beds))
        with self.assertRaises(CultivationError):
            survey_existing_nutrients(self.beds, bay=1, charge_kg=2)
        with self.assertRaises(CultivationError):
            survey_existing_nutrients(initial_cultivation(), bay=4, charge_kg=1)
        with self.assertRaises(CultivationError):
            survey_existing_nutrients(initial_cultivation(), bay=2, charge_kg=11)

    def test_three_bays_require_simultaneous_power_and_air(self):
        plan = plan_irrigation(
            self.beds, 10, operating={"GROW-1", "GROW-2"},
            air_safe={"GROW-2", "GROW-3"})
        self.assertEqual(list(plan), ["GROW-2"])
        self.assertGreater(plan["GROW-2"], 0)
        none = plan_irrigation(
            self.beds, 10, operating=set(), air_safe=set(GROW_BAYS_TO_NAMES))
        self.assertEqual(none, {})

    def test_growth_limited_by_actual_water_and_corresponding_nutrients(self):
        original = self.beds
        active = set(GROW_BAYS_TO_NAMES)
        plan = plan_irrigation(self.beds, 10,
                               operating=active, air_safe=active)
        self.assertLessEqual(sum(plan.values()), NOMINAL_WATER_KG_DAY * 10 / DAY)
        no_water = step_cultivation(self.beds, 10, planned=plan,
                                    water_delivered_kg=0)
        self.assertEqual(no_water["last"]["grown_kg"], 0)
        self.assertEqual(self.beds, original)
        half = step_cultivation(self.beds, 10, planned=plan,
                                water_delivered_kg=sum(plan.values()) / 2)
        self.assertGreater(half["last"]["grown_kg"], 0)
        self.assertLess(half["last"]["grown_kg"], 3 * 8.5 * 10 / DAY)
        self.assertTrue(validate_cultivation(half))
        with self.assertRaises(CultivationError):
            step_cultivation(self.beds, 10, planned=plan,
                             water_delivered_kg=sum(plan.values()) * 2)

    def test_harvest_moves_existing_biomass_once_not_creates_meals(self):
        ledger = self.beds
        for _ in range(500):
            plan = plan_irrigation(ledger, 10,
                                  operating={"GROW-1"}, air_safe={"GROW-1"})
            ledger = step_cultivation(ledger, 10, planned=plan,
                                      water_delivered_kg=sum(plan.values()))
        before = ledger["beds"]["GROW-1"]
        ledger, harvested = harvest_cultivation(ledger, bay=1)
        after = ledger["beds"]["GROW-1"]
        self.assertGreater(harvested, 0)
        self.assertAlmostEqual(after["standing_kg"] + after["staged_kg"],
                               before["standing_kg"] + before["staged_kg"])
        self.assertAlmostEqual(after["staged_kg"], harvested)
        self.assertEqual(after["grown_kg"], before["grown_kg"])

    def test_migrated_water_ledger_charges_only_real_cultivation_demand(self):
        water = initial_water()
        stocks = dict(normal=162000.0, reserve=70000.0, sanitary=0.0,
                      industrial=0.0, hazardous=0.0)
        plant = dict(potable=True, process={"A": True, "B": True},
                     fixed={"grey": True, "black": True}, oxygen=True,
                     bins={k: {"A": True, "B": True}
                           for k in ("sanitary", "industrial", "hazardous")})
        stopped, _, result = step_water(
            water, 10, stocks=stocks, hardware=plant,
            cultivation_demand_kg=0.0)
        self.assertEqual(result["cultivation_water_kg"], 0)
        self.assertTrue(stopped["working_kg"] <= water["working_kg"])
        with self.assertRaises(ValueError):
            step_water(water, 10, stocks=stocks, hardware=plant,
                       cultivation_demand_kg=1000)


    def test_migrate_preexisting_commissioned_beds_without_resetting_harvest(self):
        old = survey_existing_nutrients(
            initial_cultivation(), bay=1, charge_kg=4)
        plan = plan_irrigation(
            old, 10, operating={"GROW-1"}, air_safe={"GROW-1"})
        old = step_cultivation(
            old, 10, planned=plan, water_delivered_kg=sum(plan.values()))
        expected = old["beds"]["GROW-1"]["grown_kg"]
        for bed in old["beds"].values():
            del bed["released_kg"]
            del bed["replenished_nutrient_kg"]
        upgraded = migrate_cultivation_v1(old)
        self.assertAlmostEqual(
            upgraded["beds"]["GROW-1"]["grown_kg"], expected)
        self.assertEqual(upgraded["beds"]["GROW-1"]["nutrient_kg"],
                         old["beds"]["GROW-1"]["nutrient_kg"])
        self.assertEqual(migrate_cultivation_v1(upgraded), upgraded)
        self.assertTrue(validate_cultivation(upgraded))


    def test_active_cooking_does_not_double_charge_daily_rehydration_budget(self):
        water = initial_water()
        stocks = dict(normal=162000.0, reserve=70000.0, sanitary=0.0,
                      industrial=0.0, hazardous=0.0)
        plant = dict(potable=True, process={"A": True, "B": True},
                     fixed={"grey": True, "black": True}, oxygen=True,
                     bins={k: {"A": True, "B": True}
                           for k in ("sanitary", "industrial", "hazardous")})
        old, _, old_report = step_water(
            water, 10, stocks=stocks, hardware=plant)
        new, _, new_report = step_water(
            water, 10, stocks=stocks, hardware=plant,
            food_rehydration_demand_kg=0.0)
        self.assertGreater(old_report["technical_kg"],
                           new_report["technical_kg"])
        self.assertAlmostEqual(
            old_report["technical_kg"] - new_report["technical_kg"],
            (740.0 / 730.0) * 10.0 / DAY, places=8)
        with self.assertRaises(ValueError):
            step_water(water, 10, stocks=stocks, hardware=plant,
                       food_rehydration_demand_kg=500)


GROW_BAYS_TO_NAMES = tuple(f"GROW-{n}" for n in GROW_BAYS)
