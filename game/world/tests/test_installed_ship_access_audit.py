"""G19 complete installed-room and bidirectional-exit audit.

The authoritative room/exit objects are inspected without permitting passage:
live differential pressure, casualties and powered indexers remain governed by
the crew transit preflight, not by this topology audit.
"""
from evennia.utils.test_resources import EvenniaTestCase

from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.ship_access_audit import audit_access_topology


class InstalledFullShipAccessAudit(EvenniaTestCase):
    def test_all_rooms_and_both_exits_match_authored_model(self):
        built = build_canonical_ship()
        model = built["model"]
        audit = audit_access_topology(model)
        self.assertEqual(len(model.spaces), 421)
        self.assertEqual(len(model.access_links), 517)
        self.assertEqual(audit["installed_exit_directions_expected"], 1034)
        for spec in model.spaces:
            with self.subTest(room=spec.id):
                room = find_ship_space(spec.id)
                self.assertIsNotNone(room)
                self.assertEqual(room.db.ox_space_id, spec.id)
                self.assertEqual(room.db.ox_frame, spec.frame)
                self.assertEqual(room.db.ox_zone, spec.zone)
        for spec in model.access_links:
            for direction, source, target in (
                ("forward", spec.from_id, spec.to_id),
                ("reverse", spec.to_id, spec.from_id),
            ):
                with self.subTest(link=spec.id, direction=direction):
                    obj = find_world_entity(f"access:{spec.id}:{direction}")
                    self.assertIsNotNone(obj)
                    self.assertEqual(obj.location, find_ship_space(source))
                    self.assertEqual(obj.destination, find_ship_space(target))
                    self.assertEqual(obj.db.ox_access_link_id, spec.id)
                    self.assertEqual(obj.db.ox_access_direction, direction)
                    self.assertEqual(obj.db.ox_access_kind, spec.kind)
                    self.assertEqual(obj.db.ox_integration_state,
                                     "live_world_gated")

    def test_rebuild_does_not_wipe_damage_or_duplicate_exits(self):
        original = build_canonical_ship()
        sample = original["model"].access_links[0]
        forward = find_world_entity(f"access:{sample.id}:forward")
        original_pk = forward.pk
        room = find_ship_space(sample.from_id)
        room.db.ox_current_condition = "smoke-damaged"
        rebuilt = build_canonical_ship()
        self.assertEqual(rebuilt["created_spaces"], 0)
        self.assertEqual(rebuilt["created_accesses"], 0)
        self.assertEqual(find_world_entity(
            f"access:{sample.id}:forward").pk, original_pk)
        self.assertEqual(find_ship_space(sample.from_id).db.ox_current_condition,
                         "smoke-damaged")
