"""G19 six-drum attended cargo-shell repair under concurrent ship casualties.

Each scenario commissions the actual original 421-space Evennia installation.
An enrolled crew member physically obtains a shared toolkit, finite spares and
a stocked suit, enters the original cargo sector, seals a measured minor hull
leak, and exits via its as-authored rated passage. During work the same world
also sustains HAB fire/heat, quarantined drinking water and a severed main
generator feeder. Only observed process output and durable work count as repair.
"""
from __future__ import annotations

import copy
import math

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.ship_world import (
    ensure_canonical_ship, find_ship_space, find_world_entity,
)
from world.ship_crew_access import traverse_canonical_exit
from world.ship_cargo_manifest import DRUMS
from world.ship_unclassified_spaces import SECTORS
from world.models import CanonicalShipEvent, WorkReceipt
from world.continuous_ship_physics import (
    _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water,
    commission_g19_repairs, commission_g19_eva,
    commission_g19_unclassified_spaces, commission_g19_crew_physiology,
    commission_g19_instrumentation,
    survey_cargo_lot, survey_g19_cargo_sector,
    survey_g19_water_material, witness_g19_cargo_sector_leak,
    configure_scenario_casualty, configure_water_casualty,
    crew_physical_action, tick_continuous_physics,
)


class InstalledCrossDrumCasualtyRepair(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
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
        self.time = 1000.0
        self.serial = 90000

    def rid(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def at(self, room):
        loc = find_ship_space(room)
        self.assertIsNotNone(loc, room)
        self.assertTrue(self.worker.move_to(loc, quiet=True))

    def op(self, command, target, value, *, request_id=None):
        return crew_physical_action(
            self.worker, request_id or self.rid(), command, target, value)

    def traverse(self, sector, direction):
        link = find_world_entity(
            "access:ACC-" + sector + ":" + direction)
        self.assertIsNotNone(link)
        return traverse_canonical_exit(
            self.worker, link, link.destination, request_id=self.rid())

    def advance(self, seconds):
        self.assertEqual(seconds % 60, 0)
        for _ in range(int(seconds // 60)):
            self.time += 60
            tick = tick_continuous_physics(now_game_time=self.time)
            self.assertTrue(tick["advanced"])
            self.assertEqual(tick["last_game_time"], self.time)
        return tick

    def survey(self, drum):
        self.assertIn(drum, DRUMS)
        survey_cargo_lot(
            operator_approved=True, operation="verify", drum=drum)
        for sector in SECTORS:
            if not sector.startswith(drum + "-"):
                continue
            survey_g19_cargo_sector(
                operator_approved=True, sector=sector,
                free_volume_m3=50, pressure_pa=101000,
                temperature_k=293.15,
                oxygen_mass_fraction=.232,
                co2_mass_fraction=.0004,
                smoke_mass_fraction=0,
                cargo_class="empty", lot_ids=[])

    def provision_worker(self):
        self.at("TOOL-CRIB")
        self.assertEqual(
            self.op("repair", "TOOL-CRIB", "pickup_toolkit")["status"],
            "succeeded")
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="SPARES-CENTRAL", verified_kg=2)
        self.at("SPARES-CENTRAL")
        self.assertEqual(
            self.op("repair", "INV-SPARES", "pickup:2")["status"],
            "succeeded")
        self.assertEqual(
            _clock().details["repairs"]["carried_kg"][self.worker.dbref], 2)
        self.at("ENG-LOCKER")
        self.assertEqual(
            self.op("eva", "INV-DC-CONSUMABLES", "stage:0.75")["status"],
            "succeeded")
        self.at("EVA-FWD")
        self.assertEqual(
            self.op("eva", "EVA-FWD", "checkout")["status"],
            "succeeded")

    def campaign(self, drum):
        self.assertIn(drum, DRUMS)
        sector = drum + "-SEC-02"
        hatch = "ACC-" + sector
        self.survey(drum)
        self.provision_worker()

        self.at(drum + "-GALLERY")
        self.assertEqual(
            self.op("cargo_sector", sector, "secure")["status"],
            "succeeded")
        self.assertEqual(
            self.op("hatch", hatch, "open")["status"], "succeeded")
        self.assertEqual(
            self.traverse(sector, "forward")["status"], "succeeded")
        self.assertEqual(self.worker.location.db.ox_space_id, sector)
        self.assertEqual(
            self.op("hatch", hatch, "closed")["status"], "succeeded")

        survey_before = copy.deepcopy(
            _clock().details["unclassified_spaces"]["sectors"][sector])
        starting_gas = survey_before["gas"]["mass_kg"]
        starting_vented = _clock().details["lost_to_space_kg"]
        spare_stock_before = state("inventory", "INV-SPARES").quantity
        witness_g19_cargo_sector_leak(
            operator_approved=True, sector=sector, leak_kg_s=.003)
        # Damaged sector cannot be made safe by simply labelling it surveyed.
        patch_id = self.rid()
        start = self.op(
            "cargo_sector", sector, "seal", request_id=patch_id)
        self.assertEqual(start["status"], "succeeded")
        self.assertEqual(
            _clock().details["unclassified_spaces"]["sectors"][sector][
                "seal"]["remaining_s"], 180.0)

        # Simultaneous on-board casualties with the repair actually underway.
        configure_scenario_casualty(
            "PZ-HAB-01", operator=True, fire_fuel_kg=5,
            fire_burn_kg_s=.01, heat_kw=12)
        configure_water_casualty(operator=True, contaminated_kg=7)
        set_component_condition(
            "edge", "EDGE-GEN-M", "severed", operator=True)

        previous_loss = 0.0
        for elapsed in (60, 120, 180):
            tick = self.advance(60)
            d = _clock().details
            row = d["unclassified_spaces"]["sectors"][sector]
            self.assertFalse(tick["power_assured"])
            self.assertEqual(
                state("edge", "EDGE-GEN-M").condition, "severed")
            self.assertTrue(d["water"]["potable_quarantined"])
            self.assertAlmostEqual(
                d["water"]["suspected_contamination_kg"], 7)
            self.assertGreater(d["burned_fuel_kg"], 0)
            self.assertGreaterEqual(row["lost_kg"], previous_loss)
            self.assertEqual(d["rotors"][drum]["target_rpm"], 0)
            self.assertEqual(d["instrumentation"]["last_s"], self.time)
            self.assertAlmostEqual(
                row["gas"]["mass_kg"] + row["lost_kg"]
                - row["gallery_net_kg"],
                row["initial_kg"], delta=1e-5)
            self.assertAlmostEqual(
                state("inventory", "INV-GEN-CART").quantity * 1000
                + d["generator_spent_cartridge_kg"],
                d["generator_cartridge_baseline_kg"], delta=1e-4)
            if elapsed < 180:
                self.assertIsNotNone(row["seal"])
                self.assertEqual(
                    row["seal"]["remaining_s"], 180 - elapsed)
            previous_loss = row["lost_kg"]

        d = _clock().details
        row = d["unclassified_spaces"]["sectors"][sector]
        self.assertIsNone(row["seal"])
        self.assertEqual(row["seals_completed"], 1)
        self.assertEqual(row["leak_kg_s"], 0.0)
        self.assertAlmostEqual(row["lost_kg"], .54, places=5)
        self.assertAlmostEqual(starting_gas - row["gas"]["mass_kg"],
                               row["lost_kg"], delta=1e-5)
        self.assertAlmostEqual(
            d["lost_to_space_kg"] - starting_vented,
            row["lost_kg"], delta=1e-5)
        self.assertEqual(d["repairs"]["installed_kg"], 2)
        self.assertEqual(d["repairs"]["carried_kg"][self.worker.dbref], 0)
        self.assertEqual(state("inventory", "INV-SPARES").quantity,
                         spare_stock_before)

        # Time cannot undo the actual installed patch or restore vented gas.
        restored_gas = row["gas"]["mass_kg"]
        vented = row["lost_kg"]
        self.advance(120)
        row = _clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertEqual(row["seals_completed"], 1)
        self.assertEqual(row["lost_kg"], vented)
        self.assertEqual(row["gas"]["mass_kg"], restored_gas)
        self.assertTrue(_clock().details["water"]["potable_quarantined"])
        self.assertEqual(
            state("edge", "EDGE-GEN-M").condition, "severed")

        # The original authenticated receipt is globally idempotent, even
        # after the physical operation has already completed.
        snapshot = copy.deepcopy(_clock().details)
        events = CanonicalShipEvent.objects.count()
        self.assertEqual(
            self.op("cargo_sector", sector, "seal",
                    request_id=patch_id), start)
        self.assertEqual(WorkReceipt.objects.filter(pk=patch_id).count(), 1)
        self.assertEqual(CanonicalShipEvent.objects.count(), events)
        self.assertEqual(_clock().details, snapshot)

        self.assertEqual(
            self.op("hatch", hatch, "open")["status"], "succeeded")
        self.assertEqual(
            self.traverse(sector, "reverse")["status"], "succeeded")
        self.assertEqual(self.worker.location.db.ox_space_id,
                         drum + "-GALLERY")
        self.assertEqual(
            self.op("hatch", hatch, "closed")["status"], "succeeded")
        self.assertEqual(
            self.op("cargo_sector", sector, "release")["status"],
            "succeeded")
        self.assertIsNone(_clock().details["unclassified_spaces"][
            "sectors"][sector]["permit"])
        print(
            "G19_REAL_DRUM_PATCH " + drum
            + " installed_kg=2 lost_kg=" + str(vented)
            + " fire_fuel_burned_kg=" + str(d["burned_fuel_kg"]))

    def test_dr01_minor_shell_patch_with_shipwide_casualties(self):
        self.campaign("DR-01")

    def test_dr02_minor_shell_patch_with_shipwide_casualties(self):
        self.campaign("DR-02")

    def test_dr03_minor_shell_patch_with_shipwide_casualties(self):
        self.campaign("DR-03")

    def test_dr04_minor_shell_patch_with_shipwide_casualties(self):
        self.campaign("DR-04")

    def test_dr05_minor_shell_patch_with_shipwide_casualties(self):
        self.campaign("DR-05")

    def test_dr06_minor_shell_patch_with_shipwide_casualties(self):
        self.campaign("DR-06")
