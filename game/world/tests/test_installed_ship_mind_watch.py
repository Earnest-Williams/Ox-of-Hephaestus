"""Installed first watch: signal driven only by genuine network delivery.

All actions use the fitted G19 gateway, surveyed A/B fibre, live computer
power, and an actual engineer operating the original drum-3 pressure hatch.
"""
from types import SimpleNamespace

from evennia.utils.create import create_account
from world.continuous_ship_physics import (
    _clock, survey_g19_data_path,
)
from world.full_ship_operations import (
    load_candidate, set_component_condition, state,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_mind_support import data_penetrations
from world.ship_mind_watch import (
    FIRED, KEY, ShipWatchError,
)
from world.ship_mind_watch_world import (
    arm_first_watch, cancel_first_watch, first_watch_status,
)
from world.ship_network_access import NetworkAccessError, DELIVERED, PRINCIPAL
from world.ship_network_access_world import (
    enroll_access_account, network_reachable,
)
from world.tests.test_installed_ship_network_access import NetworkAccessFixture


class InstalledLeadMindFirstWatch(NetworkAccessFixture):
    def setUp(self):
        super().setUp()
        enroll_access_account(self.account, operator_approved=True)

    def _restore_drop(self):
        for rail in ("A", "B"):
            name = "NET-GW-DROP-" + rail + "-DR-03"
            set_component_condition("edge", name, "serviceable", operator=True)
            row = state("edge", name)
            survey_g19_data_path(
                operator_approved=True, component_id=name,
                evidence_id="watch-restored-" + name,
                penetration_ids=data_penetrations(row.reference, load_candidate()),
                continuity_verified=True, pressure_verified=True,
                environment_verified=True, emi_verified=True,
                continuous_rpm=None,
            )
        self.advance(1020)
        self.assertTrue(network_reachable(_clock()))

    def test_one_shot_fires_on_verified_delivery_not_on_a_noop(self):
        self.assertEqual(first_watch_status(self.account)["status"], "idle")
        first = arm_first_watch(self.account, "1" * 32, "open")
        self.assertEqual(first["status"], "armed_for_next_delivery")
        self.assertFalse(first["controls_time"])
        self.assertEqual(arm_first_watch(self.account, "1" * 32, "open"), first)
        with self.assertRaises(ShipWatchError):
            arm_first_watch(self.account, "2" * 32, "closed")
        self.assertEqual(first_watch_status(self.account)["status"], "armed")
        self.action("3", "closed")  # Existing closed hatch: no change.
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 0)
        self.assertEqual(first_watch_status(self.account)["status"], "armed")
        self.action("4", "open")
        result = first_watch_status(self.account)
        self.assertEqual(result["status"], "fired")
        self.assertEqual(result["desired"], "open")
        self.assertEqual(result["delivery_event_id"], "ox-net-" +
                         str(self.deliveries()[0].sequence))
        self.assertFalse(result["controls_time"])
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 1)
        self.action("5", "closed")
        self.action("6", "open")
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 1)
        self.assertEqual(WorkReceipt.objects.filter(
            request_id="1" * 32).count(), 1)
        self.assertEqual(CanonicalShipState.objects.get(pk=KEY).setting, "fired")

        second = arm_first_watch(self.account, "7" * 32, "closed")
        self.assertEqual(second["status"], "armed_for_next_delivery")
        self.action("8", "closed")
        self.assertEqual(first_watch_status(self.account)["status"], "fired")
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 2)

    def test_cancel_dedup_and_foreign_account_denied(self):
        fake = SimpleNamespace(pk=self.account.pk)
        with self.assertRaises(NetworkAccessError):
            arm_first_watch(fake, "9" * 32, "open")
        first = arm_first_watch(self.account, "a" * 32, "open")
        self.assertEqual(first["status"], "armed_for_next_delivery")
        cancelled = cancel_first_watch(self.account, "b" * 32)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancel_first_watch(self.account, "b" * 32), cancelled)
        with self.assertRaises(PermissionError):
            arm_first_watch(self.account, "b" * 32, "open")
        self.assertEqual(first_watch_status(self.account)["status"], "idle")
        self.action("c", "open")
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 0)
        with self.assertRaises(ShipWatchError):
            cancel_first_watch(self.account, "d" * 32)
        # A second genuine account cannot read the selected account's watch.
        second_account = create_account(
            key="OxOtherWatch-" + self._testMethodName,
            email="ox-watch-other@example.invalid",
            password="OxCI-only-second-test-password",
        )
        with self.assertRaises(NetworkAccessError):
            first_watch_status(second_account)

    def test_dark_network_cannot_fire_or_backfill_old_hatch_change(self):
        arm_first_watch(self.account, "e" * 32, "open")
        for rail in ("A", "B"):
            set_component_condition(
                "edge", "NET-GW-DROP-" + rail + "-DR-03",
                "severed", operator=True,
            )
        self.assertFalse(network_reachable(_clock()))
        with self.assertRaises(NetworkAccessError):
            first_watch_status(self.account)
        self.action("f", "open")
        self.assertEqual(len(self.local()), 1)
        self.assertEqual(len(self.deliveries()), 0)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 0)
        self._restore_drop()
        self.assertEqual(first_watch_status(self.account)["status"], "armed")
        self.assertEqual(len(self.deliveries()), 0)
        self.action("0", "closed")  # Fresh but not matching.
        self.assertEqual(first_watch_status(self.account)["status"], "armed")
        self.action("2", "open")  # New delivery, matching.
        self.assertEqual(first_watch_status(self.account)["status"], "fired")
        self.assertEqual(len(self.deliveries()), 2)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            component_key=KEY, operation=FIRED).count(), 1)
