"""G19 fitted PROP-SVC: original rated hatch, attended suit, finite gas/repair."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water, commission_g19_repairs,
    commission_g19_eva, commission_g19_crew_physiology,
    commission_g19_propulsion_bay, survey_g19_propulsion_bay,
    crew_physical_action, local_physics_readout, tick_continuous_physics,
)
from world.models import WorkReceipt


class OriginalPropulsionServiceBay(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.crew = build_ship()
        self.engineer, self.helm = self.crew["watch"], self.crew["officer"]
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.engineer.dbref])
        self.assertTrue(commission_g19_propulsion_bay(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_propulsion_bay(
            operator_approved=True)["commissioned"])
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.now, self.serial = 1000, 100

    def rid(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def at(self, room):
        self.assertTrue(self.engineer.move_to(
            find_ship_space(room), quiet=True), room)

    def action(self, kind, target, value, actor=None, request=None):
        return crew_physical_action(
            actor or self.engineer, request or self.rid(),
            kind, target, value)

    def transit(self, direction="forward"):
        door = find_world_entity(
            "access:ACC-PROP-SVC:" + direction)
        self.assertIsNotNone(door)
        return traverse_canonical_exit(
            self.engineer, door, door.destination,
            request_id=self.rid())

    def tick(self, seconds):
        while seconds:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def survey(self, pressure_pa=101325):
        return survey_g19_propulsion_bay(
            operator_approved=True, volume_m3=1000,
            pressure_pa=pressure_pa, temperature_k=293.15,
            oxygen_mass_fraction=.232,
            co2_mass_fraction=.0004, smoke_mass_fraction=0)

    def prepare(self, *, tools=False):
        self.at("PROP-CTRL")
        self.action("drive", "MAIN", "inhibit")
        self.action("drive", "RCS", "inhibit")
        if tools:
            self.at("TOOL-CRIB")
            self.action("repair", "TOOL-CRIB", "pickup_toolkit")
            survey = __import__(
                "world.continuous_ship_physics",
                fromlist=["survey_g19_water_material"])
            survey.survey_g19_water_material(
                operator_approved=True, source="INV-SPARES",
                room_id="SPARES-CENTRAL", verified_kg=3)
            self.at("SPARES-CENTRAL")
            self.action("repair", "INV-SPARES", "pickup:3")
        self.survey()
        # Real finite suit oxygen is charged once at the original locker,
        # not granted by a boolean field or on entry to the worksite.
        self.at("ENG-LOCKER")
        self.action("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.at("EVA-AFT")
        self.action("eva", "EVA-AFT", "checkout")
        self.at("TRUNK-B-AFT")

    def enter(self):
        secured = self.action("propulsion_bay", "PROP-SVC", "secure")
        self.assertEqual(secured, self.action(
            "propulsion_bay", "PROP-SVC", "secure",
            request=secured["request_id"]))
        self.action("hatch", "ACC-PROP-SVC", "open")
        self.assertEqual(self.transit()["status"], "succeeded")
        self.assertEqual(
            self.engineer.location.db.ox_space_id, "PROP-SVC")
        self.action("hatch", "ACC-PROP-SVC", "closed")

    def leave(self):
        self.action("hatch", "ACC-PROP-SVC", "open")
        self.assertEqual(self.transit("reverse")["status"], "succeeded")
        self.action("hatch", "ACC-PROP-SVC", "closed")
        self.action("propulsion_bay", "PROP-SVC", "release")

    def test_real_suited_controller_repair_then_measured_main_drive_restart(self):
        self.prepare(tools=True)
        set_component_condition(
            "equipment", "LCS-PROP", "failed", operator=True)
        # The rated hatch is not an ordinary door and no operator can
        # guess a safe atmosphere from "serviceable" room metadata.
        with self.assertRaises(PhysicsError):
            self.action("hatch", "ACC-PROP-SVC", "open")
        with self.assertRaises(CrewTransitError):
            self.transit()
        self.enter()
        at_work = local_physics_readout(
            self.engineer, "propulsion_bay")
        self.assertFalse(at_work["entry_ready"] is False)
        self.assertEqual(at_work["real_controller_condition"], "failed")
        self.action("propulsion_bay", "PROP-SVC", "inspect")
        with self.assertRaises(PhysicsError):
            self.action("drive", "MAIN", "release")
        job = self.action("repair", "equipment:LCS-PROP", "start")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(state("equipment", "LCS-PROP").condition, "failed")
        self.tick(600)
        self.assertEqual(state("equipment", "LCS-PROP").condition,
                         "serviceable")
        self.assertEqual(_clock().details["repairs"]["completed"], 1)
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 3)
        self.assertEqual(_clock().details["propulsion_bay"]["entries"], 1)
        self.assertEqual(_clock().details["propulsion_bay"]["inspections"], 1)
        with self.assertRaises(PermissionError):
            self.action("propulsion_bay", "PROP-SVC", "release")
        self.leave()
        self.assertIsNone(_clock().details["propulsion_bay"]["permit"])
        self.at("PROP-CTRL")
        self.action("drive", "MAIN", "release")
        self.helm.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        self.action("helm", "HELM", "x+", actor=self.helm)
        prior = _clock().details["motion"]["expended_propellant_kg"]
        self.tick(10)
        motion = _clock().details["motion"]
        self.assertTrue(motion["drive_firing"])
        self.assertGreater(motion["expended_propellant_kg"], prior)
        self.assertGreater(motion["velocity_m_s"][0], 0)
        self.assertEqual(WorkReceipt.objects.filter(
            operation="propulsion_bay").count(), 3)

    def test_metered_bleed_never_vents_or_invents_trunk_atmosphere(self):
        self.at("PROP-CTRL")
        self.action("drive", "MAIN", "inhibit")
        self.action("drive", "RCS", "inhibit")
        self.survey(pressure_pa=98500)
        self.at("TRUNK-B-AFT")
        before = state("pressure", "PZ-TRUNK-B-AFT").quantity
        prior_gas = _clock().details["propulsion_bay"]["gas"]["mass_kg"]
        with self.assertRaises(PhysicsError):
            self.action("hatch", "ACC-PROP-SVC", "open")
        moved = self.action("propulsion_bay", "PROP-SVC", "bleed:5")
        self.assertEqual(moved, self.action(
            "propulsion_bay", "PROP-SVC", "bleed:5",
            request=moved["request_id"]))
        later = _clock().details["propulsion_bay"]
        self.assertAlmostEqual(state("pressure", "PZ-TRUNK-B-AFT").quantity,
                               before - 5)
        self.assertAlmostEqual(later["gas"]["mass_kg"], prior_gas + 5)
        self.assertAlmostEqual(
            later["initial_survey_kg"] + later["trunk_to_bay_kg"],
            later["gas"]["mass_kg"])
        self.tick(10)
        self.assertAlmostEqual(
            _clock().details["summary"]["gas_kg"],
            sum(state("pressure", row.source_id).quantity
                for row in __import__(
                    "world.models", fromlist=["CanonicalShipState"])
                    .CanonicalShipState.objects.filter(category="pressure"))
            + later["gas"]["mass_kg"],places=3)

    def test_no_suit_no_entry_and_live_feeder_loss_pauses_controller_work(self):
        self.at("PROP-CTRL")
        self.action("drive", "MAIN", "inhibit")
        self.action("drive", "RCS", "inhibit")
        self.survey()
        self.at("TRUNK-B-AFT")
        with self.assertRaises(PhysicsError):
            self.action("propulsion_bay", "PROP-SVC", "secure")
        self.at("ENG-LOCKER")
        self.action("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.at("EVA-AFT")
        self.action("eva", "EVA-AFT", "checkout")
        self.at("TRUNK-B-AFT")
        self.enter()
        with self.assertRaises(PhysicsError):
            self.action("switch", "ISO-LP-PROP-SVC", "closed")
        self.at("PROP-CTRL")
        with self.assertRaises(PhysicsError):
            self.action("drive", "MAIN", "release")


if __name__ == "__main__":
    import unittest
    unittest.main()
