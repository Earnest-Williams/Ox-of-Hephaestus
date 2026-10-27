"""Bounded G19 medical conservation and recovery tests (no voyage)."""
import unittest
from world.ship_crew_exposure import initial_exposure
from world.ship_crew_medical import (
    MedicalError, initial_medical, begin_care, step_care, validate_medical,
)
class MedicalTests(unittest.TestCase):
    def setUp(self):
        self.h = initial_exposure()
        self.h.update(injury=0.3, condition="impaired")
        self.m = initial_medical()
    def begin(self):
        return begin_care(self.m, patient="#1", caregiver="#2",
                          health=self.h, patient_room="HAB-04",
                          caregiver_room="HAB-04", equipment_ok=True,
                          breathable=True)
    def test_finite_stores_and_no_input_mutation(self):
        result = self.begin()
        self.assertEqual(result["dressings"], 23)
        self.assertEqual(result["used_fluid_kg"], 0.5)
        self.assertTrue(validate_medical(result))
        self.assertEqual(self.m, initial_medical())
    def test_requires_real_co_location_and_safe_medical_bay(self):
        for change in ({"patient_room": "HAB-01"}, {"equipment_ok": False},
                       {"breathable": False}, {"caregiver": "#1"}):
            args = dict(patient="#1", caregiver="#2", health=self.h,
                        patient_room="HAB-04", caregiver_room="HAB-04",
                        equipment_ok=True, breathable=True)
            args.update(change)
            with self.assertRaises(MedicalError):
                begin_care(self.m, **args)
    def test_stabilisation_suspends_and_preserves_injury(self):
        m = self.begin()
        after, h, completed = step_care(m, {"#1": self.h}, 10,
                                      occupants={"#1"}, equipment_ok=True,
                                      breathable=True)
        self.assertEqual(after["cases"]["#1"]["remaining_s"], 300)
        self.assertEqual(h["#1"]["injury"], 0.3)
        self.assertFalse(completed)
    def test_30_ticks_finish_only_one_finite_course(self):
        m = self.begin()
        rows = {"#1": self.h}
        for _ in range(30):
            m, rows, completed = step_care(m, rows, 10,
                              occupants={"#1", "#2"}, equipment_ok=True,
                              breathable=True)
        self.assertEqual(completed, ("#1",))
        self.assertEqual(m["completed"], 1)
        self.assertEqual(m["cases"], {})
        self.assertGreater(rows["#1"]["injury"], 0.29)
        self.assertLess(rows["#1"]["injury"], 0.3)
    def test_dead_patient_never_revived(self):
        m = self.begin()
        dead = dict(self.h, injury=1.0, condition="dead")
        m, rows, done = step_care(m, {"#1": dead}, 10,
                              occupants={"#1", "#2"}, equipment_ok=True,
                              breathable=True)
        self.assertEqual(rows["#1"], dead)
        self.assertFalse(done)
        self.assertEqual(m["cases"], {})
    def test_invalid_quantities_and_missing_patient_fail(self):
        with self.assertRaises(MedicalError):
            step_care(self.begin(), {}, 10, occupants={"#1", "#2"},
                      equipment_ok=True, breathable=True)
        with self.assertRaises(MedicalError):
            step_care(self.m, {}, 11, occupants=set(),
                      equipment_ok=True, breathable=True)
        corrupted = self.begin()
        corrupted["fluid_kg"] += 1
        with self.assertRaises(MedicalError):
            validate_medical(corrupted)
if __name__ == "__main__":
    unittest.main()
