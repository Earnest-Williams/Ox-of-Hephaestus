"""Original EXT-PROP-AFT inspection in an installed Evennia ship."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, set_isolator, set_component_condition,
)
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    commission_g19_eva, commission_g19_crew_physiology,
    commission_g19_propulsion_exterior, survey_g19_propulsion_exhaust,
    crew_physical_action, tick_continuous_physics, local_physics_readout,
)
from world.ship_crew_access import traverse_canonical_exit
from world.models import WorkReceipt

RAIL_AFT = (
    "ACC-EXT-BOW-EXT-DR01", "ACC-EXT-DR01-EXT-DR02",
    "ACC-EXT-DR02-EXT-DR03", "ACC-EXT-DR03-EXT-F1",
    "ACC-EXT-F1-EXT-CENTRAL", "ACC-EXT-CENTRAL-EXT-DR04",
    "ACC-EXT-DR04-EXT-DR05", "ACC-EXT-DR05-EXT-DR06",
    "ACC-EXT-DR06-EXT-AFT",
)
FACE_LINK = "ACC-EXT-AFT-EXT-PROP-AFT"


class InstalledAftNozzleInspection(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        for breaker in (
                "ISO-GEN-M", "ISO-DB-A-BOW",
                "ISO-DB-A-HAB-HUB-SERVICES"):
            set_isolator(breaker, "closed", operator=True)
        commission_g19_eva(operator_approved=True)
        self.assertTrue(commission_g19_propulsion_exterior(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_propulsion_exterior(
            operator_approved=True)["commissioned"])
        self.crew = build_ship()
        self.worker = self.crew["watch"]
        self.at("PROP-CTRL")
        commission_g19_crew_physiology(
            actor_dbrefs=[self.worker.dbref], operator_approved=True)
        self.now, self.serial = 1000, 100

    def rid(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def at(self, space):
        self.assertTrue(self.worker.move_to(
            find_ship_space(space), quiet=True))

    def action(self, kind, target, value, request=None):
        return crew_physical_action(
            self.worker, request or self.rid(), kind, target, value)

    def tick(self, seconds):
        while seconds:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def transit(self, link, direction="forward"):
        exit_obj = find_world_entity(
            "access:" + link + ":" + direction)
        self.assertIsNotNone(exit_obj)
        return traverse_canonical_exit(
            self.worker, exit_obj, exit_obj.destination,
            request_id=self.rid())

    def safed(self):
        self.at("PROP-CTRL")
        self.action("drive", "MAIN", "inhibit")
        self.action("drive", "RCS", "inhibit")
        survey_g19_propulsion_exhaust(
            operator_approved=True,
            temperature_k=287, plume_clear=True)

    def permit(self):
        self.safed()
        result = self.action(
            "propulsion_service", "EXT-PROP-AFT", "secure")
        self.assertEqual(result, self.action(
            "propulsion_service", "EXT-PROP-AFT", "secure",
            request=result["request_id"]))
        return result

    def to_aft_rail(self):
        self.at("ENG-LOCKER")
        self.action("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.at("TRUNK-B-BOW")
        self.action("eva", "EVA-FWD", "inner_open")
        self.assertEqual(self.transit("ACC-EVA-FWD")["status"], "succeeded")
        self.action("eva", "EVA-FWD", "inner_close")
        self.action("eva", "EVA-FWD", "checkout")
        self.action("switch", "ISO-AIR-FIXED-EVA-FWD", "closed")
        self.action("switch", "ISO-LP-EVA-FWD", "closed")
        self.action("eva", "EVA-FWD", "pumpdown")
        self.tick(90)
        self.action("eva", "EVA-FWD", "outer_open")
        self.assertEqual(self.transit("ACC-EVA-FWD-EXT")["status"], "queued")
        self.tick(45)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-BOW")
        for link in RAIL_AFT:
            self.assertEqual(self.transit(link)["status"], "queued")
            self.tick(30)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-AFT")

    def approach(self):
        self.action("eva", FACE_LINK, "deploy")
        queued = self.transit(FACE_LINK)
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(queued["travel_seconds"], 120)

    def test_hot_unmeasured_or_uncleared_nozzle_is_denied(self):
        with self.assertRaises(PhysicsError):
            self.action("propulsion_service", "EXT-PROP-AFT", "secure")
        survey_g19_propulsion_exhaust(
            operator_approved=True, temperature_k=400,
            plume_clear=True)
        self.action("drive", "MAIN", "inhibit")
        self.action("drive", "RCS", "inhibit")
        with self.assertRaises(PhysicsError):
            self.action("propulsion_service", "EXT-PROP-AFT", "secure")
        survey_g19_propulsion_exhaust(
            operator_approved=True, temperature_k=287,
            plume_clear=False)
        with self.assertRaises(PhysicsError):
            self.action("propulsion_service", "EXT-PROP-AFT", "secure")
        survey_g19_propulsion_exhaust(
            operator_approved=True, temperature_k=287,
            plume_clear=True)
        self.action("propulsion_service", "EXT-PROP-AFT", "secure")
        with self.assertRaises(PhysicsError):
            survey_g19_propulsion_exhaust(
                operator_approved=True,
                temperature_k=275, plume_clear=True)

    def test_suited_board_inspect_retreat_and_release(self):
        self.permit()
        self.to_aft_rail()
        self.approach()
        self.tick(60)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-AFT")
        self.tick(60)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-PROP-AFT")
        self.assertTrue(local_physics_readout(
            self.worker, "propulsion_service")["ready"])
        inspected = self.action(
            "propulsion_service", "EXT-PROP-AFT", "inspect")
        self.assertEqual(inspected, self.action(
            "propulsion_service", "EXT-PROP-AFT", "inspect",
            request=inspected["request_id"]))
        self.assertEqual(_clock().details["propulsion_exterior"]["inspected"], 1)
        self.assertEqual(self.transit(FACE_LINK, "reverse")["status"], "queued")
        self.tick(120)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-AFT")
        # Fixture placement after proving the actual outward/return route.
        self.at("PROP-CTRL")
        self.action("propulsion_service", "EXT-PROP-AFT", "release")
        self.assertIsNone(_clock().details["propulsion_exterior"]["permit"])
        self.assertEqual(WorkReceipt.objects.filter(
            operation="propulsion_service").count(), 3)

    def test_nozzle_permit_inhibits_drive_rcs_attitude_ftl_and_release(self):
        self.permit()
        for action, target, command in (
                ("helm", "HELM", "x+"),
                ("attitude", "HELM", "yaw+"),
                ("drive", "MAIN", "release"),
                ("drive", "RCS", "release"),
                ("ftl", "FTL", "engage")):
            with self.subTest(action=action), self.assertRaises(PhysicsError):
                self.action(action, target, command)
        motion = _clock().details["motion"]
        self.assertEqual(motion["command"], "coast")
        self.assertEqual(motion["drive_condition"], "inhibited")
        self.assertEqual(motion["rcs_condition"], "inhibited")
        self.crew["chief"].move_to(
            find_ship_space("EXT-PROP-AFT"), quiet=True)
        with self.assertRaises(PhysicsError):
            self.action("propulsion_service", "EXT-PROP-AFT", "release")
        self.crew["chief"].move_to(
            find_ship_space("CMD-PRIMARY"), quiet=True)
        self.action("propulsion_service", "EXT-PROP-AFT", "release")

    def test_real_controller_failure_pauses_suited_approach(self):
        self.permit()
        self.to_aft_rail()
        self.approach()
        self.tick(60)
        set_component_condition(
            "equipment", "LCS-PROP", "failed", operator=True)
        self.tick(60)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-AFT")
        self.assertEqual(_clock().details["eva"]["transits"][
            self.worker.dbref]["remaining_s"], 60)
        set_component_condition(
            "equipment", "LCS-PROP", "serviceable", operator=True)
        self.tick(60)
        self.assertEqual(self.worker.location.db.ox_space_id, "EXT-PROP-AFT")
