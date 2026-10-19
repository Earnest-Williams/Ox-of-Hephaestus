"""Verify the gameplay command allowlist does not bypass Ox world rules."""
from evennia.utils.test_resources import EvenniaTestCase
from commands.default_cmdsets import CharacterCmdSet


class CharacterCommandBoundaryTests(EvenniaTestCase):
    def test_ox_character_cmdset_does_not_inherit_stock_mutators(self):
        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        keys = {cmd.key for cmd in cmdset.commands}
        for required in (
            "look", "say", "whisper", "pose", "help", "inspect",
            "oxwork", "oxworkreceipt", "oxinventory", "oxidentity",
        ):
            with self.subTest(required=required):
                self.assertIn(required, keys)
        for forbidden in (
            "home", "get", "drop", "give", "desc", "set", "create",
            "dig", "open", "teleport", "destroy", "sethome", "cpattr",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, keys)

    def test_ship_commands_have_no_legacy_inherited_defaults(self):
        from evennia.commands.default.cmdset_character import CharacterCmdSet as Stock
        self.assertFalse(issubclass(CharacterCmdSet, Stock))
