"""G19 external commercial cargo port conservation and interlock tests."""
import unittest

from world.ship_cargo_manifest import (
    CargoError, declare_cargo_lot, initial_cargo, onboard_mass_kg,
    validate_cargo, restow_cargo_lot, verify_drum, unsecured_drum_loads,
)
from world.ship_port_operations import (
    commission_port_contact, register_external_consignment, start_port_job,
    step_port_jobs, PORT_AUX_MW, contacts_active,
)
from world.ship_motion_machinery import initial_rotors


class CommercialPortTest(unittest.TestCase):
    def setUp(self):
        # Smaller realistic example; ship's full 900,000 t reference uses
        # exactly the same accounting and bounded time steps.
        self.capacity = 900_000_000.0
        self.cargo = initial_cargo(self.capacity)
        self.rotors = initial_rotors()

    def dock(self, cargo=None, portal="DR-01-P1"):
        return commission_port_contact(
            self.cargo if cargo is None else cargo,
            portal_id=portal, berth_id="BERTH-7", docked=True)

    def outbound(self):
        cargo = declare_cargo_lot(
            self.cargo, lot_id="ORE-1", mass_kg=200_000,
            drum="DR-01", azimuth_deg=0, radius_m=10)
        return self.dock(cargo)

    def test_unload_reduces_mass_gradually_and_preserves_custody(self):
        cargo = self.outbound()
        cargo = start_port_job(
            cargo, self.rotors, lot_id="ORE-1",
            portal_id="DR-01-P1", direction="unload",
            capacity_kg=self.capacity, equipment_ready=True,
            inner_gate_sealed=True)
        self.assertTrue(validate_cargo(cargo, self.capacity))
        paused, done = step_port_jobs(
            cargo, 10, available_portals=set(), capacity_kg=self.capacity)
        self.assertEqual(paused["port_jobs"], cargo["port_jobs"])
        self.assertEqual(done, ())
        warmed, done = step_port_jobs(
            cargo, 60, available_portals={"DR-01-P1"},
            capacity_kg=self.capacity)
        self.assertEqual(onboard_mass_kg(warmed), self.capacity)
        self.assertEqual(done, ())
        halfway, done = step_port_jobs(
            warmed, 50, available_portals={"DR-01-P1"},
            capacity_kg=self.capacity)
        self.assertEqual(onboard_mass_kg(halfway), self.capacity - 75_000)
        self.assertEqual(halfway["delivered_offship_kg"], 75_000)
        self.assertTrue(validate_cargo(halfway, self.capacity - 75_000))
        with self.assertRaises(CargoError):
            commission_port_contact(
                halfway, portal_id="DR-01-P1",
                berth_id="BERTH-7", docked=False)
        while halfway["port_jobs"]:
            halfway, _ = step_port_jobs(
                halfway, 60, available_portals={"DR-01-P1"},
                capacity_kg=self.capacity)
        self.assertEqual(halfway["lots"]["ORE-1"]["location"], "OFFSHIP")
        self.assertEqual(onboard_mass_kg(halfway), self.capacity - 200_000)
        self.assertTrue(validate_cargo(halfway, self.capacity - 200_000))
        free = commission_port_contact(
            halfway, portal_id="DR-01-P1",
            berth_id="BERTH-7", docked=False)
        self.assertFalse(contacts_active(free))

    def test_inbound_requires_registered_external_stock_and_capacity(self):
        cargo = self.dock()
        with self.assertRaises(CargoError):
            start_port_job(
                cargo, self.rotors, lot_id="NEW-1",
                portal_id="DR-01-P1", direction="load",
                capacity_kg=self.capacity, equipment_ready=True,
                inner_gate_sealed=True)
        cargo = register_external_consignment(
            cargo, lot_id="NEW-1", mass_kg=2000, portal_id="DR-01-P1",
            source_reference="BERTH-7")
        self.assertTrue(validate_cargo(cargo, self.capacity))
        with self.assertRaises(CargoError):
            start_port_job(
                cargo, self.rotors, lot_id="NEW-1",
                portal_id="DR-01-P1", direction="load",
                capacity_kg=self.capacity, equipment_ready=True,
                inner_gate_sealed=True)
        # Free actual mass before loading; no ship capacity from nowhere.
        cargo = declare_cargo_lot(
            cargo, lot_id="OLD-1", mass_kg=4000, drum="DR-01",
            azimuth_deg=0, radius_m=1)
        cargo = start_port_job(
            cargo, self.rotors, lot_id="OLD-1",
            portal_id="DR-01-P1", direction="unload",
            capacity_kg=self.capacity, equipment_ready=True,
            inner_gate_sealed=True)
        while cargo["port_jobs"]:
            cargo, _ = step_port_jobs(
                cargo, 60, available_portals={"DR-01-P1"},
                capacity_kg=self.capacity)
        self.assertTrue(validate_cargo(cargo, self.capacity - 4000))
        cargo = start_port_job(
            cargo, self.rotors, lot_id="NEW-1",
            portal_id="DR-01-P1", direction="load",
            capacity_kg=self.capacity, equipment_ready=True,
            inner_gate_sealed=True)
        cargo, _ = step_port_jobs(cargo, 60, available_portals={"DR-01-P1"},
                                  capacity_kg=self.capacity)
        cargo, _ = step_port_jobs(cargo, 10, available_portals={"DR-01-P1"},
                                  capacity_kg=self.capacity)
        self.assertEqual(onboard_mass_kg(cargo), self.capacity - 2000)
        self.assertFalse(cargo["lots"]["NEW-1"]["restrained"])
        self.assertTrue(unsecured_drum_loads(cargo, "DR-01"))
        with self.assertRaises(CargoError):
            verify_drum(cargo, "DR-01")
        cargo = restow_cargo_lot(
            cargo, lot_id="NEW-1", azimuth_deg=180, radius_m=1.0)
        self.assertTrue(validate_cargo(cargo, self.capacity - 2000))

    def test_no_loading_without_hardlock_or_gallery_seal(self):
        cargo = self.outbound()
        rotors = initial_rotors()
        rotors["DR-01"]["hardlock"] = False
        with self.assertRaises(CargoError):
            start_port_job(cargo, rotors, lot_id="ORE-1",
                           portal_id="DR-01-P1", direction="unload",
                           capacity_kg=self.capacity,
                           equipment_ready=True, inner_gate_sealed=True)
        with self.assertRaises(CargoError):
            start_port_job(cargo, self.rotors, lot_id="ORE-1",
                           portal_id="DR-01-P1", direction="unload",
                           capacity_kg=self.capacity,
                           equipment_ready=True, inner_gate_sealed=False)

    def test_two_portals_do_not_double_book_one_handler(self):
        cargo = self.outbound()
        cargo = commission_port_contact(
            cargo, portal_id="DR-01-P2", berth_id="BERTH-7", docked=True)
        cargo = declare_cargo_lot(
            cargo, lot_id="ORE-2", mass_kg=30000, drum="DR-01",
            azimuth_deg=180, radius_m=10)
        cargo = start_port_job(
            cargo, self.rotors, lot_id="ORE-1", portal_id="DR-01-P1",
            direction="unload", capacity_kg=self.capacity,
            equipment_ready=True, inner_gate_sealed=True)
        with self.assertRaises(CargoError):
            start_port_job(
                cargo, self.rotors, lot_id="ORE-2", portal_id="DR-01-P2",
                direction="unload", capacity_kg=self.capacity,
                equipment_ready=True, inner_gate_sealed=True)

    def test_consignment_cannot_claim_another_berth(self):
        cargo = self.dock()
        with self.assertRaises(CargoError):
            register_external_consignment(
                cargo, lot_id="FALSE-1", mass_kg=2500,
                portal_id="DR-01-P1", source_reference="BERTH-99")

    def test_bad_external_contact_and_duplicate_consignment_fail(self):
        with self.assertRaises(CargoError):
            self.dock(portal="DR-09-P1")
        cargo = self.dock()
        cargo = register_external_consignment(
            cargo, lot_id="NEW-1", mass_kg=2000, portal_id="DR-01-P1",
            source_reference="BERTH-7")
        with self.assertRaises(CargoError):
            register_external_consignment(
                cargo, lot_id="NEW-1", mass_kg=2000, portal_id="DR-01-P1",
                source_reference="BERTH-7")
        self.assertTrue(validate_cargo(cargo, self.capacity))
