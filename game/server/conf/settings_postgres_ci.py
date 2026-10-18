"""Explicitly opt-in PostgreSQL settings for disposable CI concurrency tests.

Not for production use. This never replaces the local SQLite configuration:
only the G1 contention workflow selects this module, and it refuses to load
without its separate opt-in environment variable.
"""
from __future__ import annotations

import os
from .settings import *  # noqa: F401,F403

if os.environ.get("OX_PG_CONCURRENCY_TEST") != "1":
    raise RuntimeError("PostgreSQL CI settings require OX_PG_CONCURRENCY_TEST=1")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["OX_CI_PG_DATABASE"],
        "USER": os.environ["OX_CI_PG_USER"],
        "PASSWORD": os.environ["OX_CI_PG_PASSWORD"],
        "HOST": os.environ["OX_CI_PG_HOST"],
        "PORT": os.environ["OX_CI_PG_PORT"],
        "CONN_MAX_AGE": 0,
        "OPTIONS": {"connect_timeout": 5},
    }
}
