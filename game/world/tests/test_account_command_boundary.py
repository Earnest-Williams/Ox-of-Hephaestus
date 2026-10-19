"""Account-level Ox restriction does not change the session or world layers."""
from evennia.utils.test_resources import EvenniaTestCase
from evennia.commands.default.cmdset_account import AccountCmdSet as StockAccountSet
from commands.account_cmdsets import AccountCmdSet
from django.conf import settings


class AccountCommandBoundaryTests(EvenniaTestCase):
    def test_explicit_session_and_puppet_allowlist(self):
        account_commands = AccountCmdSet()
        account_commands.at_cmdset_creation()
        keys = {command.key for command in account_commands.commands}
        self.assertEqual(
            keys,
            {"look", "ic", "ooc", "option", "quit", "password", "help"},
        )
        self.assertFalse(issubclass(AccountCmdSet, StockAccountSet))
        self.assertEqual(account_commands.priority, -10)

    def test_stock_world_bypass_and_admin_shortcuts_not_imported(self):
        account_commands = AccountCmdSet()
        account_commands.at_cmdset_creation()
        keys = {command.key for command in account_commands.commands}
        for prohibited in (
            "charcreate", "chardelete", "page", "channel", "who",
            "reload", "reset", "shutdown", "py", "newpassword",
            "examine", "irc2chan", "rss2chan", "discord2chan",
        ):
            with self.subTest(command=prohibited):
                self.assertNotIn(prohibited, keys)

    def test_session_and_unlogged_in_login_routes_remain_engine_owned(self):
        self.assertEqual(
            settings.CMDSET_ACCOUNT, "commands.account_cmdsets.AccountCmdSet",
        )
        self.assertEqual(
            settings.CMDSET_SESSION,
            "evennia.commands.default.cmdset_session.SessionCmdSet",
        )
        self.assertEqual(
            settings.CMDSET_UNLOGGEDIN,
            "evennia.commands.default.cmdset_unloggedin.UnloggedinCmdSet",
        )
