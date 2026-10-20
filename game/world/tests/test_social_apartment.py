"""Focused Evennia fixture tests: social world is not the ship."""

import os
from unittest.mock import patch

from evennia.utils.test_resources import EvenniaTestCase

from commands.default_cmdsets import CharacterCmdSet
from world.social_apartment import build_apartment, provision_apartment


class SocialApartmentWorldTests(EvenniaTestCase):
    def test_single_room_two_independent_persistent_adults(self):
        first = build_apartment()
        room, clara, ben = first["room"], first["clara"], first["ben"]
        self.assertIsNone(room.location)
        self.assertEqual(clara.location, room)
        self.assertEqual(ben.location, room)
        self.assertEqual(clara.home, room)
        self.assertEqual(ben.home, room)
        self.assertNotEqual(clara.dbref, ben.dbref)
        self.assertEqual(clara.db.social_role, "resident")
        self.assertEqual(ben.db.social_role, "guest")
        self.assertEqual([obj for obj in room.contents if obj != clara and obj != ben], [])
        second = build_apartment()
        for key in ("room", "clara", "ben"):
            self.assertEqual(first[key].id, second[key].id)
        self.assertEqual(room.exits, [])
        self.assertFalse(clara.attributes.has("ox_emotion"))
        self.assertFalse(ben.attributes.has("ox_emotion"))

    def test_repeat_fixture_does_not_teleport_or_reset_people(self):
        scene = build_apartment()
        other = self.room1
        ben = scene["ben"]
        ben.move_to(other, quiet=True)
        ben.db.social_note = "private operator marker"
        build_apartment()
        self.assertEqual(ben.location, other)
        self.assertEqual(ben.db.social_note, "private operator marker")

    def test_no_special_social_command_or_unrestricted_mutators(self):
        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        names = {cmd.key for cmd in cmdset.commands}
        self.assertTrue({"say", "whisper", "pose", "look"}.issubset(names))
        self.assertNotIn("set", names)
        self.assertNotIn("teleport", names)

    def test_clients_are_opt_in_and_never_reprovision_by_accident(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionError):
                provision_apartment()
