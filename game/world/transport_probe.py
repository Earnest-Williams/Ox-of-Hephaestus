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


# P4k: strictly disposable forty-body recovery acceptance fixture. Not a
# production roster API or a handler-accessible world mutation shortcut.
FLEET_SIZE = 40
FLEET_POSTS = (
    ("cargo_hold", "cargo_officer", "cargo"),
    ("environmental", "environment_tech", "scrubber"),
    ("bridge", "bridge_officer", "operations"),
    ("engineering", "watch_engineer", "pump"),
)


def provision_fleet() -> dict[str, dict[str, str]]:
    """Create forty separate non-privileged accounts, bodies and duty events.

    This operator command must run on an empty disposable fixture world.
    Re-entry refuses to overwrite existing accounts or characters.
    """
    from evennia.utils import gametime
    from evennia.utils.create import create_object
    from world.bootstrap import FIXTURE_CATEGORY, find_fixture
    from world.event_journal import emit
    from world.independent_rounds import schedule_rounds, tick_rounds

    password = os.environ["OX_PROBE_PASSWORD"]
    if len(password) < 20:
        raise ValueError("CI password too short")
    ship = build_ship()
    roster = {}
    for ordinal in range(FLEET_SIZE):
        role = f"fleet{ordinal:02d}"
        username = f"OxFleet{ordinal:02d}"
        marker = f"fleet-recovery-{ordinal:02d}"
        if find_fixture(marker) is not None:
            raise RuntimeError("Cannot overwrite a previously provisioned fleet body")
        if AccountDB.objects.filter(username__iexact=username).exists():
            raise RuntimeError("Cannot overwrite a previously provisioned fleet account")
        room_key, crew_role, station = FLEET_POSTS[ordinal % len(FLEET_POSTS)]
        name = f"Fleet Recovery Crew {ordinal:02d}"
        room = ship[room_key]
        person = create_object(
            "typeclasses.ship.CrewCharacter", key=name,
            location=room, home=room,
            tags=[(marker, FIXTURE_CATEGORY)],
        )
        person.db.crew_role = crew_role
        person.db.duty_title = f"Verified {station} station watch"
        person.db.watch_window = "Fleet recovery acceptance"
        account = create_account(
            username, email=username.lower() + "@example.invalid",
            password=password,
        )
        if account is None:
            raise RuntimeError("Could not provision ordinary fleet account")
        account.characters.add(person)
        account.db._last_puppet = person
        person.locks.add("puppet:pid(" + str(account.id) + ")")
        roster[role] = {
            "username": username,
            "character_dbref": person.dbref,
            "name": name,
            "duty": f"Verify and report conditions at {station}",
        }
        emit(
            ship["pump"], person, "fleet_duty_posted",
            data={"station": station, "phase": "begin"},
            text=f"Private post for {role}: inspect the {station} station this interval.",
        )
    if len({entry["character_dbref"] for entry in roster.values()}) != FLEET_SIZE:
        raise RuntimeError("Fleet must have forty different persistent bodies")
    root = Path("../.ox-state/p4k")
    root.mkdir(parents=True, exist_ok=True)
    (root / "roster.json").write_text(
        json.dumps(roster, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # This isolated test fixture advances an actual world-authoritative
    # round cycle so a normal cargo officer can inspect and report via oxwork.
    schedule_rounds(period_game_seconds=30)
    now = float(gametime.gametime(absolute=True))
    tick_rounds(now_game_time=now)
    if not tick_rounds(now_game_time=now + 35):
        raise RuntimeError("Disposable world round cycle was not opened")
    return roster


def advance_fleet_recovery() -> None:
    """Write one *new* addressed duty update per body between process boots."""
    from world.bootstrap import find_fixture
    from world.event_journal import emit
    from world.models import WorkReceipt

    ship = build_ship()
    if WorkReceipt.objects.filter(operation="round_report", target="ship").count() != FLEET_SIZE:
        raise RuntimeError("Expected forty committed, separately receipted duty reports")
    for ordinal in range(FLEET_SIZE):
        person = find_fixture(f"fleet-recovery-{ordinal:02d}")
        if person is None:
            raise RuntimeError("Cannot continue an incomplete forty-body world")
        station = FLEET_POSTS[ordinal % len(FLEET_POSTS)][2]
        emit(
            ship["pump"], person, "fleet_duty_updated",
            data={"station": station, "phase": "resume"},
            text=(f"Private update for fleet{ordinal:02d}: "
                  f"the next {station} duty interval is posted."),
        )
