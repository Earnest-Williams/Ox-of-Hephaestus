"""G19 seeded sustained multi-system casualties in the *installed* Evennia ship.

Each named seed is an independent commissioned as-fitted world. The scenario
runs 24 minutes of actual G19 clock time, exercises a crew-operated original
cargo pressure hatch, and introduces faults only through operator-only world
injection interfaces. No synthetic ship or separate physics state is created.

Use one seed per CI job to make slow-world failures exactly reproducible.
"""
from __future__ import annotations

import copy
import json
import math
import random

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.models import CanonicalShipEvent, WorkReceipt
from world.ship_world import build_canonical_ship, find_ship_space
from world.ship_unclassified_spaces import SECTORS
from world.continuous_ship_physics import (
    _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water,
    commission_g19_repairs, commission_g19_eva,
    commission_g19_unclassified_spaces, commission_g19_crew_physiology,
    commission_g19_instrumentation, configure_scenario_casualty,
    configure_water_casualty, survey_cargo_lot,
    survey_g19_cargo_sector, witness_g19_cargo_sector_leak,
    crew_physical_action, tick_continuous_physics,
)


class InstalledG19SeededEndurance(EvenniaTestCase):
    DURATION_MINUTES = 24
    STEP_S = 60.0

    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        self.worker.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.worker.dbref])
        commission_g19_unclassified_spaces(operator_approved=True)
        commission_g19_instrumentation(operator_approved=True)
        self.now_s = 1000.0
        self.serial = 88000

    def _action(self, action, target, value, *, request_id=None):
        if request_id is None:
            self.serial += 1
            request_id = f"{self.serial:032x}"
        return crew_physical_action(
            self.worker, request_id, action, target, value)

    def _survey_original_drum(self):
        survey_cargo_lot(
            operator_approved=True, operation="verify", drum="DR-01")
        for sector in SECTORS[:8]:
            survey_g19_cargo_sector(
                operator_approved=True, sector=sector,
                free_volume_m3=50, pressure_pa=101000,
                temperature_k=293.15, oxygen_mass_fraction=.232,
                co2_mass_fraction=.0004, smoke_mass_fraction=0,
                cargo_class="empty", lot_ids=[])

    def _campaign(self, seed):
        rng = random.Random(seed)
        hazard_order = ["fire", "water", "power"]
        rng.shuffle(hazard_order)
        # Pin complete fault-order coverage, rather than accidentally
        # counting two seeds which shuffled to the same permutation.
        expected_orders = {
            0x19A0: ("water", "fire", "power"),
            0x19A1: ("fire", "water", "power"),
            0x19A3: ("water", "power", "fire"),
            0x19A6: ("power", "fire", "water"),
            0x19A7: ("power", "water", "fire"),
            0x19C3: ("fire", "power", "water"),
            0x19D4: ("water", "power", "fire"),
        }
        self.assertEqual(tuple(hazard_order), expected_orders[seed])
        sector = rng.choice(SECTORS[:8])
        leak_kg_s = .025 + .005 * rng.randrange(6)
        fire_fuel_kg = 5.0 + rng.randrange(5)
        fire_rate_kg_s = .008 + .002 * rng.randrange(4)
        water_kg = 3.0 + rng.randrange(8)

        self._survey_original_drum()
        self.assertTrue(self.worker.move_to(
            find_ship_space("DR-01-GALLERY"), quiet=True))
        self._action("cargo_sector", sector, "secure")
        hatch = "ACC-" + sector
        self.serial += 1
        original_id = f"{self.serial:032x}"
        open_receipt = self._action(
            "hatch", hatch, "open", request_id=original_id)
        self.assertEqual(open_receipt["status"], "succeeded")
        witness_g19_cargo_sector_leak(
            operator_approved=True, sector=sector,
            leak_kg_s=leak_kg_s)

        total_lost = 0.0
        total_burn = 0.0
        total_vent = 0.0
        gallery_at_closure = None
        applied = set()
        trace = []

        for minute in range(self.DURATION_MINUTES):
            # Order and severity vary; clock scheduling remains deterministic.
            if minute in (1, 4, 7):
                hazard = hazard_order[(1, 4, 7).index(minute)]
                if hazard == "fire":
                    configure_scenario_casualty(
                        "PZ-HAB-01", operator=True,
                        fire_fuel_kg=fire_fuel_kg,
                        fire_burn_kg_s=fire_rate_kg_s)
                elif hazard == "water":
                    self.assertLess(
                        water_kg, _clock().details["water"]["working_kg"])
                    configure_water_casualty(
                        operator=True, contaminated_kg=water_kg)
                elif hazard == "power":
                    set_component_condition(
                        "edge", "EDGE-GEN-M", "severed", operator=True)
                applied.add(hazard)

            # A real crew member isolates the service gallery from the
            # leaking sector. The sector shell breach remains physical.
            if minute == 9:
                closed = self._action("hatch", hatch, "closed")
                self.assertEqual(closed["status"], "succeeded")
                gallery_at_closure = _clock().details[
                    "unclassified_spaces"]["sectors"][sector]["gallery_net_kg"]

            previous = self.now_s
            self.now_s += self.STEP_S
            result = tick_continuous_physics(now_game_time=self.now_s)
            self.assertTrue(result["advanced"], (seed, minute))
            self.assertEqual(result["last_game_time"], self.now_s)
            self.assertEqual(self.now_s - previous, self.STEP_S)
            d = _clock().details
            row = d["unclassified_spaces"]["sectors"][sector]

            self.assertGreaterEqual(row["lost_kg"] + 1e-7, total_lost)
            self.assertGreaterEqual(
                d["burned_fuel_kg"] + 1e-7, total_burn)
            self.assertGreaterEqual(
                d["lost_to_space_kg"] + 1e-7, total_vent)
            self.assertGreater(row["lost_kg"], 0)
            self.assertEqual(d["rotors"]["DR-01"]["target_rpm"], 0)
            self.assertEqual(d["instrumentation"]["last_s"], self.now_s)
            self.assertIsNotNone(row["gas"])

            # The as-surveyed sector gas ledger is reconciled to all
            # escape and genuine interchange with the original gallery.
            self.assertTrue(math.isclose(
                row["gas"]["mass_kg"] + row["lost_kg"]
                - row["gallery_net_kg"], row["initial_kg"],
                rel_tol=1e-10, abs_tol=1e-5), (seed, minute, row))
            self.assertGreaterEqual(row["gas"]["mass_kg"], 0)

            # Original generator cartridges remain onboard as either
            # unspent inventory or accounted spent housing mass.
            baseline = d["generator_cartridge_baseline_kg"]
            physical_stock = (
                state("inventory", "INV-GEN-CART").quantity * 1000.0)
            self.assertAlmostEqual(
                physical_stock + d["generator_spent_cartridge_kg"],
                baseline, delta=1e-4)

            if "fire" in applied:
                self.assertGreater(d["burned_fuel_kg"], 0)
            if "water" in applied:
                self.assertTrue(d["water"]["potable_quarantined"])
                self.assertAlmostEqual(
                    d["water"]["suspected_contamination_kg"],
                    water_kg, places=5)
            if "power" in applied:
                self.assertEqual(
                    state("edge", "EDGE-GEN-M").condition, "severed")
                self.assertFalse(result["power_assured"])
            if gallery_at_closure is not None:
                self.assertEqual(state("access", hatch).setting, "closed")
                self.assertAlmostEqual(
                    row["gallery_net_kg"], gallery_at_closure,
                    places=5)

            total_lost = row["lost_kg"]
            total_burn = d["burned_fuel_kg"]
            total_vent = d["lost_to_space_kg"]

            # Replay is a request to the *same* canonical world, with no
            # additional tick, resource debit, or canonical work event.
            if minute in (3, 10, 17, 23):
                snapshot = copy.deepcopy(d)
                before_events = CanonicalShipEvent.objects.count()
                self.assertFalse(tick_continuous_physics(
                    now_game_time=self.now_s)["advanced"])
                self.assertEqual(self._action(
                    "hatch", hatch, "open", request_id=original_id),
                    open_receipt)
                self.assertEqual(_clock().details, snapshot)
                self.assertEqual(
                    CanonicalShipEvent.objects.count(), before_events)
                self.assertEqual(
                    WorkReceipt.objects.filter(pk=original_id).count(), 1)
                trace.append({
                    "minute": minute + 1,
                    "lost_kg": round(total_lost, 6),
                    "burned_kg": round(total_burn, 6),
                    "vented_kg": round(total_vent, 6),
                })

        self.assertEqual(applied, {"fire", "water", "power"})
        self.assertGreater(total_lost, 0)
        self.assertGreater(total_burn, 0)
        self.assertGreater(total_vent, 0)
        self.assertTrue(_clock().details["water"]["potable_quarantined"])
        self.assertEqual(_clock().details["last_game_time"],
                         1000.0 + self.DURATION_MINUTES * self.STEP_S)
        self.assertFalse(
            arm_continuous_physics(
                operator_approved=True, now_game_time=self.now_s + 200)["armed"])
        self.assertEqual(_clock().details["last_game_time"], self.now_s)

        print("G19_SEEDED_ENDURANCE " + json.dumps({
            "seed": seed, "minutes": self.DURATION_MINUTES,
            "hazards": hazard_order, "sector": sector,
            "rate_kg_s": leak_kg_s, "traces": trace,
            "final_lost_kg": total_lost,
            "final_burned_fuel_kg": total_burn,
            "final_vented_kg": total_vent,
            "durable_work_receipts": 1,
        }, sort_keys=True))

    def test_seed_19a0(self):
        self._campaign(0x19A0)

    def test_seed_19a1(self):
        self._campaign(0x19A1)

    def test_seed_19a3(self):
        self._campaign(0x19A3)

    def test_seed_19a6(self):
        self._campaign(0x19A6)

    def test_seed_19a7(self):
        self._campaign(0x19A7)

    def test_seed_19c3(self):
        self._campaign(0x19C3)

    def test_seed_19d4_long(self):
        # Same physically installed ship and casualty rules, held under
        # prolonged blackout/quarantine and shell leakage for three hours.
        self.DURATION_MINUTES = 180
        self._campaign(0x19D4)
