"""Real drum-3 contact observations bound to the existing gateway 50 W feeder."""

from __future__ import annotations

from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    _clock, arm_continuous_physics, commission_g19_electrical,
    commission_g19_mind_power, commission_g19_mind_support,
    commission_g19_gateway_power, crew_physical_action,
    survey_g19_gateway_power, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.ship_access_contact import (
    AccessContactError, CABLE, LINK, OBSERVED, SENSOR,
    contact_specifications,
)
from world.ship_access_contact_world import (
    fit_dr03_contact, survey_dr03_contact,
)
from world.ship_model import load_ship_model
from world.models import CanonicalShipState, CanonicalShipEvent
from world.ship_world import ensure_canonical_ship, find_ship_space


class InstalledDrum3AccessContact(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        commission_g19_electrical(operator_approved=True)
        commission_g19_mind_power(operator_approved=True)
        commission_g19_mind_support(operator_approved=True)
        commission_g19_gateway_power(operator_approved=True)
        crew = build_ship()
        self.tech = crew["watch"]
        self.tech.move_to(find_ship_space("TRUNK-A-DR-03"), quiet=True)

        # Bring up the original generating supply and real panel path.
        generator = state("equipment", "GEN-M", lock=True)
        details = dict(generator.details)
        details.update(
            physics_online=True, physics_commanded_on=True, physics_startup_s=0.0)
        generator.details = details
        generator.save(update_fields=["details"])
        set_isolator("ISO-GEN-M", "closed", operator=True)
        graph = defaultdict(list)
        for edge in CanonicalShipState.objects.filter(category="edge"):
            ref = edge.reference
            if ref.get("network") == "power" and edge.setting == "available":
                graph[ref["from_node"]].append((ref["to_node"], edge))
                if ref["kind"] in {"cross_tie", "bridge_feeder"}:
                    graph[ref["to_node"]].append((ref["from_node"], edge))
        previous = {"NODE-GEN-M": None}
        queue = deque(previous)
        while queue:
            parent = queue.popleft()
            for node, edge in graph[parent]:
                if node not in previous:
                    previous[node] = (parent, edge)
                    queue.append(node)
        target = "NODE-LP-BE-05-SVC"
        self.assertIn(target, previous)
        while previous[target] is not None:
            parent, edge = previous[target]
            for isolator_id in edge.reference["isolator_ids"]:
                set_isolator(isolator_id, "closed", operator=True)
            target = parent
        survey_g19_gateway_power(
            operator_approved=True, measured_kw=.05,
            evidence_id="actual-50W-gateway-contact-source",
            thermal_path_verified=True)
        self.advance(1010)
        self.assertTrue(_clock().details["mind_gateway"]["last"]["powered"])

    def advance(self, now):
        while _clock().details["last_game_time"] < now:
            result = tick_continuous_physics(now_game_time=now)
            self.assertTrue(result["advanced"])

    def action(self, digit, value):
        return crew_physical_action(
            self.tech, digit * 32, "hatch", LINK, value)

    def contact_events(self):
        return list(CanonicalShipEvent.objects.filter(
            operation=OBSERVED).order_by("sequence"))

    def survey(self):
        specs = contact_specifications(load_ship_model())
        return survey_dr03_contact(
            operator_approved=True,
            evidence_id="dr3-passive-contact-continuity",
            continuity_verified=True,
            pressure_penetration_ids=specs[
                "edge:" + CABLE]["reference"]["pressure_penetrations"],
        )

    def test_fitted_contact_observes_only_fresh_real_hatch_changes(self):
        self.action("1", "open")  # Unfitted contact must not see the past.
        self.assertEqual(len(self.contact_events()), 0)
        with self.assertRaises(PermissionError):
            fit_dr03_contact()
        self.assertEqual(fit_dr03_contact(operator_approved=True)["created"], 2)
        self.assertEqual(fit_dr03_contact(operator_approved=True)["created"], 0)
        self.action("2", "closed")  # Not surveyed yet.
        self.assertFalse(self.contact_events())
        with self.assertRaises(AccessContactError):
            survey_dr03_contact(
                operator_approved=True, evidence_id="bad",
                continuity_verified=True, pressure_penetration_ids=[])
        self.assertTrue(self.survey()["surveyed"])
        self.assertTrue(self.survey()["idempotent"])
        self.action("3", "open")
        self.action("4", "open")  # No-op, not a contact event.
        self.action("5", "closed")
        hits = self.contact_events()
        self.assertEqual(len(hits), 2)
        self.assertEqual(
            [x.after["setting"] for x in hits], ["open", "closed"])
        self.assertEqual(
            [x.before["setting"] for x in hits], ["closed", "open"])
        self.assertTrue(all(x.actor_dbref is None for x in hits))
        self.assertTrue(all(x.request_id is None for x in hits))
        self.assertEqual(
            [x.source_event_id for x in hits],
            [str(e.sequence) for e in CanonicalShipEvent.objects.filter(
                component_key="access:" + LINK,
                operation="crew_hatch").order_by("sequence") if
             e.before.get("setting") != e.after.get("setting")][-2:])

    def test_fuse_and_damage_stop_capture_without_erasing_history(self):
        fit_dr03_contact(operator_approved=True)
        self.survey()
        self.action("6", "open")
        self.assertEqual(len(self.contact_events()), 1)
        set_isolator("ISO-PWR-GW-LCS-DR-03", "open", operator=True)
        self.action("7", "closed")
        self.assertEqual(len(self.contact_events()), 1)
        set_isolator("ISO-PWR-GW-LCS-DR-03", "closed", operator=True)
        self.advance(1020)
        # The changed fuse revision invalidates the gateway's earlier survey.
        self.action("8", "open")
        self.assertEqual(len(self.contact_events()), 1)
        set_component_condition("edge", CABLE, "severed", operator=True)
        self.action("9", "closed")
        self.assertEqual(len(self.contact_events()), 1)
        self.assertFalse(self.survey_if_fitted_and_broken())
        self.assertEqual(fit_dr03_contact(operator_approved=True)["created"], 0)
        self.assertEqual(len(self.contact_events()), 1)

    def survey_if_fitted_and_broken(self):
        try:
            self.survey()
        except AccessContactError:
            return False
        return True
