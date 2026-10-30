"""G19 fitted exterior radiator temperature and six-spot isolation sweep."""
import unittest
from world.ship_exterior_radiators import (
    RADIATORS, FACES, MAX_SKIN_K, ExteriorRadiatorError,
    initial_exterior_radiators, validate_exterior_radiators,
    survey_skin, step_skins, isolated_hardware, work_face_safe,
    issue_service, release_service,
)
from world.ship_motion_machinery import initial_rotors


def hardware():
    iso = {
        "ISO-LT-ROT-A": {"setting": "closed", "condition": "serviceable"},
        "ISO-LT-ROT-B": {"setting": "closed", "condition": "serviceable"},
        **{f"ISO-RAD-HT-{n}": {
            "setting": "closed", "condition": "serviceable"} for n in (1, 2)}}
    equipment = {"LT-PLANT": {"condition": "serviceable", "details": {
        "physics_online": False, "physics_commanded_on": False}}}
    motion = {"command": "coast", "attitude_command": "hold",
              "drive_firing": False, "ftl_leg": None,
              "angular_velocity_rad_s": [0., 0., 0.]}
    return iso, equipment, motion, initial_rotors()


class RadiatorWorkTests(unittest.TestCase):
    def test_exact_six_original_exterior_skins(self):
        self.assertEqual(len(RADIATORS), 6)
        self.assertEqual(len(FACES), 6)
        for key, spec in RADIATORS.items():
            self.assertEqual(FACES[spec["face"]], key)
        self.assertTrue(validate_exterior_radiators(initial_exterior_radiators()))
        for key in RADIATORS:
            self.assertIsNone(initial_exterior_radiators()["faces"][key]["skin_k"])

    def test_unmeasured_or_hot_skin_never_opens_a_work_platform(self):
        i, e, m, r = hardware()
        for key in RADIATORS:
            ledger = initial_exterior_radiators()
            self.assertFalse(work_face_safe(ledger, key, isolators=i,
                                            equipment=e, motion=m, rotors=r))
            ledger = survey_skin(ledger, key, temp_k=400., game_time=1)
            self.assertFalse(work_face_safe(ledger, key, isolators=i,
                                            equipment=e, motion=m, rotors=r))
            for _ in range(30):
                ledger = step_skins(ledger, 60, hot_radiators=set())
            self.assertLess(ledger["faces"][key]["skin_k"], MAX_SKIN_K)
            self.assertTrue(work_face_safe(ledger, key, isolators=i,
                                           equipment=e, motion=m, rotors=r))

    def test_ht_independent_valves_and_lt_both_actual_manifolds(self):
        i, e, m, r = hardware()
        led = initial_exterior_radiators()
        for key in RADIATORS:
            led = survey_skin(led, key, temp_k=282., game_time=1)
            self.assertTrue(work_face_safe(led, key, isolators=i,
                                           equipment=e, motion=m, rotors=r))
        i["ISO-RAD-HT-1"]["setting"] = "open"
        self.assertFalse(work_face_safe(led, "RAD-HT-1", isolators=i,
                                        equipment=e, motion=m, rotors=r))
        self.assertTrue(work_face_safe(led, "RAD-HT-2", isolators=i,
                                       equipment=e, motion=m, rotors=r))
        i["ISO-LT-ROT-A"]["setting"] = "open"
        self.assertFalse(work_face_safe(led, "RAD-LT-1", isolators=i,
                                        equipment=e, motion=m, rotors=r))
        i["ISO-LT-ROT-A"]["setting"] = "closed"
        e["LT-PLANT"]["details"]["physics_online"] = True
        self.assertFalse(isolated_hardware(
            "RAD-LT-2", isolators=i, equipment=e))

    def test_ship_movement_or_nearby_drums_block_all_affected_faces(self):
        i, e, m, r = hardware()
        led = survey_skin(initial_exterior_radiators(),
                          "RAD-LT-1", temp_k=290., game_time=1)
        self.assertTrue(work_face_safe(
            led, "RAD-LT-1", isolators=i, equipment=e, motion=m, rotors=r))
        m["command"] = "accelerate"
        self.assertFalse(work_face_safe(
            led, "RAD-LT-1", isolators=i, equipment=e, motion=m, rotors=r))
        m["command"] = "coast"
        r["DR-03"]["hardlock"] = False
        self.assertFalse(work_face_safe(
            led, "RAD-LT-1", isolators=i, equipment=e, motion=m, rotors=r))

    def test_exclusive_permit_cannot_release_with_people_or_active_work(self):
        led = survey_skin(initial_exterior_radiators(),
                          "RAD-HT-2", temp_k=280., game_time=5)
        grant = issue_service(led, radiator="RAD-HT-2", actor="#13",
                              game_time=6)
        self.assertTrue(validate_exterior_radiators(grant))
        self.assertNotEqual(grant, led)
        for blockers in ({}, {"occupied": True}, {"repair_active": True},
                         {"transit_active": True}):
            with self.subTest(blockers=blockers), self.assertRaises(
                    ExteriorRadiatorError):
                release_service(grant, radiator="RAD-HT-2",
                                actor="#12" if not blockers else "#13",
                                **blockers)
        restored = release_service(grant, radiator="RAD-HT-2",
                                   actor="#13")
        self.assertEqual(restored["issued"], 1)
        self.assertEqual(restored["released"], 1)
        self.assertFalse(restored["permits"])

    def test_hot_again_after_reopening_is_not_a_valid_resumed_worksite(self):
        i, e, m, r = hardware()
        ledger = survey_skin(initial_exterior_radiators(),
                             "RAD-HT-1", temp_k=300., game_time=100)
        ledger = issue_service(ledger, radiator="RAD-HT-1",
                               actor="#1", game_time=101)
        self.assertTrue(work_face_safe(
            ledger, "RAD-HT-1", isolators=i, equipment=e,
            motion=m, rotors=r, require_permit=True))
        i["ISO-RAD-HT-1"]["setting"] = "open"
        ledger = step_skins(ledger, 60, hot_radiators={"RAD-HT-1"})
        self.assertFalse(work_face_safe(
            ledger, "RAD-HT-1", isolators=i, equipment=e,
            motion=m, rotors=r, require_permit=True))


if __name__ == "__main__":
    unittest.main()
