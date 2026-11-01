"""Fresh planner statistics for Evennia's object, attribute and tag tables.

Bulk world construction (the installed ship writes about 1,500 objects and
10,000 attributes) starts from tables PostgreSQL has never analysed. Without
column statistics the planner assumes ``db_attrtype IS NULL`` matches almost
nothing, so each Evennia attribute lookup scans every attribute instead of
starting from the object's few links: 2.8 ms per lookup, 28 of the build's 35
seconds of database time. ANALYZE inside the building transaction counts the
transaction's own rows, and once the proportions are known the planner
scales its estimates with the tables' current size.
"""

from __future__ import annotations

from django.db import connection

HOT_TABLES: tuple[str, ...] = (
    "objects_objectdb",
    "objects_objectdb_db_attributes",
    "objects_objectdb_db_tags",
    "typeclasses_attribute",
    "typeclasses_tag",
)


def refresh() -> None:
    """ANALYZE the tables Evennia's attribute and tag lookups join."""
    statement: str = "ANALYZE " + ", ".join(HOT_TABLES)
    with connection.cursor() as cursor:
        cursor.execute(statement)
