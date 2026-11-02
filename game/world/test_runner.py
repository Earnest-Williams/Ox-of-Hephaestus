"""Run Ox game tests with the GAME's Django application registry.

The plain `evennia test` launcher intentionally substitutes
`evennia.settings_default`, which cannot contain the Ox world journal model.
This runner does not modify upstream Evennia or any deployment settings.

From game/: python -m world.test_runner world.tests.test_ship --verbosity=2

``--prebuilt-ship`` clones the test database from the installed ship built
once per design (``world.ship_snapshot``) instead of an empty migrated one.
Use it only when every selected test runs on the canonical installed ship.
"""

from __future__ import annotations

import os
import sys

PREBUILT_FLAG: str = "--prebuilt-ship"
SCHEMA_PROBE_TABLE: str = "server_serverconfig"


def _migrate_empty_game_database() -> None:
    """Give the game database a schema before Evennia first imports.

    ``evennia._init()`` imports ``evennia.utils.gametime``, which reads
    ServerConfig from the game database (not the test database) and only
    tolerates SQLite's error for a missing table. On PostgreSQL a fresh
    checkout would fail before any test ran, so migrate it once (seconds).
    """
    from django.core.management import call_command
    from django.db import connection

    if SCHEMA_PROBE_TABLE in connection.introspection.table_names():
        return
    print("Migrating the empty game database " + str(connection.settings_dict["NAME"]))
    call_command("migrate", interactive=False, verbosity=0)
    connection.close()


def main() -> None:
    os.environ["DJANGO_SETTINGS_MODULE"] = "server.conf.settings"
    arguments: list[str] = sys.argv[1:]
    prebuilt: bool = PREBUILT_FLAG in arguments
    arguments = [argument for argument in arguments if argument != PREBUILT_FLAG]
    import django

    django.setup()

    if prebuilt:
        from django.db import connections

        from world.ship_snapshot import ensure_template

        template: str = ensure_template()
        connections["default"].settings_dict["TEST"]["TEMPLATE"] = template
        print("Test database cloned from prebuilt ship " + template)

    _migrate_empty_game_database()
    import evennia

    evennia._init()

    from django.core.management import execute_from_command_line

    execute_from_command_line(["ox-game-test", "test", *arguments])


if __name__ == "__main__":
    main()
