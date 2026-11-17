"""Installed request-only hatch handover over real drum-3 survey and fibre."""
from world.tests.test_installed_ship_network_access import NetworkAccessFixture

from world.continuous_ship_physics import crew_physical_action
from world.full_ship_operations import state, set_component_condition
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
from world.ship_network_access_world import enroll_access_account
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
        self.assertEqual(dr03_hatch_request_status(
            self.account, "1" * 32)["status"], "accepted_for_manual_action")
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
