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


if __name__ == "__main__":
    main()
