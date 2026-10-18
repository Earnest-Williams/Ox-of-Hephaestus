"""Required Evennia server lifecycle hook placeholders.

No simulation tick, external AI process or pump automation starts here yet.
"""


def at_server_init() -> None:
    """Called before each server start."""


def at_server_start() -> None:
    """Called on each server start."""


def at_server_stop() -> None:
    """Called before shutdown or reload."""


def at_server_reload_start() -> None:
    """Called before a hot reload."""


def at_server_reload_stop() -> None:
    """Called after a hot reload."""


def at_server_cold_start() -> None:
    """Called after a cold start."""


def at_server_cold_stop() -> None:
    """Called before a cold shutdown."""
