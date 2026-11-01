"""Installed Evennia cultivated-bed and local work receipt regression."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state,
)
from world.continuous_ship_physics import (
    arm_continuous_physics, commission_g19_electrical, commission_g19_water,
    commission_g19_cultivation, survey_g19_cultivation_nutrients,
    crew_physical_action, local_physics_readout, PhysicsError,
)
from world.models import CanonicalShipState, WorkReceipt


class InstalledCultivationTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        self.worker.move_to(find_ship_space("HAB-02-GROW"), quiet=True)

    def test_install_is_idempotent_and_inventories_three_real_grow_bays(self):
        self.assertEqual(commission_g19_cultivation(
            operator_approved=True)["beds"], 3)
        self.assertEqual(commission_g19_cultivation(
            operator_approved=True), {"commissioned": False})
        self.assertFalse(local_physics_readout(
            self.worker, "GROW-1")["surveyed"])
        for number, room in ((1, "HAB-02-GROW"),
                             (2, "HAB-06-GROW"),
                             (3, "HAB-08-GROW")):
            self.assertEqual(state("equipment", f"GROW-{number}-CTRL").space_id, room)
            self.assertEqual(state("equipment", f"GROW-{number}-NUTRIENT").space_id, room)

    def test_positive_operator_charge_and_local_harvest_receipt(self):
        commission_g19_cultivation(operator_approved=True)
        with self.assertRaises(PermissionError):
            survey_g19_cultivation_nutrients(bay=1, charge_kg=2)
        survey_g19_cultivation_nutrients(
            operator_approved=True, bay=1, charge_kg=2)
        with self.assertRaises(PhysicsError):
            survey_g19_cultivation_nutrients(
                operator_approved=True, bay=1, charge_kg=2)
        read = local_physics_readout(self.worker, "GROW-1")
        self.assertEqual(read["nutrient_kg"], 2)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "9" * 32, "cultivation", "GROW-1", "harvest")
        self.assertFalse(WorkReceipt.objects.filter(pk="9" * 32).exists())
        self.worker.move_to(find_ship_space("HAB-06-GROW"), quiet=True)
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "GROW-1")
