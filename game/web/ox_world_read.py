"""Developer-scope ``ox.world.read/1`` endpoint.

SKETCH. ``GET /ox/api/v1/world-read/?cursor=...`` for authenticated Developers
only, using the existing terminal's permission gate. Read-only; no mutation
route is added. Add to ``web/urls.py``::

    path("ox/api/v1/world-read/", world_read, name="ox-world-read"),

Status codes: 401/403 from the gate, 409 for a stale or foreign cursor
(restart from page 1), 503 while the ship or physics is not installed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from web.ox_terminal import _deny_non_developer, _locked_response
from world.full_ship_operations import ShipOperationsError
from world.world_read_projection import ProjectionError, StaleCursor
from world.world_read_source import developer_page

MAX_CURSOR_CHARS: int = 1024
View = TypeVar("View", bound=Callable[..., HttpResponse])
# Typed boundary over Django's untyped decorators and the terminal gate.
_get_only: Callable[[View], View] = cast(Callable[[View], View], require_GET)
_no_cache: Callable[[View], View] = cast(Callable[[View], View], never_cache)
_deny: Callable[[HttpRequest], HttpResponse | None] = cast(
    Callable[[HttpRequest], HttpResponse | None], _deny_non_developer
)
_locked: Callable[..., HttpResponse] = cast(
    Callable[..., HttpResponse], _locked_response
)


@_get_only
@_no_cache
def world_read(request: HttpRequest) -> HttpResponse:
    denial: HttpResponse | None = _deny(request)
    if denial is not None:
        return denial
    cursor: str | None = request.GET.get("cursor") or None
    if cursor is not None and len(cursor) > MAX_CURSOR_CHARS:
        return HttpResponse("Cursor too long.", status=400, content_type="text/plain")
    user: Any = request.user
    viewer: str = "developer:" + str(user.pk)
    try:
        page = developer_page(viewer, cursor)
    except StaleCursor:
        return HttpResponse("Stale cursor.", status=409, content_type="text/plain")
    except (ShipOperationsError, ProjectionError):
        return HttpResponse(
            "World read unavailable.", status=503, content_type="text/plain"
        )
    response: HttpResponse = _locked(
        page.model_dump_json(), content_type="application/json"
    )
    return response
