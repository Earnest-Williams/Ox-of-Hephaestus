"""Database-backed tests for canonical topology materialisation."""

from __future__ import annotations

from evennia.utils.test_resources import EvenniaTestCase

from world.ship_model import AccessLinkSpec, ShipWorldModel, SpaceSpec
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity


class CanonicalShipWorldTests(EvenniaTestCase):
    def _model(self) -> ShipWorldModel:
        return ShipWorldModel(
            schema_version="ox.ship-world/0.1",
            model_version="test-v1",
            principal={"name": "Ox test hull"},
            spaces=(
                SpaceSpec(
                    id="A",
                    name="Test Forward",
                    kind="compartment",
                    frame="fixed",
                    zone="test",
                    current_condition="serviceable",
                    metadata={"damage_control_sector": "test-forward"},
                ),
                SpaceSpec(
                    id="B",
                    name="Test Aft",
                    kind="compartment",
                    frame="fixed",
                    zone="test",
                    current_condition="serviceable",
                    metadata={},
                ),
            ),
            access_links=(
                AccessLinkSpec(
                    id="AB",
                    from_id="A",
                    to_id="B",
                    kind="pressure_hatch",
                    metadata={},
                ),
            ),
        )

    def test_materialises_persistent_rooms_and_bidirectional_access(self):
        built = build_canonical_ship(self._model())
        room_a = find_ship_space("A")
        room_b = find_ship_space("B")
        self.assertIsNotNone(room_a)
        self.assertIsNotNone(room_b)
        self.assertEqual(room_a.db.ox_damage_control_sector, "test-forward")
        self.assertEqual(room_a.db.ox_current_condition, "serviceable")

        forward = find_world_entity("access:AB:forward")
        reverse = find_world_entity("access:AB:reverse")
        self.assertEqual(forward.location, room_a)
        self.assertEqual(forward.destination, room_b)
        self.assertEqual(reverse.location, room_b)
        self.assertEqual(reverse.destination, room_a)
        self.assertEqual(forward.db.ox_integration_state, "developer_topology_only")
        self.assertEqual(built["created_spaces"], 2)
        self.assertEqual(built["created_accesses"], 2)

    def test_rerun_preserves_live_condition_and_object_identity(self):
        first = build_canonical_ship(self._model())
        room = first["spaces"]["A"]
        room.db.ox_current_condition = "smoke-damaged"
        second = build_canonical_ship(self._model())
        self.assertEqual(second["spaces"]["A"].id, room.id)
        self.assertEqual(second["spaces"]["A"].db.ox_current_condition, "smoke-damaged")
        self.assertEqual(second["created_spaces"], 0)
        self.assertEqual(second["created_accesses"], 0)

    def test_rebuild_preserves_both_access_object_identities(self):
        build_canonical_ship(self._model())
        original_forward = find_world_entity("access:AB:forward").id
        original_reverse = find_world_entity("access:AB:reverse").id
        build_canonical_ship(self._model())
        self.assertEqual(find_world_entity("access:AB:forward").id, original_forward)
        self.assertEqual(find_world_entity("access:AB:reverse").id, original_reverse)
