"""Evennia server service that remembers why it is going down (ADR 0010).

Evennia calls ``at_server_cold_stop`` for both a ``shutdown`` and a ``reset``,
without saying which. After a reset the Portal starts a replacement Server at
once (Evennia does this after every first-start initial setup), so stopping
the game's database then would cut off the new process mid-startup. This
subclass records the mode so the hook can keep the database running across a
reset.
"""

from __future__ import annotations

from typing import Any

from evennia.server.service import EvenniaServerService

RESET: str = "reset"


class OxServerService(EvenniaServerService):  # type: ignore[misc]
    shutdown_mode: str | None = None

    def shutdown(self, mode: str = "reload", _reactor_stopping: bool = False) -> Any:
        # The reactor's own "before shutdown" trigger calls back in with
        # ``_reactor_stopping`` once the real shutdown is under way; keep the
        # mode that started it.
        if not _reactor_stopping:
            self.shutdown_mode = mode
        return super().shutdown(mode=mode, _reactor_stopping=_reactor_stopping)


def restarting_after_reset() -> bool:
    """True while the running Server shuts down only to be restarted."""
    import evennia

    service: object = getattr(evennia, "EVENNIA_SERVER_SERVICE", None)
    return getattr(service, "shutdown_mode", None) == RESET
