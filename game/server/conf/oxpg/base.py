"""Django backend: PostgreSQL that starts the game's private cluster on demand.

Identical to ``django.db.backends.postgresql`` except that a refused first
connection starts the cluster and creates the database, then retries once.
Connecting first keeps the common path free of subprocess calls.
``connection.vendor`` stays ``"postgresql"``.

Test databases also turn autovacuum off on every table. A Django test writes
its fixture inside one transaction and rolls it back; autovacuum then records
the table as holding zero rows while its pages remain, and the next test's
planner trusts that. With 421 spaces and 808 units that turned millisecond
tag lookups into half-second nested loops. A never-analysed table is instead
estimated from its current size, which is right for a fixture built per test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.backends.postgresql import base as postgresql
from django.db.backends.postgresql import creation

from .cluster import Layout, ensure_running, layout_for


def cluster_layout() -> Layout:
    return layout_for(Path(str(settings.OX_PG_DATA_DIR)))


NO_AUTOVACUUM: str = """
DO $$
DECLARE target regclass;
BEGIN
    FOR target IN
        SELECT c.oid::regclass FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' AND n.nspname = current_schema()
    LOOP
        EXECUTE format(
            'ALTER TABLE %s SET (autovacuum_enabled = off,'
            ' toast.autovacuum_enabled = off)', target);
    END LOOP;
END $$;
"""


class DatabaseCreation(creation.DatabaseCreation):  # type: ignore[misc]
    def create_test_db(self, *args: Any, **kwargs: Any) -> str:
        name: str = super().create_test_db(*args, **kwargs)
        with self.connection.cursor() as cursor:
            cursor.execute(NO_AUTOVACUUM)
        return name


class DatabaseWrapper(postgresql.DatabaseWrapper):  # type: ignore[misc]
    creation_class = DatabaseCreation

    def get_new_connection(self, conn_params: dict[str, Any]) -> Any:
        try:
            return super().get_new_connection(conn_params)
        except postgresql.Database.OperationalError:
            # Not running, never initialised, or the database is missing.
            ensure_running(cluster_layout(), str(conn_params["dbname"]))
            return super().get_new_connection(conn_params)
