"""Django backend: PostgreSQL that starts the game's private cluster on demand.

Identical to ``django.db.backends.postgresql`` except that a refused first
connection starts the cluster and creates the database, then retries once.
Connecting first keeps the common path free of subprocess calls.
``connection.vendor`` stays ``"postgresql"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.backends.postgresql import base as postgresql

from .cluster import Layout, ensure_running, layout_for


def cluster_layout() -> Layout:
    return layout_for(Path(str(settings.OX_PG_DATA_DIR)))


class DatabaseWrapper(postgresql.DatabaseWrapper):  # type: ignore[misc]
    def get_new_connection(self, conn_params: dict[str, Any]) -> Any:
        try:
            return super().get_new_connection(conn_params)
        except postgresql.Database.OperationalError:
            # Not running, never initialised, or the database is missing.
            ensure_running(cluster_layout(), str(conn_params["dbname"]))
            return super().get_new_connection(conn_params)
