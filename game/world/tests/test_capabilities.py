"""Actor-scoped local action discovery against real Evennia objects."""
from __future__ import annotations

import json
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase
from commands.capabilities import CmdOxCapabilities
from commands.ship import CmdInspect
from world.bootstrap import build_ship, find_fixture
from world.capabilities import local_capabilities

CHALLENGE = "a" * 32


class CapabilityWorldTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        self.ship = build_ship()
        self.ari = self.ship["watch"]
        self.lin = self.ship["officer"]

    def test_locality_and_traversable_ship_exits_only(self):
        self.assertTrue(self.ari.move_to(self.ship["mess"], quiet=True))
        result = local_capabilities(self.ari, CHALLENGE)
        self.assertEqual(result["actor_dbref"], self.ari.dbref)
        self.assertEqual(result["room"]["dbref"], self.ship["mess"].dbref)
        self.assertEqual([x["command"] for x in result["exits"]], ["out"])
        self.assertEqual(result["exits"][0]["destination_name"], "Connecting Passage")
        self.assertEqual(result["equipment"], [])
        self.assertTrue(self.ari.move_to(self.ship["passage"], quiet=True))
        result = local_capabilities(self.ari, CHALLENGE)
        self.assertIn("engineering", [x["command"] for x in result["exits"]])
        # Engineering's pump is *not* disclosed from the passage.
        self.assertNotIn("pump", [x["target"] for x in result["equipment"]])
        # Exits beyond the current room are not enumerated, even though the
        # ship's global graph exists in the world database.
        self.assertNotIn("workshop", [x["command"] for x in result["exits"]])

    def test_stateful_local_actions_are_not_promises_or_permissions(self):
        pump = self.ship["pump"]
        self.assertTrue(pump.inject_fault()[0])
        self.assertEqual(pump.state, "low_pressure")
        self.assertTrue(self.ari.move_to(self.ship["mess"], quiet=True))
        result = local_capabilities(self.ari, CHALLENGE)
        self.assertNotIn("pump", [x["target"] for x in result["equipment"]])
        # Even an engineer with detailed knowledge cannot repair from the mess.
        self.assertFalse(pump.isolate(self.ari)[0])
        self.assertTrue(self.ari.move_to(self.ship["engineering"], quiet=True))
        result = local_capabilities(self.ari, CHALLENGE)
        self.assertEqual(result["equipment"][0]["target"], "pump")
        self.assertEqual(result["equipment"][0]["operations"], ["inspect", "isolate"])
        self.assertTrue(self.ari.move_to(self.ship["mess"], quiet=True))
        # This stale snapshot does not grant remote physical authority.
        self.assertFalse(pump.isolate(self.ari)[0])
        self.assertEqual(pump.state, "low_pressure")
        # A non-engineer may inspect a local pump, but not isolate it.
        self.assertTrue(self.lin.move_to(self.ship["engineering"], quiet=True))
        other = local_capabilities(self.lin, CHALLENGE)
        self.assertEqual(other["equipment"][0]["operations"], ["inspect"])
        self.assertFalse(pump.isolate(self.lin)[0])

    def test_access_locks_filter_exits_and_actual_world_traversal(self):
        passage_exit = find_fixture("exit-passage-engineering")
        self.assertTrue(self.ari.move_to(self.ship["passage"], quiet=True))
        self.assertIn("engineering", [x["command"] for x in
                      local_capabilities(self.ari, CHALLENGE)["exits"]])
        passage_exit.locks.add("traverse:false()")
        self.assertNotIn("engineering", [x["command"] for x in
                         local_capabilities(self.ari, CHALLENGE)["exits"]])
        # A stock Evennia traversal still enforces its own lock.
        self.assertFalse(passage_exit.access(self.ari, "traverse"))
        self.assertEqual(self.ari.location, self.ship["passage"])

    def test_nonce_and_actor_are_authored_by_world_not_command_arguments(self):
        with self.assertRaises(PermissionError):
            local_capabilities(self.ari, "invalid")
        with self.assertRaises(PermissionError):
            local_capabilities(None, CHALLENGE)
        cmd = CmdOxCapabilities()
        cmd.caller = self.ari
        cmd.args = CHALLENGE
        with patch.object(self.ari, "msg") as output:
            cmd.func()
            self.assertEqual(output.call_count, 1)
            wire = output.call_args.kwargs["ox_capabilities"]
            decoded = json.loads(wire[0][0])
            self.assertEqual(decoded["nonce"], CHALLENGE)
            self.assertEqual(decoded["actor_dbref"], self.ari.dbref)
            self.assertNotIn("private", str(decoded).lower())

    def test_inspection_changes_current_eligible_actions_without_moving(self):
        self.assertTrue(self.ship["scrubber"].inject_fault()[0])
        teo = self.ship["environment"]
        before = local_capabilities(teo, CHALLENGE)
        self.assertEqual(before["equipment"][0]["operations"], ["inspect"])
        cmd = CmdInspect()
        cmd.caller = teo
        cmd.args = "scrubber"
        with patch.object(teo, "msg"):
            cmd.func()
        after = local_capabilities(teo, CHALLENGE)
        self.assertEqual(after["equipment"][0]["operations"], ["inspect", "isolate"])
        self.assertEqual(after["room"], before["room"])

if __name__ == "__main__":
    import unittest
    unittest.main()
