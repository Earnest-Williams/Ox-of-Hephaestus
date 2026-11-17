"""Installed request-only hatch handover over real drum-3 survey and fibre."""
from world.tests.test_installed_ship_network_access import NetworkAccessFixture

from world.continuous_ship_physics import (
    _clock, crew_physical_action, survey_g19_data_path,
)
from world.full_ship_operations import (
    load_candidate, state, set_component_condition,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_access_contact import LINK, OBSERVED
from world.ship_dr03_hatch_policy import (
    DECIDED, KEY, ROOM, REQUESTED, HatchHandoverError,
)
from world.ship_dr03_hatch_handover_world import (
    commission_dr03_hatch_handover, decide_dr03_hatch,
    dr03_hatch_request_status, local_dr03_hatch_pending,
    request_dr03_hatch,
)
from world.ship_network_access_world import (
    enroll_access_account, network_reachable,
)
from world.ship_mind_support import data_penetrations
from world.ship_network_access import DELIVERED, PRINCIPAL
from world.ship_world import find_ship_space


class InstalledDr03HatchHandover(NetworkAccessFixture):
    def setUp(self):
        super().setUp()
        enroll_access_account(self.account, operator_approved=True)
        self.tech.move_to(find_ship_space(ROOM), quiet=True)
        self.assertTrue(commission_dr03_hatch_handover(
            operator_approved=True)["commissioned"])

    def test_request_local_acceptance_and_real_manual_hatch(self):
        prior = state("access", LINK).setting
        requested = "closed" if prior == "open" else "open"
        first = request_dr03_hatch(self.account, "1" * 32, requested)
        self.assertEqual(first["status"], "pending_local_decision")
        self.assertFalse(first["physical_actuation"])
        self.assertEqual(state("access", LINK).setting, prior)
        self.assertEqual(CanonicalShipState.objects.get(pk=KEY).setting, "pending")
        view = local_dr03_hatch_pending(self.tech)
        self.assertTrue(view["pending"])
        self.assertEqual(view["request_id"], "1" * 32)
        self.assertEqual(view["desired"], requested)
        self.assertFalse(view["physical_actuation"])
        self.assertEqual(request_dr03_hatch(
            self.account, "1" * 32, requested), first)
        self.assertEqual(WorkReceipt.objects.filter(
            request_id="1" * 32).count(), 1)
        self.assertEqual(dr03_hatch_request_status(
            self.account, "1" * 32)["status"], "pending_local_decision")
        with self.assertRaises(HatchHandoverError):
            request_dr03_hatch(self.account, "2" * 32, prior)

        decision = decide_dr03_hatch(
            self.tech, "3" * 32, "1" * 32, "accept")
        self.assertEqual(decision["status"], "accepted_for_manual_action")
        self.assertFalse(decision["physical_actuation"])
        self.assertEqual(decide_dr03_hatch(
            self.tech, "3" * 32, "1" * 32, "accept"), decision)
        self.assertEqual(state("access", LINK).setting, prior)
        self.assertEqual(CanonicalShipState.objects.get(pk=KEY).setting, "idle")
        self.assertFalse(local_dr03_hatch_pending(self.tech)["pending"])
        self.assertEqual(dr03_hatch_request_status(
            self.account, "1" * 32)["status"], "accepted_for_manual_action")
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation=REQUESTED).count(), 1)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation=DECIDED).count(), 1)

        # Only an attended crew work receipt actually moves the rated hatch.
        self.tech.move_to(find_ship_space("TRUNK-A-DR-03"), quiet=True)
        self.action("4", requested)
        self.assertEqual(state("access", LINK).setting, requested)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation=OBSERVED).count(), 1)
        confirmed = dr03_hatch_request_status(self.account, "1" * 32)
        self.assertEqual(confirmed["status"], "world_confirmed_at_source_time")
        self.assertFalse(confirmed["physical_actuation"])
        self.assertIsNotNone(confirmed["physical_confirmation"])
        self.assertEqual(confirmed["physical_confirmation"]["status"],
                         "world_confirmed_at_source_time")
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=PRINCIPAL, operation=DELIVERED).count(), 1)
        self.assertTrue(commission_dr03_hatch_handover(
            operator_approved=True)["request_only"])
        self.assertFalse(commission_dr03_hatch_handover(
            operator_approved=True)["commissioned"])

    def test_dark_fibre_does_not_prevent_local_decline_or_manual_action(self):
        prior = state("access", LINK).setting
        requested = "closed" if prior == "open" else "open"
        request_dr03_hatch(self.account, "5" * 32, requested)
        for rail in ("A", "B"):
            set_component_condition(
                "edge", "NET-GW-DROP-" + rail + "-DR-03",
                "severed", operator=True,
            )
        with self.assertRaises(HatchHandoverError):
            request_dr03_hatch(self.account, "6" * 32, prior)
        with self.assertRaises(HatchHandoverError):
            dr03_hatch_request_status(self.account, "5" * 32)
        # The original local panel must still show the pending request.
        local_view = local_dr03_hatch_pending(self.tech)
        self.assertTrue(local_view["pending"])
        self.assertEqual(local_view["request_id"], "5" * 32)
        self.assertEqual(local_view["desired"], requested)
        decision = decide_dr03_hatch(
            self.tech, "7" * 32, "5" * 32, "decline")
        self.assertEqual(decision["status"], "declined_by_crew")
        self.assertEqual(CanonicalShipState.objects.get(pk=KEY).setting, "idle")
        with self.assertRaises(HatchHandoverError):
            request_dr03_hatch(self.account, "7" * 32, requested)
        self.tech.move_to(find_ship_space("TRUNK-A-DR-03"), quiet=True)
        self.action("8", requested)
        self.assertEqual(state("access", LINK).setting, requested)
        # Return to the real console so this checks stale request identity,
        # not the independent physical-presence guard.
        self.tech.move_to(find_ship_space(ROOM), quiet=True)
        with self.assertRaises(HatchHandoverError):
            decide_dr03_hatch(self.tech, "9" * 32, "5" * 32, "accept")

    def test_offline_local_action_has_no_retroactive_confirmation(self):
        prior = state("access", LINK).setting
        requested = "closed" if prior == "open" else "open"
        request_dr03_hatch(self.account, "a" * 32, requested)
        decide_dr03_hatch(self.tech, "b" * 32, "a" * 32, "accept")
        for rail in ("A", "B"):
            set_component_condition(
                "edge", "NET-GW-DROP-" + rail + "-DR-03",
                "severed", operator=True,
            )
        self.tech.move_to(find_ship_space("TRUNK-A-DR-03"), quiet=True)
        self.action("c", requested)
        self.assertEqual(state("access", LINK).setting, requested)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation=OBSERVED).count(), 1)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation=DELIVERED, component_key=PRINCIPAL).count(), 0)

        # Repairs and fresh surveys restore future transport; they cannot
        # backfill a contact frame that was never delivered at event time.
        for rail in ("A", "B"):
            name = "NET-GW-DROP-" + rail + "-DR-03"
            set_component_condition("edge", name, "serviceable", operator=True)
            cable = state("edge", name)
            survey_g19_data_path(
                operator_approved=True, component_id=name,
                evidence_id="hatch-confirmation-resurvey-" + name,
                penetration_ids=data_penetrations(
                    cable.reference, load_candidate()),
                continuity_verified=True, pressure_verified=True,
                environment_verified=True, emi_verified=True,
                continuous_rpm=None,
            )
        self.advance(1020)
        self.assertTrue(network_reachable(_clock()))
        status = dr03_hatch_request_status(self.account, "a" * 32)
        self.assertEqual(status["status"], "accepted_for_manual_action")
        self.assertIsNone(status["physical_confirmation"])

    def test_later_request_cannot_claim_earlier_accepted_work(self):
        prior = state("access", LINK).setting
        requested = "closed" if prior == "open" else "open"
        request_dr03_hatch(self.account, "d" * 32, requested)
        decide_dr03_hatch(self.tech, "e" * 32, "d" * 32, "accept")
        request_dr03_hatch(self.account, "f" * 32, prior)
        decide_dr03_hatch(self.tech, "1" * 32, "f" * 32, "decline")
        self.tech.move_to(find_ship_space("TRUNK-A-DR-03"), quiet=True)
        self.action("2", requested)
        older = dr03_hatch_request_status(self.account, "d" * 32)
        self.assertEqual(older["status"], "accepted_for_manual_action")
        self.assertIsNone(older["physical_confirmation"])
        declined = dr03_hatch_request_status(self.account, "f" * 32)
        self.assertEqual(declined["status"], "declined_by_crew")
        self.assertIsNone(declined["physical_confirmation"])

