"""Django registration for Ox-owned authoritative world records."""
from django.apps import AppConfig
from django.core import checks


def postgresql_only(app_configs, **kwargs):
    """ADR 0010: the journal's commit-ordered sequence and the row locks that
    guard world work exist only on PostgreSQL. Refuse any other backend
    rather than silently losing those guarantees."""
    from django.db import connections

    vendor = connections["default"].vendor
    if vendor == "postgresql":
        return []
    return [checks.Error(
        "Ox requires PostgreSQL; the default database is " + vendor + ".",
        hint="Use the game-managed cluster in server/conf/settings.py (ADR 0010).",
        id="ox.E001",
    )]


class OxWorldConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "world"
    verbose_name = "Ox ship world"

    def ready(self):
        checks.register(postgresql_only)
