"""P4d: expandable freighter compartments, specialist work and world facts."""
from __future__ import annotations

from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase
from commands.departments import CmdCertify, CmdReplaceCartridge, CmdRestartScrubber, CmdRestow
from commands.ship import CmdInspect, CmdIsolate, CmdShipFault, CmdShipRole
from world.bootstrap import build_ship, find_fixture
from world.live_crew import inbox


class DepartmentWorldTests(EvenniaTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ship = build_ship()
        self.cargo = self.ship["cargo"]
        self.tech = self.ship["environment"]
        self.lin = self.ship["officer"]
        self.ari = self.ship["watch"]

    def command(self, command_type, actor, args: str) -> str:
        command = command_type()
        command.caller = actor
        command.args = args
        with patch.object(actor, "msg") as output:
            command.func()
            self.assertTrue(output.called)
            return str(output.call_args.args[0])

    def test_all_seven_rooms_navigable_and_idempotent(self):
        ship = self.ship
        self.assertEqual(len({
            ship[name].id for name in (
                "bridge", "passage", "engineering", "cargo_hold",
                "environmental", "mess", "workshop",
            )
        }), 7)
        for outward, back, origin, target in (
            ("exit-passage-cargo", "exit-cargo-passage", "passage", "cargo_hold"),
            ("exit-passage-environmental", "exit-environmental-passage",
             "passage", "environmental"),
            ("exit-passage-mess", "exit-mess-passage", "passage", "mess"),
            ("exit-engineering-workshop", "exit-workshop-engineering",
             "engineering", "workshop"),
        ):
            self.assertEqual(find_fixture(outward).location, ship[origin])
            self.assertEqual(find_fixture(outward).destination, ship[target])
            self.assertEqual(find_fixture(back).location, ship[target])
            self.assertEqual(find_fixture(back).destination, ship[origin])
        self.assertEqual(self.cargo.location, ship["cargo_hold"])
        self.assertEqual(self.tech.location, ship["environmental"])
        self.assertEqual(self.cargo.db.crew_role, "cargo_officer")
        self.assertEqual(self.tech.db.crew_role, "environment_tech")
        self.assertIn("Mara Voss", ship["duties"].readout())
        self.assertIn("Teo Hale", ship["roster"].readout())

        self.assertTrue(ship["cradle"].inject_fault()[0])
        self.assertTrue(ship["scrubber"].inject_fault()[0])
        self.tech.move_to(ship["passage"], quiet=True)
        again = build_ship()
        self.assertEqual(again["cradle"].id, ship["cradle"].id)
        self.assertEqual(again["scrubber"].id, ship["scrubber"].id)
        self.assertEqual(again["cargo"].id, self.cargo.id)
        self.assertEqual(again["environment"].id, self.tech.id)
        self.assertEqual(again["scrubber"].state, "saturated")
        self.assertEqual(again["cradle"].state, "unsecured")
        self.assertEqual(self.tech.location, ship["passage"])
        self.assertEqual(len(again["cradle"].db.event_history), 1)
        self.assertEqual(len(again["scrubber"].db.event_history), 1)

    def test_cargo_load_recovery_requires_specialist_and_fresh_inspections(self):
        cradle = self.ship["cradle"]
        self.assertEqual(cradle.state, "secured")
        self.assertEqual(cradle.db.loaded_containers, 8)
        self.assertTrue(cradle.inject_fault()[0])
        self.assertEqual(cradle.db.loose_restraints, 2)
        self.assertFalse(cradle.restow(self.cargo)[0])
        self.assertFalse(cradle.restow(self.lin)[0])
        self.assertIn("UNSECURED", self.command(CmdInspect, self.cargo, "cargo"))
        self.assertFalse(cradle.restow(self.ari)[0])
        self.cargo.move_to(self.ship["passage"], quiet=True)
        self.assertFalse(cradle.restow(self.cargo)[0])
        self.cargo.move_to(self.ship["cargo_hold"], quiet=True)
        self.assertIn("restowed", self.command(CmdRestow, self.cargo, "cargo"))
        self.assertEqual(cradle.state, "restowed")
        self.assertFalse(cradle.certify(self.cargo)[0])
        self.assertIn("RESTOWED", self.command(CmdInspect, self.cargo, "cargo"))
        self.assertIn("certified", self.command(CmdCertify, self.cargo, "cargo"))
        self.assertEqual(cradle.state, "secured")
        self.assertEqual(cradle.db.loose_restraints, 0)
        self.assertEqual([e["operation"] for e in cradle.db.event_history],
                         ["shift", "restow", "certify"])
        self.assertEqual(cradle.db.event_history[1]["actor_dbref"], self.cargo.dbref)
        self.assertTrue(all(isinstance(e["game_time"], float)
                            for e in cradle.db.event_history))

    def test_scrubber_inventory_and_role_scoped_procedure(self):
        scrubber = self.ship["scrubber"]
        self.assertEqual(scrubber.state, "nominal")
        self.assertEqual(scrubber.db.spare_cartridges, 2)
        self.assertTrue(scrubber.inject_fault()[0])
        self.assertFalse(scrubber.isolate(self.lin)[0])
        self.assertFalse(scrubber.isolate(self.tech)[0])
        self.assertIn("SATURATED", self.command(CmdInspect, self.tech, "scrubber"))
        self.assertIn("isolated", self.command(CmdIsolate, self.tech, "scrubber"))
        self.assertFalse(scrubber.restart(self.tech)[0])
        self.assertIn("replaced", self.command(CmdReplaceCartridge, self.tech, "scrubber"))
        self.assertEqual(scrubber.db.spare_cartridges, 1)
        self.assertFalse(scrubber.restart(self.tech)[0])
        self.assertIn("SERVICED", self.command(CmdInspect, self.tech, "scrubber"))
        self.assertIn("nominal", self.command(CmdRestartScrubber, self.tech, "scrubber"))
        self.assertEqual(scrubber.state, "nominal")

        # A second real failure consumes the final locally stocked cartridge.
        self.assertTrue(scrubber.inject_fault()[0])
        self.assertIn("SATURATED", self.command(CmdInspect, self.tech, "scrubber"))
        self.assertTrue(scrubber.isolate(self.tech)[0])
        self.assertTrue(scrubber.replace(self.tech)[0])
        self.assertEqual(scrubber.db.spare_cartridges, 0)
        scrubber.note_inspection(self.tech)
        self.assertTrue(scrubber.restart(self.tech)[0])
        self.assertTrue(scrubber.inject_fault()[0])
        scrubber.note_inspection(self.tech)
        self.assertTrue(scrubber.isolate(self.tech)[0])
        self.assertFalse(scrubber.replace(self.tech)[0])
        self.assertEqual(scrubber.state, "isolated")
        self.assertEqual([e["operation"] for e in scrubber.db.event_history].count("replace"), 2)

    def test_events_and_bridge_telemetry_respect_character_visibility(self):
        ship = self.ship
        self.assertTrue(ship["cradle"].inject_fault()[0])
        self.assertTrue(ship["scrubber"].inject_fault()[0])
        self.assertEqual([e["kind"] for e in inbox(self.cargo)], ["cargo_shift"])
        self.assertEqual([e["kind"] for e in inbox(self.tech)], ["atmosphere_alarm"])
        self.assertEqual([e["kind"] for e in inbox(self.lin)],
                         ["cargo_shift", "atmosphere_alarm"])
        self.assertEqual(inbox(self.ari), [])
        self.assertIn("C-01 cargo restraints: UNSECURED", ship["operations"].readout())
        self.assertIn("A-01 atmosphere scrubber: SATURATED", ship["operations"].readout())
        self.assertIn("UNSECURED", self.command(CmdInspect, self.lin, "operations"))
        self.assertFalse(ship["cradle"].restow(self.lin)[0])
        self.assertFalse(ship["scrubber"].isolate(self.lin)[0])
        self.assertFalse(ship["cradle"].access(self.cargo, "get"))
        self.assertFalse(ship["scrubber"].access(self.tech, "get"))

    def test_developer_can_try_both_specialist_roles_without_npc_puppeting(self):
        player = self.char1
        player.move_to(self.ship["cargo_hold"], quiet=True)
        with patch.object(player, "check_permstring", return_value=False):
            self.assertIn("Only developers",
                          self.command(CmdShipRole, player, "cargo"))
        self.assertNotEqual(player.db.crew_role, "cargo_officer")
        with patch.object(player, "check_permstring", return_value=True):
            self.assertIn("specialist duty",
                          self.command(CmdShipRole, player, "cargo"))
        self.assertEqual(player.db.crew_role, "cargo_officer")
        cradle = self.ship["cradle"]
        self.assertTrue(cradle.inject_fault()[0])
        cradle.note_inspection(player)
        self.assertTrue(cradle.restow(player)[0])
        cradle.note_inspection(player)
        self.assertTrue(cradle.certify(player)[0])
        with patch.object(player, "check_permstring", return_value=True):
            self.assertIn("specialist duty",
                          self.command(CmdShipRole, player, "environment"))
        player.move_to(self.ship["environmental"], quiet=True)
        self.assertEqual(player.db.crew_role, "environment_tech")
        scrubber = self.ship["scrubber"]
        self.assertTrue(scrubber.inject_fault()[0])
        scrubber.note_inspection(player)
        self.assertTrue(scrubber.isolate(player)[0])
        self.assertTrue(scrubber.replace(player)[0])
        scrubber.note_inspection(player)
        self.assertTrue(scrubber.restart(player)[0])

    def test_unprivileged_fault_command_cannot_mutate_systems(self):
        # Command security is enforced even if called without Evennia's parser.
        with patch.object(self.cargo, "check_permstring", return_value=False):
            self.assertIn("Only developers",
                          self.command(CmdShipFault, self.cargo, "cargo"))
        self.assertEqual(self.ship["cradle"].state, "secured")
        with patch.object(self.tech, "check_permstring", return_value=True):
            self.assertIn("saturated",
                          self.command(CmdShipFault, self.tech, "scrubber"))
        self.assertEqual(self.ship["scrubber"].state, "saturated")
        self.assertFalse(self.ship["cradle"].inject_fault(actor=self.cargo)[0])
        # Future skills are descriptive tags, not role bypasses or stat gains.
        self.assertEqual(self.ship["cradle"].SKILL_TAGS["restow"], "cargo_rigging")
        self.assertEqual(
            self.ship["scrubber"].SKILL_TAGS["replace"], "environmental_maintenance"
        )
