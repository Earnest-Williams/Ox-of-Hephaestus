"""Access and presentation regressions for the developer-only live terminal."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from web.ox_terminal import (
    spatial_state,
    terminal,
    terminal_css,
    terminal_js,
)


class TerminalAccessTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, url, *, authenticated=True, developer=False, superuser=False):
        request = self.factory.get(url)
        request.user = SimpleNamespace(
            is_authenticated=authenticated,
            is_superuser=superuser,
            check_permstring=lambda permission: developer and permission == "Developer",
        )
        return request

    def test_routes_are_in_local_evennia_urlconf(self):
        self.assertEqual(reverse("ox-terminal"), "/ox/console/")
        self.assertEqual(reverse("ox-spatial-state"), "/ox/api/v1/spatial-state/")

    def test_every_endpoint_rejects_anonymous_or_ordinary_account(self):
        for view, url in (
            (terminal, "/ox/console/"),
            (terminal_css, "/ox/console/theme.css"),
            (terminal_js, "/ox/console/live.js"),
            (spatial_state, "/ox/api/v1/spatial-state/"),
        ):
            with self.subTest(view=view.__name__):
                self.assertEqual(
                    view(self._request(url, authenticated=False)).status_code, 401
                )
                self.assertEqual(
                    view(self._request(url, developer=False)).status_code, 403
                )

    def test_developer_gets_existing_wire_renderer_with_live_overlay(self):
        response = terminal(self._request("/ox/console/", developer=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("no-store", response["Cache-Control"])
        html = response.content.decode("utf-8")
        self.assertIn("Ox of Hephaestus", html)
        self.assertIn('id="ship-data"', html)
        self.assertIn('/ox/console/live.js', html)
        self.assertIn('/ox/console/theme.css', html)

    def test_authorised_projection_is_read_only(self):
        snapshot = {
            "schema": "ox.telemetry.spatial/0.1",
            "space_states": [{"id": "CMD-PRIMARY", "condition": "serviceable"}],
        }
        with patch("web.ox_terminal.read_spatial_telemetry", return_value=snapshot):
            response = spatial_state(self._request("/ox/api/v1/spatial-state/", superuser=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json() if hasattr(response, "json") else
                         __import__("json").loads(response.content), snapshot)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            spatial_state(self.factory.post("/ox/api/v1/spatial-state/")).status_code,
            405,
        )

    def test_only_explicit_overlay_assets_are_exposed(self):
        css = terminal_css(self._request("/ox/console/theme.css", developer=True))
        js = terminal_js(self._request("/ox/console/live.js", developer=True))
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertIn(b"ox-live-card", css.content)
        self.assertIn(b"/ox/api/v1/spatial-state/", js.content)
