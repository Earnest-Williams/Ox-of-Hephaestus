"""Idempotent, opt-in TWO-PERSON apartment fixture for social GOAP.

No ship bootstrap changes. No ship systems, existing crew or shared private
agent memories are imported into this scene. The room and bodies are Evennia
world facts; private emotional preferences belong to each handler agent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object

CATEGORY = "ox_social_goap_v1"


def _object(marker: str):
    matches = list(ObjectDB.objects.get_by_tag(key=marker, category=CATEGORY))
    if len(matches) > 1:
        raise RuntimeError(f"Duplicated social fixture tag: {marker}")
    return matches[0] if matches else None


def build_apartment() -> dict:
    """Create the location and two adults once; never reset existing state."""
    room = _object("apartment")
    if room is None:
        room = create_object(
            "typeclasses.social.SocialRoom",
            key="Clara's Apartment",
            tags=[("apartment", CATEGORY)],
            nohome=True,
        )
        room.db.desc = (
            "A small, lived-in apartment with a sofa, lamp, coffee table "
            "and kitchenette. It is late evening; Clara and Ben have just "
            "returned from a date they both enjoyed."
        )

    specs = (
        ("clara", "Clara", "resident",
         "An adult woman, home after an evening out."),
        ("ben", "Ben", "guest",
         "An adult man visiting after an evening out."),
    )
    result = {"room": room}
    for marker, name, role, desc in specs:
        person = _object(marker)
        if person is None:
            person = create_object(
                "typeclasses.social.SocialPerson", key=name,
                location=room, home=room, tags=[(marker, CATEGORY)],
            )
            person.db.social_role = role
            person.db.desc = desc
        result[marker] = person
    return result


def provision_apartment() -> dict[str, str]:
    """Operator-only disposable TWO-account setup for real-client GOAP tests.

    Authentication and puppet restrictions are ordinary Evennia mechanisms.
    Calling this never starts models, a scheduler or an AI supervisor.
    """
    if os.environ.get("OX_SOCIAL_GOAP_LIVE_CI") != "1":
        raise PermissionError("Social account provisioning is disposable opt-in only")
    password = os.environ["OX_PROBE_PASSWORD"]
    if len(password) < 20:
        raise ValueError("Probe password too short")
    from evennia.accounts.models import AccountDB
    from evennia.utils.create import create_account

    people = build_apartment()
    result = {}
    for label, username in (("clara", "OxSocialClara"), ("ben", "OxSocialBen")):
        if AccountDB.objects.filter(username__iexact=username).exists():
            raise RuntimeError("Refusing to overwrite an existing social bot account")
        account = create_account(
            username, email=username.lower() + "@example.invalid",
            password=password,
        )
        if account is None:
            raise RuntimeError("Social bot provisioning failed")
        person = people[label]
        account.characters.add(person)
        account.db._last_puppet = person
        person.locks.add("puppet:pid(" + str(account.id) + ")")
        result[label] = person.dbref
    output = Path("../.ox-state/g7-social-ids.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return result
