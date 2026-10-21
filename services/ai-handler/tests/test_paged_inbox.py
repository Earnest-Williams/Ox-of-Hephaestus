"""Non-network inbox replay and crash-safe agent cursor tests."""
from collections import deque
import copy
import unittest

from ox_ai.ports.evennia.client import WebPacket
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


class Brain:
    def __init__(self, seen=()):
        self.seen = set(seen)

    def observe_event(self, event):
        self.seen.add(event["event_id"])


class SupervisorFixture:
    read_inbox = CrewWatchSupervisor.read_inbox
    inbox_events_since = CrewWatchSupervisor.inbox_events_since

    def __init__(self, client, saved=None):
        snapshot = copy.deepcopy(saved or {})
        observations = snapshot.pop("_seen", [])
        self.clients = {"lin": client}
        self.brains = {"lin": Brain(observations)}
        self.state = snapshot
        self.saved = None
        self.checkpoints = 0
        self._inbox_history = {}
        self._inbox_sequences = {}
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
        self.assertEqual(worker.inbox_events_since(
            "lin", initial[-1]["sequence"],
        ), [])
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
        self.assertEqual(len(worker._inbox_history["lin"]), old_cursor)
        client.disconnect_page = None
        retried = await worker.read_inbox("lin")
        self.assertEqual(len(retried), 430)
        self.assertEqual(len(worker.brains["lin"].seen), 430)
        self.assertEqual(worker.state["inbox_cursors"]["lin"], 430)

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
        self.assertEqual(worker._inbox_history, {})
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

        class FiveFixture(SupervisorFixture):
            read_inbox = FiveCrewSupervisor.read_inbox

            def __init__(self, client, saved):
                super().__init__(client, saved)
                agenda_record = self.state.setdefault(
                    "agendas", {},
                ).setdefault("lin", {"last_sequence": 160})
                self.agendas = {"lin": PrivateAgenda(agenda_record)}
                self.epistemics = {"lin": PrivateProof()}
                self.state.setdefault("specialist_completed", [])

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
