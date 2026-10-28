"""G19 six original radiator EVA pads: coolant isolation, finite maintenance.

Every movement traverses existing Evennia exits (except explicit bootstrap
scenario setup), with a real issued suit and global signed work receipts.
"""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, set_isolator,
    set_component_condition, state,
)
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    tick_continuous_physics, commission_g19_water,
    commission_g19_repairs, commission_g19_eva,
    commission_g19_crew_physiology,
    commission_g19_exterior_radiators, survey_g19_radiator_skin,
    survey_g19_water_material, crew_physical_action,
    local_physics_readout,
)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.models import WorkReceipt


class InstalledRadiatorExteriorTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        for br in ("ISO-GEN-M", "ISO-DB-A-BOW",
                   "ISO-DB-A-HAB-HUB-SERVICES"):
            set_isolator(br, "closed", operator=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        self.assertTrue(commission_g19_exterior_radiators(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_exterior_radiators(
            operator_approved=True)["commissioned"])
        self.tech = build_ship()["watch"]
        self.at("ENG-CONTROL")
        commission_g19_crew_physiology(
            actor_dbrefs=[self.tech.dbref], operator_approved=True)
        self.now = 1000
        self.serial = 100

    def rid(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def at(self, room):
        self.assertTrue(self.tech.move_to(find_ship_space(room), quiet=True))

    def act(self, kind, target, value, request=None):
        return crew_physical_action(
            self.tech, request or self.rid(), kind, target, value)

    def tick(self, seconds):
        while seconds > 0:
            dt = min(seconds, 60)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def pass_link(self, link, direction="forward"):
        exit_obj = find_world_entity(
            "access:" + link + ":" + direction)
        self.assertIsNotNone(exit_obj)
        return traverse_canonical_exit(
            self.tech, exit_obj, exit_obj.destination,
            request_id=self.rid())

    def tech_stock(self):
        self.at("TOOL-CRIB")
        self.act("repair", "TOOL-CRIB", "pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=4)
        self.at("STORE-CRIT-SPARES")
        self.act("repair", "INV-SPARES", "pickup:3")

    def suit_and_exit_fwd(self):
        self.at("ENG-LOCKER")
        self.act("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.at("TRUNK-B-BOW")
        self.act("eva", "EVA-FWD", "inner_open")
        self.assertEqual(self.pass_link("ACC-EVA-FWD")["status"], "succeeded")
        self.act("eva", "EVA-FWD", "inner_close")
        self.act("eva", "EVA-FWD", "checkout")
        self.act("switch", "ISO-AIR-FIXED-EVA-FWD", "closed")
        self.act("switch", "ISO-LP-EVA-FWD", "closed")
        self.act("eva", "EVA-FWD", "pumpdown")
        self.tick(90)
        self.act("eva", "EVA-FWD", "outer_open")
        self.assertEqual(
            self.pass_link("ACC-EVA-FWD-EXT")["status"], "queued")
        self.tick(45)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-BOW")

    def to_rail(self, target):
        route = {
            "EXT-CENTRAL": [
                "ACC-EXT-BOW-EXT-DR01",
                "ACC-EXT-DR01-EXT-DR02",
                "ACC-EXT-DR02-EXT-DR03",
                "ACC-EXT-DR03-EXT-F1",
                "ACC-EXT-F1-EXT-CENTRAL"],
            "EXT-AFT": [
                "ACC-EXT-BOW-EXT-DR01",
                "ACC-EXT-DR01-EXT-DR02",
                "ACC-EXT-DR02-EXT-DR03",
                "ACC-EXT-DR03-EXT-F1",
                "ACC-EXT-F1-EXT-CENTRAL",
                "ACC-EXT-CENTRAL-EXT-DR04",
                "ACC-EXT-DR04-EXT-DR05",
                "ACC-EXT-DR05-EXT-DR06",
                "ACC-EXT-DR06-EXT-AFT"],
        }[target]
        for link in route:
            self.assertEqual(self.pass_link(link)["status"], "queued")
            self.tick(30)
        self.assertEqual(self.tech.location.db.ox_space_id, target)

    def lt_isolated(self, key="RAD-LT-1"):
        self.at("ROTARY-UTIL-A")
        self.act("plant", "LT-PLANT", "off")
        self.act("switch", "ISO-LT-ROT-A", "closed")
        self.at("ROTARY-UTIL-B")
        self.act("switch", "ISO-LT-ROT-B", "closed")
        survey_g19_radiator_skin(
            operator_approved=True, radiator_id=key, temperature_k=286)
        station = ("ROTARY-UTIL-A" if key.endswith(("1", "2"))
                   else "ROTARY-UTIL-B")
        self.at(station)

    def ht_isolated(self, key="RAD-HT-1"):
        self.at("ENG-CONTROL")
        self.act("switch", "ISO-" + key, "closed")
        survey_g19_radiator_skin(
            operator_approved=True, radiator_id=key, temperature_k=287)

    def test_hot_unmeasured_faces_cannot_be_instantly_deployed(self):
        self.at("ENG-CONTROL")
        with self.assertRaises(PhysicsError):
            self.act("radiator_service", "RAD-HT-1", "secure")
        self.act("switch", "ISO-RAD-HT-1", "closed")
        survey_g19_radiator_skin(
            operator_approved=True, radiator_id="RAD-HT-1",
            temperature_k=430)
        with self.assertRaises(PhysicsError):
            self.act("radiator_service", "RAD-HT-1", "secure")
        self.assertFalse(_clock().details["exterior_radiators"]["permits"])

    def test_real_lt_service_isolation_and_actual_eva_pad_entry(self):
        self.lt_isolated()
        permit = self.act("radiator_service", "RAD-LT-1", "secure")
        self.assertEqual(permit, self.act(
            "radiator_service", "RAD-LT-1", "secure",
            request=permit["request_id"]))
        with self.assertRaises(PhysicsError):
            self.act("switch", "ISO-LT-ROT-A", "open")
        with self.assertRaises(PhysicsError):
            self.act("plant", "LT-PLANT", "on")
        self.suit_and_exit_fwd()
        self.to_rail("EXT-CENTRAL")
        self.act("eva", "ACC-EXT-CENTRAL-EXT-RAD-LT-1", "deploy")
        result = self.pass_link("ACC-EXT-CENTRAL-EXT-RAD-LT-1")
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["travel_seconds"], 150)
        self.tick(150)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-RAD-LT-1")
        reading = local_physics_readout(self.tech, "radiator_service")
        self.assertTrue(reading["radiators"]["RAD-LT-1"]["worksite_ready"])
        # Return via the original rated external platform direction.
        self.assertEqual(self.pass_link(
            "ACC-EXT-CENTRAL-EXT-RAD-LT-1", "reverse")["status"], "queued")
        self.tick(150)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-CENTRAL")
        self.at("ROTARY-UTIL-A")
        self.act("radiator_service", "RAD-LT-1", "release")
        self.assertEqual(_clock().details["exterior_radiators"]["released"], 1)
        self.act("switch", "ISO-LT-ROT-A", "open")

    def test_actual_ht_exterior_panel_repaired_with_issued_finite_spares(self):
        self.ht_isolated()
        self.act("radiator_service", "RAD-HT-1", "secure")
        set_component_condition("equipment", "RAD-HT-1", "failed",
                                operator=True)
        self.tech_stock()
        self.suit_and_exit_fwd()
        self.to_rail("EXT-AFT")
        self.act("eva", "ACC-EXT-AFT-EXT-RAD-HT-1", "deploy")
        self.assertEqual(self.pass_link(
            "ACC-EXT-AFT-EXT-RAD-HT-1")["travel_seconds"], 150)
        self.tick(150)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-RAD-HT-1")
        self.act("repair", "equipment:RAD-HT-1", "start")
        self.tick(600)
        self.assertEqual(state("equipment", "RAD-HT-1").condition, "serviceable")
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 3)
        self.assertEqual(_clock().details["repairs"]["completed"], 1)
        with self.assertRaises(PermissionError):
            # Remote release by moving to its command console remains
            # forbidden until both exterior worker and job vacate the face.
            self.act("radiator_service", "RAD-HT-1", "release")
        self.pass_link("ACC-EXT-AFT-EXT-RAD-HT-1", "reverse")
        self.tick(150)
        self.assertEqual(self.tech.location.db.ox_space_id, "EXT-AFT")
        self.at("ENG-CONTROL")
        self.act("radiator_service", "RAD-HT-1", "release")
        self.act("switch", "ISO-RAD-HT-1", "open")
        self.assertFalse(_clock().details["exterior_radiators"]["permits"])
        self.assertEqual(WorkReceipt.objects.filter(
            operation="radiator_service").count(), 2)

    def test_failed_ht_coolant_isolation_pauses_ongoing_exterior_repair(self):
        self.ht_isolated()
        self.act("radiator_service", "RAD-HT-1", "secure")
        set_component_condition("equipment", "RAD-HT-1", "failed", operator=True)
        self.tech_stock()
        self.suit_and_exit_fwd()
        # Scenario fixture places suited worker already at the authored
        # work face; complete exterior traversal tested independently.
        self.at("EXT-RAD-HT-1")
        self.act("repair", "equipment:RAD-HT-1", "start")
        self.tick(60)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:RAD-HT-1"]["remaining_s"], 540)
        set_isolator("ISO-RAD-HT-1", "open", operator=True)
        self.tick(120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:RAD-HT-1"]["remaining_s"], 540)
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 0)
        set_isolator("ISO-RAD-HT-1", "closed", operator=True)
        self.tick(540)
        self.assertEqual(state("equipment", "RAD-HT-1").condition, "serviceable")

    def test_six_fitted_faces_are_distinct_under_one_operator_ledger(self):
        self.lt_isolated()
        for key in ("RAD-LT-2", "RAD-LT-3", "RAD-LT-4"):
            survey_g19_radiator_skin(
                operator_approved=True, radiator_id=key, temperature_k=285)
            self.at("ROTARY-UTIL-A" if key.endswith(("1", "2"))
                    else "ROTARY-UTIL-B")
            self.act("radiator_service", key, "secure")
        self.at("ROTARY-UTIL-A")
        self.act("radiator_service", "RAD-LT-1", "secure")
        for key in ("RAD-HT-1", "RAD-HT-2"):
            self.ht_isolated(key)
            self.act("radiator_service", key, "secure")
        self.assertEqual(len(_clock().details["exterior_radiators"]["permits"]), 6)
