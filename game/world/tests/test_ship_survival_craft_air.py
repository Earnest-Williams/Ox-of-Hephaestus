"""Finite two-craft rescue air tests: no hidden oxygen or energy."""
import copy
import unittest
from types import SimpleNamespace

from world.ship_survival_craft_air import (
    PACKS, MAX_RETAINED_KG, DURATION_RATED_S,
    SurvivalAirError, initial_survival_air, validate_survival_air,
    survey_survival_air, command_survival_air, step_survival_air,
)


def worlds():
    equipment={k:SimpleNamespace(space_id=room,condition="serviceable")
               for k,(room,zone,hatch) in PACKS.items()}
    access={hatch:SimpleNamespace(setting="closed",condition="serviceable")
            for room,zone,hatch in PACKS.values()}
    cells={zone:{"mass":100.0,"oxygen":23.0,"co2":1.0,"smoke":0.0,
                 "volume":80.0,"capacity":1200.0,
                 "temperature":293.15,
                 "energy":1300.0*293.15}
           for room,zone,hatch in PACKS.values()}
    return equipment,access,cells


class SurvivalCraftAirTests(unittest.TestCase):
    def test_exact_two_original_shelters_and_no_free_charge(self):
        self.assertEqual(len(PACKS),2)
        original=initial_survival_air()
        self.assertTrue(validate_survival_air(original))
        with self.assertRaises(SurvivalAirError):
            command_survival_air(original,"RESCUE-FWD-LSS","scrub")
        with self.assertRaises(SurvivalAirError):
            survey_survival_air(
                original,"RESCUE-FWD-LSS",
                capacity_kg=MAX_RETAINED_KG+1,runtime_s=10)
        with self.assertRaises(SurvivalAirError):
            survey_survival_air(
                original,"RESCUE-FWD-LSS",
                capacity_kg=.05,runtime_s=DURATION_RATED_S+1)

    def test_shut_original_hatch_has_real_gas_and_media_transfer(self):
        original=survey_survival_air(
            initial_survival_air(),"RESCUE-FWD-LSS",
            capacity_kg=.2,runtime_s=3600)
        original=command_survival_air(original,"RESCUE-FWD-LSS","scrub")
        equip,access,cells=worlds()
        prior_mass=cells["PZ-BOW-RESCUE"]["mass"]
        prior_o2=cells["PZ-BOW-RESCUE"]["oxygen"]
        first,cells=step_survival_air(
            original,10,now_s=1010,equipment=equip,access=access,cells=cells)
        captured=first["meter"]["captured_kg"]
        self.assertGreater(captured,0)
        self.assertAlmostEqual(cells["PZ-BOW-RESCUE"]["mass"]+captured,prior_mass)
        self.assertAlmostEqual(cells["PZ-BOW-RESCUE"]["co2"]+captured,1.0)
        self.assertEqual(cells["PZ-BOW-RESCUE"]["oxygen"],prior_o2)
        self.assertAlmostEqual(first["units"]["RESCUE-FWD-LSS"][
            "charge"]["runtime_remaining_s"],3590)
        self.assertEqual(first["units"]["RESCUE-AFT-LSS"]["captured_kg"],0)
        self.assertTrue(validate_survival_air(first))
        with self.assertRaises(SurvivalAirError):
            step_survival_air(
                first,10,now_s=1010,equipment=equip,access=access,cells=cells)

    def test_open_hatch_power_failure_and_media_depletion_do_not_mint_air(self):
        first=survey_survival_air(
            initial_survival_air(),"RESCUE-FWD-LSS",
            capacity_kg=.01,runtime_s=12)
        first=command_survival_air(first,"RESCUE-FWD-LSS","scrub")
        equip,access,cells=worlds()
        access["ACC-RESCUE-FWD"].setting="open"
        paused,cells=step_survival_air(
            first,10,now_s=1010,equipment=equip,access=access,cells=cells)
        self.assertEqual(paused["meter"]["captured_kg"],0)
        self.assertEqual(paused["units"]["RESCUE-FWD-LSS"][
            "charge"]["runtime_remaining_s"],12)
        access["ACC-RESCUE-FWD"].setting="closed"
        equip["RESCUE-FWD-LSS"].condition="failed"
        broken,cells=step_survival_air(
            paused,10,now_s=1020,equipment=equip,access=access,cells=cells)
        self.assertEqual(broken["meter"]["captured_kg"],0)
        equip["RESCUE-FWD-LSS"].condition="serviceable"
        used,cells=step_survival_air(
            broken,10,now_s=1030,equipment=equip,access=access,cells=cells)
        self.assertGreater(used["meter"]["captured_kg"],0)
        after,cells=step_survival_air(
            used,10,now_s=1040,equipment=equip,access=access,cells=cells)
        self.assertEqual(after["units"]["RESCUE-FWD-LSS"][
            "charge"]["runtime_remaining_s"],0)
        self.assertLessEqual(after["units"]["RESCUE-FWD-LSS"][
            "captured_kg"],.01)
        stopped,cells=step_survival_air(
            after,10,now_s=1050,equipment=equip,access=access,cells=cells)
        self.assertEqual(stopped["last"]["captured_kg"],0)
        with self.assertRaises(SurvivalAirError):
            command_survival_air(stopped,"RESCUE-FWD-LSS","scrub")

    def test_tamper_and_duplicate_survey_are_rejected(self):
        first=survey_survival_air(
            initial_survival_air(),"RESCUE-AFT-LSS",
            capacity_kg=.02,runtime_s=100)
        with self.assertRaises(SurvivalAirError):
            survey_survival_air(
                first,"RESCUE-AFT-LSS",capacity_kg=.02,runtime_s=100)
        corrupted=copy.deepcopy(first)
        corrupted["units"]["RESCUE-AFT-LSS"]["charge"][
            "runtime_remaining_s"]=101
        with self.assertRaises(SurvivalAirError):
            validate_survival_air(corrupted)
        corrupted=copy.deepcopy(first)
        corrupted["units"]["RESCUE-AFT-LSS"]["captured_kg"]=.5
        with self.assertRaises(SurvivalAirError):
            validate_survival_air(corrupted)


if __name__=="__main__":
    unittest.main()
