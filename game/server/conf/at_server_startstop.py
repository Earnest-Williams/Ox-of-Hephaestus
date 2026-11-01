"""Required Evennia server lifecycle hooks for persistent Ox world services."""


def at_server_init() -> None:
    """Called before each server start."""


def at_server_start() -> None:
    """Ensure canonical topology and persistent world-owned clocks exist."""
    from world.live_clock import ensure_clock_script
    from world.ship_world import ensure_canonical_ship
    from world.terminal_failure import ensure_terminal_clock

    ensure_canonical_ship()
    ensure_clock_script()
    ensure_terminal_clock()
    from world.continuous_ship_physics import ensure_continuous_physics_clock
    ensure_continuous_physics_clock()


def at_server_stop() -> None:
    """Called before shutdown or reload."""


def at_server_reload_start() -> None:
    """Called before a hot reload."""


def at_server_reload_stop() -> None:
    """Called after a hot reload."""


def at_server_cold_start() -> None:
    """Called after a cold start."""


def at_server_cold_stop() -> None:
    """Called before a cold shutdown: stop the game's private database last.

    Evennia keeps writing after this hook (ticker and on-demand state, final
    runtime), so the database stops only once the reactor has shut down. A
    reload never reaches here and keeps it running. Any later connection
    (``evennia shell``, tests) starts it again on demand.
    """
    from twisted.internet import reactor

    def stop_database() -> None:
        from django.db import connections

        from server.conf.oxpg.base import cluster_layout
        from server.conf.oxpg.cluster import stop

        connections.close_all()
        stop(cluster_layout())

    reactor.addSystemEventTrigger("after", "shutdown", stop_database)
