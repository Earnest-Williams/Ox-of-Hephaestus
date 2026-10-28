"""G19 food chain: strict mass, calories, nutrients, spoilage and seeded faults.

No 40-person voyage or external model inference. Every resource must have a
physically identifiable origin, in-transit custody and finite destination.
"""
import copy
import math
import random
import unittest

from world.ship_food_logistics import (
    FoodError, STORES, GALLEY, MESS, RECIPES, NUTRIENT_STORES,
    INITIAL_DRY_KG, INITIAL_CONVENTIONAL_KG, CALORIES,
    initial_food, validate_food, unconsumed_stored_kg, take_stored,
    deliver_to_galley, prepare_meal, take_meal, set_meal_in_mess,
    eat_meal, step_food, take_waste, deliver_waste, certify_nutrients,
    take_nutrients, install_nutrients, collect_crop, CREW_DAILY_KCAL,
)
from world.ship_food_cultivation import (
    initial_cultivation, survey_existing_nutrients,
    plan_irrigation, step_cultivation, harvest_cultivation,
    replenish_nutrients, validate_cultivation,
)


def readings(temperature=294):
    return {room: temperature for room in (*STORES, GALLEY, MESS)}


def stocked_galley():
    food = initial_food()
    for kind in ("dry", "conventional"):
        food = take_stored(
            food, actor="#17", room="STORE-FOOD-AFT", kind=kind, kg=2)
        food = deliver_to_galley(food, actor="#17")
    return food


def issue_meal(food, *, recipe="stored"):
    food = prepare_meal(
        food, recipe=recipe, water_delivered_kg=RECIPES[recipe]["water"])
    food = take_meal(food, actor="#17")
    food = set_meal_in_mess(food, actor="#17")
    return food


class FoodManifestTests(unittest.TestCase):
    def test_original_stores_split_one_and_only_one_manifest(self):
        food = initial_food()
        self.assertEqual(set(food["stores"]), set(STORES))
        self.assertAlmostEqual(
            sum(sum(v.values()) for v in food["stores"].values()), 56790)
        self.assertAlmostEqual(sum(s["dry"] for s in food["stores"].values()),
                               INITIAL_DRY_KG)
        self.assertAlmostEqual(
            sum(s["conventional"] for s in food["stores"].values()),
            INITIAL_CONVENTIONAL_KG)
        self.assertTrue(validate_food(food, inventory_kg=56790))
        with self.assertRaises(FoodError):
            initial_food(inventory_kg=200000)
        with self.assertRaises(FoodError):
            validate_food(food, inventory_kg=56789)

    def test_real_worker_carry_and_one_way_source_debit(self):
        original = initial_food()
        food = take_stored(original, actor="#17",
                           room="HAB-03-FOOD-STORES", kind="dry", kg=2.5)
        self.assertAlmostEqual(food["carried"]["#17"]["food"]["dry"], 2.5)
        self.assertAlmostEqual(original["stores"]["HAB-03-FOOD-STORES"]["dry"] -
                               food["stores"]["HAB-03-FOOD-STORES"]["dry"], 2.5)
        food = deliver_to_galley(food, actor="#17")
        self.assertAlmostEqual(food["galley_raw"]["dry"], 2.5)
        self.assertEqual(food["carried"]["#17"]["food"]["dry"], 0)
        self.assertTrue(validate_food(food, inventory_kg=56790))
        for room in ("GEN-A-ROOM", "HAB-02-GROW"):
            with self.subTest(room=room), self.assertRaises(FoodError):
                take_stored(food, actor="#17", room=room, kind="dry", kg=1)
        with self.assertRaises(FoodError):
            take_stored(food, actor="#17", room="STORE-FOOD-AFT",
                        kind="fresh", kg=1)

    def test_carry_capacity_cannot_be_bypassed_by_multiple_sources(self):
        food = initial_food()
        food = take_stored(food, actor="#17",
                           room="STORE-FOOD-AFT", kind="dry", kg=4.9)
        with self.assertRaises(FoodError):
            take_stored(food, actor="#17", room="STORE-FOOD-AFT",
                        kind="conventional", kg=0.2)
        with self.assertRaises(FoodError):
            take_stored(food, actor="crew-17", room="STORE-FOOD-AFT",
                        kind="dry", kg=1)

    def test_absent_ingredients_and_water_cannot_prepare_fake_meal(self):
        food = initial_food()
        for recipe in RECIPES:
            with self.subTest(recipe=recipe), self.assertRaises(FoodError):
                prepare_meal(food, recipe=recipe,
                             water_delivered_kg=RECIPES[recipe]["water"])
        food = stocked_galley()
        with self.assertRaises(FoodError):
            prepare_meal(food, recipe="stored", water_delivered_kg=0)
        with self.assertRaises(FoodError):
            prepare_meal(food, recipe="stored", water_delivered_kg=500)

    def test_physical_recipe_calories_carry_serving_and_eat_once(self):
        food = stocked_galley()
        food = issue_meal(food)
        self.assertEqual(len(food["meals"][GALLEY]), 0)
        self.assertEqual(len(food["meals"][MESS]), 1)
        expected_kcal = sum(
            RECIPES["stored"][k] * (1 - 0.04) * CALORIES[k]
            for k in ("dry", "conventional", "fresh"))
        food, kcal = eat_meal(food, actor="#22", room=MESS)
        self.assertAlmostEqual(kcal, expected_kcal)
        self.assertEqual(food["meter"]["meals_consumed"], 1)
        self.assertAlmostEqual(food["crew"]["#22"]["eaten_kcal"], expected_kcal)
        self.assertAlmostEqual(food["meter"]["stored_eaten_kg"],
                               sum(RECIPES["stored"][k] for k in
                                   ("dry", "conventional")) * 0.96)
        self.assertAlmostEqual(food["meter"]["water_eaten_kg"],
                               RECIPES["stored"]["water"])
        self.assertTrue(validate_food(
            food, inventory_kg=unconsumed_stored_kg(food)))
        with self.assertRaises(FoodError):
            eat_meal(food, actor="#22", room=MESS)

    def test_galley_refuse_is_real_and_can_only_be_delivered_once(self):
        food = stocked_galley()
        food = prepare_meal(
            food, recipe="stored",
            water_delivered_kg=RECIPES["stored"]["water"])
        amount = food["waste"][GALLEY]
        self.assertGreater(amount, 0)
        food = take_waste(food, actor="#17", room=GALLEY, kg=amount)
        self.assertAlmostEqual(food["waste"][GALLEY], 0)
        with self.assertRaises(FoodError):
            take_waste(food, actor="#17", room=GALLEY, kg=amount)
        food = deliver_waste(food, actor="#17", kg=amount)
        self.assertAlmostEqual(food["meter"]["waste_deposited_kg"], amount)
        with self.assertRaises(FoodError):
            deliver_waste(food, actor="#17", kg=amount)
        self.assertTrue(validate_food(food))

    def test_stored_food_temperature_failure_has_persistent_loss(self):
        good = initial_food()
        safe = step_food(good, 10, temperatures_k=readings(294))
        hot = step_food(good, 10, temperatures_k=readings(320))
        self.assertGreater(hot["meter"]["stored_wasted_kg"],
                           safe["meter"]["stored_wasted_kg"] * 100)
        self.assertLess(unconsumed_stored_kg(hot),
                        unconsumed_stored_kg(safe))
        self.assertAlmostEqual(
            INITIAL_DRY_KG + INITIAL_CONVENTIONAL_KG,
            unconsumed_stored_kg(hot) + hot["meter"]["stored_wasted_kg"],
            places=4)
        self.assertTrue(validate_food(hot))

    def test_prepared_portions_spoil_in_actual_room_and_remain_refuse(self):
        food = issue_meal(stocked_galley())
        meal = food["meals"][MESS][0]
        meal["age_s"] = 36 * 3600 - 4
        food = step_food(food, 10, temperatures_k=readings())
        self.assertEqual(food["meter"]["meals_spoiled"], 1)
        self.assertEqual(food["meals"][MESS], [])
        self.assertGreater(food["waste"][MESS], 0)
        self.assertTrue(validate_food(food))

    def test_hunger_progression_only_on_registered_living_people(self):
        food = initial_food()
        food["crew"]["#21"] = {
            "balance_kcal": -3 * CREW_DAILY_KCAL + 0.001,
            "eaten_kcal": 0, "meals": 0,
        }
        food["crew"]["#99"] = {
            "balance_kcal": -7 * CREW_DAILY_KCAL,
            "eaten_kcal": 0, "meals": 0,
        }
        food = step_food(food, 10, temperatures_k=readings(),
                         living_crew=("#21",))
        self.assertIn("#21", food["last"]["impaired"])
        self.assertNotIn("#99", food["last"]["impaired"])
        self.assertEqual(food["crew"]["#99"]["balance_kcal"],
                         -7 * CREW_DAILY_KCAL)

    def test_real_meals_reduce_cumulative_nutritional_deficit(self):
        food = issue_meal(stocked_galley())
        food["crew"]["#22"] = {
            "balance_kcal": -3 * CREW_DAILY_KCAL - 50.0,
            "eaten_kcal": 0, "meals": 0}
        food = step_food(food, 10, temperatures_k=readings(),
                         living_crew=("#22",))
        self.assertIn("#22", food["last"]["impaired"])
        food, _ = eat_meal(food, actor="#22", room=MESS)
        self.assertNotIn("#22", food["last"]["impaired"])
        self.assertGreater(food["crew"]["#22"]["balance_kcal"],
                           -3 * CREW_DAILY_KCAL)

    def test_finite_nutrients_must_be_issued_then_locally_installed(self):
        crop = survey_existing_nutrients(
            initial_cultivation(), bay=1, charge_kg=5)
        food = initial_food()
        food = certify_nutrients(food, room="HAB-01-SPARES",
                                 kg=10, already_surveyed_kg=12)
        with self.assertRaises(FoodError):
            certify_nutrients(food, room="HAB-01-SPARES",
                              kg=10, already_surveyed_kg=12)
        food = take_nutrients(food, actor="#17", room="HAB-01-SPARES",
                              kg=4, available_kg=12)
        food = install_nutrients(food, actor="#17", kg=4)
        crop = replenish_nutrients(crop, bay=1, kg=4)
        self.assertAlmostEqual(crop["beds"]["GROW-1"]["nutrient_kg"], 9)
        self.assertAlmostEqual(food["meter"]["nutrient_installed_kg"], 4)
        self.assertTrue(validate_cultivation(crop))
        self.assertTrue(validate_food(food))
        with self.assertRaises(Exception):
            replenish_nutrients(crop, bay=1, kg=2)

    def test_measured_crop_mass_moves_from_rack_to_real_carrier(self):
        crop = survey_existing_nutrients(
            initial_cultivation(), bay=1, charge_kg=4)
        for _ in range(300):
            plan = plan_irrigation(crop, 10,
                                   operating={"GROW-1"}, air_safe={"GROW-1"})
            crop = step_cultivation(crop, 10, planned=plan,
                                    water_delivered_kg=sum(plan.values()))
        crop, harvested = harvest_cultivation(crop, bay=1)
        food, new_crop = collect_crop(
            initial_food(), crop, actor="#17", bay=1, kg=harvested)
        self.assertAlmostEqual(
            crop["beds"]["GROW-1"]["staged_kg"] -
            new_crop["beds"]["GROW-1"]["staged_kg"], harvested)
        self.assertAlmostEqual(
            food["carried"]["#17"]["food"]["fresh"], harvested)
        self.assertTrue(validate_cultivation(new_crop))
        self.assertTrue(validate_food(food))
        with self.assertRaises(FoodError):
            collect_crop(food, new_crop, actor="#17", bay=1,
                         kg=harvested)

    def test_reject_nans_negative_and_manifest_conservation_tampering(self):
        food = initial_food()
        with self.assertRaises(FoodError):
            take_stored(food, actor="#17", room="STORE-FOOD-AFT",
                        kind="dry", kg=float("nan"))
        with self.assertRaises(FoodError):
            certify_nutrients(food, room="FAKE-STORES", kg=5,
                              already_surveyed_kg=10)
        broken = copy.deepcopy(food)
        broken["stores"]["STORE-FOOD-AFT"]["dry"] += 1
        with self.assertRaises(FoodError):
            validate_food(broken)
        broken = copy.deepcopy(food)
        broken["meter"]["fresh_collected_kg"] = 3.0
        with self.assertRaises(FoodError):
            validate_food(broken)

    def test_seeded_randomized_food_transfer_and_no_double_spending(self):
        rand = random.Random(6729)
        food = stocked_galley()
        for _ in range(200):
            option = rand.randrange(5)
            try:
                if option == 0:
                    food = take_stored(
                        food, actor="#17", room=rand.choice(tuple(STORES)),
                        kind=rand.choice(("dry", "conventional")),
                        kg=rand.choice((0.2, 0.5, 1.0, 3.0)))
                elif option == 1:
                    food = deliver_to_galley(food, actor="#17")
                elif option == 2:
                    food = prepare_meal(food, recipe="stored",
                                        water_delivered_kg=RECIPES["stored"]["water"])
                elif option == 3:
                    food = step_food(food, 10, temperatures_k=readings(320))
                else:
                    food, _ = eat_meal(food, actor="#17", room=GALLEY)
            except FoodError:
                pass
            self.assertTrue(validate_food(food))
            self.assertGreaterEqual(unconsumed_stored_kg(food), 0)
        self.assertAlmostEqual(
            unconsumed_stored_kg(food) +
            food["meter"]["stored_eaten_kg"] +
            food["meter"]["stored_wasted_kg"], 56790, places=3)
