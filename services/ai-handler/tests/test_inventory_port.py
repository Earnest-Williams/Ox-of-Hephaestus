"""No missing inventory observation can be interpreted as zero stock."""
import json
import unittest
from unittest.mock import AsyncMock, Mock

from ox_ai.ports.evennia.inventory import InventoryObservation, InventoryPort

ACTOR = "#27"
NONCE = "0" * 32


class InventorySchemaTests(unittest.TestCase):
    def example(self):
        return {
            "version": 1, "nonce": NONCE, "actor_dbref": ACTOR,
            "room_dbref": "#18", "local_cartridges": 1,
            "game_time": 47.25,
            "carried": ["oxitem-" + "a" * 32],
        }

    def test_valid_local_and_unknown_remote_are_separate(self):
        current = InventoryObservation.parse(
            self.example(), actor_dbref=ACTOR, nonce=NONCE,
        )
        self.assertEqual(current.local_cartridges, 1)
        sample = self.example()
        sample["local_cartridges"] = None
        unknown = InventoryObservation.parse(
            sample, actor_dbref=ACTOR, nonce=NONCE,
        )
        self.assertIsNone(unknown.local_cartridges)
        self.assertNotEqual(current, unknown)

    def test_false_other_identity_unknown_version_or_unsafe_text_refused(self):
        for key, val in (
            ("version", True), ("version", 5),
            ("actor_dbref", "#999"),
            ("nonce", "1" * 32),
            ("local_cartridges", "0"),
            ("local_cartridges", -1),
            ("room_dbref", "Engineering"),
            ("game_time", float("nan")),
            ("game_time", -1),
        ):
            with self.subTest(key=key):
                sample = self.example()
                sample[key] = val
                with self.assertRaises((PermissionError, ValueError)):
                    InventoryObservation.parse(
                        sample, actor_dbref=ACTOR, nonce=NONCE,
                    )
        sample = self.example()
        sample["carried"].append("not-an-item")
        with self.assertRaises(ValueError):
            InventoryObservation.parse(sample, actor_dbref=ACTOR, nonce=NONCE)


class InventoryPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_unauthenticated_session_never_reads_inventory(self):
        client = Mock()
        client.authenticated = False
        client.send_line = AsyncMock()
        with self.assertRaises(PermissionError):
            await InventoryPort(client).observe()
        client.send_line.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
