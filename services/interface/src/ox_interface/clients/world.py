"""Typed client for the developer-scope ``ox.world.read/1`` endpoint.

SKETCH. Read-only; the interface never touches the game database. The
developer session cookie is supplied by the operator running the interface.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Final

import orjson
from ox_contracts.world_read_model import DeveloperWorldPage, parse_world_read_page

MAX_PAGES: Final[int] = 64
MAX_RESTARTS: Final[int] = 2
MAX_BODY_BYTES: Final[int] = 4_194_304


class StaleSeries(RuntimeError):
    """The world evicted the publication mid-read."""


@dataclass(frozen=True, slots=True)
class WorldReadClient:
    base_url: str
    session_cookie: str
    timeout_s: float = 10.0

    def _get(self, cursor: str | None) -> DeveloperWorldPage:
        query: str = "?" + urllib.parse.urlencode({"cursor": cursor}) if cursor else ""
        url: str = self.base_url.rstrip("/") + "/ox/api/v1/world-read/" + query
        request: urllib.request.Request = urllib.request.Request(
            url, headers={"Cookie": "sessionid=" + self.session_cookie}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as reply:
                body: bytes = reply.read(MAX_BODY_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                raise StaleSeries("Publication evicted") from exc
            raise
        if len(body) > MAX_BODY_BYTES:
            raise ValueError("Oversized world-read page")
        page = parse_world_read_page(orjson.loads(body))
        if not isinstance(page, DeveloperWorldPage):
            raise PermissionError("Developer endpoint returned an actor page")
        return page

    def _series_once(self) -> tuple[DeveloperWorldPage, ...]:
        pages: list[DeveloperWorldPage] = [self._get(None)]
        while not pages[-1].page.complete and len(pages) < MAX_PAGES:
            page: DeveloperWorldPage = self._get(pages[-1].page.next_cursor)
            if page.publication_seq != pages[0].publication_seq:
                raise StaleSeries("Mixed publications in one series")
            pages.append(page)
        if not pages[-1].page.complete:
            raise RuntimeError("World-read series exceeded its page budget")
        return tuple(pages)

    def snapshot(self) -> tuple[DeveloperWorldPage, ...]:
        for attempt in range(MAX_RESTARTS + 1):
            try:
                return self._series_once()
            except StaleSeries:
                if attempt == MAX_RESTARTS:
                    raise
        raise RuntimeError("unreachable")
