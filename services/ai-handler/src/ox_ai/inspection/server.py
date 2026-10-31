"""Loopback, read-only HTTP for ``ox.handler.inspect/1``.

SKETCH. Standard library only, so the handler keeps no web framework:

    python -m ox_ai.inspection.server \\
        --state .ox-state/p4e-supervisor.json --grants ~/.config/ox/grants.json

``GET /v1/characters/<dbref>/epistemics`` with ``Authorization: Bearer <t>``.
Binds 127.0.0.1 only. It reads the checkpoint file the supervisor writes
atomically; it shares no memory with, and cannot signal, the supervisor.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, Final

from pydantic import ValidationError

from ox_ai.inspection.authorization import Grant, authorize, load_grants
from ox_ai.inspection.authorization import resolve_token
from ox_ai.inspection.projection import InspectionUnavailable, inspection_page

ROUTE_PREFIX: Final[str] = "/v1/characters/"
ROUTE_SUFFIX: Final[str] = "/epistemics"
MAX_DBREF_CHARS: Final[int] = 17


def character_from_path(path: str) -> str | None:
    if not (path.startswith(ROUTE_PREFIX) and path.endswith(ROUTE_SUFFIX)):
        return None
    candidate: str = path[len(ROUTE_PREFIX) : -len(ROUTE_SUFFIX)]
    digits: str = candidate[1:]
    if (
        candidate.startswith("#")
        and 2 <= len(candidate) <= MAX_DBREF_CHARS
        and digits.isdigit()
        and digits[0] != "0"
    ):
        return candidate
    return None


class InspectionHandler(BaseHTTPRequestHandler):
    state_path: ClassVar[Path]
    grants: ClassVar[dict[str, Grant]]

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        # Percent-encoded "#": the client sends %23; decode only that.
        path: str = self.path.split("?", 1)[0].replace("%23", "#")
        character: str | None = character_from_path(path)
        header: str = self.headers.get("Authorization", "")
        token: str = header[7:] if header.startswith("Bearer ") else ""
        not_found: bytes = b"Not found."
        if character is None:
            self._send(HTTPStatus.NOT_FOUND, not_found, "text/plain")
            return
        try:
            authorize(resolve_token(token, self.grants), character)
            page = inspection_page(self.state_path.read_bytes(), character)
        except InspectionUnavailable:
            self._send(HTTPStatus.NOT_FOUND, not_found, "text/plain")
            return
        except (OSError, ValidationError, KeyError, TypeError, ValueError):
            self._send(
                HTTPStatus.SERVICE_UNAVAILABLE, b"Checkpoint unreadable.", "text/plain"
            )
            return
        self._send(
            HTTPStatus.OK, page.model_dump_json().encode("utf-8"), "application/json"
        )

    def log_message(self, format: str, *args: object) -> None:
        return  # never log tokens or paths with private identifiers


def serve(state: Path, grants: Path, port: int) -> None:
    InspectionHandler.state_path = state
    InspectionHandler.grants = load_grants(grants)
    with ThreadingHTTPServer(("127.0.0.1", port), InspectionHandler) as server:
        server.serve_forever()


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--grants", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8711)
    args: argparse.Namespace = parser.parse_args()
    state_path: Path = args.state
    grants_path: Path = args.grants
    port: int = args.port
    serve(state_path, grants_path.expanduser(), port)


if __name__ == "__main__":
    main()
