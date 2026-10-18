"""Local-only Evennia settings for the Ox spaceship proving ground.

This is a standalone game directory, not a modification of Evennia's engine.
Do not expose this development server to untrusted networks.
"""

from __future__ import annotations

import os
from pathlib import Path
import secrets

from evennia.settings_default import *  # noqa: F401,F403

SERVERNAME = "Ox of Hephaestus — Prototype Ship"
GAME_SLOGAN = "A working ship and an autonomous crew, eventually."

# The unreviewed prototype is deliberately limited to local connections.
LOCKDOWN_MODE = True
TELNET_INTERFACES = ["127.0.0.1"]
WEBSERVER_INTERFACES = ["127.0.0.1"]
WEBSOCKET_CLIENT_INTERFACE = "127.0.0.1"
NEW_ACCOUNT_REGISTRATION_ENABLED = False

BASE_ACCOUNT_TYPECLASS = "evennia.accounts.accounts.DefaultAccount"
BASE_OBJECT_TYPECLASS = "evennia.objects.objects.DefaultObject"
BASE_CHARACTER_TYPECLASS = "typeclasses.ship.CrewCharacter"
BASE_ROOM_TYPECLASS = "typeclasses.ship.ShipRoom"
BASE_EXIT_TYPECLASS = "evennia.objects.objects.DefaultExit"
BASE_CHANNEL_TYPECLASS = "evennia.comms.comms.DefaultChannel"
BASE_SCRIPT_TYPECLASS = "evennia.scripts.scripts.DefaultScript"
BASE_GUEST_TYPECLASS = "evennia.accounts.accounts.DefaultGuest"

CMDSET_UNLOGGEDIN = "evennia.commands.default.cmdset_unloggedin.UnloggedinCmdSet"
CMDSET_SESSION = "evennia.commands.default.cmdset_session.SessionCmdSet"
CMDSET_ACCOUNT = "evennia.commands.default.cmdset_account.AccountCmdSet"
CMDSET_CHARACTER = "commands.default_cmdsets.CharacterCmdSet"

# Avoid a public, reusable Django signing key in Git history. For development
# only, create a private persistent key on first launch (ignored by git). A
# deployment must supply OX_SECRET_KEY and use an intentionally audited config.
_key_from_env = os.environ.get("OX_SECRET_KEY")
if _key_from_env:
    SECRET_KEY = _key_from_env
else:
    _secret_path = Path(__file__).with_name(".local-secret")
    if not _secret_path.is_file():
        _generated_key = secrets.token_urlsafe(48)
        try:
            with _secret_path.open("x", encoding="utf-8") as _secret_file:
                os.chmod(_secret_path, 0o600)
                _secret_file.write(_generated_key)
        except FileExistsError:
            pass
    SECRET_KEY = _secret_path.read_text(encoding="utf-8").strip()
    if not SECRET_KEY:
        raise RuntimeError("Empty local Django secret key; set OX_SECRET_KEY")
