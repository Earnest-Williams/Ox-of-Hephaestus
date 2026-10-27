"""Pure six-drum cargo thermal, LT budget and irreversible freight damage tests."""
import copy
import unittest

from world.ship_cargo_manifest import (
    initial_cargo, declare_cargo_lot, split_cargo_lot, onboard_mass_kg)
from world.ship_cargo_environment import (
    CargoClimateError, DRUMS, COOLER_LIMIT_KW,
    initial_cargo_environment, validate_cargo_environment,
    survey_drum_environment, survey_sensitive_lot,
    inherit_split_care, set_cargo_target, step_cargo_environment,
)


def freight():
    original = initial_cargo(900_000_000)
    declared = declare_cargo_lot(
        original, lot_id="MEDICINE", mass_kg=20000,
        drum="DR-03", azimuth_deg=0, radius_m=5,
        kind="sled", restrained=True)
    return declared


def measured(temperature=284., target=275., capacity=1000.,
             conductivity=1.0):
    manifest = freight()
    initial = initial_cargo_environment()
    climate = survey_drum_environment(
        initial, manifest, "DR-03", temperature_k=temperature,
        target_k=target, heat_capacity_kj_k=capacity,
        conductance_kw_k=conductivity)
    return manifest, climate


def run(climate, manifest, *, seconds=10, ambient=303.15,
        active=("DR-03-CARGO-HX", "DR-03-CARGO-GAS"),
        lt=("NODE-DR-03-LT-IF",), budget=200):
    return step_cargo_environment(
        climate, manifest, seconds,
        ambient_by_drum={"DR-03": ambient},
        operating_machines=active, connected_lt_nodes=lt,
        cooling_budget_kw=budget)


class CargoClimateContracts(unittest.TestCase):
    def test_unsurveyed_900000_tonnes_stays_unclassified_not_refrigerated(self):
        manifest = freight()
        initial = initial_cargo_environment()
        self.assertEqual(initial["lots"], {})
        self.assertEqual(len(initial["drums"]), 6)
        after, heat, cool = run(initial, manifest)
        self.assertEqual(after, initial)
        self.assertEqual(heat, {})
        self.assertEqual(cool, 0.0)
        self.assertEqual(onboard_mass_kg(manifest), 900_000_000)
        with self.assertRaises(CargoClimateError):
            survey_sensitive_lot(initial, manifest, "MEDICINE", "cold_chain")

    def test_finite_cargo_heat_exchange_debits_shared_lt_radiators(self):
        manifest, climate = measured(temperature=300, target=275)
        with_cooling, heat, reject_kw = run(
            climate, manifest, ambient=300, budget=11.0)
        self.assertAlmostEqual(reject_kw, 11)
        self.assertAlmostEqual(
            with_cooling["drums"]["DR-03"]["temperature_k"], 299.89)
        self.assertEqual(heat["DR-03"], 0.0)
        self.assertAlmostEqual(
            with_cooling["meter"]["radiator_rejected_kj"], 110)
        self.assertAlmostEqual(with_cooling["last"]["cooling_kw"], 11)
        self.assertEqual(with_cooling["last"]["cooled_drums"], ["DR-03"])
        with_max, _, cap = run(climate, manifest, ambient=300, budget=1000)
        self.assertEqual(cap, COOLER_LIMIT_KW)
        self.assertLess(with_max["drums"]["DR-03"]["temperature_k"],
                        with_cooling["drums"]["DR-03"]["temperature_k"])
        self.assertEqual(climate["meter"]["radiator_rejected_kj"], 0)

    def test_real_coolant_route_and_both_machines_required(self):
        manifest, climate = measured()
        cooled, _, kW = run(climate, manifest)
        self.assertGreater(kW, 0)
        for active, lt in (
            (("DR-03-CARGO-HX",), ("NODE-DR-03-LT-IF",)),
            (("DR-03-CARGO-GAS",), ("NODE-DR-03-LT-IF",)),
            (("DR-03-CARGO-HX", "DR-03-CARGO-GAS"), ()),
            ((), ("NODE-DR-03-LT-IF",)),
        ):
            with self.subTest(active=active, lt=lt):
                stop, wall, heat = run(
                    climate, manifest, active=active, lt=lt)
                self.assertEqual(heat, 0)
                self.assertGreater(wall["DR-03"], 0)
                self.assertGreater(
                    stop["drums"]["DR-03"]["temperature_k"],
                    climate["drums"]["DR-03"]["temperature_k"])
        self.assertEqual(len(cooled["last"]["unmeasured_drums"]), 5)

    def test_gallery_energy_exchange_signed_and_cooling_independent(self):
        manifest, climate = measured(temperature=300, target=290,
                                      capacity=1000, conductivity=1)
        warmed, heat, kw = run(
            climate, manifest, ambient=290, active=(), lt=(), budget=0)
        self.assertEqual(kw, 0)
        self.assertAlmostEqual(heat["DR-03"], -100.0)
        self.assertAlmostEqual(
            warmed["drums"]["DR-03"]["temperature_k"], 299.9)
        self.assertAlmostEqual(
            warmed["meter"]["gallery_exchange_kj"], -100)
        # Hot service gallery, temperature > nominal survey band, is a
        # casualty to integrate, rather than a reason to erase cargo state.
        worse, exchange, _ = run(
            warmed, manifest, ambient=680, active=(), lt=(), budget=0)
        self.assertGreater(exchange["DR-03"], 0)
        self.assertGreater(worse["drums"]["DR-03"]["temperature_k"],
                           warmed["drums"]["DR-03"]["temperature_k"])

    def test_sensitive_lot_degrades_in_actual_drum_not_unknown_cargo(self):
        manifest, climate = measured(temperature=288, target=275)
        climate = survey_sensitive_lot(
            climate, manifest, "MEDICINE", "cold_chain")
        original_mass = onboard_mass_kg(manifest)
        before = copy.deepcopy(climate)
        degraded, heat, kw = run(
            climate, manifest, active=(), lt=(), budget=0)
        lot = degraded["lots"]["MEDICINE"]
        self.assertGreater(lot["excursion_s"], 0)
        self.assertLess(lot["quality"], 1)
        self.assertIn("MEDICINE", degraded["last"]["exposed_lots"])
        self.assertEqual(onboard_mass_kg(manifest), original_mass)
        self.assertEqual(before["lots"]["MEDICINE"]["quality"], 1)
        # Enabling control may halt future damage; it does not undo loss.
        conditioned = set_cargo_target(
            degraded, manifest, "DR-03", 270)
        self.assertEqual(
            conditioned["lots"]["MEDICINE"]["quality"], lot["quality"])

    def test_lot_split_preserves_existing_damage_and_transfer_uncertainty(self):
        manifest, climate = measured(temperature=290)
        climate = survey_sensitive_lot(
            climate, manifest, "MEDICINE", "cold_chain")
        climate, _, _ = run(climate, manifest, active=(), lt=(), budget=0)
        divided = split_cargo_lot(
            manifest, source_id="MEDICINE", new_id="PALLET", mass_kg=6000)
        inherited = inherit_split_care(
            climate, manifest, divided, "MEDICINE", "PALLET")
        self.assertEqual(inherited["lots"]["PALLET"],
                         inherited["lots"]["MEDICINE"])
        self.assertEqual(onboard_mass_kg(divided), onboard_mass_kg(manifest))
        with self.assertRaises(CargoClimateError):
            inherit_split_care(inherited, divided, divided,
                               "MEDICINE", "PALLET")
        moving = copy.deepcopy(divided)
        moving["lots"]["PALLET"]["location"] = "SPINE-FREIGHT"
        old_score = inherited["lots"]["PALLET"]["quality"]
        moved, _, _ = run(inherited, moving)
        self.assertEqual(moved["lots"]["PALLET"]["quality"], old_score)
        self.assertEqual(moved["lots"]["PALLET"]["unmeasured_s"], 10)

    def test_surveys_sensors_and_energy_budget_reject_forged_values(self):
        manifest, climate = measured()
        for target, args in (
            ("DR-03", {"temperature_k": 288, "target_k": 275,
                       "heat_capacity_kj_k": 1000,
                       "conductance_kw_k": 1}),
            ("DR-08", {"temperature_k": 288, "target_k": 275,
                       "heat_capacity_kj_k": 1000,
                       "conductance_kw_k": 1}),
            ("DR-05", {"temperature_k": float("nan"), "target_k": 275,
                       "heat_capacity_kj_k": 1000,
                       "conductance_kw_k": 1}),
        ):
            with self.subTest(drum=target):
                with self.assertRaises(CargoClimateError):
                    survey_drum_environment(climate, manifest, target, **args)
        for dt, budget in ((11, 50), (10, -1), (float("nan"), 20)):
            with self.assertRaises(CargoClimateError):
                run(climate, manifest, seconds=dt, budget=budget)
        damaged = copy.deepcopy(climate)
        damaged["meter"]["radiator_rejected_kj"] = -5
        with self.assertRaises(CargoClimateError):
            validate_cargo_environment(damaged, manifest)
