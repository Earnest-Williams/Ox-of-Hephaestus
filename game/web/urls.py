"""Ox developer terminal alongside the unchanged stock Evennia website."""

from django.urls import path

from evennia.web.urls import urlpatterns as stock_urlpatterns

from web.ox_terminal import spatial_state, terminal, terminal_css, terminal_js

urlpatterns = [
    path("ox/console/", terminal, name="ox-terminal"),
    path("ox/console/theme.css", terminal_css, name="ox-terminal-css"),
    path("ox/console/live.js", terminal_js, name="ox-terminal-js"),
    path("ox/api/v1/spatial-state/", spatial_state, name="ox-spatial-state"),
    *stock_urlpatterns,
]
