"""Finite real-shell containment without any ship/world initialization."""
import unittest

from world.ship_hull_restoration import initial_hull, register_breach
from world.ship_major_damage import (
    MajorDamageError, exterior_face_for, initial_major_damage,
    validate_major_damage, register_major_site, start_containment,
    step_containments, revoke_containment, external_repair_ready,
)

class MajorBreachKernelTests(unittest.TestCase):
    def setUp(self):
        self.zone = "PZ-DR-01-SVC"
        self.face = exterior_face_for(self.zone)
        hull = register_breach(
            initial_hull(), zone=self.zone, site_room="DR-01-GALLERY",
            leak_kg_s=0.5)
        self.reg = register_major_site(
            initial_major_damage(), hull, zone=self.zone,
            exterior_room=self.face,
            boundaries=["ACC-DR-01-SEC-01", "ACC-DR-01-LOCK-ROT"])
        self.assertTrue(validate_major_damage(self.reg))

    def test_six_authored_cargo_skin_faces(self):
        for i in range(1, 7):
            self.assertEqual(
                exterior_face_for(f"PZ-DR-{i:02d}-SVC"),
                f"EXT-DR{i:02d}-SKIN")
        with self.assertRaises(MajorDamageError):
            exterior_face_for("PZ-DR-07-SVC")
        with self.assertRaises(MajorDamageError):
            exterior_face_for("PZ-HAB-03")

    def test_isolation_consumes_120_game_seconds_without_auto_healing(self):
        job = start_containment(self.reg, zone=self.zone, actor="#42")
        for _ in range(4):
            job, completed = step_containments(job, 30, ready_zones=set())
            self.assertFalse(completed)
        self.assertEqual(job["sites"][self.zone]["remaining_s"], 120)
        job, _ = step_containments(job, 60, ready_zones={self.zone})
        self.assertFalse(job["sites"][self.zone]["isolated"])
        job, completed = step_containments(job, 60, ready_zones={self.zone})
        self.assertEqual(completed, (self.zone,))
        self.assertEqual(job["containments_completed"], 1)
        self.assertFalse(external_repair_ready(
            job, zone=self.zone, room=self.face, suit_valid=True,
            actual_closed_boundaries={"ACC-DR-01-LOCK-ROT"}))
        self.assertTrue(external_repair_ready(
            job, zone=self.zone, room=self.face, suit_valid=True,
            actual_closed_boundaries={
                "ACC-DR-01-LOCK-ROT", "ACC-DR-01-SEC-01"}))
        self.assertFalse(external_repair_ready(
            job, zone=self.zone, room=self.face, suit_valid=False,
            actual_closed_boundaries={
                "ACC-DR-01-LOCK-ROT", "ACC-DR-01-SEC-01"}))

    def test_reopening_a_bulkhead_invalidates_capture(self):
        job = start_containment(self.reg, zone=self.zone, actor="#42")
        job, _ = step_containments(job, 60, ready_zones={self.zone})
        job, _ = step_containments(job, 60, ready_zones={self.zone})
        revoked = revoke_containment(job, zone=self.zone)
        self.assertFalse(revoked["sites"][self.zone]["isolated"])
        self.assertEqual(revoked["containments_completed"], 1)
        self.assertFalse(external_repair_ready(
            revoked, zone=self.zone, room=self.face, suit_valid=True,
            actual_closed_boundaries={
                "ACC-DR-01-LOCK-ROT", "ACC-DR-01-SEC-01"}))
        rerun = start_containment(revoked, zone=self.zone, actor="#42")
        self.assertEqual(rerun["sites"][self.zone]["remaining_s"], 120)

    def test_registration_rejects_unrelated_worksite_or_small_leak(self):
        hull = register_breach(
            initial_hull(), zone=self.zone, site_room="DR-01-HUB",
            leak_kg_s=0.005)
        with self.assertRaises(MajorDamageError):
            register_major_site(
                initial_major_damage(), hull, zone=self.zone,
                exterior_room=self.face,
                boundaries=["ACC-DR-01-LOCK-ROT"])
        with self.assertRaises(MajorDamageError):
            register_major_site(
                self.reg, hull, zone=self.zone,
                exterior_room="EXT-DR02-SKIN",
                boundaries=["ACC-DR-01-LOCK-ROT"])
        with self.assertRaises(MajorDamageError):
            register_major_site(
                initial_major_damage(), hull, zone=self.zone,
                exterior_room=self.face, boundaries=[])

    def test_job_identity_and_corruption_are_rejected(self):
        bad = dict(self.reg)
        bad["containments_completed"] = -1
        with self.assertRaises(MajorDamageError):
            validate_major_damage(bad)
        job = start_containment(self.reg, zone=self.zone, actor="#3")
        with self.assertRaises(MajorDamageError):
            start_containment(job, zone=self.zone, actor="#3")
        with self.assertRaises(MajorDamageError):
            step_containments(job, 61, ready_zones={self.zone})
        with self.assertRaises(MajorDamageError):
            step_containments(job, float("nan"), ready_zones={self.zone})


if __name__ == "__main__":
    unittest.main()
