"""Installed authenticated access history over the actual drum-3 A/B fibre.

The source is a real attended hatch action. An unsurveyed, dark or isolated
reader never gains access to an account merely because the world knows truth.
"""

from __future__ import annotations

from collections import defaultdict, deque
from types import SimpleNamespace

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    _clock, arm_continuous_physics, commission_g19_electrical,
    commission_g19_mind_power, commission_g19_mind_support,
    commission_g19_gateway_power, crew_physical_action,
    survey_g19_gateway_power, survey_g19_data_path,
    survey_g19_mind_cooling, tick_continuous_physics,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    load_candidate, set_component_condition, set_isolator, state,
)
from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_access_contact import CABLE, LINK, OBSERVED, contact_specifications
from world.ship_access_contact_world import fit_dr03_contact, survey_dr03_contact
from world.ship_mind_power import load_design
from world.ship_mind_support import data_penetrations, load_support
from world.ship_network_access import DELIVERED, NetworkAccessError, PRINCIPAL
from world.ship_network_access_world import (
    access_page, acknowledge_page, enroll_access_account, network_reachable,
)
from world.ship_model import load_ship_model
from world.ship_world import ensure_canonical_ship, find_ship_space


class InstalledNetworkAccessDelivery(EvenniaTestCase):
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
        self.tech = build_ship()["watch"]
        self.tech.move_to(find_ship_space("TRUNK-A-DR-03"), quiet=True)

        # One measured generating supply, its original local panel, and the
        # *independent* selected A input to each of the five compute islands.
        generator = state("equipment", "GEN-M", lock=True)
        generator.details = dict(generator.details, physics_online=True,
                                 physics_commanded_on=True, physics_startup_s=0.0)
        generator.save(update_fields=["details"])
        set_isolator("ISO-GEN-M", "closed", operator=True)
        graph = defaultdict(list)
        for edge in CanonicalShipState.objects.filter(category="edge"):
            reference = edge.reference
            if reference.get("network") == "power" and edge.setting == "available":
                graph[reference["from_node"]].append((reference["to_node"], edge))
                if reference["kind"] in {"cross_tie", "bridge_feeder"}:
                    graph[reference["to_node"]].append((reference["from_node"], edge))
        route = {"NODE-GEN-M": None}
        queue = deque(route)
        while queue:
            from_node = queue.popleft()
            for to_node, edge in graph[from_node]:
                if to_node not in route:
                    route[to_node] = (from_node, edge)
                    queue.append(to_node)
        destination = "NODE-LP-BE-05-SVC"
        self.assertIn(destination, route)
        while route[destination] is not None:
            source, edge = route[destination]
            for isolator in edge.reference["isolator_ids"]:
                set_isolator(isolator, "closed", operator=True)
            destination = source
        for island in load_design()["islands"]:
            feed = next(x for x in island["inputs"] if x["source"] == "A")
            for item in feed["route_domains"]:
                if item.startswith("ISO-") and state("isolator", item).setting != "closed":
                    set_isolator(item, "closed", operator=True)
        survey_g19_gateway_power(
            operator_approved=True, measured_kw=.05,
            evidence_id="real-50W-network-access-input", thermal_path_verified=True,
        )

        # Candidate fibres are not live until each fitted conductor is surveyed,
        # including moving pressure-qualified rotary joints.
        ship = load_candidate()
        for row in CanonicalShipState.objects.filter(
                source_model="ox.ship-support/1").order_by("source_id"):
            # This source model also owns the commissioned gateway's power
            # feeder and thermal mounting strap; only mind_data conductors
            # and continuous rotary optical joints can be continuity-surveyed.
            if (row.reference.get("network") == "mind_data"
                    and (row.category == "edge"
                         or row.source_id in {"NET-ROT-A", "NET-ROT-B"})):
                survey_g19_data_path(
                    operator_approved=True,
                    component_id=row.source_id,
                    evidence_id="net-delivery-physical-" + row.source_id,
                    penetration_ids=data_penetrations(row.reference, ship),
                    continuity_verified=True, pressure_verified=True,
                    environment_verified=True, emi_verified=True,
                    continuous_rpm=3.6 if row.category == "equipment" else None,
                )
        for pod in load_support()["cooling_islands"]:
            survey_g19_mind_cooling(
                operator_approved=True,
                buffer_id=pod["independent_buffer_id"],
                capacity_kj=720, free_kj=720,
            )
        self.advance(1010)
        self.assertTrue(_clock().details["mind_gateway"]["last"]["powered"])
        self.assertTrue(_clock().details["mind_gateway"]["last"]["connected"])
        self.assertTrue(network_reachable(_clock()))
        self.assertEqual(fit_dr03_contact(operator_approved=True)["created"], 2)
        specs = contact_specifications(load_ship_model())
        survey_dr03_contact(
            operator_approved=True, evidence_id="contact-ground-truth",
            continuity_verified=True,
            pressure_penetration_ids=specs[
                "edge:" + CABLE]["reference"]["pressure_penetrations"],
        )

    def advance(self, now):
        while _clock().details["last_game_time"] < now:
            result = tick_continuous_physics(now_game_time=now)
            self.assertTrue(result["advanced"])

    def action(self, digit, value):
        receipt = crew_physical_action(
            self.tech, digit * 32, "hatch", LINK, value)
        self.assertEqual(receipt["status"], "succeeded")

    def local(self):
        return list(CanonicalShipEvent.objects.filter(
            operation=OBSERVED).order_by("sequence"))

    def deliveries(self):
        return list(CanonicalShipEvent.objects.filter(
            operation=DELIVERED, component_key=PRINCIPAL).order_by("sequence"))

    def enroll(self):
        return enroll_access_account(
            self.account, operator_approved=True)

    def test_account_bound_pages_replay_until_ack_and_hide_world_identity(self):
        with self.assertRaises(PermissionError):
            enroll_access_account(self.account)
        with self.assertRaises(NetworkAccessError):
            access_page(self.account)
        self.assertTrue(self.enroll()["enrolled"])
        self.assertFalse(self.enroll()["enrolled"])
        self.action("1", "open")
        self.action("2", "open")  # No state change.
        self.action("3", "closed")
        self.assertEqual(len(self.local()), 2)
        self.assertEqual(len(self.deliveries()), 2)
        page1 = access_page(self.account, limit=1)
        self.assertTrue(page1["has_more"])
        self.assertEqual(len(page1["events"]), 1)
        self.assertEqual(page1, access_page(self.account, limit=1))
        self.assertNotIn("actor_dbref", page1["events"][0])
        self.assertEqual(page1["events"][0]["kind"], "hatch_change")
        self.assertEqual(page1["events"][0]["setting_after"], "open")
        with self.assertRaises(NetworkAccessError):
            acknowledge_page(self.account, "v1.2." + "0" * 64)
        denied = SimpleNamespace(pk=self.account.pk)
        with self.assertRaises(NetworkAccessError):
            access_page(denied)
        self.assertTrue(acknowledge_page(
            self.account, page1["ack_token"])["acknowledged"])
        self.assertTrue(acknowledge_page(
            self.account, page1["ack_token"])["idempotent"])
        second = access_page(self.account)
        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(second["events"][0]["setting_after"], "closed")
        self.assertTrue(acknowledge_page(
            self.account, second["ack_token"])["acknowledged"])
        self.assertEqual(access_page(self.account)["events"], [])
        principal = CanonicalShipState.objects.get(pk=PRINCIPAL)
        self.assertEqual(
            principal.details["acked_sequence"],
            self.deliveries()[-1].sequence)

    def test_network_fault_does_not_buffer_local_events_for_reconnect(self):
        self.enroll()
        self.action("4", "open")
        self.assertEqual(len(self.deliveries()), 1)
        set_component_condition(
            "edge", "NET-GW-DROP-A-DR-03", "severed", operator=True)
        set_component_condition(
            "edge", "NET-GW-DROP-B-DR-03", "severed", operator=True)
        self.assertFalse(network_reachable(_clock()))
        self.action("5", "closed")
        self.assertEqual(len(self.local()), 2)
        self.assertEqual(len(self.deliveries()), 1)
        with self.assertRaises(NetworkAccessError):
            access_page(self.account)
        # Even nominal repairs do not recreate *surveyed* continuity.
        set_component_condition(
            "edge", "NET-GW-DROP-A-DR-03", "serviceable", operator=True)
        set_component_condition(
            "edge", "NET-GW-DROP-B-DR-03", "serviceable", operator=True)
        for name in ("NET-GW-DROP-A-DR-03", "NET-GW-DROP-B-DR-03"):
            row = state("edge", name)
            survey_g19_data_path(
                operator_approved=True, component_id=name,
                evidence_id="resurvey-restored-" + name,
                penetration_ids=data_penetrations(row.reference, load_candidate()),
                continuity_verified=True, pressure_verified=True,
                environment_verified=True, emi_verified=True,
                continuous_rpm=None,
            )
        self.advance(1020)
        self.assertTrue(network_reachable(_clock()))
        self.action("6", "open")
        self.assertEqual(len(self.deliveries()), 2)
        page = access_page(self.account)
        self.assertEqual(
            [x["setting_after"] for x in page["events"]],
            ["open", "open"])
        self.assertEqual(len(self.local()), 3)

    def test_core_power_break_between_ticks_stops_delivery(self):
        self.enroll()
        self.action("7", "open")
        self.assertEqual(len(self.deliveries()), 1)
        # Isolate all five island grid inputs. Gateway retains its local
        # 50 W supply; stale previous-tick "compute_ready" must not deliver.
        for island in load_design()["islands"]:
            a = next(x for x in island["inputs"] if x["source"] == "A")
            set_isolator(a["breaker"], "open", operator=True)
        self.assertFalse(network_reachable(_clock()))
        self.action("8", "closed")
        self.assertEqual(len(self.local()), 2)
        self.assertEqual(len(self.deliveries()), 1)
