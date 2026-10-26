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
        self.locks.add("traverse:all()")
        self.db.ox_integration_state = "live_world_gated"

    def at_traverse(self, traversing_object, target_location, **kwargs):
        if self.db.ox_access_kind == "development_entry":
            if traversing_object.check_permstring("Developer"):
                return super().at_traverse(traversing_object, target_location, **kwargs)
            traversing_object.msg("Development boarding is restricted to operators.")
            return
        from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
        try:
            result = traverse_canonical_exit(traversing_object, self, target_location)
            if result.get("status") == "queued":
                traversing_object.msg(
                    f"Indexed personnel transfer engaged: {result['travel_seconds']:.0f}"
                    " game-seconds at the rated station. Remain aboard until arrival.")
        except (CrewTransitError, PermissionError) as exc:
            traversing_object.msg(str(exc))


class ShipWorldRoot(DefaultObject):
    """Unlocated anchor recording which prepared topology has been deployed."""

    def at_object_creation(self) -> None:
        super().at_object_creation()
        self.locks.add("get:false();drop:false();view:perm(Developer)")
