"""Install the canonical Ox topology and operational proving-ground fixture.

Evennia invokes this hook once on the first complete game-server startup.
The full topology is idempotent and preserves live world state on reruns; the
legacy small fixture remains temporarily because current systems and tests
still depend on its staffed equipment while those subsystems migrate.
"""


def at_initial_setup() -> None:
    """Seed the real hull topology, then the existing operational fixture."""
    from world.bootstrap import build_ship
    from world.ship_world import build_canonical_ship

    build_canonical_ship()
    build_ship()
