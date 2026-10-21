"""Non-network inbox replay and crash-safe agent cursor tests."""
from collections import deque
import copy
import json
import tempfile
from pathlib import Path
import unittest

from ox_ai.ports.evennia.client import WebPacket
from ox_ai.ports.evennia.journal import continue_digest, journal_seed
from ox_ai.runtime.watch_service import CrewWatchSupervisor, replay_inbox_pages


def event(serial, recipient):
    return {
        "event_id": f"oxevt-v2-{serial:04d}",
        "sequence": serial,
        "recipient_dbref": recipient,
        "sender_dbref": "#50",
        "kind": "alarm",
        "game_time": float(serial),
        "text": "Station alarm",
        "datum_serial": serial,
    }


class MockInboxClient:
    def __init__(self, recipient, events, disconnect_page=None):
        self.character_dbref = recipient
        self.events = events
        self.disconnect_page = disconnect_page
        self.commands = []
        self.pending = deque()

    async def send_line(self, command):
        self.commands.append(command)
        if self.disconnect_page == len(self.commands):
            raise ConnectionError("Simulated lost connection mid-replay")
        after = int(command.split()[1])
        accessible = [e for e in self.events
                      if e["recipient_dbref"] == self.character_dbref
                      and e["sequence"] > after]
        page = accessible[:128]
        cursor = page[-1]["sequence"] if page else after
        for e in page:
            self.pending.append(WebPacket("ox_event", (e,), {"ox_inbox_page": True}))
        self.pending.append(WebPacket("ox_inbox_done", ({
            "version": 2, "count": len(page), "next_cursor": cursor,
            "has_more": len(accessible) > 128,
        },), {}))

    async def receive(self):
        return self.pending.popleft()

    async def receive_matching(self, predicate, *, frame_budget=256):
        for _ in range(frame_budget):
            packet = self.pending.popleft()
            if predicate(packet):
                return packet
        raise RuntimeError("No matching replay packet")


class MockCertifiedClient(MockInboxClient):
    """Authoritative actor-bound journal head for offline cache-reuse tests."""

    authenticated = True

    def __init__(self, recipient, events, generation="a" * 32):
        super().__init__(recipient, events)
        self.generation = generation

    async def send_line(self, command):
        if not command.startswith("oxjournal "):
            return await super().send_line(command)
        self.commands.append(command)
        _, nonce, requested = command.split()
        cursor = int(requested)
        addressed = [
            event for event in self.events
            if event["recipient_dbref"] == self.character_dbref
        ]
        digest = journal_seed(self.generation, self.character_dbref)
        old_prefix = digest if cursor == 0 else None
        for record in addressed:
            # The mock packet is in original Evennia wire form; for the
            # canonical journal chain it must be restored to the same
            # original nested source shape as replay_inbox_pages().
            actual = {
                key: value for key, value in record.items()
                if not key.startswith("datum_")
            }
            actual["data"] = {
                key[len("datum_"):]: value
                for key, value in record.items()
                if key.startswith("datum_")
            }
            digest = continue_digest(digest, actual)
            if actual["sequence"] == cursor:
                old_prefix = digest
        self.pending.append(WebPacket("ox_journal_proof", (json.dumps({
            "version": 1, "nonce": nonce,
            "actor_dbref": self.character_dbref,
            "generation": self.generation,
            "requested_cursor": cursor,
            "prefix_digest": old_prefix,
            "head_cursor": addressed[-1]["sequence"] if addressed else 0,
            "head_digest": digest,
        }),), {}))


class Brain:
    def __init__(self, seen=()):
        self.seen = set(seen)

    def observe_event(self, event):
        self.seen.add(event["event_id"])


class SupervisorFixture:
    read_inbox = CrewWatchSupervisor.read_inbox
    inbox_events_since = CrewWatchSupervisor.inbox_events_since
    prove_world_event = CrewWatchSupervisor.prove_world_event

    def __init__(self, client, saved=None):
        snapshot = copy.deepcopy(saved or {})
        observations = snapshot.pop("_seen", [])
        self.clients = {"lin": client}
        self.brains = {"lin": Brain(observations)}
        self.state = snapshot
        self.ids = {"lin": client.character_dbref}
        self.saved = None
        self.checkpoints = 0
        self._evidence_temporary = tempfile.TemporaryDirectory(prefix="ox-index-test-")
        self._evidence_indexes = {}
        self._inbox_hydrated = set()
        self._inbox_role_locks = {}

    def checkpoint(self):
        self.checkpoints += 1
        self.saved = copy.deepcopy(self.state)
        self.saved["_seen"] = sorted(self.brains["lin"].seen)


class InboxReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_interleaved_2401_events_without_page_loss(self):
        events = [event(n, "#10" if n % 4 else "#11")
                  for n in range(1, 2402)]
        client = MockInboxClient("#10", events)
        read, cursor = await replay_inbox_pages(client)
        expected = [e for e in events if e["recipient_dbref"] == "#10"]
        self.assertEqual([e["event_id"] for e in read],
                         [e["event_id"] for e in expected])
        self.assertEqual(cursor, expected[-1]["sequence"])
        self.assertGreater(len(client.commands), 10)
        self.assertEqual(client.commands[0], "oxinbox 0")
        self.assertNotEqual(client.commands[1], "oxinbox 0")

    async def test_streaming_hydration_keeps_only_one_page_in_python(self):
        events = [event(n, "#10" if n % 4 else "#11")
                  for n in range(1, 8002)]
        client = MockInboxClient("#10", events)
        page_sizes = []
        received_ids = set()

        def append_validated_page(page):
            page_sizes.append(len(page))
            self.assertLessEqual(len(page), 128)
            for event_record in page:
                self.assertEqual(event_record["recipient_dbref"], "#10")
                received_ids.add(event_record["event_id"])

        collected, cursor = await replay_inbox_pages(
            client, page_sink=append_validated_page,
        )
        self.assertEqual(collected, [])  # not the full voyage in a Python list
        self.assertEqual(len(received_ids), 6001)
        self.assertEqual(cursor, 8001)
        self.assertEqual(len(page_sizes), 47)
        self.assertGreater(max(page_sizes), 120)
        self.assertEqual(client.commands[0], "oxinbox 0")
        self.assertNotEqual(client.commands[-1], "oxinbox 0")

    async def test_mid_page_restart_without_losing_event(self):
        events = [event(n, "#10") for n in range(1, 321)]
        failing = MockInboxClient("#10", events, disconnect_page=2)
        with self.assertRaises(ConnectionError):
            await replay_inbox_pages(failing)
        replayed, cursor = await replay_inbox_pages(
            MockInboxClient("#10", events)
        )
        self.assertEqual(len(replayed), 320)
        self.assertEqual(cursor, 320)

    async def test_checkpoint_cursor_only_after_observations(self):
        events = [event(n, "#10") for n in range(1, 301)]
        first = SupervisorFixture(MockInboxClient("#10", events))
        self.assertEqual(len(await first.read_inbox("lin")), 300)
        self.assertEqual(first.state["inbox_cursors"]["lin"], 300)
        self.assertEqual(len(first.brains["lin"].seen), 300)
        self.assertEqual(first.clients["lin"].commands[0], "oxinbox 0")
        self.assertEqual(first.checkpoints, 1)
        self.assertEqual(len(await first.read_inbox("lin")), 300)
        self.assertEqual(first.clients["lin"].commands[-1], "oxinbox 300")
        self.assertEqual(first.checkpoints, 1)
        second = SupervisorFixture(
            MockInboxClient("#10", events), first.saved,
        )
        self.assertEqual(len(await second.read_inbox("lin")), 300)
        # Cold start rehydrates history for legacy lookups; it must NOT
        # re-observe already checkpointed brain episodes or rewrite state.
        self.assertEqual(second.clients["lin"].commands[0], "oxinbox 0")
        self.assertEqual(second.checkpoints, 0)
        self.assertEqual(len(second.brains["lin"].seen), 300)
        events.extend([event(n, "#10") for n in range(301, 406)])
        self.assertEqual(len(await second.read_inbox("lin")), 405)
        self.assertEqual(second.state["inbox_cursors"]["lin"], 405)
        self.assertEqual(len(second.brains["lin"].seen), 405)
        self.assertEqual(second.clients["lin"].commands[-1], "oxinbox 300")
        self.assertEqual(second.checkpoints, 1)
        self.assertEqual(len(second.inbox_events_since("lin", 300)), 105)

    async def test_incremental_reader_avoids_repeated_full_pagination(self):
        events = [event(n, "#10" if n % 5 else "#11")
                  for n in range(1, 2402)]
        client = MockInboxClient("#10", events)
        worker = SupervisorFixture(client)
        initial = await worker.read_inbox("lin")
        page_count = len(client.commands)
        self.assertGreater(page_count, 10)
        self.assertEqual(client.commands[0], "oxinbox 0")
        self.assertEqual(len(worker.brains["lin"].seen), len(initial))
        self.assertEqual(len(await worker.read_inbox("lin")), len(initial))
        self.assertEqual(client.commands[page_count:], [
            "oxinbox " + str(initial[-1]["sequence"]),
        ])
        self.assertEqual(worker.checkpoints, 1)
        self.assertEqual(len(worker.inbox_events_since(
            "lin", initial[-1]["sequence"],
        )), 0)
        events.extend([event(n, "#10") for n in range(2402, 2572)])
        appended = await worker.read_inbox("lin")
        self.assertEqual(len(appended), len(initial) + 170)
        self.assertEqual(client.commands[page_count + 1],
                         "oxinbox " + str(initial[-1]["sequence"]))
        self.assertEqual(len(worker.brains["lin"].seen), len(appended))
        self.assertEqual(worker.state["inbox_cursors"]["lin"], 2571)
        self.assertEqual(worker.checkpoints, 2)
        self.assertEqual(len(worker.inbox_events_since(
            "lin", initial[-1]["sequence"],
        )), 170)

    async def test_hot_cold_full_replay_preserves_old_work_proof_on_restart(self):
        records = [event(n, "#10") for n in range(1, 451)]
        saved = {"hail_work": {
            "hail-open": {"role": "lin", "hail_event_id": "oxevt-v2-0005"},
        }}
        first = SupervisorFixture(MockInboxClient("#10", records), saved)
        initial = await first.read_inbox("lin")
        self.assertEqual(len(initial), 450)
        archive = first._evidence_indexes["lin"]
        self.assertEqual((archive.hot_count, archive.cold_count), (257, 193))
        self.assertEqual(
            initial.get("oxevt-v2-0005")["sequence"], 5,
        )
        self.assertEqual(
            initial.get("oxevt-v2-0001")["sequence"], 1,
        )
        self.assertIsNone(archive._db.execute(
            "SELECT payload FROM events WHERE sequence=1"
        ).fetchone()[0])
        # Process-local archives remain disposable. A second process still
        # authenticates the full inbox from zero, not a portable local cache.
        second = SupervisorFixture(MockInboxClient("#10", records), first.saved)
        reread = await second.read_inbox("lin")
        self.assertEqual(len(reread), 450)
        self.assertEqual(second.clients["lin"].commands[0], "oxinbox 0")
        self.assertEqual((second._evidence_indexes["lin"].hot_count,
                          second._evidence_indexes["lin"].cold_count), (257, 193))
        self.assertEqual(len(second.brains["lin"].seen), 450)
        self.assertEqual(second.checkpoints, 0)
        records.extend([event(n, "#10") for n in range(451, 631)])
        advanced = await second.read_inbox("lin")
        self.assertEqual(len(advanced), 630)
        self.assertEqual(len(second.brains["lin"].seen), 630)
        self.assertEqual(advanced.get("oxevt-v2-0001")["sequence"], 1)
        self.assertEqual(advanced.get("oxevt-v2-0005")["sequence"], 5)
        self.assertEqual((second._evidence_indexes["lin"].hot_count,
                          second._evidence_indexes["lin"].cold_count), (257, 373))

    async def test_authenticated_cache_reuse_skips_old_network_pages(self):
        events = [event(n, "#10") for n in range(1, 801)]
        with tempfile.TemporaryDirectory() as folder:
            first = SupervisorFixture(MockCertifiedClient("#10", events))
            first._journal_continuity = True
            first._evidence_root = Path(folder)
            old = await first.read_inbox("lin")
            self.assertEqual(len(old), 800)
            self.assertEqual(first._evidence_indexes["lin"].cold_count, 544)
            saved = first.saved
            first._evidence_indexes["lin"].close()
            second_client = MockCertifiedClient("#10", events)
            second = SupervisorFixture(second_client, saved)
            second._journal_continuity = True
            second._evidence_root = Path(folder)
            restored = await second.read_inbox("lin")
            self.assertEqual(len(restored), 800)
            self.assertEqual(len(second.brains["lin"].seen), 800)
            self.assertEqual(second.checkpoints, 0)
            self.assertEqual(
                [command for command in second_client.commands
                 if command.startswith("oxinbox ")],
                ["oxinbox 800"],
            )
            self.assertEqual(restored.get("oxevt-v2-0001")["sequence"], 1)
            events.extend(event(n, "#10") for n in range(801, 901))
            resumed = await second.read_inbox("lin")
            self.assertEqual(len(resumed), 900)
            self.assertEqual(len(second.brains["lin"].seen), 900)
            self.assertEqual(
                [cmd for cmd in second_client.commands if cmd.startswith("oxinbox ")],
                ["oxinbox 800", "oxinbox 800"],
            )
            self.assertEqual(
                second._evidence_indexes["lin"].stored_attestation()[1], 900,
            )
            second._evidence_indexes["lin"].close()

    async def test_interrupted_attested_delta_is_not_partially_sealed(self):
        history = [event(n, "#10") for n in range(1, 301)]
        with tempfile.TemporaryDirectory() as folder:
            client = MockCertifiedClient("#10", history)
            worker = SupervisorFixture(client)
            worker._journal_continuity = True
            worker._evidence_root = Path(folder)
            await worker.read_inbox("lin")
            base_digest = worker._evidence_indexes["lin"].stored_attestation()
            self.assertEqual(base_digest[1], 300)
            history.extend(event(n, "#10") for n in range(301, 601))
            # One later page has been indexed inside the transaction when the
            # next world page disappears; neither events nor digest commit.
            client.disconnect_page = len(client.commands) + 2
            with self.assertRaises(ConnectionError):
                await worker.read_inbox("lin")
            self.assertEqual(worker._evidence_indexes["lin"].cursor, 300)
            self.assertEqual(
                worker._evidence_indexes["lin"].stored_attestation(), base_digest,
            )
            self.assertEqual(worker.state["inbox_cursors"]["lin"], 300)
            client.disconnect_page = None
            replayed = await worker.read_inbox("lin")
            self.assertEqual(len(replayed), 600)
            self.assertEqual(
                worker._evidence_indexes["lin"].stored_attestation()[1], 600,
            )
            worker._evidence_indexes["lin"].close()

    async def test_cached_prefix_change_rewind_and_epoch_reset_fail_closed(self):
        original = [event(n, "#10") for n in range(1, 551)]
        with tempfile.TemporaryDirectory() as folder:
            first = SupervisorFixture(MockCertifiedClient("#10", original))
            first._journal_continuity = True
            first._evidence_root = Path(folder)
            await first.read_inbox("lin")
            state = first.saved
            first._evidence_indexes["lin"].close()

            cases = (
                ("world_rewind", original[:400], "a" * 32),
                ("generation_change", original, "b" * 32),
                ("changed_old_event", [
                    {**e, "text": "changed historical content"} if
                    e["sequence"] == 3 else e for e in original
                ], "a" * 32),
            )
            for label, world, generation in cases:
                with self.subTest(label=label):
                    worker = SupervisorFixture(
                        MockCertifiedClient("#10", world, generation), state,
                    )
                    worker._journal_continuity = True
                    worker._evidence_root = Path(folder)
                    with self.assertRaises(RuntimeError):
                        await worker.read_inbox("lin")
                    self.assertEqual(worker.checkpoints, 0)
                    self.assertEqual(worker.state["inbox_cursors"]["lin"], 550)
                    self.assertEqual(len(worker.brains["lin"].seen), 550)
                    worker._evidence_indexes["lin"].close()

    async def test_cache_corruption_and_interrupted_checkpoint_recovery(self):
        class FailOnce(SupervisorFixture):
            def __init__(self, client):
                super().__init__(client)
                self.fail = True

            def checkpoint(self):
                if self.fail:
                    self.fail = False
                    raise OSError("checkpoint storage interruption")
                super().checkpoint()

        records = [event(n, "#10") for n in range(1, 321)]
        with tempfile.TemporaryDirectory() as folder:
            failed = FailOnce(MockCertifiedClient("#10", records))
            failed._journal_continuity = True
            failed._evidence_root = Path(folder)
            with self.assertRaisesRegex(OSError, "checkpoint storage interruption"):
                await failed.read_inbox("lin")
            self.assertEqual(failed._evidence_indexes["lin"].cursor, 320)
            self.assertEqual(
                failed._evidence_indexes["lin"].stored_attestation()[1], 320,
            )
            failed._evidence_indexes["lin"].close()
            next_worker = SupervisorFixture(MockCertifiedClient("#10", records))
            next_worker._journal_continuity = True
            next_worker._evidence_root = Path(folder)
            restored = await next_worker.read_inbox("lin")
            self.assertEqual(len(restored), 320)
            self.assertEqual(next_worker.checkpoints, 1)
            self.assertEqual(len(next_worker.brains["lin"].seen), 320)
            next_worker._evidence_indexes["lin"].close()
            # A damaged cold body is never accepted merely because the saved
            # attestation table and world prefix both look correct.
            from ox_ai.runtime.evidence_index import ActorEvidenceIndex
            archive = ActorEvidenceIndex(Path(folder) / "lin.sqlite3", "#10")
            archive._db.execute(
                "UPDATE cold_events SET body=? WHERE sequence=?",
                (b"corrupt", 1),
            )
            archive.close()
            blocked = SupervisorFixture(MockCertifiedClient("#10", records),
                                        next_worker.saved)
            blocked._journal_continuity = True
            blocked._evidence_root = Path(folder)
            with self.assertRaises(RuntimeError):
                await blocked.read_inbox("lin")
            self.assertEqual(blocked.checkpoints, 0)
            blocked._evidence_indexes["lin"].close()

    async def test_interrupted_incremental_pages_leave_cursor_unadvanced(self):
        events = [event(n, "#10") for n in range(1, 151)]
        client = MockInboxClient("#10", events)
        worker = SupervisorFixture(client)
        await worker.read_inbox("lin")
        old_cursor = worker.state["inbox_cursors"]["lin"]
        events.extend([event(n, "#10") for n in range(151, 431)])
        client.disconnect_page = len(client.commands) + 2
        with self.assertRaises(ConnectionError):
            await worker.read_inbox("lin")
        self.assertEqual(worker.state["inbox_cursors"]["lin"], old_cursor)
        self.assertEqual(len(worker.brains["lin"].seen), old_cursor)
        self.assertEqual(len(worker._evidence_indexes["lin"].view()), old_cursor)
        client.disconnect_page = None
        retried = await worker.read_inbox("lin")
        self.assertEqual(len(retried), 430)
        self.assertEqual(len(worker.brains["lin"].seen), 430)
        self.assertEqual(worker.state["inbox_cursors"]["lin"], 430)

    async def test_checkpoint_failure_replays_indexed_but_unsaved_delta(self):
        class FailOnce(SupervisorFixture):
            def __init__(self, client):
                super().__init__(client)
                self.fail_next_save = True

            def checkpoint(self):
                if self.fail_next_save:
                    self.fail_next_save = False
                    raise OSError("synthetic checkpoint disk failure")
                super().checkpoint()

        events = [event(i, "#10") for i in range(1, 181)]
        client = MockInboxClient("#10", events)
        worker = FailOnce(client)
        with self.assertRaisesRegex(OSError, "checkpoint disk failure"):
            await worker.read_inbox("lin")
        self.assertEqual(worker.state.get("inbox_cursors", {}), {})
        self.assertEqual(worker._evidence_indexes["lin"].cursor, 180)
        self.assertEqual(worker._inbox_hydrated, set())
        self.assertEqual(len(worker.brains["lin"].seen), 180)
        self.assertEqual(worker.checkpoints, 0)

        # The failed save did not fabricate or drop an event. The same
        # process can reuse validated archived rows and save its cursor.
        self.assertEqual(len(await worker.read_inbox("lin")), 180)
        self.assertEqual(client.commands[-1], "oxinbox 180")
        self.assertEqual(worker.state["inbox_cursors"]["lin"], 180)
        self.assertEqual(len(worker.brains["lin"].seen), 180)
        self.assertEqual(worker.checkpoints, 1)

    async def test_world_rewind_does_not_trust_saved_handler_cursor(self):
        old = {
            "inbox_cursors": {"lin": 300},
            "_seen": [f"oxevt-v2-{i:04d}" for i in range(1, 301)],
        }
        worker = SupervisorFixture(
            MockInboxClient("#10", [event(i, "#10") for i in range(1, 201)]),
            old,
        )
        with self.assertRaisesRegex(RuntimeError, "behind local actor checkpoint"):
            await worker.read_inbox("lin")
        self.assertEqual(worker.state["inbox_cursors"]["lin"], 300)
        self.assertEqual(worker._evidence_indexes["lin"].cursor, 0)
        self.assertEqual(worker._inbox_hydrated, set())
        self.assertEqual(worker.checkpoints, 0)

    async def test_same_role_concurrent_reads_serialize_on_one_socket(self):
        import asyncio
        client = MockInboxClient("#10", [
            event(n, "#10") for n in range(1, 190)
        ])
        worker = SupervisorFixture(client)
        both = await asyncio.gather(
            worker.read_inbox("lin"), worker.read_inbox("lin"),
        )
        self.assertEqual([len(events) for events in both], [189, 189])
        self.assertEqual(worker.checkpoints, 1)
        self.assertEqual(client.commands[0], "oxinbox 0")
        self.assertEqual(client.commands[-1], "oxinbox 189")
        self.assertEqual(len(worker.brains["lin"].seen), 189)

    async def test_incomplete_page_cannot_advance_any_cursor(self):
        class Partial(MockInboxClient):
            async def send_line(self, command):
                self.commands.append(command)
                self.pending.append(WebPacket("ox_inbox_done", ({
                    "version": 2, "count": 1,
                    "next_cursor": 17, "has_more": False,
                },), {}))
        worker = SupervisorFixture(Partial("#10", []))
        with self.assertRaisesRegex(RuntimeError, "count disagrees"):
            await worker.read_inbox("lin")
        self.assertEqual(worker.state.get("inbox_cursors", {}), {})
        self.assertEqual(worker._evidence_indexes["lin"].cursor, 0)
        self.assertEqual(worker._inbox_hydrated, set())
        self.assertEqual(worker.checkpoints, 0)

    async def test_private_agenda_and_proof_cursor_backfill_after_parent_checkpoint(self):
        from ox_ai.runtime.five_crew_service import FiveCrewSupervisor

        class PrivateProof:
            def __init__(self):
                self.seen = []
            def receive_event(self, event):
                self.seen.append(event["event_id"])

        class PrivateAgenda:
            def __init__(self, record):
                self.record = record
                self.seen = []
            def observe(self, event):
                self.seen.append(event["event_id"])
                self.record["last_sequence"] = event["sequence"]
            def task(self, _event_id):
                return None

        class FiveFixture(FiveCrewSupervisor):
            def __init__(self, client, saved):
                # Real inheritance is needed: FiveCrewSupervisor.read_inbox
                # uses super() to reach the parent world inbox reader.
                # Supply an isolated test state without opening sockets.
                SupervisorFixture.__init__(self, client, saved)
                agenda_record = self.state.setdefault(
                    "agendas", {},
                ).setdefault("lin", {"last_sequence": 160})
                self.agendas = {"lin": PrivateAgenda(agenda_record)}
                self.epistemics = {"lin": PrivateProof()}
                self.state.setdefault("specialist_completed", [])

            def checkpoint(self):
                SupervisorFixture.checkpoint(self)

        events = [event(n, "#10") for n in range(1, 351)]
        # Simulate an interrupted earlier process: parent cursor and native
        # brain checkpoint reached 350, but its two private consumers only
        # committed through 150 and 160. A new process must not lose 151+.
        saved = {
            "inbox_cursors": {"lin": 350},
            "epistemic_event_cursors": {"lin": 150},
            "agendas": {"lin": {"last_sequence": 160}},
            "specialist_completed": [],
            "_seen": [f"oxevt-v2-{n:04d}" for n in range(1, 351)],
        }
        worker = FiveFixture(MockInboxClient("#10", events), saved)
        self.assertEqual(len(await worker.read_inbox("lin")), 350)
        self.assertEqual(len(worker.epistemics["lin"].seen), 200)
        self.assertEqual(len(worker.agendas["lin"].seen), 190)
        self.assertEqual(worker.state["epistemic_event_cursors"]["lin"], 350)
        self.assertEqual(worker.agendas["lin"].record["last_sequence"], 350)
        self.assertEqual(worker.checkpoints, 1)
        self.assertEqual(len(await worker.read_inbox("lin")), 350)
        self.assertEqual(worker.clients["lin"].commands[-1], "oxinbox 350")
        self.assertEqual(worker.checkpoints, 1)
        self.assertEqual(len(worker.epistemics["lin"].seen), 200)

    async def test_exact_world_proof_is_serialized_and_does_not_advance_history(self):
        from unittest.mock import AsyncMock, patch
        from ox_ai.ports.evennia.evidence import EventProof

        class HeldLease:
            def assert_held(self):
                return None

        client = MockInboxClient("#10", [])
        worker = SupervisorFixture(client)
        worker.lease = HeldLease()
        address = "oxevt-v2-0015"
        source = {
            "event_id": address, "sequence": 15,
            "recipient_dbref": "#10", "sender_dbref": "#21",
            "kind": "radio_alert", "data": {"alarm_id": "test"},
            "text": "World evidence", "game_time": 42.0,
        }

        async def verified(event_id):
            self.assertEqual(event_id, address)
            self.assertTrue(worker._inbox_role_locks["lin"].locked())
            return EventProof("#10", address, "found", source)

        with patch("ox_ai.runtime.watch_service.WorldEventPort") as port:
            port.return_value.lookup = AsyncMock(side_effect=verified)
            received = await worker.prove_world_event(
                "lin", address, kind="radio_alert", sender_dbref="#21",
            )
            self.assertEqual(received, source)
            port.assert_called_with(client)
            with self.assertRaises(PermissionError):
                await worker.prove_world_event(
                    "lin", address, kind="release_granted",
                )
        with self.assertRaises(PermissionError):
            await worker.prove_world_event("another", address, kind="radio_alert")
        self.assertEqual(worker.state, {})
        self.assertEqual(worker._inbox_hydrated, set())
        self.assertEqual(worker._evidence_indexes, {})
        self.assertEqual(worker.checkpoints, 0)

    async def test_private_scope_and_stalled_cursor_fail_closed(self):
        class Stalled(MockInboxClient):
            async def send_line(self, command):
                self.pending.append(WebPacket("ox_inbox_done", ({
                    "version": 2, "count": 1,
                    "next_cursor": 0, "has_more": True,
                },), {}))
        with self.assertRaises(RuntimeError):
            await replay_inbox_pages(Stalled("#10", []))

        class Leaking(MockInboxClient):
            async def send_line(self, command):
                self.pending.append(WebPacket(
                    "ox_event", (event(1, "#99"),), {"ox_inbox_page": True},
                ))
        with self.assertRaises(PermissionError):
            await replay_inbox_pages(Leaking("#10", []))
