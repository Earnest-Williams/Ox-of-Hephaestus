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
            self.pending.append(WebPacket("ox_event", (e,), {}))
        self.pending.append(WebPacket("ox_inbox_done", ({
            "version": 2, "count": len(page), "next_cursor": cursor,
            "has_more": len(accessible) > 128,
        },), {}))

    async def receive(self):
        return self.pending.popleft()


class Brain:
    def __init__(self, seen=()):
        self.seen = set(seen)

    def observe_event(self, event):
        self.seen.add(event["event_id"])


class SupervisorFixture:
    read_inbox = CrewWatchSupervisor.read_inbox

    def __init__(self, client, saved=None):
        snapshot = copy.deepcopy(saved or {})
        observations = snapshot.pop("_seen", [])
        self.clients = {"lin": client}
        self.brains = {"lin": Brain(observations)}
        self.state = snapshot
        self.saved = None

    def checkpoint(self):
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
        second = SupervisorFixture(
            MockInboxClient("#10", events), first.saved,
        )
        self.assertEqual(len(await second.read_inbox("lin")), 300)
        self.assertEqual(len(second.brains["lin"].seen), 300)
        events.extend([event(n, "#10") for n in range(301, 406)])
        self.assertEqual(len(await second.read_inbox("lin")), 405)
        self.assertEqual(second.state["inbox_cursors"]["lin"], 405)
        self.assertEqual(len(second.brains["lin"].seen), 405)

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
                    "ox_event", (event(1, "#99"),), {},
                ))
        with self.assertRaises(PermissionError):
            await replay_inbox_pages(Leaking("#10", []))
