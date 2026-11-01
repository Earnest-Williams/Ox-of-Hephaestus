"""G19 authentic original generator service room passage and isolated restart."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, state, set_isolator)
from world.ship_world import ensure_canonical_ship, find_ship_space, find_world_entity
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water, commission_g19_repairs,
    commission_g19_eva, commission_g19_crew_physiology,
    commission_g19_generator_bays, survey_g19_generator_room,
    crew_physical_action, local_physics_readout, tick_continuous_physics)


class OriginalGeneratorRooms(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        crew = build_ship()
        self.worker = crew["watch"]
        self.assertTrue(self.worker.move_to(
            find_ship_space("ENG-CONTROL"), quiet=True))
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.worker.dbref])
        self.assertTrue(commission_g19_generator_bays(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_generator_bays(
            operator_approved=True)["commissioned"])
        self.sequence = 100

    def at(self, room):
        self.assertTrue(self.worker.move_to(
            find_ship_space(room), quiet=True), room)

    def request(self):
        self.sequence += 1
        return f"{self.sequence:032x}"

    def action(self, kind, target, value):
        return crew_physical_action(self.worker, self.request(), kind, target, value)

    def transit(self, link, direction):
        exit_obj = find_world_entity(f"access:{link}:{direction}")
        self.assertIsNotNone(exit_obj)
        return traverse_canonical_exit(
            self.worker, exit_obj, exit_obj.destination,
            request_id=self.request())

    def survey(self, room):
        from world.ship_generator_bay_service import ROOMS
        return survey_g19_generator_room(
            operator_approved=True, room_id=room,
            volume_m3=ROOMS[room][5] * .75,
            pressure_pa=101000, temperature_k=293.15,
            oxygen_mass_fraction=.232, co2_mass_fraction=.0004,
            smoke_mass_fraction=0, skin_temperature_k=299)

    def checkout_suit(self, trunk):
        self.at("ENG-LOCKER")
        self.action("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.at("TRUNK-B-AFT")
        self.action("eva", "EVA-AFT", "inner_open")
        self.transit("ACC-EVA-AFT", "forward")
        self.action("eva", "EVA-AFT", "inner_close")
        self.action("eva", "EVA-AFT", "checkout")
        self.action("eva", "EVA-AFT", "inner_open")
        self.transit("ACC-EVA-AFT", "reverse")
        self.action("eva", "EVA-AFT", "inner_close")
        self.at(trunk)

    def test_original_generator_B_suited_entry_lockout_and_restart(self):
        room = "GEN-B-ROOM"
        link = "ACC-GEN-B-ROOM"
        self.action("generator_bay", room, "trip")
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "open")
        self.survey(room)
        self.at("TRUNK-B-AFT")
        with self.assertRaises(PhysicsError):
            self.action("generator_bay", room, "secure")
        with self.assertRaises(CrewTransitError):
            self.transit(link, "forward")
        self.checkout_suit("TRUNK-B-AFT")
        receipt = self.action("generator_bay", room, "secure")
        self.assertEqual(receipt["status"], "succeeded")
        with self.assertRaises(PhysicsError):
            self.action("generator_bay", room, "secure")
        self.action("hatch", link, "open")
        self.assertEqual(self.transit(link, "forward")["status"], "succeeded")
        self.action("hatch", link, "closed")
        self.assertEqual(self.worker.location.db.ox_space_id, room)
        measured = local_physics_readout(self.worker, "generator_bay")["rooms"][room]
        self.assertTrue(measured["entry_ready"])
        self.assertEqual(measured["original_breaker"], "open")
        self.action("generator_bay", room, "inspect")
        self.at("ENG-CONTROL")
        with self.assertRaises(PhysicsError):
            self.action("generator_bay", room, "rearm")
        self.at(room)
        self.action("hatch", link, "open")
        self.assertEqual(self.transit(link, "reverse")["status"], "succeeded")
        self.action("hatch", link, "closed")
        self.action("generator_bay", room, "release")
        self.at("ENG-CONTROL")
        self.action("generator_bay", room, "rearm")
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "closed")
        self.assertTrue(state("equipment", "GEN-B").details["physics_commanded_on"])
        self.assertIsNone(_clock().details["generator_bays"]["rooms"][room]["permit"])
        self.assertEqual(_clock().details["generator_bays"]["rooms"][room]["entries"], 1)

    def test_other_two_rooms_have_separate_unmeasured_gas(self):
        self.action("generator_bay", "GEN-M-ROOM", "trip")
        self.survey("GEN-M-ROOM")
        recorded = _clock().details["generator_bays"]["rooms"]
        self.assertGreater(recorded["GEN-M-ROOM"]["initial_kg"], 0)
        self.assertIsNone(recorded["GEN-A-ROOM"]["gas"])
        self.assertIsNone(recorded["GEN-B-ROOM"]["gas"])
        self.at("TRUNK-A-AFT")
        with self.assertRaises(PhysicsError):
            self.action("hatch", "ACC-GEN-A-ROOM", "open")
        self.assertEqual(recorded["GEN-M-ROOM"]["received_kg"], 0.0)
