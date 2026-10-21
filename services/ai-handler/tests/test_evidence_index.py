"""Bounded-memory, recipient-scoped historical evidence index contracts."""
import sqlite3
import tempfile
from pathlib import Path
import unittest

from ox_ai.runtime.evidence_index import ActorEvidenceIndex, checkpoint_evidence_pins
from ox_ai.ports.evennia.journal import continue_digest, journal_seed


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

    def test_lossless_hot_cold_selection_exact_proofs_and_snapshots(self):
        records = [
            evidence(i, kind=("anomaly_crew_report" if i % 11 == 0
                              else "ship_notice"),
                     case_id="old-case" if i % 11 == 0 else "other")
            for i in range(1, 1001)
        ]
        with self.archive.transaction():
            for start in range(0, len(records), 128):
                self.archive.append_page(records[start:start + 128])
            self.archive.replace_pins(["oxevt-v2-0003", "oxevt-v2-0044"])
        earlier = self.archive.view()
        self.assertEqual(self.archive.hot_count, 1000)
        with self.archive.transaction():
            moved = self.archive.compact_hot(recent=31, batch_size=17)
        self.assertEqual(moved, 967)
        self.assertEqual(self.archive.hot_count, 33)
        self.assertEqual(self.archive.cold_count, 967)
        self.assertEqual(len(earlier), len(records))
        self.assertEqual(list(earlier), records)
        self.assertEqual(
            earlier.get("oxevt-v2-0001"), records[0],
        )
        self.assertEqual(
            earlier.get("oxevt-v2-0003"), records[2],
        )
        self.assertEqual(
            [x["event_id"] for x in earlier.select(
                kind="anomaly_crew_report", data={"case_id": "old-case"},
            )],
            [e["event_id"] for e in records if e["kind"] == "anomaly_crew_report"],
        )
        self.assertEqual(
            earlier.latest("anomaly_crew_report")["sequence"], 990,
        )
        self.assertEqual(earlier[:3], records[:3])
        self.assertEqual(earlier[-2:], records[-2:])
        self.assertEqual(list(reversed(earlier))[:2], records[-2:][::-1])
        self.assertEqual(
            self.archive._db.execute(
                "SELECT payload FROM events WHERE sequence=1"
            ).fetchone()[0], None,
        )
        self.assertIsNotNone(self.archive._db.execute(
            "SELECT body FROM cold_events WHERE sequence=1"
        ).fetchone()[0])

    def test_open_obligations_outlive_hot_window_and_historic_snapshots(self):
        with self.archive.transaction():
            self.archive.append_page([
                evidence(1, kind="crew_hail", hail_id="open-hail"),
                evidence(2, kind="captain_problem_open", ticket_id="open-case"),
                evidence(3, kind="crew_hail", hail_id="finished-hail"),
                evidence(4, kind="hail_answered", hail_id="finished-hail"),
                *[evidence(i) for i in range(5, 301)],
            ])
        previous = self.archive.view(through=3)
        self.assertEqual(
            [e["sequence"] for e in previous.pending("hail")], [1, 3],
        )
        moved = self.archive.compact_hot(recent=12, batch_size=19)
        self.assertEqual(moved, 286)
        self.assertEqual(self.archive.hot_count, 14)
        self.assertEqual(
            [e["sequence"] for e in self.archive.view().pending("hail")], [1],
        )
        self.assertEqual(
            [e["sequence"] for e in self.archive.view().pending("captain")], [2],
        )
        self.assertEqual(
            [e["sequence"] for e in previous.pending("hail")], [1, 3],
        )
        self.assertEqual(self.archive.view().get("oxevt-v2-0003")["sequence"], 3)
        self.assertIsNotNone(self.archive._db.execute(
            "SELECT payload FROM events WHERE sequence=1"
        ).fetchone()[0])
        self.assertIsNone(self.archive._db.execute(
            "SELECT payload FROM events WHERE sequence=3"
        ).fetchone()[0])

    def test_repin_promotes_exact_cold_evidence_without_world_change(self):
        with self.archive.transaction():
            self.archive.append_page([evidence(i) for i in range(1, 81)])
        self.archive.compact_hot(recent=8)
        self.assertEqual((self.archive.hot_count, self.archive.cold_count), (8, 72))
        self.archive.replace_pins({"oxevt-v2-0005"})
        self.assertEqual((self.archive.hot_count, self.archive.cold_count), (9, 71))
        self.assertEqual(self.archive.view().get("oxevt-v2-0005"), evidence(5))
        self.archive.replace_pins(set())
        self.archive.compact_hot(recent=8)
        self.assertEqual((self.archive.hot_count, self.archive.cold_count), (8, 72))
        self.assertEqual(self.archive.view().get("oxevt-v2-0005"), evidence(5))

    def test_cold_checksum_corruption_fails_closed_and_transaction_rolls_back(self):
        with self.archive.transaction():
            self.archive.append_page([evidence(i) for i in range(1, 40)])
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            with self.archive.transaction():
                self.archive.compact_hot(recent=2, batch_size=5)
                raise RuntimeError("simulated disk crash")
        self.assertEqual(self.archive.cold_count, 0)
        self.assertEqual(self.archive.hot_count, 39)
        self.archive.compact_hot(recent=2)
        with self.assertRaises(ValueError):
            self.archive.compact_hot(recent=0)
        with self.assertRaises(ValueError):
            self.archive.replace_pins({"not-a-world-id"})
        self.archive._db.execute(
            "UPDATE cold_events SET body=? WHERE sequence=1", (b"tampered",),
        )
        with self.assertRaises(RuntimeError):
            self.archive.view().get("oxevt-v2-0001")
        self.assertEqual(self.archive.view().get("oxevt-v2-0039"), evidence(39))

    def test_lossless_sqlite_repack_preserves_archive_and_world_seal(self):
        generation = "b" * 32
        digest = journal_seed(generation, "#42")
        messages = []
        for n in range(1, 3073):
            kind = ("crew_hail" if n == 1
                    else "captain_problem_open" if n == 2
                    else "ship_notice")
            details = ({"hail_id": "still-open"} if n == 1
                       else {"ticket_id": "still-open-ticket"} if n == 2
                       else {"case_id": f"case-{n % 25}"})
            item = evidence(n, kind=kind, **details)
            item["text"] = ("Archived reactor pressure log with detailed "
                            "readings and signed observations. " * 19)
            messages.append(item)
        with self.archive.transaction():
            for offset in range(0, len(messages), 128):
                page = messages[offset:offset + 128]
                self.archive.append_page(page)
                for item in page:
                    digest = continue_digest(digest, item)
            self.archive.replace_pins({"oxevt-v2-0003"})
            self.assertGreater(self.archive.compact_hot(), 2048)
            self.archive.seal_attestation(generation, digest)
        before_bytes = self.archive.path.stat().st_size
        with self.assertRaisesRegex(RuntimeError, "during an evidence transaction"):
            with self.archive.transaction():
                self.archive.repack_if_worthwhile()
        self.assertTrue(self.archive.repack_if_worthwhile())
        after_bytes = self.archive.path.stat().st_size
        self.assertLess(after_bytes, before_bytes)
        self.assertFalse(self.archive.repack_if_worthwhile())
        self.assertEqual(
            self.archive.stored_attestation(), (generation, 3072, digest),
        )
        self.assertEqual(self.archive.recompute_prefix(generation), digest)
        self.assertEqual(self.archive.view().get("oxevt-v2-0001"), messages[0])
        self.assertEqual(self.archive.view().get("oxevt-v2-3072"), messages[-1])
        self.assertEqual(
            [e["sequence"] for e in self.archive.view().pending("hail")], [1],
        )
        self.assertEqual(
            [e["sequence"] for e in self.archive.view().pending("captain")], [2],
        )
        with self.assertRaises(ValueError):
            self.archive.repack_if_worthwhile(after_demotions=0)
        reopened = ActorEvidenceIndex(self.archive.path, "#42")
        try:
            self.assertEqual(reopened.recompute_prefix(generation), digest)
            self.assertEqual(reopened.view().get("oxevt-v2-0017"), messages[16])
            self.assertFalse(reopened.repack_if_worthwhile())
        finally:
            reopened.close()

    def test_repack_batched_demotion_counter_is_durable_and_rollback_safe(self):
        with self.archive.transaction():
            self.archive.append_page([
                evidence(n) for n in range(1, 62)
            ])
            moved = self.archive.compact_hot(recent=8)
            self.assertEqual(moved, 53)
        self.assertFalse(self.archive.repack_if_worthwhile(after_demotions=75))
        before_count = self.archive._db.execute(
            "SELECT demoted_since_repack FROM local_maintenance"
        ).fetchone()[0]
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(n) for n in range(62, 103)
                ])
                self.archive.compact_hot(recent=8)
                raise RuntimeError("interrupted")
        self.assertEqual(self.archive.cursor, 61)
        self.assertEqual(self.archive._db.execute(
            "SELECT demoted_since_repack FROM local_maintenance"
        ).fetchone()[0], before_count)
        with self.archive.transaction():
            self.archive.append_page([
                evidence(n) for n in range(62, 103)
            ])
            self.archive.compact_hot(recent=8)
        self.assertTrue(self.archive.repack_if_worthwhile(after_demotions=75))
        self.assertEqual(len(self.archive.view()), 102)
        self.assertEqual(self.archive._db.execute(
            "SELECT demoted_since_repack FROM local_maintenance"
        ).fetchone()[0], 0)

    def test_repack_requires_proportionally_more_growth_in_large_archives(self):
        with self.archive.transaction():
            for start in range(1, 1001, 128):
                self.archive.append_page([
                    evidence(i) for i in range(start, min(start + 128, 1001))
                ])
            self.archive.compact_hot(recent=8)
        self.assertTrue(self.archive.repack_if_worthwhile(after_demotions=8))

        def grow(first, end):
            with self.archive.transaction():
                self.archive.append_page([
                    evidence(i) for i in range(first, end)
                ])
                self.archive.compact_hot(recent=8)

        grow(1001, 1041)
        self.assertFalse(self.archive.repack_if_worthwhile(after_demotions=8))
        grow(1041, 1281)
        self.assertFalse(self.archive.repack_if_worthwhile(after_demotions=8))
        grow(1281, 1361)
        self.assertTrue(self.archive.repack_if_worthwhile(after_demotions=8))
        self.assertEqual(len(self.archive.view()), 1360)
        self.assertEqual(self.archive.view().get("oxevt-v2-0001"), evidence(1))
        self.assertFalse(self.archive.repack_if_worthwhile(after_demotions=8))

    def test_checkpoint_hot_pins_ignore_terminal_and_cross_role_work(self):
        state = {
            "current": {"radio_event": "oxevt-v2-0007"},
            "hail_work": {
                "hail-a": {"role": "lin", "hail_event_id": "oxevt-v2-0003"},
                "hail-b": {"role": "ari", "hail_event_id": "oxevt-v2-0004"},
            },
            "specialist_jobs": {
                "lin": {"event_id": "oxevt-v2-0008"},
                "ari": {"event_id": "oxevt-v2-0009"},
            },
            "agendas": {
                "lin": {"tasks": {
                    "a": {"task_id": "oxevt-v2-0010", "status": "deferred"},
                    "b": {"task_id": "oxevt-v2-0011", "status": "completed"},
                }},
            },
            "completed": [{"resolution_event": "oxevt-v2-0001"}],
            "specialist_handled": {"lin": ["oxevt-v2-0002"]},
        }
        self.assertEqual(
            checkpoint_evidence_pins(state, "lin"),
            {"oxevt-v2-0003", "oxevt-v2-0007",
             "oxevt-v2-0008", "oxevt-v2-0010"},
        )

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
