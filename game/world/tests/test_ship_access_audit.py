"""Pure G19 full authored traversal-inventory regressions, no crew voyage."""
import unittest

from world.ship_access_audit import (
    ShipAccessAuditError, audit_access_topology, authored_route)
from world.ship_model import ShipWorldModel, SpaceSpec, AccessLinkSpec, load_ship_model


def fixture(broken=False):
    rooms = tuple(SpaceSpec(
        id=name, name=name, kind="room", frame="fixed",
        zone="test", current_condition="serviceable", metadata={})
        for name in ("CMD-PRIMARY", "B", "C", "D"))
    links = [AccessLinkSpec(
        id="AB", from_id="CMD-PRIMARY", to_id="B",
        kind="ordinary", metadata={"pressure_boundary": True}),
        AccessLinkSpec(
        id="BC", from_id="B", to_id="C",
        kind="pressure_hatch", metadata={})]
    if not broken:
        links.append(AccessLinkSpec(
            id="CD", from_id="C", to_id="D",
            kind="ordinary", metadata={}))
    return ShipWorldModel(
        schema_version="ox.ship-world/0.1", model_version="audit-test",
        principal={}, spaces=rooms, access_links=tuple(links))


class AccessTopologyAuditTests(unittest.TestCase):
    def test_both_directions_and_itinerary(self):
        model = fixture()
        audit = audit_access_topology(model, require_connected=True)
        self.assertEqual(audit["spaces"], 4)
        self.assertEqual(audit["physical_links"], 3)
        self.assertEqual(audit["installed_exit_directions_expected"], 6)
        self.assertEqual(audit["reachable_from_command"], 4)
        self.assertEqual(audit["rated_pressure_boundary_labels"], 1)
        self.assertEqual(authored_route(model, "D"), [
            ("CMD-PRIMARY", "AB", "B"), ("B", "BC", "C"), ("C", "CD", "D")])
        self.assertEqual(authored_route(model, "CMD-PRIMARY"), [])

    def test_unreachable_is_reported_and_strict_mode_rejects(self):
        model = fixture(broken=True)
        audit = audit_access_topology(model)
        self.assertEqual(audit["unreachable_from_command"], ["D"])
        self.assertEqual(audit["component_sizes"], [3, 1])
        with self.assertRaises(ShipAccessAuditError):
            audit_access_topology(model, require_connected=True)
        with self.assertRaises(ShipAccessAuditError):
            authored_route(model, "D")

    def test_malformed_link_and_unknown_target_fail(self):
        model = fixture()
        with self.assertRaises(ShipAccessAuditError):
            authored_route(model, "NO-SUCH-COMPARTMENT")
        duplicate = ShipWorldModel(
            schema_version=model.schema_version,
            model_version=model.model_version, principal=model.principal,
            spaces=model.spaces, access_links=model.access_links +
            (model.access_links[0],))
        with self.assertRaises(ShipAccessAuditError):
            audit_access_topology(duplicate)

    def test_full_canonical_geometry_is_indexed(self):
        model = load_ship_model()
        audit = audit_access_topology(model)
        self.assertEqual(audit["spaces"], 421)
        self.assertEqual(audit["physical_links"], 517)
        self.assertEqual(audit["installed_exit_directions_expected"], 1034)
        self.assertEqual(sum(audit["component_sizes"]), 421)
