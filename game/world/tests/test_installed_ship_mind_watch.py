"""Installed first watch: signal driven only by genuine network delivery.

All actions use the fitted G19 gateway, surveyed A/B fibre, live computer
power, and an actual engineer operating the original drum-3 pressure hatch.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.db import transaction
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
        with self.assertRaises(ShipWatchError):
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

    def test_player_wake_is_emitted_only_after_world_commit(self):
        arm_first_watch(self.account, "5" * 32, "open")
        account_type = type(self.account)
        with patch.object(account_type, "msg", autospec=True) as messages:
            with self.captureOnCommitCallbacks(execute=True):
                self.action("6", "open")
                # The hatch and network delivery are committed together.
                # A notice before the outer transaction's commit would be
                # able to describe work that might still roll back.
                notices = [
                    call for call in messages.call_args_list
                    if "ox_watch_fired" in call.kwargs
                ]
                self.assertFalse(notices)
            notices = [
                call for call in messages.call_args_list
                if "ox_watch_fired" in call.kwargs
            ]
            self.assertEqual(len(notices), 1)
            self.assertEqual(notices[0].args[0].pk, self.account.pk)
            payload = json.loads(notices[0].kwargs["ox_watch_fired"][0][0])
            self.assertEqual(payload["schema_version"], "ox.ship-mind-watch-wake/1")
            self.assertEqual(payload["request_id"], "5" * 32)
            self.assertEqual(payload["status"], "fired")
            self.assertEqual(payload["desired"], "open")
            self.assertEqual(
                payload["delivery_event_id"],
                "ox-net-" + str(self.deliveries()[0].sequence),
            )
            self.assertFalse(payload["controls_time"])
            self.assertFalse(payload["physical_actuation"])
            self.assertNotIn("actor_dbref", payload)
            self.assertNotIn("location", payload)
            self.assertEqual(first_watch_status(self.account)["status"], "fired")

    def test_rolled_back_physical_work_never_wakes_an_account(self):
        arm_first_watch(self.account, "7" * 32, "open")

        class CancelTestTransaction(Exception):
            pass

        with patch.object(type(self.account), "msg", autospec=True) as messages:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(CancelTestTransaction):
                    with transaction.atomic():
                        self.action("8", "open")
                        self.assertEqual(
                            CanonicalShipEvent.objects.filter(
                                component_key=KEY, operation=FIRED).count(), 1)
                        raise CancelTestTransaction
            notices = [
                call for call in messages.call_args_list
                if "ox_watch_fired" in call.kwargs
            ]
            self.assertFalse(notices)
        self.assertEqual(
            CanonicalShipEvent.objects.filter(
                component_key=KEY, operation=FIRED).count(), 0)
        self.assertEqual(len(self.deliveries()), 0)
        self.assertEqual(first_watch_status(self.account)["status"], "armed")

    def test_enrolment_changed_before_commit_suppresses_stale_wake(self):
        arm_first_watch(self.account, "9" * 32, "open")
        with patch.object(type(self.account), "msg", autospec=True) as messages:
            with self.captureOnCommitCallbacks(execute=True):
                self.action("a", "open")
                principal = CanonicalShipState.objects.get(pk=PRINCIPAL)
                principal.reference = dict(
                    principal.reference, epoch="f" * 32)
                principal.save(update_fields=["reference"])
            self.assertFalse([
                c for c in messages.call_args_list
                if "ox_watch_fired" in c.kwargs
            ])
        # Historical observation survives, but old enrolment cannot claim it.
        self.assertEqual(
            CanonicalShipEvent.objects.filter(
                component_key=KEY, operation=FIRED).count(), 1)

