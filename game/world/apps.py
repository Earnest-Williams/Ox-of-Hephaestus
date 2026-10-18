"""Django registration for Ox-owned authoritative world records."""
from django.apps import AppConfig


class OxWorldConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "world"
    verbose_name = "Ox ship world"
