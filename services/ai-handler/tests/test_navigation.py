"""Private, bounded GOAP exploration over authenticated local exit observations."""
import asyncio
from types import SimpleNamespace
import unittest

from ox_ai.planning.navigation import (
    CrewNavigator, NavigationKnowledge, RouteUnreachable,
)
from ox_ai.ports.evennia.capabilities import (
    CapabilitySnapshot, ExitCapability, FixtureCapability,
)

ACTOR = "#77"
NONCE = "f" * 32
ROOMS = {
    "#11": "Crew Mess",
    "#12": "Connecting Passage",
    "#13": "Engineering",
    "#14": "Machine Shop",
    "#15": "Cargo Hold",
    "#16": "Environmental Plant",
    "#17": "Bridge",
}
EDGES = {
    "#11": [("out", "#12")],
    "#12": [("fore", "#17"), ("engineering", "#13"),
            ("mess", "#11"), ("starboard", "#15"), ("port", "#16")],
    "#13": [("out", "#12"), ("workshop", "#14")],
    "#14": [("out", "#13")],
    "#15": [("port", "#12")],
    "#16": [("starboard", "#12")],
    "#17": [("aft", "#12")],
}


class FakeWorldPort:
    """Exposes only exits in the character's *current* room, never a map."""
    def __init__(self, *, blocked=(), alternative=False, late_lock=False):
        self.client = SimpleNamespace(character_dbref=ACTOR)
        self.here = "#11"
        self.graph = {room: list(edges) for room, edges in EDGES.items()}
        if alternative:
            self.graph["#11"].append(("shop hatch", "#14"))
            self.graph["#14"].append(("mess", "#11"))
        self.blocked = set(blocked)
        self.late_lock = late_lock
        self.moved = []
        self.observed = []
        self.calls = 0

    async def observe(self):
        self.calls += 1
        self.observed.append(self.here)
        exits = tuple(
            ExitCapability(
                "#" + str(100 + int(self.here[1:]) * 20 + index),
                command, destination, ROOMS[destination],
            )
            for index, (command, destination) in enumerate(self.graph[self.here])
            if (self.here, command) not in self.blocked
        )
        equipment = ()
        if self.here == "#13":
            equipment = (
                FixtureCapability("#801", "Cooling Pump P-01", "pump",
                                  ("inspect",)),
            )
        return CapabilitySnapshot(ACTOR, self.here, ROOMS[self.here], exits, equipment)

    async def traverse(self, snapshot, edge):
        if self.late_lock and self.here == "#12" and edge.command == "engineering":
            self.blocked.add(("#12", "engineering"))
            self.late_lock = False
        fresh = await self.observe()
        if fresh.room_dbref != snapshot.room_dbref or edge not in fresh.exits:
            return fresh, False
        self.moved.append(edge.command)
        self.here = edge.destination_dbref
        return await self.observe(), True


class TypedCapabilityTests(unittest.TestCase):
    def valid(self):
        return {
            "version": 1, "nonce": NONCE, "actor_dbref": ACTOR,
            "room": {"dbref": "#11", "name": "Crew Mess"},
            "exits": [{"exit_dbref": "#301", "command": "out",
                       "destination_dbref": "#12",
                       "destination_name": "Connecting Passage"}],
            "equipment": [],
        }

    def test_actor_nonce_and_exact_schema(self):
        snap = CapabilitySnapshot.parse(self.valid(), actor_dbref=ACTOR, nonce=NONCE)
        self.assertEqual(snap.room_dbref, "#11")
        self.assertEqual(snap.exits[0].command, "out")
        wrong = self.valid()
        wrong["actor_dbref"] = "#99"
        with self.assertRaises(PermissionError):
            CapabilitySnapshot.parse(wrong, actor_dbref=ACTOR, nonce=NONCE)
        wrong = self.valid()
        wrong["nonce"] = "e" * 32
        with self.assertRaises(PermissionError):
            CapabilitySnapshot.parse(wrong, actor_dbref=ACTOR, nonce=NONCE)

    def test_reject_malformed_and_untrusted_world_payload(self):
        for field, value in (
            ("version", 2), ("version", True), ("exits", "all"),
            ("room", {"dbref": "#11", "name": "Crew Mess", "secret": 1}),
        ):
            malformed = self.valid()
            malformed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                CapabilitySnapshot.parse(malformed, actor_dbref=ACTOR, nonce=NONCE)
        malformed = self.valid()
        malformed["exits"][0]["command"] = "teleport; sudo"
        with self.assertRaises(ValueError):
            CapabilitySnapshot.parse(malformed, actor_dbref=ACTOR, nonce=NONCE)
        malformed = self.valid()
        malformed["equipment"] = [{
            "fixture_dbref": "#400", "name": "Remote", "target": "reactor",
            "operations": ["start"]
        }]
        with self.assertRaises(ValueError):
            CapabilitySnapshot.parse(malformed, actor_dbref=ACTOR, nonce=NONCE)

    def test_private_persistent_knowledge_rejects_other_characters(self):
        p = FakeWorldPort()
        k = NavigationKnowledge(ACTOR)
        k.remember(asyncio.run(p.observe()))
        restored = NavigationKnowledge(ACTOR, k.to_record())
        self.assertEqual(restored.to_record(), k.to_record())
        with self.assertRaises(PermissionError):
            NavigationKnowledge("#78", k.to_record())
        with self.assertRaises(PermissionError):
            k.remember(CapabilitySnapshot("#78", "#11", "Crew Mess", (), ()))

    def test_no_omniscient_route_before_exploration(self):
        p = FakeWorldPort()
        k = NavigationKnowledge(ACTOR)
        k.remember(asyncio.run(p.observe()))
        _, next_exit = k.next_step("#11", "Engineering", forbidden=set())
        self.assertEqual(next_exit.command, "out")
        self.assertNotIn("#13", k.rooms)


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_independent_mess_to_engineering_via_two_real_exits(self):
        port = FakeWorldPort()
        navigator = CrewNavigator(port)
        result = await navigator.navigate("Engineering")
        self.assertEqual(result.status, "arrived")
        self.assertEqual(result.final_room, "#13")
        self.assertEqual(result.traversed_exits, ("out", "engineering"))
        self.assertEqual(port.here, "#13")
        self.assertNotIn("#13", port.observed[:2])
        self.assertEqual(navigator.knowledge.rooms["#13"]["name"], "Engineering")

    async def test_blocked_exit_never_teleports_or_fabricates_equipment_effect(self):
        port = FakeWorldPort(blocked={("#12", "engineering")})
        result = await CrewNavigator(port).navigate("Engineering", max_movements=20)
        self.assertEqual(result.status, "blocked")
        self.assertNotEqual(port.here, "#13")
        self.assertNotIn("engineering", port.moved)
        self.assertLessEqual(len(port.moved), 20)

    async def test_alternative_hatch_reroutes_around_locked_primary_path(self):
        port = FakeWorldPort(blocked={("#12", "engineering")}, alternative=True)
        result = await CrewNavigator(port).navigate("Engineering", max_movements=24)
        self.assertEqual(result.status, "arrived")
        self.assertEqual(port.here, "#13")
        self.assertIn("shop hatch", result.traversed_exits)
        self.assertNotIn("engineering", result.traversed_exits)

    async def test_permission_withdrawn_between_plan_and_traversal(self):
        port = FakeWorldPort(alternative=True, late_lock=True)
        result = await CrewNavigator(port).navigate("Engineering", max_movements=24)
        self.assertEqual(result.status, "arrived")
        self.assertEqual(port.here, "#13")
        self.assertIn("shop hatch", result.traversed_exits)
        self.assertNotIn("engineering", port.moved)
        self.assertEqual(port.blocked, {("#12", "engineering")})

    async def test_restarts_from_actual_room_not_historic_position(self):
        port = FakeWorldPort()
        first = CrewNavigator(port)
        self.assertEqual((await first.navigate("Engineering")).status, "arrived")
        state = first.knowledge.to_record()
        port.here = "#11"  # authoritative game moved actor while AI was absent
        resumed = CrewNavigator(port, knowledge=NavigationKnowledge(ACTOR, state))
        result = await resumed.navigate("Engineering")
        self.assertEqual(result.status, "arrived")
        self.assertEqual(port.here, "#13")

    async def test_mismatched_brain_identity_is_refused(self):
        port = FakeWorldPort()
        agent = SimpleNamespace(character_id="#99")
        with self.assertRaises(PermissionError):
            CrewNavigator(port, brain=agent)


if __name__ == "__main__":
    unittest.main()
