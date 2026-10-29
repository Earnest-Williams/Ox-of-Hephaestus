"""Pure G19 portable CO2 scrubber custody, finite output and recovery."""
import copy
import unittest
from types import SimpleNamespace
from world.ship_portable_air import (
    STOWAGE, PortableAirError, initial_portable_air, validate_portable_air,
    survey_portable_air, command_portable_air, step_portable_air,
)


class PortableScrubberTests(unittest.TestCase):
    def setUp(self):
        self.start = initial_portable_air()
        self.rooms = set(STOWAGE.values()) | {"RESCUE-FWD"}
        self.equipment = {key: SimpleNamespace(space_id=room,condition="serviceable")
                          for key,room in STOWAGE.items()}
        self.cells = {"PZ-BOW-RESCUE": {
            "mass": 100., "oxygen": 23., "co2": 1., "smoke": 0.,
            "volume": 80., "temperature": 293.15, "capacity": 1200.,
            "energy": 1300. * 293.15}}
        self.zones = {"RESCUE-FWD": "PZ-BOW-RESCUE"}

    def configured(self):
        name = "PORT-SCRUB-01"
        ledger = survey_portable_air(self.start,name,media_kg=.05,battery_s=30)
        ledger = command_portable_air(ledger,name,"take",actor="#22",
                                      room="TRUNK-A-BOW",known_rooms=self.rooms)
        ledger = command_portable_air(ledger,name,"place",actor="#22",
                                      room="RESCUE-FWD",known_rooms=self.rooms)
        ledger = command_portable_air(ledger,name,"on",actor="#22",
                                      room="RESCUE-FWD",known_rooms=self.rooms)
        return name,ledger

    def test_four_original_units_and_one_time_finite_survey(self):
        self.assertEqual(len(STOWAGE),4)
        self.assertTrue(validate_portable_air(self.start))
        with self.assertRaises(PortableAirError):
            command_portable_air(self.start,"PORT-SCRUB-01","on",actor="#22",
                                  room="TRUNK-A-BOW",known_rooms=self.rooms)
        ledger = survey_portable_air(self.start,"PORT-SCRUB-01",
                                     media_kg=.05,battery_s=30)
        with self.assertRaises(PortableAirError):
            survey_portable_air(ledger,"PORT-SCRUB-01",
                                media_kg=.05,battery_s=30)
        with self.assertRaises(PortableAirError):
            survey_portable_air(self.start,"PORT-SCRUB-01",
                                media_kg=101,battery_s=30)

    def test_carriage_requires_real_custody_and_displacement(self):
        name,ledger=self.configured()
        with self.assertRaises(PortableAirError):
            command_portable_air(ledger,name,"take",actor="#33",
                                  room="RESCUE-FWD",known_rooms=self.rooms)
        with self.assertRaises(PortableAirError):
            command_portable_air(ledger,name,"place",actor="#33",
                                  room="RESCUE-FWD",known_rooms=self.rooms)
        ledger=command_portable_air(ledger,name,"off",actor="#22",
                                    room="RESCUE-FWD",known_rooms=self.rooms)
        ledger=command_portable_air(ledger,name,"take",actor="#22",
                                    room="RESCUE-FWD",known_rooms=self.rooms)
        self.assertIsNone(ledger["units"][name]["room"])
        with self.assertRaises(PortableAirError):
            command_portable_air(ledger,name,"on",actor="#22",
                                  room="RESCUE-FWD",known_rooms=self.rooms)

    def test_real_gas_mass_and_finite_battery_media(self):
        name,ledger=self.configured()
        result,cells=step_portable_air(ledger,10,now_s=1010,
                                      equipment=self.equipment,
                                      room_zones=self.zones,cells=self.cells)
        used=result["meter"]["captured_kg"]
        self.assertGreater(used,0)
        self.assertAlmostEqual(cells["PZ-BOW-RESCUE"]["mass"]+used,100)
        self.assertAlmostEqual(cells["PZ-BOW-RESCUE"]["co2"]+used,1)
        self.assertEqual(cells["PZ-BOW-RESCUE"]["oxygen"],23)
        self.assertEqual(result["units"][name]["survey"]["battery_remaining_s"],20)
        with self.assertRaises(PortableAirError):
            step_portable_air(result,10,now_s=1010,
                              equipment=self.equipment,
                              room_zones=self.zones,cells=cells)
        for t in (1020,1030,1040):
            result,cells=step_portable_air(result,10,now_s=t,
                                           equipment=self.equipment,
                                           room_zones=self.zones,cells=cells)
        self.assertEqual(result["units"][name]["survey"]["battery_remaining_s"],0)
        self.assertLessEqual(result["meter"]["captured_kg"],.05)
        self.assertTrue(validate_portable_air(result))

    def test_broken_or_unknown_gas_does_not_grant_output(self):
        name,ledger=self.configured()
        self.equipment[name].condition="failed"
        state,cells=step_portable_air(ledger,10,now_s=1010,
                                     equipment=self.equipment,
                                     room_zones=self.zones,cells=self.cells)
        self.assertEqual(state["meter"]["captured_kg"],0)
        self.assertEqual(state["units"][name]["survey"]["battery_remaining_s"],30)
        self.equipment[name].condition="serviceable"
        state["units"][name]["room"]="F2-BAY"
        state,cells=step_portable_air(state,10,now_s=1020,
                                     equipment=self.equipment,
                                     room_zones=self.zones,cells=cells)
        self.assertEqual(state["meter"]["captured_kg"],0)

    def test_tamper_rejected(self):
        name,ledger=self.configured()
        bad=copy.deepcopy(ledger)
        bad["units"][name]["survey"]["battery_remaining_s"]=31
        with self.assertRaises(PortableAirError):
            validate_portable_air(bad)


if __name__=="__main__":
    unittest.main()
