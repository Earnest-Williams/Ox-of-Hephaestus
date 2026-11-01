"""Exact, index-backed lookup of Ox objects by their durable plain tag.

Evennia's ``ObjectDB.objects.get_by_tag`` compares ``UPPER(key)`` and
``UPPER(category)`` and counts matches over a self-join. PostgreSQL cannot use
the tag index for that, and while a fixture is being built inside one
transaction (a test, or ``build_canonical_ship``) the planner has no statistics
for the rows just written, so each lookup can degrade into a nested loop over
every tag link. Building the 421-space ship does thousands of these lookups.

Evennia stores plain tag keys and categories lower-cased (``TagHandler.add``),
so an exact match on the lower-cased values is equivalent and hits the
``(db_key, db_category, db_tagtype, db_model)`` index directly.
"""

from __future__ import annotations

from evennia.objects.models import ObjectDB

_MODEL: str = "objectdb"


def objects_tagged(marker: str, category: str) -> list[ObjectDB]:
    """Every object carrying the plain tag ``marker`` in ``category``."""
    key: str = marker.strip().lower()
    group: str = category.strip().lower()
    return list(
        ObjectDB.objects.filter(
            db_tags__db_key=key,
            db_tags__db_category=group,
            db_tags__db_tagtype__isnull=True,
            db_tags__db_model=_MODEL,
        )
        .distinct()
        .order_by("id")
    )
