"""Actor-scope ``ox.world.read/1`` over the character's own socket.

SKETCH. Usage: ``oxworldread <32-hex-nonce> [cursor]``

The session's puppet is the only actor; no character, room or scope argument
is accepted. The reply is one OOB ``ox_world_read`` frame carrying a JSON
envelope ``{"nonce": ..., "status": ..., "page": ...}`` so the handler can
bind the reply to its challenge (the page model itself forbids extra keys).
Register in ``commands/default_cmdsets.py`` beside ``oxcapabilities``.

The producer and its dependencies (``game/requirements-ox.txt``) load on
first use, so a server without them still boots and replies "unavailable".
"""

from __future__ import annotations

from typing import Any

from evennia.commands.command import Command

from world.full_ship_operations import ShipOperationsError

NONCE_HEX: int = 32


def _valid_nonce(value: str) -> bool:
    return len(value) == NONCE_HEX and all(c in "0123456789abcdef" for c in value)


class CmdOxWorldRead(Command):
    """Return this character's legitimately observed world page."""

    key = "oxworldread"
    locks = "cmd:all()"
    # Set by Evennia's command handler before func(); declared for mypy.
    args: str
    caller: Any

    def func(self) -> None:
        parts: list[str] = str(self.args).split()
        if not 1 <= len(parts) <= 2 or not _valid_nonce(parts[0]):
            self.caller.msg("Usage: oxworldread <32 lowercase hex nonce> [cursor]")
            return
        nonce: str = parts[0]
        cursor: str | None = parts[1] if len(parts) == 2 else None
        try:
            import orjson

            from world.world_read_projection import ProjectionError, StaleCursor
            from world.world_read_source import actor_page
        except ImportError:
            # Without orjson the reply is still well-formed JSON.
            self.caller.msg(
                ox_world_read=(
                    ['{"nonce": "%s", "status": "unavailable", "page": null}' % nonce],
                    {},
                )
            )
            return
        envelope: dict[str, Any]
        try:
            page = actor_page(self.caller, cursor)
            envelope = {
                "nonce": nonce,
                "status": "ok",
                "page": page.model_dump(mode="json"),
            }
        except StaleCursor:
            envelope = {"nonce": nonce, "status": "stale_cursor", "page": None}
        except (ShipOperationsError, ProjectionError):
            envelope = {"nonce": nonce, "status": "unavailable", "page": None}
        payload: str = orjson.dumps(envelope).decode("utf-8")
        self.caller.msg(ox_world_read=([payload], {}))
