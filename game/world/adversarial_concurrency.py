"""Adversarial PostgreSQL ship-world interleavings on disposable CI only.

Invoked by world.postgres_contention after Django/Evennia initialization.
Separate connections compete on actual Evennia Attributes and world locks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os

from django.db import close_old_connections, connections
from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object

from world.bootstrap import find_fixture
from world.crew_interaction import send_hail, answer_hail
from world.live_clock import schedule_handover, tick_game_clock
from world.live_crew import inbox


def _race(func, *inputs):
    gate = Barrier(len(inputs), timeout=15)

    def one(arg):
        close_old_connections()
        try:
            gate.wait()
            return func(arg)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(inputs)) as workers:
        futures = [workers.submit(one, arg) for arg in inputs]
        return [future.result(timeout=40) for future in futures]


def verify_concurrent_hails_and_duties(ship):
    if (os.environ.get("OX_PG_CONCURRENCY_TEST") != "1"
            or os.environ.get("DJANGO_SETTINGS_MODULE") !=
            "server.conf.settings_postgres_ci"):
        raise RuntimeError("Disposable PostgreSQL CI settings required")

    guests = [
        create_object(
            "typeclasses.ship.CrewCharacter", key=f"Adversarial Guest {n}",
            location=ship["bridge"], home=ship["bridge"],
        ) for n in (1, 2)
    ]

    def hail(args):
        dbref, role, message = args
        actor = ObjectDB.objects.get(pk=int(dbref[1:]))
        return send_hail(actor, role, message)

    first = _race(
        hail,
        (guests[0].dbref, "mara", "Freight status?"),
        (guests[1].dbref, "teo", "Atmosphere status?"),
    )
    assert all(ok for ok, _ in first), first
    ids = [message.split()[-1] for _, message in first]
    assert len(set(ids)) == 2, first
    ledger = dict(find_fixture("pump-p01").db.ox_hails or {})
    assert all(hail_id in ledger for hail_id in ids), (ids, ledger)
    assert sum(e["kind"] == "crew_hail" for e in inbox(ship["cargo"])) == 1
    assert sum(e["kind"] == "crew_hail" for e in inbox(ship["environment"])) == 1
    print("OX_G5_PG_UNIQUE_SIMULTANEOUS_HAILS_PASS", flush=True)

    duplicate = _race(
        hail,
        (guests[0].dbref, "iona", "One"),
        (guests[0].dbref, "iona", "Two"),
    )
    assert sorted(ok for ok, _ in duplicate) == [False, True], duplicate
    accepted = next(message.split()[-1] for ok, message in duplicate if ok)
    addressed = [e for e in inbox(ship["chief"])
                 if e["kind"] == "crew_hail"
                 and e["data"].get("hail_id") == accepted]
    assert len(addressed) == 1, addressed
    print("OX_G5_PG_ONE_PENDING_HAIL_PER_PAIR_PASS", flush=True)

    def answer(_unused):
        actor = ObjectDB.objects.get(pk=ship["chief"].pk)
        return answer_hail(actor, accepted, "ack")

    replies = _race(answer, 1, 2)
    assert all(ok for ok, _ in replies), replies
    player = ObjectDB.objects.get(pk=guests[0].pk)
    outbound = [e for e in inbox(player) if e["kind"] == "crew_reply"
                and e["data"].get("hail_id") == accepted]
    confirmed = [e for e in inbox(ship["chief"])
                 if e["kind"] == "hail_answered"
                 and e["data"].get("hail_id") == accepted]
    assert len(outbound) == len(confirmed) == 1, (outbound, confirmed)
    print("OX_G5_PG_ONE_CONCURRENT_HAIL_REPLY_PASS", flush=True)

    schedule_handover(delay_game_seconds=5)
    assert tick_game_clock(now_game_time=100) is False
    before = {
        role: sum(e["kind"] == "handover_due" for e in inbox(ship[role]))
        for role in ("watch", "chief")
    }

    def tick(_unused):
        return tick_game_clock(now_game_time=106)

    fired = _race(tick, 1, 2)
    assert sorted(fired) == [False, True], fired
    assert tick_game_clock(now_game_time=120) is False
    for role in ("watch", "chief"):
        after = sum(e["kind"] == "handover_due" for e in inbox(ship[role]))
        assert after == before[role] + 1, (role, before, after)
    print("OX_G5_PG_ONE_CONCURRENT_DUTY_DEADLINE_PASS", flush=True)
