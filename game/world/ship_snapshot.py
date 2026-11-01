"""Build the installed ship once per design; clone it for tests.

Materialising the canonical 421-space ship issues about 93,000 queries
(roughly 41% of them Evennia savepoints). On PostgreSQL every one is a
round trip, so building it in each test's ``setUp`` dominated the installed
suites. The design is fixed per commit, so the result is too: this module
builds it once into a database named by a fingerprint of everything that
shapes it, and test databases are then created as file-level copies
(``CREATE DATABASE ... TEMPLATE``). Each test still rolls back its own
transaction, and ``build_canonical_ship()`` takes its existing early return.

From game/:
    python -m world.ship_snapshot ensure   # print the template, building it
    python -m world.ship_snapshot build    # internal: build into OX_PG_DATABASE

Opt in from the test runner with ``--prebuilt-ship``. Only suites whose tests
all use the canonical installed ship should opt in; builder tests that
materialise small synthetic models need an empty world.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _hashlib import HASH
    from psycopg import Connection

GAME_DIR: Path = Path(__file__).resolve().parents[1]
REPO_DIR: Path = GAME_DIR.parent
PREFIX: str = "ox_ship_"
BUILDING_SUFFIX: str = "_building"
LOCK_KEY: int = 0x0F5_5A1D  # session advisory lock serialising template builds

# Everything that decides the rows of a freshly built ship.
DESIGN_FILES: tuple[str, ...] = (
    "design/ship/ox_full_ship.json",
    "game/world/ship_model.py",
    "game/world/ship_world.py",
    "game/world/tagged.py",
    "game/world/ship_snapshot.py",
    "game/typeclasses/ship_world.py",
    "game/typeclasses/ship.py",
    "evennia/VERSION.txt",
)
MIGRATION_GLOBS: tuple[str, ...] = (
    "game/world/migrations/*.py",
    "evennia/*/migrations/*.py",
)


def _design_paths() -> Iterator[Path]:
    for name in DESIGN_FILES:
        yield REPO_DIR / name
    for pattern in MIGRATION_GLOBS:
        yield from sorted(REPO_DIR.glob(pattern))


def fingerprint() -> str:
    """Stable digest of the design inputs, independent of checkout location."""
    digest: "HASH" = hashlib.sha256()
    for path in _design_paths():
        relative: bytes = path.relative_to(REPO_DIR).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big") + relative)
        content: bytes = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big") + content)
    return digest.hexdigest()[:16]


def template_name(print_: str | None = None) -> str:
    return PREFIX + (print_ if print_ is not None else fingerprint())


def _admin_connect() -> "Connection[tuple[Any, ...]]":
    """Autocommit connection to the cluster's maintenance database."""
    import psycopg

    from server.conf.oxpg.base import cluster_layout
    from server.conf.oxpg.cluster import ROLE, ensure_running

    layout = cluster_layout()
    ensure_running(layout, "postgres")
    return psycopg.connect(
        host=str(layout.socket_dir), user=ROLE, dbname="postgres", autocommit=True
    )


def _build_into(database: str) -> None:
    """Materialise the ship in a separate interpreter bound to ``database``."""
    env: dict[str, str] = dict(os.environ)
    env["OX_PG_DATABASE"] = database
    env["DJANGO_SETTINGS_MODULE"] = "server.conf.settings"
    subprocess.run(
        [sys.executable, "-m", "world.ship_snapshot", "build"],
        cwd=GAME_DIR,
        env=env,
        check=True,
    )


def ensure_template() -> str:
    """Return the current design's template database, building it if absent."""
    from psycopg import sql

    name: str = template_name()
    building: str = name + BUILDING_SUFFIX
    with _admin_connect() as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        rows: list[tuple[Any, ...]] = conn.execute(
            "SELECT datname FROM pg_database WHERE datname LIKE %s", (PREFIX + "%",)
        ).fetchall()
        names: set[str] = {str(row[0]) for row in rows}
        if name not in names:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(building))
            )
            _build_into(building)
            # The rename is the completion marker: a crash leaves only
            # ``*_building``, which the next attempt discards.
            conn.execute(
                sql.SQL("ALTER DATABASE {} RENAME TO {}").format(
                    sql.Identifier(building), sql.Identifier(name)
                )
            )
        for stale in sorted(names - {name}):
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(stale)
                )
            )
    return name


def _build() -> None:
    database: str = os.environ.get("OX_PG_DATABASE", "")
    if not (database.startswith(PREFIX) and database.endswith(BUILDING_SUFFIX)):
        raise SystemExit("build only runs into an ox_ship_*_building database")
    import django

    django.setup()
    from django.core.management import call_command
    from django.db import connection

    if connection.introspection.table_names():
        raise SystemExit(database + " is not empty")
    call_command("migrate", interactive=False, verbosity=0)
    import evennia

    evennia._init()
    from world.ship_world import build_canonical_ship

    build_canonical_ship()
    connection.close()


def main() -> int:
    command: str = sys.argv[1] if len(sys.argv) == 2 else ""
    if command == "build":
        _build()
        return 0
    if command == "ensure":
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")
        import django

        django.setup()
        print(ensure_template())
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
