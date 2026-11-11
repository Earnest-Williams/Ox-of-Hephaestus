"""Installed access evidence: real hatch transitions, traversal and indexed arrival."""

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    arm_continuous_physics, commission_g19_personnel_transfers,
    crew_physical_action, tick_continuous_physics,
)
from world.full_ship_operations import (
    initialize_nominal_atmosphere, install_candidate, install_pressure_cells,
    set_isolator,
)
from world.models import CanonicalShipEvent
from world.ship_access_observations import (
    internal_access_page, load_access_plan,
)
from world.ship_crew_access import traverse_canonical_exit
from world.ship_model import load_ship_model
from world.ship_world import (
    ensure_canonical_ship, find_ship_space, find_world_entity,
)


class InstalledAccessEvidence(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_personnel_transfers(operator_approved=True)
        self.tech = build_ship()["watch"]
        self.model = load_ship_model()
        self.plan = load_access_plan(self.model)

    def action(self, digit, action, target, value):
        return crew_physical_action(
            self.tech, digit * 32, action, target, value)

    def test_world_events_project_real_changes_without_fabricating_movement(self):
        fixed = "ACC-DR-01-LOCK-FIX"
        indexed = "ACC-DR-01-LOCK-ROT"
        self.tech.move_to(find_ship_space("TRUNK-A-DR-01"), quiet=True)
        self.action("1", "hatch", fixed, "open")
        self.action("2", "hatch", fixed, "open")  # receipted no-op
        self.action("3", "hatch", fixed, "closed")  # no traversal
        self.action("4", "hatch", fixed, "open")
        fixed_exit = find_world_entity("access:" + fixed + ":forward")
        lock = find_ship_space("DR-01-SERVICE-LOCK")
        self.assertEqual(traverse_canonical_exit(
            self.tech, fixed_exit, lock, request_id="5" * 32)["status"], "succeeded")
        self.action("6", "hatch", fixed, "closed")
        self.action("7", "rotor", "DR-01", "passenger_extend")
        indexed_exit = find_world_entity("access:" + indexed + ":forward")
        hub = find_ship_space("DR-01-HUB")
        self.assertEqual(traverse_canonical_exit(
            self.tech, indexed_exit, hub, request_id="8" * 32)["status"], "queued")
        # Queued is not an arrival.
        pending = internal_access_page(
            self.model, self.plan, observed_links={fixed, indexed})
        self.assertEqual([r["source_type"] for r in pending["events"]].count(
            "crew_indexed_transfer_complete"), 0)
        for now in (1060, 1120, 1180):
            tick_continuous_physics(now_game_time=now)
        self.assertEqual(self.tech.location, hub)
        page = internal_access_page(
            self.model, self.plan, observed_links={fixed, indexed})
        events = page["events"]
        kinds = [r["source_type"] for r in events]
        self.assertEqual(kinds.count("crew_hatch"), 4)
        self.assertEqual(kinds.count("crew_traverse"), 1)
        self.assertEqual(kinds.count("crew_indexed_transfer_complete"), 1)
        self.assertEqual([r["setting_after"] for r in events
                          if r["kind"] == "hatch_change"],
                         ["open", "closed", "open", "closed"])
        self.assertEqual([r["direction"] for r in events if r["kind"] != "hatch_change"],
                         ["forward", "forward"])
        self.assertTrue(all("actor_dbref" not in r for r in events))
        self.assertEqual(len({r["source_event_id"] for r in events}), len(events))
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="crew_hatch", component_key="access:" + fixed).count(), 5)
        unseen = internal_access_page(
            self.model, self.plan, observed_links=set())
        self.assertEqual(unseen["events"], [])
