"""G19 physical portable emergency pump and smoke fan pure acceptance."""
import copy
import unittest
from types import SimpleNamespace

from world.ship_portable_damage import (
    FITTED, PUMPS, FANS, PortableDamageError, initial_portable_damage,
    validate_portable_damage, survey_portable_damage,
    command_portable_damage, step_portable_damage,
)
from world.ship_water_recycling import initial_water


class PortableMachineTests(unittest.TestCase):
    def setUp(self):
        self.units = {key: SimpleNamespace(space_id=home,condition="serviceable")
                      for key,home in FITTED.items()}
        self.known = set(FITTED.values()) | {"WASTE-A","WASTE-B","TEST-CABIN"}
        self.stations = {"A":"WASTE-A","B":"WASTE-B"}
        self.zones = {"TEST-CABIN":"PZ-CABIN"}
        self.cells = {"PZ-CABIN": {
            "mass":100.0,"oxygen":22.0,"co2":.03,"smoke":.1,
            "volume":80.0,"capacity":1200.0,
            "temperature":293.15,"energy":1300.0*293.15}}
        self.water=initial_water()
        self.water["local"]["A"]["grey"] = 8.0
        self.water["working_kg"] -= 8.0

    def setup_pump(self):
        name="DC-PUMP-01"
        ledger=survey_portable_damage(initial_portable_damage(),name,battery_s=30)
        ledger=self.action(ledger,name,"take","TRUNK-A-BOW")
        ledger=self.action(ledger,name,"place","WASTE-A")
        ledger=self.action(ledger,name,"route:A:grey","WASTE-A")
        ledger=self.action(ledger,name,"on","WASTE-A")
        return name,ledger

    def setup_fan(self):
        name="DC-SMOKE-FAN-01"
        ledger=survey_portable_damage(initial_portable_damage(),name,
                                      battery_s=30,filter_kg=.05)
        ledger=self.action(ledger,name,"take","TRUNK-A-BOW")
        ledger=self.action(ledger,name,"place","TEST-CABIN")
        ledger=self.action(ledger,name,"on","TEST-CABIN")
        return name,ledger

    def action(self,ledger,name,action,room,actor="#22"):
        return command_portable_damage(
            ledger,name,action,room=room,actor=actor,
            known_rooms=self.known,pump_stations=self.stations)

    def step(self,ledger,clock,*,ready=None):
        return step_portable_damage(
            ledger,10,now_s=clock,equipment=self.units,cells=self.cells,
            room_zones=self.zones,water=self.water,
            wet_ready=ready if ready is not None else {},
            pump_stations=self.stations)

    def test_exact_original_roster_and_finite_unique_survey(self):
        self.assertEqual((len(PUMPS),len(FANS),len(FITTED)),(4,6,10))
        self.assertTrue(validate_portable_damage(initial_portable_damage()))
        ledger=survey_portable_damage(
            initial_portable_damage(),"DC-SMOKE-FAN-06",
            battery_s=60,filter_kg=.04)
        with self.assertRaises(PortableDamageError):
            survey_portable_damage(ledger,"DC-SMOKE-FAN-06",
                                   battery_s=60,filter_kg=.04)
        with self.assertRaises(PortableDamageError):
            survey_portable_damage(initial_portable_damage(),
                                   "DC-PUMP-01",battery_s=30,filter_kg=2)
        with self.assertRaises(PortableDamageError):
            survey_portable_damage(initial_portable_damage(),
                                   "DC-SMOKE-FAN-01",battery_s=0,filter_kg=1)

    def test_pump_really_moves_liquid_with_exact_valved_route(self):
        name,ledger=self.setup_pump()
        refused,_,w=self.step(ledger,1010,ready={"B_grey":True})
        self.assertEqual(refused["meter"]["pumped_kg"],0)
        self.assertEqual(w["fixed"]["grey"],0)
        self.assertEqual(refused["units"][name]["survey"]["battery_remaining_s"],30)
        moved,_,w=self.step(refused,1020,ready={"A_grey":True})
        pumped=moved["units"][name]["last_kg"]
        self.assertGreater(pumped,0)
        self.assertAlmostEqual(w["fixed"]["grey"],pumped)
        self.assertAlmostEqual(w["local"]["A"]["grey"]+pumped,8)
        self.assertAlmostEqual(moved["meter"]["pumped_kg"],pumped)
        self.assertEqual(moved["units"][name]["survey"]["battery_remaining_s"],20)
        with self.assertRaises(PortableDamageError):
            self.step(moved,1020,ready={"A_grey":True})
        self.assertTrue(validate_portable_damage(moved))

    def test_pump_cannot_overfill_or_cross_wrong_medium(self):
        name,ledger=self.setup_pump()
        self.water["fixed"]["grey"]=9999.0
        moved,_,w=self.step(ledger,1010,ready={"A_black":True,"A_grey":True})
        self.assertEqual(moved["meter"]["pumped_kg"],1.0)
        self.assertEqual(w["fixed"]["grey"],10000.0)
        moved,_,w=self.step(moved,1020,ready={"A_grey":True})
        self.assertEqual(w["fixed"]["grey"],10000.0)
        self.assertEqual(moved["meter"]["pumped_kg"],1.0)

    def test_fan_recirculates_and_conserves_smoke_as_retained_filter(self):
        name,ledger=self.setup_fan()
        mass=self.cells["PZ-CABIN"]["mass"]
        smoke=self.cells["PZ-CABIN"]["smoke"]
        next_step,cells,_=self.step(ledger,1010)
        captured=next_step["meter"]["smoke_captured_kg"]
        self.assertGreater(captured,0)
        self.assertGreater(next_step["meter"]["recirculated_m3"],0)
        self.assertAlmostEqual(cells["PZ-CABIN"]["mass"]+captured,mass)
        self.assertAlmostEqual(cells["PZ-CABIN"]["smoke"]+captured,smoke)
        self.assertEqual(cells["PZ-CABIN"]["oxygen"],22)
        self.assertEqual(next_step["units"][name]["survey"]["battery_remaining_s"],20)
        with self.assertRaises(PortableDamageError):
            self.step(next_step,1010)

    def test_failed_fan_trips_and_cannot_auto_restart_after_repair(self):
        name,ledger=self.setup_fan()
        self.units[name].condition="failed"
        stopped,_,_=self.step(ledger,1010)
        self.assertEqual(stopped["units"][name]["mode"],"off")
        self.assertEqual(stopped["meter"]["smoke_captured_kg"],0)
        self.units[name].condition="serviceable"
        after,_,_=self.step(stopped,1020)
        self.assertEqual(after["meter"]["recirculated_m3"],0)
        self.assertEqual(after["units"][name]["survey"]["battery_remaining_s"],30)

    def test_carry_and_route_fail_closed(self):
        name,ledger=self.setup_pump()
        with self.assertRaises(PortableDamageError):
            self.action(ledger,name,"take","WASTE-A")
        with self.assertRaises(PortableDamageError):
            self.action(ledger,name,"route:B:grey","WASTE-A")
        with self.assertRaises(PortableDamageError):
            self.action(ledger,name,"place","WASTE-A",actor="#43")
        bad=copy.deepcopy(ledger)
        bad["units"][name]["cumulative_kg"]=99
        with self.assertRaises(PortableDamageError):
            validate_portable_damage(bad)


if __name__=="__main__":
    unittest.main()
