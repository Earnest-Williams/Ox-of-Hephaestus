"""Real PostgreSQL G1 contention probe against authoritative Evennia actions.

Use ONLY after migrations on a disposable test database, never a saved ship.
Exercises independent DB connections and actual SELECT FOR UPDATE row locks.
No model, privileged AI API, or second world-state database is involved.

    OX_PG_CONCURRENCY_TEST=1 DJANGO_SETTINGS_MODULE=server.conf.settings_postgres_ci \
        python -m world.postgres_contention
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier, Event

if os.environ.get("OX_PG_CONCURRENCY_TEST") != "1":
    raise RuntimeError("Refusing to run the destructive CI-only contention probe")
if os.environ.get("DJANGO_SETTINGS_MODULE") != "server.conf.settings_postgres_ci":
    raise RuntimeError("PostgreSQL contention probe requires its isolated settings")

import django
django.setup()

import evennia
evennia._init()

from django.db import close_old_connections, connection, connections, transaction
from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object
from world.bootstrap import build_ship, find_fixture
from world.live_crew import fixture_setup, inbox
from world.models import WorkReceipt
from world.work_actions import execute_work


def assert_postgres() -> None:
    if connection.vendor != "postgresql":
        raise RuntimeError(
            f"This probe must run against PostgreSQL, got {connection.vendor}"
        )
    if WorkReceipt.objects.exists() or ObjectDB.objects.exists():
        # Evennia's first boot / migrate may install a few default objects.
        # Do not destroy existing ship data: ensure no installed Ox fixture.
        if find_fixture("pump-p01") is not None or WorkReceipt.objects.exists():
            raise RuntimeError("Refusing to modify a populated ship or work ledger")


def race(actor_ids: tuple[str, str], verb: str, target: str,
         request_ids: tuple[str, str]) -> list[dict]:
    """Two separate database connections, deliberately aligned starts."""
    start = Barrier(2, timeout=15)

    def attempt(dbref: str, request_id: str) -> dict:
        close_old_connections()
        try:
            actor = ObjectDB.objects.get(pk=int(dbref.lstrip("#")))
            start.wait()
            return execute_work(actor, request_id, verb, target)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(attempt, actor, rid)
                   for actor, rid in zip(actor_ids, request_ids)]
        return [future.result(timeout=30) for future in pending]


def locked_writer_probe(pump_id: int, actor_dbref: str) -> None:
    """Prove that the common ship lock actually blocks a concurrent writer."""
    acquired, release, attempted = Event(), Event(), Event()

    def hold() -> None:
        close_old_connections()
        try:
            with transaction.atomic():
                ObjectDB.objects.select_for_update().get(pk=pump_id)
                acquired.set()
                if not release.wait(timeout=12):
                    raise RuntimeError("Other transaction never released row lock")
        finally:
            connections.close_all()

    def blocked_relay() -> dict:
        close_old_connections()
        try:
            person = ObjectDB.objects.get(pk=int(actor_dbref.lstrip("#")))
            attempted.set()
            return execute_work(person, "f" * 32, "radio", "ship")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        locker = pool.submit(hold)
        assert acquired.wait(timeout=10), "Writer did not acquire PostgreSQL row lock"
        writer = pool.submit(blocked_relay)
        assert attempted.wait(timeout=10), "Second DB writer never attempted work"
        try:
            assert not writer.done(), "Writer completed with world row lock held"
            # Holding the lock until here guarantees overlap between the two
            # independent transactions, rather than sequential test calls.
        finally:
            release.set()
        locker.result(timeout=15)
        outcome = writer.result(timeout=15)
    assert outcome["status"] == "succeeded", outcome
    assert WorkReceipt.objects.filter(request_id="f" * 32).count() == 1



def journal_commit_order_probe(recipient_dbref: str) -> None:
    """Sequence visibility cannot outrun an uncommitted journal writer.

    Both threads use independent PostgreSQL transactions. A inserts and holds
    its transaction; B attempts the next event. Under the old implementation B
    committed a higher sequence first and a saved inbox cursor lost A forever.
    """
    from world.event_journal import emit, inbox_page
    from world.models import CrewEvent
    from concurrent.futures import ThreadPoolExecutor

    inserted_a, allow_commit_a, attempting_b = Event(), Event(), Event()
    start_after = CrewEvent.objects.order_by("-sequence").values_list(
        "sequence", flat=True,
    ).first() or 0

    def writer_a():
        close_old_connections()
        try:
            with transaction.atomic():
                recipient = ObjectDB.objects.get(pk=int(recipient_dbref[1:]))
                event = emit(None, recipient, "pg_order_a")
                inserted_a.set()
                assert allow_commit_a.wait(timeout=12), "A release not signalled"
            return event
        finally:
            connections.close_all()

    def writer_b():
        close_old_connections()
        try:
            assert inserted_a.wait(timeout=10), "A never inserted its event"
            recipient = ObjectDB.objects.get(pk=int(recipient_dbref[1:]))
            attempting_b.set()
            return emit(None, recipient, "pg_order_b")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(writer_a)
        assert inserted_a.wait(timeout=10), "A never acquired the journal lock"
        b = pool.submit(writer_b)
        assert attempting_b.wait(timeout=10), "B never attempted its insertion"
        try:
            assert not b.done(), "B passed the uncommitted journal writer"
            # There is no committed B event beyond this cursor before A ends.
            before = inbox_page(
                ObjectDB.objects.get(pk=int(recipient_dbref[1:])),
                after=start_after,
            )
            assert not any(
                e["kind"] in ("pg_order_a", "pg_order_b")
                for e in before["events"]
            ), before
        finally:
            allow_commit_a.set()
        ea, eb = a.result(timeout=15), b.result(timeout=15)

    recipient = ObjectDB.objects.get(pk=int(recipient_dbref[1:]))
    page = inbox_page(recipient, after=start_after)
    ours = [e for e in page["events"]
            if e["kind"] in ("pg_order_a", "pg_order_b")]
    assert [e["event_id"] for e in ours] == [
        ea["event_id"], eb["event_id"],
    ], ours
    assert ea["sequence"] < eb["sequence"], (ea, eb)
    print("OX_PG_JOURNAL_COMMIT_ORDER_PASS", flush=True)


def concurrent_receipt_provenance_probe(actor_dbref: str) -> None:
    """A ship receipt must never attribute a concurrent clock event."""
    from world.event_journal import emit
    from world.models import CrewEvent
    from unittest.mock import patch
    from world import work_actions
    from threading import Event as ThreadEvent

    # Inject a competing direct journal writer before the ship action emits.
    # The old global before/after query assigned that unrelated row to work.
    started, finished = ThreadEvent(), ThreadEvent()
    original_action = work_actions._social_action
    actor = ObjectDB.objects.get(pk=int(actor_dbref[1:]))

    def other_writer():
        close_old_connections()
        try:
            started.set()
            recipient = ObjectDB.objects.get(pk=actor.pk)
            return emit(None, recipient, "pg_unrelated_receipt_probe")
        finally:
            finished.set()
            connections.close_all()

    def interleaved_action(person, operation, arguments):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(other_writer)
            assert started.wait(timeout=10)
            pending.result(timeout=15)
        return original_action(person, operation, arguments)

    with patch.object(work_actions, "_social_action", side_effect=interleaved_action):
        receipt = execute_work(actor, "e" * 32, "radio", "ship")
    assert finished.is_set()
    assert receipt["status"] == "succeeded", receipt
    event = CrewEvent.objects.get(event_id=receipt["source_event_id"])
    assert event.kind == "radio_alert", (receipt, event.kind)
    assert event.recipient_dbref != actor_dbref
    print("OX_PG_RECEIPT_EXACT_EVENT_PROVENANCE_PASS", flush=True)



def captain_alarm_lock_order_probe(ship) -> None:
    """A repeated A-01 alarm must lock its ticket before its first event.

    Hold the alarm's transaction after its first journal append while a
    separate PostgreSQL connection attempts the captain reminder. The
    ticket remains unavailable to a NOWAIT reader, and the concurrent
    reminder proceeds after commit without a ticket/journal deadlock.
    """
    from unittest.mock import patch
    from django.db import DatabaseError
    from world import live_crew
    from world.captain import tick_captain_obligations
    from world.models import CaptainObligation, CrewEvent

    # The preceding scarce-cartridge contention ended with A-01 serviced.
    # Restore it through the real local technician procedure, leaving the
    # captain's existing alarm obligation open for another physical fault.
    scrubber = ObjectDB.objects.get(pk=ship["scrubber"].pk)
    technician = ObjectDB.objects.get(pk=ship["environment"].pk)
    assert scrubber.state == "serviced", scrubber.state
    scrubber.note_inspection(technician)
    restored, reason = scrubber.restart(technician)
    assert restored and scrubber.state == "nominal", reason
    ticket = CaptainObligation.objects.get(
        kind="atmosphere_alarm", source_ref="atmosphere-scrubber",
        status="open",
    )
    ticket.due_game_time = 1.0
    ticket.save(update_fields=["due_game_time"])
    before_bridge = CrewEvent.objects.filter(
        recipient_dbref=ship["officer"].dbref, kind="atmosphere_alarm",
    ).count()
    before_tech = CrewEvent.objects.filter(
        recipient_dbref=technician.dbref, kind="atmosphere_alarm",
    ).count()
    before_reminders = CrewEvent.objects.filter(
        recipient_dbref=ship["captain"].dbref, kind="captain_review_due",
    ).count()

    first_event, resume_alarm, tick_attempted = Event(), Event(), Event()
    original_emit = live_crew.emit

    def pause_alarm_after_append(pump, recipient, kind, **kwargs):
        event = original_emit(pump, recipient, kind, **kwargs)
        if kind == "atmosphere_alarm" and recipient.dbref == ship["officer"].dbref:
            first_event.set()
            if not resume_alarm.wait(timeout=12):
                raise RuntimeError("Alarm writer was not released")
        return event

    def alarm_writer():
        close_old_connections()
        try:
            fixture = ObjectDB.objects.get(pk=ship["scrubber"].pk)
            return fixture.inject_fault()
        finally:
            connections.close_all()

    def reminder_writer():
        close_old_connections()
        try:
            tick_attempted.set()
            return tick_captain_obligations(now_game_time=2.0)
        finally:
            connections.close_all()

    with patch.object(live_crew, "emit", side_effect=pause_alarm_after_append):
        with ThreadPoolExecutor(max_workers=2) as pool:
            alarm = pool.submit(alarm_writer)
            reminder = None
            try:
                assert first_event.wait(timeout=10), "Alarm never appended first event"
                # The opposite ordering (journal first) leaves this row free
                # and would allow captain clock to take it before the alarm.
                locked = False
                try:
                    with transaction.atomic():
                        CaptainObligation.objects.select_for_update(nowait=True).get(
                            pk=ticket.pk,
                        )
                except DatabaseError:
                    locked = True
                assert locked, "Alarm acquired journal lock before captain obligation"
                reminder = pool.submit(reminder_writer)
                assert tick_attempted.wait(timeout=10), "Reminder did not attempt work"
                assert not reminder.done(), "Reminder bypassed uncommitted alarm ticket"
            finally:
                resume_alarm.set()
            applied, detail = alarm.result(timeout=15)
            assert applied, detail
            assert reminder is not None and reminder.result(timeout=15) == 1

    assert CrewEvent.objects.filter(
        recipient_dbref=ship["officer"].dbref, kind="atmosphere_alarm",
    ).count() == before_bridge + 1
    assert CrewEvent.objects.filter(
        recipient_dbref=technician.dbref, kind="atmosphere_alarm",
    ).count() == before_tech + 1
    assert CrewEvent.objects.filter(
        recipient_dbref=ship["captain"].dbref, kind="captain_review_due",
    ).count() == before_reminders + 1
    assert CaptainObligation.objects.filter(
        kind="atmosphere_alarm", source_ref="atmosphere-scrubber",
        status="open",
    ).count() == 1
    print("OX_PG_CAPTAIN_ALARM_JOURNAL_LOCK_ORDER_PASS", flush=True)


def captain_first_obligation_race_probe(ship) -> None:
    """Two genuinely concurrent openers must create one world obligation.

    The first opener holds its transaction and P-01 lock while the second
    attempts the same as-yet-uncommitted identity on another connection.
    Both must receive the same ticket; the captain gets one source event.
    """
    from django.db import DatabaseError
    from world.captain import open_obligation
    from world.models import CaptainObligation, CrewEvent

    source = "pg-ci-disposable-open-race"
    created, release_first, second_attempted = Event(), Event(), Event()

    def first_writer():
        close_old_connections()
        try:
            with transaction.atomic():
                ticket_id = open_obligation("atmosphere_alarm", source, priority=90)
                created.set()
                assert release_first.wait(timeout=12), "First obligation not released"
            return ticket_id
        finally:
            connections.close_all()

    def second_writer():
        close_old_connections()
        try:
            assert created.wait(timeout=10), "First obligation not created"
            second_attempted.set()
            return open_obligation("atmosphere_alarm", source, priority=90)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_writer)
        assert created.wait(timeout=10), "First opener failed"
        second = pool.submit(second_writer)
        try:
            assert second_attempted.wait(timeout=10), "Second opener never attempted"
            assert not second.done(), "Second opener bypassed uncommitted obligation"
            blocked = False
            try:
                with transaction.atomic():
                    ObjectDB.objects.select_for_update(nowait=True).get(
                        pk=ship["pump"].pk,
                    )
            except DatabaseError:
                blocked = True
            assert blocked, "First-time obligation open did not hold P-01 lock"
        finally:
            release_first.set()
        ticket_ids = (first.result(timeout=15), second.result(timeout=15))

    assert ticket_ids[0] == ticket_ids[1], ticket_ids
    assert CaptainObligation.objects.filter(
        kind="atmosphere_alarm", source_ref=source,
        status="open",
    ).count() == 1
    assert CrewEvent.objects.filter(
        kind="captain_problem_open", details__ticket_id=ticket_ids[0],
    ).count() == 1
    print("OX_PG_CAPTAIN_FIRST_OBLIGATION_UNIQUE_PASS", flush=True)


def main() -> None:
    assert_postgres()
    fixture_setup(scheduled_clock=False)
    ship = build_ship()
    lin, ari = ship["officer"], ship["watch"]
    pump, scrubber = ship["pump"], ship["scrubber"]

    # Same actor and same global ID raced through two connections: one
    # authoritative receipt and one physical/social observation only.
    same = race(
        (lin.dbref, lin.dbref), "radio", "ship",
        ("1" * 32, "1" * 32),
    )
    assert len(same) == 2 and same[0] == same[1], same
    assert same[0]["status"] == "succeeded", same
    assert WorkReceipt.objects.filter(pk="1" * 32).count() == 1
    assert [e["kind"] for e in inbox(ari)].count("radio_alert") == 1
    print("OX_G1_PG_SAME_ID_RACE_ONE_RECEIPT_PASS", flush=True)

    # Competing independent, role-authorized actors both try the LAST
    # cartridge. Only one can succeed, and the second refusal is durable.
    assert scrubber.inject_fault()[0]
    scrubber.note_inspection(ship["environment"])
    isolated = execute_work(
        ship["environment"], "2" * 32, "isolate", "scrubber",
    )
    assert isolated["status"] == "succeeded", isolated
    scrubber.db.spare_cartridges = 1
    relief = create_object(
        "typeclasses.ship.CrewCharacter",
        key="Disposable parallel environmental technician",
        location=ship["environmental"],
        home=ship["environmental"],
    )
    relief.db.crew_role = "environment_tech"
    attempts = race(
        (ship["environment"].dbref, relief.dbref),
        "replace", "scrubber", ("3" * 32, "4" * 32),
    )
    assert sorted(x["status"] for x in attempts) == [
        "failed", "succeeded",
    ], attempts
    scrubber_fresh = ObjectDB.objects.get(pk=scrubber.pk)
    assert int(scrubber_fresh.db.spare_cartridges) == 0
    assert [x["operation"] for x in scrubber_fresh.db.event_history].count(
        "replace"
    ) == 1
    receipts = list(
        WorkReceipt.objects.filter(target="scrubber", operation="replace")
    )
    assert len(receipts) == 2 and len({
        x.request_id for x in receipts
    }) == 2
    assert sorted(x.outcome["status"] for x in receipts) == [
        "failed", "succeeded",
    ]
    print("OX_G1_PG_LAST_CARTRIDGE_NO_DOUBLE_CONSUMPTION_PASS", flush=True)

    # The row lock remains held until transaction commit even when another
    # authorized work command is competing for the ship resource.
    locked_writer_probe(pump.pk, lin.dbref)
    assert [e["kind"] for e in inbox(ari)].count("radio_alert") == 2
    print("OX_G1_PG_BLOCKING_SHIP_ROW_LOCK_PASS", flush=True)

    # Postgres rollback must remove *both* the world event and its receipt.
    before_count = WorkReceipt.objects.count()
    before_events = [e["event_id"] for e in inbox(ari)]
    try:
        with transaction.atomic():
            execute_work(lin, "5" * 32, "radio", "ship")
            raise RuntimeError("Synthetic rollback after world action")
    except RuntimeError as exc:
        assert str(exc).startswith("Synthetic rollback"), str(exc)
    assert WorkReceipt.objects.count() == before_count
    assert [e["event_id"] for e in inbox(ari)] == before_events
    print("OX_G1_PG_ROLLBACK_NO_PHANTOM_EVENTS_PASS", flush=True)

    from world.adversarial_concurrency import verify_concurrent_hails_and_duties
    verify_concurrent_hails_and_duties(ship)

    journal_commit_order_probe(ari.dbref)
    concurrent_receipt_provenance_probe(lin.dbref)
    captain_alarm_lock_order_probe(ship)
    captain_first_obligation_race_probe(ship)


if __name__ == "__main__":
    main()
