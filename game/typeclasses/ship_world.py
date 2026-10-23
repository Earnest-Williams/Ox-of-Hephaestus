"""Typeclasses for the canonical full-ship topology integration."""

from __future__ import annotations

from evennia.objects.objects import DefaultExit, DefaultObject

from typeclasses.ship import ShipRoom


class CanonicalShipRoom(ShipRoom):
    """A physical space loaded from the canonical current-installation model."""


class CanonicalShipAccess(DefaultExit):
    """A physical access link whose operational interlocks are not wired yet.

    Stage-one topology is intentionally Developer-only. Later integration can
    replace this conservative lock with pressure, machinery, EVA, indexing and
    permission checks without rebuilding the room graph.
    """

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.locks.add("traverse:perm(Developer)")
        self.db.ox_integration_state = "developer_topology_only"


class ShipWorldRoot(DefaultObject):
    """Unlocated anchor recording which prepared topology has been deployed."""

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.locks.add("get:false();drop:false();view:perm(Developer)")
