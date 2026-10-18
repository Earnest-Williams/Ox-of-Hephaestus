"""Run Ox game tests with the GAME's Django application registry.

The plain `evennia test` launcher intentionally substitutes
`evennia.settings_default`, which cannot contain the Ox world journal model.
This runner does not modify upstream Evennia or any deployment settings.

From game/: python -m world.test_runner world.tests.test_ship --verbosity=2
"""
from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ["DJANGO_SETTINGS_MODULE"] = "server.conf.settings"
    import django
    django.setup()

    import evennia
    evennia._init()

    from django.core.management import execute_from_command_line
    execute_from_command_line(["ox-game-test", "test", *sys.argv[1:]])


if __name__ == "__main__":
    main()
