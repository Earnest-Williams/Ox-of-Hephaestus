"""G19 original PROP-SVC positive gas, physically metered hatch and work permit."""
import copy
import unittest

from world.ship_propulsion_bay_service import (
    BayAccessError, VOLUME_MAX_M3, initial_bay_service, validate_bay,
    survey_existing_gas, source_pressure, bay_pressure, bay_gas_safe,
    equalize_from_trunk, bay_entry_ready, safe_motion, permit_entry,
    finish_entry, inspect_bay, release_entry,
)

MOTION = {
    "command": "coast", "attitude_command": "hold",
    "drive_condition": "inhibited", "rcs_condition": "inhibited",
    "drive_firing": False, "attitude_firing": False,
    "ftl_leg": None, "drive_heat_kj": 0,
}


def sample(pressure=101000):
    return survey_existing_gas(
        initial_bay_service(), volume_m3=1000,
        pressure_pa=pressure, temperature_k=293.15,
        oxygen_mass_fraction=.232, co2_mass_fraction=.0004,
        smoke_mass_fraction=0, now_s=1000, hatch_closed=True)


def trunk():
    mass = 101325 * 950/(287.05*293.15)
    return {
        "mass_kg": mass, "oxygen_kg": mass*.232,
        "co2_kg": mass*.0004, "smoke_kg": 0.002,
        "temperature_k": 293.15,
        "volume_m3": 950,
    }


class PropulsionBayPureTests(unittest.TestCase):
    def test_survey_does_not_invent_replenishable_gas_or_a_new_pressure_cell(self):
        initial = initial_bay_service()
        self.assertTrue(validate_bay(initial))
        self.assertFalse(bay_entry_ready(
            initial, source_pa=101325, source_safe=True, motion=MOTION,
            feeder_open=True, hatch_sound=True, other_closed=True,
            now_s=1000, require_permit=False))
        self.assertGreater(VOLUME_MAX_M3, 1200)
        s = sample()
        self.assertAlmostEqual(
            s["initial_survey_kg"], 101000*1000/(287.05*293.15))
        self.assertEqual(s["trunk_to_bay_kg"], 0)
        self.assertTrue(bay_gas_safe(s["gas"]))
        with self.assertRaises(BayAccessError):
            survey_existing_gas(
                s, volume_m3=1000, pressure_pa=111000,
                temperature_k=293.15, oxygen_mass_fraction=.232,
                co2_mass_fraction=.0004, smoke_mass_fraction=0,
                now_s=1020, hatch_closed=True)
        with self.assertRaises(BayAccessError):
            survey_existing_gas(
                initial, volume_m3=2000, pressure_pa=101000,
                temperature_k=293.15, oxygen_mass_fraction=.232,
                co2_mass_fraction=.0004, smoke_mass_fraction=0,
                now_s=1000, hatch_closed=True)

    def test_bounded_bleed_reduces_real_source_and_credits_exact_bay_mass(self):
        s = sample(98500)
        source = trunk()
        before = source["mass_kg"] + s["gas"]["mass_kg"]
        self.assertFalse(bay_entry_ready(
            s, source_pa=source_pressure(source), source_safe=True,
            motion=MOTION, feeder_open=True, hatch_sound=True,
            other_closed=True, now_s=1000, require_permit=False))
        s, source = equalize_from_trunk(
            s, requested_kg=5, source=source, now_s=1010,
            source_safe=True, hatch_closed=True, other_closed=True)
        self.assertAlmostEqual(
            source["mass_kg"] + s["gas"]["mass_kg"], before,
            places=9)
        self.assertAlmostEqual(s["trunk_to_bay_kg"], 5)
        self.assertAlmostEqual(
            s["gas"]["mass_kg"],
            s["initial_survey_kg"] + 5)
        self.assertAlmostEqual(
            s["gas"]["oxygen_kg"] + source["oxygen_kg"],
            sample(98500)["gas"]["oxygen_kg"] + trunk()["oxygen_kg"])
        self.assertAlmostEqual(
            s["gas"]["smoke_kg"] + source["smoke_kg"],
            sample(98500)["gas"]["smoke_kg"] + trunk()["smoke_kg"])
        self.assertTrue(validate_bay(s))
        # One more measured, bounded tap can bring the pressurised compartment
        # through a real 2 kPa differential threshold; never instant gas.
        if abs(source_pressure(source) - bay_pressure(s["gas"])) > 2000:
            s, source = equalize_from_trunk(
                s, requested_kg=2, source=source, now_s=1020,
                source_safe=True, hatch_closed=True, other_closed=True)
        self.assertTrue(bay_entry_ready(
            s, source_pa=source_pressure(source), source_safe=True,
            motion=MOTION, feeder_open=True, hatch_sound=True,
            other_closed=True, now_s=1020, require_permit=False))

    def test_no_unsafe_hatch_shortcut_even_with_suit_and_permission(self):
        s = sample()
        for params in (
                {"source_safe":False}, {"feeder_open":False},
                {"hatch_sound":False}, {"other_closed":False},
                {"source_pa":111000},
                {"motion":{**MOTION,"drive_condition":"operational"}},
                {"motion":{**MOTION,"rcs_condition":"operational"}},
                {"motion":{**MOTION,"command":"x+"}},
                {"motion":{**MOTION,"drive_heat_kj":3000000}},
                {"now_s":3000},
        ):
            opts = {
                "source_pa":101325, "source_safe":True,
                "motion":MOTION, "feeder_open":True,
                "hatch_sound":True, "other_closed":True,
                "now_s":1000, "require_permit":False,
            }
            opts.update(params)
            self.assertFalse(bay_entry_ready(s, **opts), params)
        toxic = survey_existing_gas(
            initial_bay_service(), volume_m3=1000,
            pressure_pa=101000, temperature_k=293.15,
            oxygen_mass_fraction=.05, co2_mass_fraction=.15,
            smoke_mass_fraction=0, now_s=1000, hatch_closed=True)
        self.assertFalse(bay_gas_safe(toxic["gas"]))
        with self.assertRaises(BayAccessError):
            equalize_from_trunk(
                s, requested_kg=5, source=trunk(), now_s=1000,
                source_safe=True, hatch_closed=False, other_closed=True)
        with self.assertRaises(BayAccessError):
            equalize_from_trunk(
                s, requested_kg=1000, source=trunk(), now_s=1000,
                source_safe=True, hatch_closed=True, other_closed=True)

    def test_one_worker_real_bay_entry_and_closed_boundary_release(self):
        s = sample()
        self.assertTrue(bay_entry_ready(
            s, source_pa=101325, source_safe=True, motion=MOTION,
            feeder_open=True, hatch_sound=True, other_closed=True,
            now_s=1000, require_permit=False))
        permit=permit_entry(s, worker="#1", now_s=1000)
        self.assertFalse(bay_entry_ready(
            permit, source_pa=101325, source_safe=True, motion=MOTION,
            feeder_open=False, hatch_sound=True, other_closed=True,
            now_s=1000))
        with self.assertRaises(BayAccessError):
            permit_entry(permit, worker="#2", now_s=1000)
        with self.assertRaises(BayAccessError):
            finish_entry(permit, worker="#2")
        inside = finish_entry(permit, worker="#1")
        self.assertEqual(inside["entries"],1)
        inspected = inspect_bay(inside,worker="#1")
        self.assertEqual(inspected["inspections"],1)
        with self.assertRaises(BayAccessError):
            release_entry(inspected, worker="#1", hatch_closed=False,
                          bay_empty=True, repairs_active=False)
        with self.assertRaises(BayAccessError):
            release_entry(inspected, worker="#1", hatch_closed=True,
                          bay_empty=False, repairs_active=False)
        with self.assertRaises(BayAccessError):
            release_entry(inspected, worker="#1", hatch_closed=True,
                          bay_empty=True, repairs_active=True)
        final = release_entry(
            inspected, worker="#1", hatch_closed=True,
            bay_empty=True, repairs_active=False)
        self.assertIsNone(final["permit"])
        self.assertEqual(final["entries"],1)
        broken = copy.deepcopy(final)
        broken["trunk_to_bay_kg"]+=1
        with self.assertRaises(BayAccessError):
            validate_bay(broken)


if __name__ == "__main__":
    unittest.main()
