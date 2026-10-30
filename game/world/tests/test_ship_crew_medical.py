"""HAB-04 first-aid stores, human custody and finite stabilisation."""
import copy
import unittest

from world.ship_crew_exposure import initial_exposure
from world.ship_crew_medical import (
    MedicalError, TREATMENT_ROOM, OBSERVATION_ROOM, initial_medical, validate_medical,
    carry_medical_kit, begin_care, begin_observation, discharge_observation, step_care,
)


class MedicalTests(unittest.TestCase):
    def setUp(self):
        self.h = initial_exposure()
        self.h.update(injury=0.30, condition="impaired")
        self.m = initial_medical(dressings=4, fluid_kg=2.0)

    def staged(self):
        med = carry_medical_kit(
            self.m, actor="#2", verb="pickup", cases=2)
        return carry_medical_kit(
            med, actor="#2", verb="deliver")

    def begin(self):
        return begin_care(self.staged(), patient="#1", caregiver="#2",
                          health=self.h, patient_room=TREATMENT_ROOM,
                          caregiver_room=TREATMENT_ROOM,
                          equipment_ok=True, breathable=True)

    def test_no_unsurveyed_stock_and_bounded_operator_survey(self):
        self.assertEqual(initial_medical()["dressings"], 0)
        self.assertEqual(initial_medical()["pharmacy_dressings"], 0)
        with self.assertRaises(MedicalError):
            initial_medical(dressings=25, fluid_kg=12.0)
        with self.assertRaises(MedicalError):
            initial_medical(dressings=24, fluid_kg=12.01)
        with self.assertRaises(MedicalError):
            initial_medical(dressings=True, fluid_kg=12.0)

    def test_kit_custody_requires_real_pickup_and_delivery(self):
        carried = carry_medical_kit(self.m, actor="#2", verb="pickup", cases=2)
        self.assertEqual(carried["pharmacy_dressings"], 2)
        self.assertEqual(carried["dressings"], 0)
        self.assertEqual(carried["carried"]["#2"]["fluid_kg"], 1.0)
        with self.assertRaises(MedicalError):
            carry_medical_kit(carried, actor="#2", verb="pickup", cases=1)
        delivered = carry_medical_kit(carried, actor="#2", verb="deliver")
        self.assertEqual(delivered["dressings"], 2)
        self.assertEqual(delivered["fluid_kg"], 1.0)
        self.assertFalse(delivered["carried"])
        self.assertTrue(validate_medical(delivered))
        self.assertEqual(self.m["pharmacy_dressings"], 4)

    def test_finite_stores_and_no_input_mutation(self):
        m = self.staged()
        result = begin_care(
            m, patient="#1", caregiver="#2", health=self.h,
            patient_room=TREATMENT_ROOM, caregiver_room=TREATMENT_ROOM,
            equipment_ok=True, breathable=True)
        self.assertEqual(result["dressings"], 1)
        self.assertEqual(result["used_fluid_kg"], .5)
        self.assertEqual(result["pharmacy_dressings"], 2)
        self.assertEqual(m["used_dressings"], 0)

    def test_requires_real_co_location_and_safe_medical_bay(self):
        for change in ({"patient_room": "HAB-04-COR"},
                       {"equipment_ok": False}, {"breathable": False},
                       {"caregiver": "#1"}):
            args = dict(patient="#1", caregiver="#2", health=self.h,
                        patient_room=TREATMENT_ROOM,
                        caregiver_room=TREATMENT_ROOM,
                        equipment_ok=True, breathable=True)
            args.update(change)
            with self.assertRaises(MedicalError):
                begin_care(self.staged(), **args)
        with self.assertRaises(MedicalError):
            begin_care(self.m, patient="#1", caregiver="#2", health=self.h,
                       patient_room=TREATMENT_ROOM,
                       caregiver_room=TREATMENT_ROOM,
                       equipment_ok=True, breathable=True)

    def test_stabilisation_suspends_and_preserves_injury(self):
        m = self.begin()
        after, h, completed = step_care(
            m, {"#1": self.h}, 10, occupants={"#1"},
            equipment_ok=True, breathable=True)
        self.assertEqual(after["cases"]["#1"]["remaining_s"], 300)
        self.assertEqual(h["#1"]["injury"], 0.30)
        self.assertFalse(completed)

    def test_30_ticks_finish_only_one_finite_course(self):
        m = self.begin()
        rows = {"#1": copy.deepcopy(self.h)}
        for _ in range(30):
            m, rows, completed = step_care(
                m, rows, 10, occupants={"#1", "#2"},
                equipment_ok=True, breathable=True)
        self.assertEqual(completed, ("#1",))
        self.assertEqual(m["completed"], 1)
        self.assertEqual(m["cases"], {})
        self.assertAlmostEqual(rows["#1"]["injury"], .297)
        self.assertEqual(m["used_dressings"], 1)
        self.assertEqual(m["used_fluid_kg"], .5)

    def test_dead_patient_never_revived_and_stores_not_refunded(self):
        dead = dict(self.h, injury=1.0, condition="dead")
        m, rows, done = step_care(
            self.begin(), {"#1": dead}, 10, occupants={"#1", "#2"},
            equipment_ok=True, breathable=True)
        self.assertEqual(rows["#1"], dead)
        self.assertFalse(done)
        self.assertFalse(m["cases"])
        self.assertEqual(m["used_dressings"], 1)

    def test_followup_observation_consumes_stock_and_persists_recovery(self):
        m = self.staged()
        m = begin_observation(
            m, patient="#1", caregiver="#2", health=self.h,
            patient_room=TREATMENT_ROOM, caregiver_room=TREATMENT_ROOM,
            equipment_ok=True, breathable=True)
        self.assertEqual(m["used_dressings"], 1)
        self.assertEqual(m["observations"]["#1"]["remaining_s"], 7200)
        before = self.h["injury"]
        paused, unchanged, _ = step_care(
            m, {"#1": self.h}, 10, occupants={"#1"},
            equipment_ok=True, breathable=True)
        self.assertEqual(unchanged["#1"]["injury"], before)
        self.assertEqual(paused["observations"]["#1"]["remaining_s"], 7200)
        progressed, recovered, _ = step_care(
            m, {"#1": self.h}, 10, occupants={"#1", "#2"},
            equipment_ok=True, breathable=True)
        self.assertLess(recovered["#1"]["injury"], before)
        self.assertEqual(progressed["observations"]["#1"]["observed_s"], 10)
        self.assertEqual(progressed["used_fluid_kg"], .5)

    def test_observation_rejects_duplicate_attendant_and_replay_stock(self):
        m = begin_observation(
            self.staged(), patient="#1", caregiver="#2", health=self.h,
            patient_room=TREATMENT_ROOM, caregiver_room=TREATMENT_ROOM,
            equipment_ok=True, breathable=True)
        with self.assertRaises(MedicalError):
            begin_observation(m, patient="#1", caregiver="#2",
                              health=self.h, patient_room=TREATMENT_ROOM,
                              caregiver_room=TREATMENT_ROOM,
                              equipment_ok=True, breathable=True)
        discharged = discharge_observation(m, patient="#1", caregiver="#2")
        self.assertFalse(discharged["observations"])
        self.assertEqual(discharged["used_dressings"], 1)
        with self.assertRaises(MedicalError):
            discharge_observation(discharged, patient="#1", caregiver="#2")

    def test_real_observation_room_has_separate_finite_stock_and_power(self):
        in_hand = carry_medical_kit(
            self.m, actor="#2", verb="pickup", cases=2)
        at_obs = carry_medical_kit(
            in_hand, actor="#2", verb="deliver",
            destination=OBSERVATION_ROOM)
        self.assertEqual(at_obs["obs_dressings"], 2)
        self.assertEqual(at_obs["dressings"], 0)
        with self.assertRaises(MedicalError):
            begin_observation(
                self.staged(), patient="#1", caregiver="#2", health=self.h,
                patient_room=OBSERVATION_ROOM,
                caregiver_room=OBSERVATION_ROOM,
                equipment_ok=True, breathable=True)
        course = begin_observation(
            at_obs, patient="#1", caregiver="#2", health=self.h,
            patient_room=OBSERVATION_ROOM,
            caregiver_room=OBSERVATION_ROOM,
            equipment_ok=True, breathable=True)
        self.assertEqual(course["obs_dressings"], 1)
        self.assertEqual(course["obs_fluid_kg"], .5)
        self.assertEqual(course["observations"]["#1"]["room"],
                         OBSERVATION_ROOM)
        # A treatment-room witness cannot substitute for the actual
        # powered, staffed observation site.
        paused, health, _ = step_care(
            course, {"#1": self.h}, 10, occupants={"#1", "#2"},
            equipment_ok=True, breathable=True,
            observer_occupants=set(), observer_powered=True,
            observer_breathable=True)
        self.assertEqual(paused["observations"]["#1"]["observed_s"], 0)
        self.assertEqual(health["#1"]["injury"], self.h["injury"])
        unpowered, health, _ = step_care(
            course, {"#1": self.h}, 10, occupants=set(),
            equipment_ok=True, breathable=True,
            observer_occupants={"#1", "#2"}, observer_powered=False,
            observer_breathable=True)
        self.assertEqual(unpowered["observations"]["#1"]["observed_s"], 0)
        recovered, health, _ = step_care(
            course, {"#1": self.h}, 10, occupants=set(),
            equipment_ok=False, breathable=True,
            observer_occupants={"#1", "#2"}, observer_powered=True,
            observer_breathable=True)
        self.assertEqual(recovered["observations"]["#1"]["observed_s"], 10)
        self.assertLess(health["#1"]["injury"], self.h["injury"])
        self.assertEqual(recovered["used_dressings"], 1)

    def test_malformed_legacy_and_new_observation_stock_are_rejected(self):
        staged = carry_medical_kit(
            carry_medical_kit(
                self.m, actor="#2", verb="pickup", cases=1),
            actor="#2", verb="deliver", destination=OBSERVATION_ROOM)
        staged["obs_fluid_kg"] += .5
        with self.assertRaises(MedicalError):
            validate_medical(staged)
        damaged = initial_medical(dressings=2, fluid_kg=1)
        damaged["observation_completed"] = -1
        with self.assertRaises(MedicalError):
            validate_medical(damaged)

    def test_observation_completion_and_fatality(self):
        m = begin_observation(
            self.staged(), patient="#1", caregiver="#2", health=self.h,
            patient_room=TREATMENT_ROOM, caregiver_room=TREATMENT_ROOM,
            equipment_ok=True, breathable=True)
        rows = {"#1": copy.deepcopy(self.h)}
        for _ in range(720):
            m, rows, _ = step_care(
                m, rows, 10, occupants={"#1", "#2"},
                equipment_ok=True, breathable=True)
        self.assertFalse(m["observations"])
        self.assertEqual(m["observation_completed"], 1)
        self.assertAlmostEqual(rows["#1"]["injury"], .30 - .000003 * 7200)
        fatal = begin_observation(
            self.staged(), patient="#1", caregiver="#2", health=self.h,
            patient_room=TREATMENT_ROOM, caregiver_room=TREATMENT_ROOM,
            equipment_ok=True, breathable=True)
        dead = dict(self.h, injury=1.0, condition="dead")
        fatal, result, _ = step_care(
            fatal, {"#1": dead}, 10, occupants={"#1", "#2"},
            equipment_ok=True, breathable=True)
        self.assertEqual(result["#1"]["condition"], "dead")
        self.assertEqual(fatal["observation_completed"], 0)

    def test_corrupt_stores_and_unbounded_clock_are_rejected(self):
        damaged = self.staged()
        damaged["fluid_kg"] += .5
        with self.assertRaises(MedicalError):
            validate_medical(damaged)
        damaged = self.begin()
        damaged["cases"]["#1"]["remaining_s"] = float("nan")
        with self.assertRaises(MedicalError):
            validate_medical(damaged)
        with self.assertRaises(MedicalError):
            step_care(self.begin(), {}, 11, occupants={"#1", "#2"},
                      equipment_ok=True, breathable=True)


if __name__ == "__main__":
    unittest.main()
