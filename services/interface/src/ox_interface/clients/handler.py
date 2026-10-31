"""Typed client for the handler's ``ox.handler.inspect/1`` loopback API.

SKETCH. The interface holds one bearer token. With a character grant it can
read only that character; a refusal looks exactly like "no such character".
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Final

from ox_contracts.handler_inspection import InspectionPage, parse_inspection_json

MAX_BODY_BYTES: Final[int] = 1_048_576


@dataclass(frozen=True, slots=True)
class HandlerInspectionClient:
    base_url: str
    token: str
    timeout_s: float = 5.0

    def epistemics(self, character_id: str) -> InspectionPage | None:
        """None means not found *or* not authorized; the API does not say which."""
        path: str = (
            "/v1/characters/"
            + urllib.parse.quote(character_id, safe="")
            + "/epistemics"
        )
        request: urllib.request.Request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            headers={"Authorization": "Bearer " + self.token},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as reply:
                body: bytes = reply.read(MAX_BODY_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        if len(body) > MAX_BODY_BYTES:
            raise ValueError("Oversized inspection page")
        page: InspectionPage = parse_inspection_json(body)
        if page.character_id != character_id:
            raise PermissionError("Inspection returned another character")
        return page
