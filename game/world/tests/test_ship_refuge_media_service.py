"""Pure G19 verified local refuge-media replacement and sorbent custody."""
import copy
import unittest

from world.ship_refuge_life_support import (
    RefugeAirError, NOMINAL_CAPTURE_KG, initial_refuge_scrubbers,
    survey_refuge_scrubber, validate_refuge_scrubbers,
)
from world.ship_refuge_media_service import (
    MAX_CARRIED_MEDIA_KG, MAX_LOCAL_SPENT_MEDIA_KG,
    initial_refuge_media_service, validate_refuge_media_service,
    load_refuge_media,
)


class RefugeMediaServiceContracts(unittest.TestCase):
    PACK = "HAB-04-REFUGE-AIR"

    def initial(self, capacity=0.008, captured=0.008):
        bank = survey_refuge_scrubber(
            initial_refuge_scrubbers(), self.PACK,
            remaining_capacity_kg=capacity)
        bank["units"][self.PACK]["captured_kg"] = captured
        bank["meter"]["captured_kg"] = captured
        validate_refuge_scrubbers(bank)
        return bank

    def service(self, bank, custody, kg, stock=8000, located=8):
        return load_refuge_media(
            bank, custody, self.PACK, kg,
            surveyed_local_stock_kg=located,
            inventory_stock_kg=stock)

    def test_new_finite_media_occupies_unsurveyed_slots_and_debits_stock(self):
        bank, custody = self.initial(), initial_refuge_media_service()
        original = copy.deepcopy(bank)
        new, service, stock_left = self.service(bank, custody, 4.0)
        self.assertAlmostEqual(new["units"][self.PACK]["capacity_kg"], 4.008)
        self.assertAlmostEqual(new["units"][self.PACK]["captured_kg"], .008)
        self.assertEqual(service["meter"]["fresh_installed_kg"], 4.0)
        self.assertEqual(service["meter"]["retired_capture_kg"], 0)
        self.assertAlmostEqual(stock_left, 7996.0)
        self.assertEqual(original, bank)
        self.assertEqual(custody, initial_refuge_media_service())
        self.assertTrue(validate_refuge_media_service(service))

    def test_retired_captured_gas_remains_aboard_with_spent_media(self):
        bank = self.initial(NOMINAL_CAPTURE_KG, 12.0)
        custody = initial_refuge_media_service()
        before_co2 = bank["meter"]["captured_kg"]
        first, service, stock = self.service(bank, custody, 4)
        self.assertAlmostEqual(first["meter"]["captured_kg"], 8.0)
        self.assertAlmostEqual(service["meter"]["retired_capture_kg"], 4)
        self.assertAlmostEqual(
            first["meter"]["captured_kg"] +
            service["meter"]["retired_capture_kg"], before_co2)
        self.assertEqual(service["sites"][self.PACK]["sealed_spent_media_kg"], 4)
        second, custody2, stock2 = self.service(
            first, service, 4, stock=stock, located=4)
        self.assertAlmostEqual(second["meter"]["captured_kg"], 4)
        self.assertAlmostEqual(custody2["meter"]["retired_capture_kg"], 8)
        self.assertAlmostEqual(
            second["meter"]["captured_kg"] +
            custody2["meter"]["retired_capture_kg"], before_co2)
        with self.assertRaises(RefugeAirError):
            self.service(second, custody2, 4, stock=stock2, located=4)
        self.assertEqual(MAX_LOCAL_SPENT_MEDIA_KG, 8)

    def test_only_local_surveyed_portable_stock_can_be_consumed(self):
        bank = self.initial()
        custody = initial_refuge_media_service()
        for kg, located, ship in (
            (0, 8, 8000), (-1, 8, 8000), (4.1, 8, 8000),
            (4, 3, 8000), (4, 8, 3),
            (float("nan"), 8, 8000)):
            with self.subTest(kg=kg, located=located, ship=ship):
                with self.assertRaises(RefugeAirError):
                    self.service(bank, custody, kg, stock=ship,
                                 located=located)
        self.assertEqual(MAX_CARRIED_MEDIA_KG, 4.0)
        with self.assertRaises(RefugeAirError):
            load_refuge_media(
                initial_refuge_scrubbers(), custody, self.PACK, 1,
                surveyed_local_stock_kg=2,
                inventory_stock_kg=8000)

    def test_corrupt_site_custody_and_capture_account_refused(self):
        c = initial_refuge_media_service()
        bad = copy.deepcopy(c)
        bad["sites"][self.PACK]["sealed_spent_media_kg"] = 10
        with self.assertRaises(RefugeAirError):
            validate_refuge_media_service(bad)
        bad = copy.deepcopy(c)
        bad["meter"]["fresh_installed_kg"] = 100
        with self.assertRaises(RefugeAirError):
            validate_refuge_media_service(bad)
