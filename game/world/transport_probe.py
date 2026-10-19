"""Disposable CI-only native account provisioning for transport probes.

Run as the operator from the local development shell. Never expose this as
an in-world command; never print the password or create privileged NPC accounts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from evennia.accounts.models import AccountDB
from evennia.utils.create import create_account

from world.bootstrap import build_ship


CREW = (
    ("ari", "watch", "OxBotAri"),
    ("lin", "officer", "OxBotLin"),
    ("iona", "chief", "OxBotIona"),
)
SPECIALISTS = (
    ("mara", "cargo", "OxBotMara"),
    ("teo", "environment", "OxBotTeo"),
)


def provision(*, include_specialists: bool = False,
              include_captain: bool = False) -> dict[str, str]:
    password = os.environ["OX_PROBE_PASSWORD"]
    if len(password) < 20:
        raise ValueError("CI password too short")
    ship = build_ship()
    mapping = {}
    if include_captain and not include_specialists:
        raise ValueError("Captain trial requires the existing five crew")
    extra = (("captain", "captain", "OxBotCaptain"),) if include_captain else ()
    for key, ship_key, username in (
        *CREW, *(SPECIALISTS if include_specialists else ()), *extra,
    ):
        if AccountDB.objects.filter(username__iexact=username).exists():
            raise RuntimeError("Refusing to replace an existing crew account")
        account = create_account(username, email=username.lower() + '@example.invalid', password=password)
        if account is None:
            raise RuntimeError("Unable to provision non-privileged account")
        char = ship[ship_key]
        account.characters.add(char)
        account.db._last_puppet = char
        # Only that account may control its assigned crew body.
        char.locks.add("puppet:pid(" + str(account.id) + ")")
        mapping[key] = char.dbref
    path = Path("../.ox-state/p3a-ids.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({role: mapping[role] for role, *_ in CREW}),
        encoding="utf-8",
    )
    if include_specialists:
        Path("../.ox-state/p4e-ids.json").write_text(
            json.dumps(mapping), encoding="utf-8"
        )
    if include_captain:
        Path("../.ox-state/p4f-captain-id.json").write_text(
            json.dumps({"captain": mapping["captain"]}), encoding="utf-8",
        )
        # Keep the legacy P4e identity file exactly five roles, so
        # three- and five-crew integrations remain compatible.
        Path("../.ox-state/p4e-ids.json").write_text(
            json.dumps({key: mapping[key] for key, *_ in (*CREW, *SPECIALISTS)}),
            encoding="utf-8",
        )
    return mapping
