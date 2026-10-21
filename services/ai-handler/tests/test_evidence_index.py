"""Bounded-memory, recipient-scoped historical evidence index contracts."""
import sqlite3
import tempfile
from pathlib import Path
import unittest

from ox_ai.runtime.evidence_index import ActorEvidenceIndex


def evidence(n, recipient="#42", *, kind="ship_notice", **data):
    return {
        "event_id": f"oxevt-v2-{n:04d}",
        "sequence": n,
        "recipient_dbref": recipient,
        "sender_dbref": "#1",
        "kind": kind,
        "text": "World-addressed evidence",
        "game_time": float(n),
        "data": data,
    }


class IndexedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ox-evidence-test-")
        self.addCleanup(self.temp.cleanup)
        self.archive = ActorEvidenceIndex(
            Path(self.temp.name) / "actor.sqlite3", "#42"
        )
        self.addCleanup(self.archive.close)

    def test_exact_kind_and_case_lookup_with_immutable_snapshot(self):
        with self.archive.transaction():
            self.archive.append_page([
                evidence(1, kind="captain_problem_open", ticket_id="a"),
                evidence(2, kind="anomaly_notice", case_id="case-a"),
                evidence(4, kind="captain_review_due", ticket_id="a"),
                evidence(7, kind="anomaly_notice", case_id="case-b"),
            ])
        old = self.archive.view()
        self.assertEqual(len(old), 4)
        self.assertEqual(old[-1]["sequence"], 7)
        self.assertEqual([e["sequence"] for e in reversed(old)], [7, 4, 2, 1])
        self.assertEqual(old.get("oxevt-v2-0004")["kind"], "captain_review_due")
        self.assertIsNone(old.get("nonexistent"))
        self.assertEqual(
            [x["sequence"] for x in old.select(kind="anomaly_notice")],
            [2, 7],
        )
        self.assertEqual(
            old.latest("anomaly_notice", data={"case_id": "case-a"})["sequence"], 2,
        )
        with self.archive.transaction():
            self.archive.append_page([evidence(
                9, kind="captain_review_due", ticket_id="a",
            )])
        self.assertEqual(len(old), 4)  # previously returned view cannot change
        self.assertIsNone(old.get("oxevt-v2-0009"))
        newer = self.archive.view()
        self.assertEqual(len(newer), 5)
        self.assertEqual(newer.latest(
            "captain_review_due", data={"ticket_id": "a"},
        )["sequence"], 9)
        self.assertEqual([x["sequence"] for x in newer.select(
            kind="captain_review_due", data={"ticket_id": "a"},
            newest_first=True,
        )], [9, 4])
        self.assertEqual([x["sequence"] for x in self.archive.view(after=4)],
                         [7, 9])

    def test_actor_scope_and_causal_order_fail_closed(self):
        with self.archive.transaction():
            self.archive.append_page([evidence(5)])
        with self.assertRaises(PermissionError):
            with self.archive.transaction():
                self.archive.append_page([evidence(6, recipient="#99")])
        with self.assertRaises(ValueError):
            with self.archive.transaction():
                self.archive.append_page([evidence(5)])
        with self.assertRaises(ValueError):
            with self.archive.transaction():
                self.archive.append_page([evidence(8), evidence(7)])
        with self.assertRaises(ValueError):
            list(self.archive.view().select(data={"evil' OR 1=1 --": "x"}))
        self.assertEqual(self.archive.cursor, 5)
        self.assertEqual(len(self.archive.view()), 1)
        with self.assertRaises(PermissionError):
            ActorEvidenceIndex(Path(self.temp.name) / "actor.sqlite3", "#99")

    def test_transaction_rollback_does_not_advance_history(self):
        with self.assertRaisesRegex(RuntimeError, "lost page"):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(i, kind="shipment") for i in range(1, 129)
                ])
                raise RuntimeError("lost page")
        self.assertEqual(self.archive.cursor, 0)
        self.assertEqual(len(self.archive.view()), 0)
        with self.archive.transaction():
            self.archive.append_page([evidence(130)])
        self.assertEqual([e["sequence"] for e in self.archive.view()], [130])

    def test_many_records_remain_on_disk_not_in_python_history_list(self):
        # The index holds only SQLite rows, plus a 512 KiB DB page cache.
        # No one Python list of 12,800 events survives after each page append.
        for start in range(1, 12801, 128):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(i, kind=("alarm" if i % 10 == 0 else "ship_notice"))
                    for i in range(start, start + 128)
                ])
        view = self.archive.view()
        self.assertEqual(len(view), 12800)
        self.assertEqual(len(list(view.select(kind="alarm"))), 1280)
        self.assertEqual(view[0]["sequence"], 1)
        self.assertEqual(view[-1]["sequence"], 12800)
        self.assertEqual(view.latest("alarm")["sequence"], 12800)
        self.assertGreater(self.archive.path.stat().st_size, 12800)
        self.assertFalse(hasattr(self.archive, "_inbox_history"))
        self.assertFalse(hasattr(view, "_events"))

    def test_open_obligations_and_pinned_historical_views(self):
        with self.archive.transaction():
            self.archive.append_page([
                evidence(1, kind="crew_hail", hail_id="hail-a"),
                evidence(2, kind="captain_problem_open", ticket_id="ticket-a"),
                evidence(3, kind="crew_hail", hail_id="hail-b"),
            ])
        earlier = self.archive.view()
        self.assertEqual([e["sequence"] for e in earlier.pending("hail")], [1, 3])
        self.assertEqual([e["sequence"] for e in earlier.pending("captain")], [2])
        with self.archive.transaction():
            self.archive.append_page([
                evidence(4, kind="hail_answered", hail_id="hail-a"),
                evidence(5, kind="captain_world_resolved", ticket_id="ticket-a"),
            ])
        # Closing a claim does not revise an older pinned historical view.
        self.assertEqual([e["sequence"] for e in earlier.pending("hail")], [1, 3])
        self.assertEqual([e["sequence"] for e in earlier.pending("captain")], [2])
        now = self.archive.view()
        self.assertEqual([e["sequence"] for e in now.pending("hail")], [3])
        self.assertEqual(list(now.pending("captain")), [])
        self.assertEqual(now.get("oxevt-v2-0001")["kind"], "crew_hail")
        self.assertEqual(
            now.latest("hail_answered", data={"hail_id": "hail-a"})["sequence"], 4,
        )
        self.assertEqual(
            list(now.select(kind="crew_hail", after=1))[0]["sequence"], 3,
        )
        self.assertIsNone(
            now.latest("hail_answered", data={"hail_id": "hail-a"}, after=4),
        )
        with self.assertRaises(ValueError):
            list(now.pending("unknown"))
        with self.assertRaises(ValueError):
            list(now.select(after=-1))

    def test_obligation_state_rollback_and_orphan_close(self):
        with self.archive.transaction():
            self.archive.append_page([
                evidence(1, kind="hail_answered", hail_id="never-opened"),
                evidence(2, kind="crew_hail", hail_id="active"),
            ])
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(3, kind="hail_answered", hail_id="active"),
                ])
                raise RuntimeError("truncated")
        self.assertEqual(
            [x["data"]["hail_id"] for x in self.archive.view().pending("hail")],
            ["active"],
        )
        with self.assertRaises(ValueError):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(3, kind="crew_hail", hail_id="active"),
                ])
        self.assertEqual(self.archive.cursor, 2)
        with self.assertRaises(ValueError):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(3, kind="captain_problem_open"),
                ])
        self.assertEqual(self.archive.cursor, 2)

    def test_actor_ids_are_restricted_and_view_slices_are_scoped(self):
        with self.assertRaises(PermissionError):
            ActorEvidenceIndex(Path(self.temp.name) / "bad.sqlite3", "../42")
        with self.archive.transaction():
            self.archive.append_page([evidence(2), evidence(4), evidence(9)])
        view = self.archive.view(after=2, through=9)
        self.assertEqual([e["sequence"] for e in view], [4, 9])
        self.assertEqual([e["sequence"] for e in view[:]], [4, 9])
        self.assertEqual(view[-2]["sequence"], 4)
        with self.assertRaises(IndexError):
            _ = view[2]


if __name__ == "__main__":
    unittest.main()
