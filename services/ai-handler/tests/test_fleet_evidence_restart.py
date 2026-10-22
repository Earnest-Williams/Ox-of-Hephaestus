"""Fast, independent contract checks for the P4f 40-actor profile.

No Evennia instance, hosted model, or native Concordia installation needed.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
import unittest

from ox_ai.runtime.evidence_index import ActorEvidenceIndex
from scenarios.profiling.fleet_evidence_restart import (
    actor_specs,
    build_archives,
    event_for,
    profile_fleet,
    run_cohort,
    verify_actor,
)


class FleetEvidenceRestartTests(unittest.TestCase):
    def test_world_sequences_interleave_without_crossover(self):
        actors = actor_specs(4, 800)
        self.assertEqual([a["event_count"] for a in actors], [400, 800, 800, 1200])
        a = event_for(actors[0], 1, 4, 160)
        b = event_for(actors[1], 1, 4, 160)
        c = event_for(actors[0], 2, 4, 160)
        self.assertEqual([a["sequence"], b["sequence"], c["sequence"]], [1, 2, 5])
        self.assertEqual(len({a["event_id"], b["event_id"], c["event_id"]}), 3)
        self.assertEqual((a["recipient_dbref"], c["recipient_dbref"]), ("#1000", "#1000"))
        self.assertEqual(b["recipient_dbref"], "#1001")

    def test_small_fleet_compares_both_policies_and_verified_old_proofs(self):
        result = profile_fleet(
            actors=4, events_per_actor=800, chars=160,
            stagger_width=2, trials=2,
        )
        self.assertEqual(result["fixture"]["build"]["total_events"], 3200)
        self.assertEqual(
            [(r["trial"], r["mode"]) for r in result["rounds"]],
            [(1, "staggered"), (1, "simultaneous"),
             (2, "simultaneous"), (2, "staggered")],
        )
        for r in result["rounds"]:
            self.assertEqual(len(r["actors"]), 4)
            self.assertGreater(r["cohort_wall_s"], 0)
            self.assertEqual({a["actor_dbref"] for a in r["actors"]},
                             {"#1000", "#1001", "#1002", "#1003"})
            self.assertGreater(r["p95_actor_ready_s"], 0)
        self.assertTrue(result["stage_coverage"]["complete_archive_and_obligation_verification"])
        self.assertFalse(result["stage_coverage"]["evennia_websocket_authentication"])
        self.assertGreater(result["fixture"]["build"]["archive_bytes"], 0)

    def test_same_population_runs_width_sweep_in_reversed_order(self):
        result = profile_fleet(
            actors=4, events_per_actor=800, chars=160,
            stagger_width=2, trials=2, widths=(1, 2, 4),
        )
        self.assertEqual(result["fixture"]["build"]["total_events"], 3200)
        self.assertEqual(result["fixture"]["worker_widths"], [1, 2, 4])
        self.assertEqual(
            [(r["trial"], r["parallel_workers"]) for r in result["rounds"]],
            [(1, 1), (1, 2), (1, 4), (2, 4), (2, 2), (2, 1)],
        )
        self.assertEqual(
            [s["parallel_workers"] for s in result["summary"]], [1, 2, 4]
        )
        for record in result["rounds"]:
            self.assertEqual(
                {row["actor_dbref"] for row in record["actors"]},
                {"#1000", "#1001", "#1002", "#1003"},
            )
            self.assertEqual(sum(
                row["event_count"] for row in record["actors"]
            ), 3200)
            self.assertGreater(record["cohort_wall_s"], 0)

    def test_corruption_and_foreign_actor_fail_without_poisoning_other_cache(self):
        with tempfile.TemporaryDirectory() as dirname:
            specs = actor_specs(4, 800)
            build_archives(Path(dirname), specs, chars=160)
            with self.assertRaises(PermissionError):
                ActorEvidenceIndex(Path(specs[0]["path"]), specs[1]["actor_dbref"])
            verified = verify_actor(specs[1], 0.0, 4)
            self.assertEqual(verified["event_count"], 800)
            with sqlite3.connect(specs[0]["path"]) as db:
                db.execute(
                    "UPDATE events SET data_index='{}' WHERE sequence=?",
                    (specs[0]["ordinal"] + 1,),
                )
            with self.assertRaisesRegex(RuntimeError, "Indexed metadata disagrees"):
                verify_actor(specs[0], 0.0, 4)
            # Another actor still passes full verification.
            self.assertGreater(
                run_cohort(specs[1:3], mode="staggered", width=1)["cohort_wall_s"],
                0,
            )

    def test_bad_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            actor_specs(3, 800)
        with self.assertRaises(ValueError):
            actor_specs(4, 300)
        with self.assertRaises(ValueError):
            profile_fleet(
                actors=4, events_per_actor=800, chars=160,
                stagger_width=4, trials=1,
            )
        with self.assertRaises(ValueError):
            profile_fleet(
                actors=4, events_per_actor=800, chars=160,
                stagger_width=2, trials=0,
            )
        for widths in ((1, 1), (0, 4), (1, 5), (), (True, 2)):
            with self.subTest(widths=widths), self.assertRaises(ValueError):
                profile_fleet(
                    actors=4, events_per_actor=800, chars=160,
                    stagger_width=2, trials=1, widths=widths,
                )



if __name__ == "__main__":
    unittest.main()
