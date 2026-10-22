"""Developer-only Ox wire terminal and narrowly scoped world telemetry.

Evennia's stock website and webclient remain unchanged. This endpoint serves
the existing standalone wire renderer with a separate live overlay; it never
publishes the source file or world state to anonymous visitors.
"""

from __future__ import annotations

from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.http import require_GET

from world.ship_model import canonical_model_path
from world.ship_telemetry import read_spatial_telemetry

WIRE_NAME = "Ox_Ship_Wire_Render_v0.4.html"


def _deny_non_developer(request):
    """Reject anonymous and non-Developer sessions before reading any data."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return HttpResponse("Authentication required.", status=401, content_type="text/plain")
    checker = getattr(user, "check_permstring", None)
    allowed = bool(
        getattr(user, "is_superuser", False)
        or (callable(checker) and checker("Developer"))
    )
    if not allowed:
        return HttpResponse("Developer permission required.", status=403, content_type="text/plain")
    return None


def _locked_response(content, *, content_type):
    response = HttpResponse(content, content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response


@require_GET
@never_cache
@xframe_options_deny
def terminal(request):
    """Serve the unchanged drawing code plus separately maintained overlays."""
    denial = _deny_non_developer(request)
    if denial is not None:
        return denial

    html = canonical_model_path().with_name(WIRE_NAME).read_text(encoding="utf-8")
    closing = "</body>"
    if closing not in html:
        return HttpResponse("Wire source missing body terminator.", status=500)

    stylesheet = reverse("ox-terminal-css")
    script = reverse("ox-terminal-js")
    injection = (
        f'<link rel="stylesheet" href="{stylesheet}">'
        f'<script src="{script}" defer></script>'
    )
    return _locked_response(
        html.replace(closing, injection + closing, 1),
        content_type="text/html; charset=utf-8",
    )


def _asset(request, name: str, content_type: str):
    denial = _deny_non_developer(request)
    if denial is not None:
        return denial
    path = Path(__file__).resolve().with_name(name)
    return _locked_response(path.read_text(encoding="utf-8"), content_type=content_type)


@require_GET
@never_cache
def terminal_css(request):
    """Styling for the authenticated live overlay only."""
    return _asset(request, "ox_terminal.css", "text/css; charset=utf-8")


@require_GET
@never_cache
def terminal_js(request):
    """Browser-side read-only state overlay on the existing Canvas renderer."""
    return _asset(request, "ox_terminal.js", "text/javascript; charset=utf-8")


@require_GET
@never_cache
def spatial_state(request):
    """Export only the canonical room conditions the developer can inspect."""
    denial = _deny_non_developer(request)
    if denial is not None:
        return denial
    response = JsonResponse(read_spatial_telemetry())
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    return response
