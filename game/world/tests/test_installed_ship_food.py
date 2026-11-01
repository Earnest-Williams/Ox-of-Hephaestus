"""G19 actual installed food rooms, finite stock, local crew and sanitation.

No autonomous voyage and no synthetic galley, stock, corridor or nutrient.
"""
from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, state,
)
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    commission_g19_water, commission_g19_cultivation,
    commission_g19_food, commission_g19_crew_physiology,
    survey_g19_cultivation_nutrients, survey_g19_water_material,
    survey_g19_food_nutrient_stock, crew_physical_action,
    tick_continuous_physics, local_physics_readout,
)
from world.models import CanonicalShipState, WorkReceipt


class InstalledFoodTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        self.worker = build_ship()["watch"]
        self.at_room("HAB-01-FOOD-STORES")
        commission_g19_crew_physiology(
            actor_dbrefs=[self.worker.dbref], operator_approved=True)

    def at_room(self, room):
        position = find_ship_space(room)
        self.assertIsNotNone(position, room)
        self.worker.move_to(position, quiet=True)

    def food(self):
        return CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["food"]

    def receipt(self, number, site, action):
        return crew_physical_action(
            self.worker, f"{number:032x}", "food", site, action)

    def line_up_source(self, start, destination):
        edges = list(CanonicalShipState.objects.filter(
            category="edge", reference__network="power"))
        graph = defaultdict(list)
        for edge in edges:
            if edge.setting != "available" or edge.condition in {
                    "faulted", "failed", "destroyed", "jammed", "severed"}:
                continue
            a, b = edge.reference["from_node"], edge.reference["to_node"]
            graph[a].append((b, edge))
            if edge.reference.get("kind") in {"bridge_feeder", "cross_tie"}:
                graph[b].append((a, edge))
        q, seen, parent = deque([start]), {start}, {}
        while q and destination not in seen:
            for nxt, edge in graph[q.popleft()]:
                if nxt not in seen:
                    seen.add(nxt)
                    parent[nxt] = edge, edge.reference["from_node"], edge.reference["to_node"]
                    q.append(nxt)
        self.assertIn(destination, seen)
        node = destination
        while node != start:
            edge, a, b = parent[node]
            for iso in edge.reference["isolator_ids"]:
                if state("isolator", iso).setting != "closed":
                    set_isolator(iso, "closed", operator=True)
            node = a if node == b else b

    def prime_plant(self):
        # The original HAB-02 galley panel is wired to the B-side bus.
        # Cross-tie EDGE-MSB-XTIE is STANDBY, not a free A->B shortcut.
        set_isolator("ISO-GEN-M", "closed", operator=True)
        set_isolator("ISO-GEN-B", "closed", operator=True)
        self.line_up_source("NODE-GEN-B", "NODE-HAB-02-GALLEY-LP")
        for row in CanonicalShipState.objects.filter(category="isolator"):
            if row.reference.get("network") in {
                    "potable_water", "greywater", "blackwater"}:
                if row.condition in {"serviceable", "degraded"}:
                    set_isolator(row.source_id, "open", operator=True)

    def test_one_original_inventory_and_no_reset_or_global_remote_oracle(self):
        self.assertEqual(commission_g19_food(operator_approved=True)["stores"], 5)
        self.assertEqual(commission_g19_food(operator_approved=True),
                         {"commissioned": False})
        self.assertAlmostEqual(
            state("inventory", "INV-FOOD-LONG-LEG").quantity, 56.79)
        self.assertGreater(local_physics_readout(
            self.worker, "food")["stored_kg_by_kind"]["dry"], 0)
        self.at_room("HAB-02-MESS")
        self.assertNotIn("stored_kg_by_kind",
                         local_physics_readout(self.worker, "food"))
        self.assertIsNone(local_physics_readout(self.worker, "nutrition")[
            "personal_nutrition"])
        self.assertIsNone(self.food()["carried"].get(self.worker.dbref))

    def test_food_issued_at_one_store_is_not_issued_by_remote_worker(self):
        commission_g19_food(operator_approved=True)
        room = "HAB-01-FOOD-STORES"
        before = self.food()["stores"][room]["conventional"]
        first = self.receipt(1, room, "take:conventional:1")
        self.assertEqual(first["status"], "succeeded")
        self.assertAlmostEqual(
            self.food()["stores"][room]["conventional"], before - 1)
        self.assertEqual(self.receipt(1, room, "take:conventional:1"), first)
        with self.assertRaises(PermissionError):
            self.receipt(1, room, "take:conventional:2")
        self.at_room("HAB-02-GALLEY")
        self.assertEqual(
            self.receipt(2, "HAB-02-GALLEY", "deliver")["status"], "succeeded")
        self.assertAlmostEqual(self.food()["galley_raw"]["conventional"], 1)
        self.assertAlmostEqual(
            state("inventory", "INV-FOOD-LONG-LEG").quantity, 56.79)
        with self.assertRaises((PhysicsError, PermissionError)):
            self.receipt(3, room, "take:dry:2")
        self.assertFalse(WorkReceipt.objects.filter(pk=f"{3:032x}").exists())

    def test_galley_cannot_cook_without_real_feeder(self):
        commission_g19_food(operator_approved=True)
        self.receipt(4, "HAB-01-FOOD-STORES", "take:dry:0.3")
        self.at_room("HAB-02-GALLEY")
        self.receipt(5, "HAB-02-GALLEY", "deliver")
        self.at_room("HAB-03-FOOD-STORES")
        self.receipt(6, "HAB-03-FOOD-STORES", "take:conventional:0.7")
        self.at_room("HAB-02-GALLEY")
        self.receipt(7, "HAB-02-GALLEY", "deliver")
        before = self.food()["meter"]["meals_prepared"]
        with self.assertRaises(PhysicsError):
            self.receipt(8, "HAB-02-GALLEY", "cook:stored")
        self.assertEqual(self.food()["meter"]["meals_prepared"], before)
        self.assertFalse(WorkReceipt.objects.filter(pk=f"{8:032x}").exists())

    def test_actual_store_to_galley_to_mess_and_real_crew_meal(self):
        commission_g19_food(operator_approved=True)
        self.receipt(9, "HAB-01-FOOD-STORES", "take:dry:1")
        self.at_room("HAB-03-FOOD-STORES")
        self.receipt(10, "HAB-03-FOOD-STORES", "take:conventional:1")
        self.at_room("HAB-02-GALLEY")
        self.receipt(11, "HAB-02-GALLEY", "deliver")
        self.prime_plant()
        water_before = self.food()["meter"]["water_used_kg"]
        made = self.receipt(12, "HAB-02-GALLEY", "cook:stored")
        self.assertEqual(made["status"], "succeeded")
        self.assertAlmostEqual(
            self.food()["meter"]["water_used_kg"] - water_before, 0.12)
        self.assertEqual(self.food()["meter"]["meals_prepared"], 1)
        taken = self.receipt(13, "HAB-02-GALLEY", "meal_take")
        self.at_room("HAB-02-MESS")
        self.receipt(14, "HAB-02-MESS", "meal_serve")
        meal = self.receipt(15, "HAB-02-MESS", "eat")
        self.assertEqual(meal["status"], "succeeded")
        self.assertEqual(self.food()["meter"]["meals_consumed"], 1)
        self.assertGreater(self.food()["crew"][self.worker.dbref]["eaten_kcal"], 700)
        self.assertLess(state("inventory", "INV-FOOD-LONG-LEG").quantity, 56.79)
        self.assertEqual(self.receipt(15, "HAB-02-MESS", "eat"), meal)
        self.assertEqual(self.food()["meter"]["meals_consumed"], 1)
        with self.assertRaises(PhysicsError):
            self.receipt(16, "HAB-02-MESS", "eat")

    def test_original_spares_are_physically_debited_for_crop_nutrients(self):
        commission_g19_food(operator_approved=True)
        commission_g19_cultivation(operator_approved=True)
        survey_g19_cultivation_nutrients(
            operator_approved=True, bay=3, charge_kg=5)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="HAB-08-SPARES", verified_kg=5)
        with self.assertRaises(PermissionError):
            survey_g19_food_nutrient_stock(
                room_id="HAB-08-SPARES", kg=4)
        survey_g19_food_nutrient_stock(
            operator_approved=True, room_id="HAB-08-SPARES", kg=4)
        starting_stock = state("inventory", "INV-SPARES").quantity
        self.at_room("HAB-08-SPARES")
        self.receipt(17, "HAB-08-SPARES", "nutrient_take:3")
        self.assertAlmostEqual(
            state("inventory", "INV-SPARES").quantity,
            starting_stock - .003)
        self.at_room("HAB-08-GROW")
        self.receipt(18, "HAB-08-GROW", "nutrient_install:3")
        self.assertAlmostEqual(
            CanonicalShipState.objects.get(
                pk="meta:continuous-physics").details[
                "cultivation"]["beds"]["GROW-3"]["nutrient_kg"], 8)
        self.assertEqual(self.food()["carried"][self.worker.dbref]["nutrient_kg"], 0)
        self.assertEqual(self.receipt(18, "HAB-08-GROW", "nutrient_install:3")[
            "status"], "succeeded")
        with self.assertRaises(PhysicsError):
            self.receipt(19, "HAB-08-GROW", "nutrient_install:3")

    def test_spoilage_debits_live_original_food_inventory(self):
        commission_g19_food(operator_approved=True)
        self.prime_plant()
        before = state("inventory", "INV-FOOD-LONG-LEG").quantity
        first = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(first["advanced"])
        self.assertLess(
            state("inventory", "INV-FOOD-LONG-LEG").quantity, before)
        self.assertGreater(self.food()["meter"]["stored_wasted_kg"], 0)
        self.assertGreater(first["food_waste_held_kg"], 0)
        repeat = tick_continuous_physics(now_game_time=1010)
        self.assertFalse(repeat["advanced"])
        self.assertAlmostEqual(
            state("inventory", "INV-FOOD-LONG-LEG").quantity,
            first["food_stored_kg"] / 1000, delta=1e-7)


    def test_galley_scraps_reach_original_sealed_sanitary_receiver_once(self):
        commission_g19_food(operator_approved=True)
        self.receipt(30, "HAB-01-FOOD-STORES", "take:dry:0.25")
        self.receipt(31, "HAB-01-FOOD-STORES", "take:conventional:0.75")
        self.at_room("HAB-02-GALLEY")
        self.receipt(32, "HAB-02-GALLEY", "deliver")
        self.prime_plant()
        self.receipt(33, "HAB-02-GALLEY", "cook:stored")
        initial_waste = self.food()["waste"]["HAB-02-GALLEY"]
        self.assertGreater(initial_waste, 0.02)
        taken = self.receipt(34, "HAB-02-GALLEY", "waste_take:0.02")
        self.assertEqual(taken["status"], "succeeded")
        self.at_room("HAB-06-ECLSS-A")
        before = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["water"][
            "cassettes"]["sanitary"]["A"]
        stock_before = state("inventory", "INV-WASTE-RESIDUE").quantity
        receipt = self.receipt(35, "HAB-06-ECLSS-A", "waste_deposit:0.02")
        self.assertEqual(receipt["status"], "succeeded")
        water = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["water"]
        self.assertAlmostEqual(
            water["cassettes"]["sanitary"]["A"] - before, 0.02, places=7)
        self.assertAlmostEqual(
            state("inventory", "INV-WASTE-RESIDUE").quantity -
            stock_before, 0.00002, places=9)
        self.assertAlmostEqual(
            self.food()["meter"]["waste_deposited_kg"], 0.02, places=7)
        self.assertEqual(
            self.receipt(35, "HAB-06-ECLSS-A", "waste_deposit:0.02"), receipt)
        with self.assertRaises(PhysicsError):
            self.receipt(36, "HAB-06-ECLSS-A", "waste_deposit:0.02")
        self.assertAlmostEqual(
            self.food()["waste"]["HAB-02-GALLEY"],
            initial_waste - 0.02, places=7)

    def test_named_helper_can_feed_patient_in_original_cabin_only(self):
        patient = build_ship()["captain"]
        cabin = "HAB-01-CAB-01"
        self.assertIsNotNone(find_ship_space(cabin))
        self.assertTrue(patient.move_to(find_ship_space(cabin), quiet=True))
        commission_g19_crew_physiology(
            actor_dbrefs=[patient.dbref], operator_approved=True)
        commission_g19_food(operator_approved=True)
        self.receipt(40, "HAB-01-FOOD-STORES", "take:dry:0.3")
        self.receipt(41, "HAB-01-FOOD-STORES", "take:conventional:0.6")
        self.at_room("HAB-02-GALLEY")
        self.receipt(42, "HAB-02-GALLEY", "deliver")
        self.prime_plant()
        self.receipt(43, "HAB-02-GALLEY", "cook:stored")
        self.receipt(44, "HAB-02-GALLEY", "meal_take")
        with self.assertRaises(PermissionError):
            self.receipt(45, cabin, "feed:" + patient.dbref)
        self.at_room(cabin)
        first = self.receipt(46, cabin, "feed:" + patient.dbref)
        self.assertEqual(first["status"], "succeeded")
        result = self.food()
        self.assertGreater(result["crew"][patient.dbref]["eaten_kcal"], 700)
        self.assertNotIn(self.worker.dbref, result["crew"])
        self.assertEqual(self.receipt(46, cabin, "feed:" + patient.dbref), first)
        with self.assertRaises(PhysicsError):
            self.receipt(47, cabin, "feed:" + patient.dbref)
        with self.assertRaises(PhysicsError):
            self.receipt(48, cabin, "feed:#99999999")
        self.assertFalse(WorkReceipt.objects.filter(pk=f"{48:032x}").exists())
