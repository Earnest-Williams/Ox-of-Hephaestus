"""Install the tiny ship after Evennia creates its initial rooms and account.

Evennia invokes this hook once on the first complete game-server startup.
The builder is also safe to run manually; it never resets existing pump state.
"""


def at_initial_setup() -> None:
    """Seed the playable Ox fixture as part of Evennia's first-run setup."""
    from world.bootstrap import build_ship

    build_ship()
