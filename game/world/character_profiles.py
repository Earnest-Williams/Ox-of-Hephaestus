"""Idempotent binding of existing ship crew to authoritative person records.

No role -> skill inheritance after creation. Current G3f qualification gates
continue to operate against their old 0-4 vector until separately migrated.
Only world bootstrap and authorised world code should call these functions.
"""
from __future__ import annotations

from django.db import transaction

from world.character_dimensions import PROFILE_VERSION, neutral_profile, validate_profile
from world.models import CharacterProfile, CharacterSkill
from world.skill_catalogue import SKILLS, initial_skill_estimates


# Stable *people*, not interchangeable roles. A duty transfer never changes ID.
FIXTURE_PERSON_IDS = {
    "crew-chief": "crew.iona-vek",
    "crew-watch": "crew.ari-sen",
    "crew-bridge": "crew.lin-sato",
    "crew-cargo": "crew.mara-voss",
    "crew-environment": "crew.teo-hale",
    "crew-captain": "crew.captain-initial",
}
FIXTURE_CATEGORY = "ox_ship_prototype"


@transaction.atomic
def seed_existing_crew(marker: str, actor) -> CharacterProfile:
    """Create each existing person's baseline and estimated skills once.

    Does not mutate the old G3f skill vector, roles, existing person data,
    proficiency advances, crew memory, duties, or controller checkpoints.
    """
    if marker not in FIXTURE_PERSON_IDS:
        raise ValueError("Unrecognised canonical crew marker")
    if (actor is None or not isinstance(getattr(actor, "dbref", None), str)
            or not actor.tags.has(marker, category=FIXTURE_CATEGORY)):
        raise PermissionError("Person seeding requires the matching world fixture")
    person_id = FIXTURE_PERSON_IDS[marker]
    aptitudes, psychology = neutral_profile()
    validate_profile(aptitudes, psychology)
    raw = actor.db.ox_skills
    # Evennia's persisted db dictionaries are SaverDict proxies, not plain dicts.
    estimates = initial_skill_estimates(dict(raw or {}))

    profile, _created = CharacterProfile.objects.select_for_update().get_or_create(
        person_id=person_id,
        defaults={
            "character_dbref": actor.dbref,
            "schema_version": PROFILE_VERSION,
            "aptitudes": aptitudes,
            "psychology": psychology,
            "styles": [],
            "source": "g4b_existing_crew",
        },
    )
    if profile.character_dbref != actor.dbref:
        raise PermissionError("Permanent person identity is bound to another world character")
    if profile.schema_version != PROFILE_VERSION:
        raise RuntimeError("Unsupported world character profile version")
    validate_profile(profile.aptitudes, profile.psychology)

    # Merge overlapping legacy coarse estimates by maximum; NEVER give
    # additional proficiency on repeated fixture setup or duty reassignment.
    for skill_id, proficiency in estimates.items():
        CharacterSkill.objects.get_or_create(
            person=profile, skill_id=skill_id,
            defaults={
                "proficiency": proficiency,
                "source": "g3f_legacy_initial_estimate",
            },
        )
    return profile


def profile_for_actor(actor) -> CharacterProfile | None:
    """Internal world lookup; never expose other people's data in OOB messages."""
    if actor is None or not isinstance(getattr(actor, "dbref", None), str):
        raise PermissionError("World actor identity is required")
    return CharacterProfile.objects.filter(character_dbref=actor.dbref).first()


def skill_for_actor(actor, skill_id: str) -> int:
    """Read actual world competency, not a perceived skill or role permission."""
    if skill_id not in SKILLS:
        raise ValueError("Unknown canonical world skill identifier")
    profile = profile_for_actor(actor)
    if profile is None:
        return 0
    found = CharacterSkill.objects.filter(person=profile, skill_id=skill_id).first()
    return found.proficiency if found is not None else 0
