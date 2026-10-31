"""Reproducible multi-system Ox voyages, crash points, and event storms.

Runs on the real Evennia test database. The only synthetic input is the
operator's initial equipment faults and spare stock; crew work uses the
same world-authorized receipt API as authenticated sessions.
"""
from __future__ import annotations

import random

from django.db import transaction
from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.crew_interaction import answer_hail, send_hail
from world.event_journal import emit, inbox_page
from world.live_clock import tick_game_clock
from world.live_crew import fixture_setup, inbox, note_inspection
from world.models import CrewEvent, WorkReceipt
from world.work_actions import execute_work, work_receipt


class SyntheticCrash(RuntimeError):
    pass


class AdversarialVoyageTests(EvenniaTestCase):
    """Deterministically interleave independent legitimate world work."""

    SEED = 20261019

    def setUp(self):
        super().setUp()
        fixture_setup(scheduled_clock=True)
        self.ship = build_ship()
        self.serial = 0

    def _new_id(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def _work(self, actor, operation, target="ship", *, status="succeeded"):
        request_id = self._new_id()
        original = execute_work(actor, request_id, operation, target)
        self.assertEqual(
            original["status"], status,
            f"{operation} {target} {actor.key} request={request_id}",
        )
        self.assertEqual(
            execute_work(actor, request_id, operation, target),
            original, "Replaying an operation must not repeat its effect",
        )
        outsider = (self.ship["officer"] if actor != self.ship["officer"]
                    else self.ship["cargo"])
        self.assertEqual(work_receipt(outsider, request_id)["status"], "unknown")
        self.assertEqual(work_receipt(actor, request_id), original)
        return request_id, original

    def test_seeded_three_cycle_ship_with_interleaved_dependent_work(self):
        ship = self.ship
        pump, cradle, scrubber = ship["pump"], ship["cradle"], ship["scrubber"]
        rng = random.Random(self.SEED)
        # Operator-only scenario initialization, not an AI inventory mutation.
        scrubber.db.spare_cartridges = 3
        guest = create_object(
            "typeclasses.ship.CrewCharacter", key="Voyage Guest",
            location=ship["bridge"], home=ship["bridge"],
        )
        role_names = {"lin": "officer", "ari": "watch", "iona": "chief",
                      "mara": "cargo", "teo": "environment"}
        fault_receipts = []

        for cycle in range(3):
            active = ship["watch"] if cycle == 0 else ship["chief"]
            reviewer = ship["chief"] if cycle == 0 else ship["watch"]
            if cycle:
                self.assertTrue(pump.inject_fault()[0])
            self.assertTrue(cradle.inject_fault()[0])
            self.assertTrue(scrubber.inject_fault()[0])

            # Attempt and durably refuse invalid work BEFORE a valid repair.
            forbidden, refused = self._work(
                ship["officer"], "restow", "cargo", status="failed")
            fault_receipts.append((ship["officer"], forbidden, "restow", "cargo", refused))
            forbidden, refused = self._work(
                ship["cargo"], "certify", "cargo", status="failed")
            fault_receipts.append((ship["cargo"], forbidden, "certify", "cargo", refused))
            forbidden, refused = self._work(
                ship["environment"], "replace", "scrubber", status="failed")
            fault_receipts.append((ship["environment"], forbidden, "replace", "scrubber", refused))

            if cycle == 0:
                # Crash after a world action but before the enclosing DB
                # transaction commits: neither event nor work ID may survive.
                request_id = self._new_id()
                original_count = CrewEvent.objects.count()
                with self.assertRaises(SyntheticCrash):
                    with transaction.atomic():
                        outcome = execute_work(ship["officer"], request_id, "radio")
                        self.assertEqual(outcome["status"], "succeeded")
                        raise SyntheticCrash("interrupted before commit")
                self.assertEqual(CrewEvent.objects.count(), original_count)
                self.assertEqual(
                    work_receipt(ship["officer"], request_id)["status"], "unknown")
                self.assertEqual(
                    execute_work(ship["officer"], request_id, "radio")["status"],
                    "succeeded", "Original request is valid after proven absence")

            cradle.note_inspection(ship["cargo"])
            scrubber.note_inspection(ship["environment"])
            phase_one = [
                (active, "isolate", "pump"),
                (ship["cargo"], "restow", "cargo"),
                (ship["environment"], "isolate", "scrubber"),
            ]
            rng.shuffle(phase_one)
            for actor, operation, target in phase_one:
                self._work(actor, operation, target)

            cradle.note_inspection(ship["cargo"])
            scrubber.note_inspection(ship["environment"])
            phase_two = [
                (active, "repair", "pump"),
                (ship["cargo"], "certify", "cargo"),
                (ship["environment"], "replace", "scrubber"),
            ]
            rng.shuffle(phase_two)
            for actor, operation, target in phase_two:
                self._work(actor, operation, target)

            scrubber.note_inspection(ship["environment"])
            self._work(ship["environment"], "restart", "scrubber")
            self._work(active, "request")
            note_inspection(reviewer, pump)
            self._work(reviewer, "approve")
            self._work(active, "commission", "pump")
            note_inspection(active, pump)
            self._work(active, "resolve")

            target_role = rng.choice(tuple(role_names))
            accepted, hail = send_hail(
                guest, target_role, f"Status during watch segment {cycle}?")
            self.assertTrue(accepted, hail)
            hail_id = hail.split()[-1]
            responder = ship[role_names[target_role]]
            self.assertTrue(answer_hail(responder, hail_id, "ack")[0])
            self.assertTrue(answer_hail(responder, hail_id, "ack")[0])
            self.assertEqual(
                len([e for e in inbox(guest)
                     if e["kind"] == "crew_reply"
                     and e["data"].get("hail_id") == hail_id]), 1)

            # A permanent failed receipt remains failed even after the world
            # has since reached the state that would allow a NEW attempt.
            for actor, request_id, operation, target, original in fault_receipts:
                self.assertEqual(
                    execute_work(actor, request_id, operation, target), original)

            self.assertEqual(pump.state, "normal")
            self.assertEqual(cradle.state, "secured")
            self.assertEqual(scrubber.state, "nominal")
            self.assertTrue(pump.db.ox_incident_closed)

            if cycle == 0:
                self.assertFalse(tick_game_clock(now_game_time=100))
                self.assertTrue(tick_game_clock(now_game_time=106))
                self.assertFalse(tick_game_clock(now_game_time=110))
                self._work(ship["watch"], "offer")
                self._work(ship["chief"], "accept")
                self.assertEqual(
                    ship["roster"].db.ox_active_engineer, ship["chief"].dbref)

        self.assertEqual(scrubber.db.spare_cartridges, 0)
        for name, event, times in (
            ("pump", "fault", 3), ("pump", "isolate", 3),
            ("pump", "repair", 3), ("pump", "commission", 3),
            ("cradle", "shift", 3), ("cradle", "restow", 3),
            ("cradle", "certify", 3), ("scrubber", "saturate", 3),
            ("scrubber", "isolate", 3), ("scrubber", "replace", 3),
            ("scrubber", "restart", 3),
        ):
            actual = [e for e in ship[name].db.event_history
                      if e["operation"] == event]
            self.assertEqual(len(actual), times, f"{name}/{event}")
        self.assertEqual(
            len({r.request_id for r in WorkReceipt.objects.all()}),
            WorkReceipt.objects.count())
        self.assertEqual(
            len([e for e in inbox(guest) if e["kind"] == "crew_reply"]), 3)

    def test_seeded_event_storm_replay_privacy_and_mid_write_rollbacks(self):
        ship = self.ship
        rng = random.Random(0xF731)
        recipients = [ship["officer"]] * 153 + [ship["cargo"]] * 27
        rng.shuffle(recipients)
        for sequence, person in enumerate(recipients):
            if sequence % 23 == 0:
                before = CrewEvent.objects.count()
                with self.assertRaises(SyntheticCrash):
                    with transaction.atomic():
                        emit(ship["pump"], person, "voyage_diagnostic",
                             data={"sample": sequence, "aborted": True}, text="Test observation.")
                        raise SyntheticCrash("before journal commit")
                self.assertEqual(CrewEvent.objects.count(), before)
            emit(ship["pump"], person, "voyage_diagnostic",
                 data={"sample": sequence, "aborted": False}, text="Test observation.")

        for role, expected in (("officer", 153), ("cargo", 27),
                               ("environment", 0)):
            actor = ship[role]
            cursor, seen, sequences = 0, [], []
            for page_number in range(5):
                page = inbox_page(actor, after=cursor)
                seen += page["events"]
                sequences += [e["sequence"] for e in page["events"]]
                self.assertTrue(all(
                    e["recipient_dbref"] == actor.dbref for e in page["events"]))
                if not page["has_more"]:
                    break
                self.assertGreater(page["next_cursor"], cursor)
                cursor = page["next_cursor"]
            else:
                self.fail("Recipient-specific inbox did not terminate")
            relevant = [e for e in seen if e["kind"] == "voyage_diagnostic"]
            self.assertEqual(len(relevant), expected)
            self.assertEqual(sequences, sorted(set(sequences)))
            self.assertTrue(all(e["data"]["aborted"] is False for e in relevant))
            if role == "officer":
                self.assertGreater(len(seen), 128)
