"""Pure G19 tests: all 40 authored cabin coils, finite independent LT heat."""
import copy
import unittest
from types import SimpleNamespace

from world.ship_cabin_fancoils import (
    FANCOILS, MAX_UNIT_KW, CabinCoilError,
    coil_power_node, coil_coolant_node,
    initial_cabin_coils, validate_cabin_coils,
    command_cabin_coil, step_cabin_coils,
)


def installed():
    equipment = {
        name: SimpleNamespace(space_id=room, condition="serviceable")
        for name, (room, zone) in FANCOILS.items()
    }
    cells = {
        zone: {"mass": 120.0, "capacity": 30000.0,
               "temperature": 303.15,
               "energy": (30000.0 + 120.0) * 303.15}
        for room, zone in FANCOILS.values()
    }
    return equipment, cells


class CabinFanCoilTests(unittest.TestCase):
    def test_as_fitted_roster_has_exactly_forty_on_four_original_arcs(self):
        self.assertEqual(len(FANCOILS), 40)
        self.assertEqual(
            {room[:6] for room, zone in FANCOILS.values()},
            {"HAB-01", "HAB-03", "HAB-05", "HAB-07"})
        self.assertEqual(len({coil_power_node(n) for n in FANCOILS}), 40)
        self.assertEqual(len({coil_coolant_node(n) for n in FANCOILS}), 40)
        self.assertTrue(validate_cabin_coils(initial_cabin_coils()))
        with self.assertRaises(CabinCoilError):
            coil_coolant_node("HAB-02-CAB-01-FANCOIL")

    def test_real_individual_electricity_and_lt_circuit_required(self):
        name = "HAB-01-CAB-01-FANCOIL"
        ledger = command_cabin_coil(initial_cabin_coils(), name, "on")
        equipment, cells = installed()
        first, cells, reserved = step_cabin_coils(
            ledger, 10, now_s=1010, powered_nodes=set(),
            coolant_nodes={coil_coolant_node(name)},
            equipment=equipment, cells=cells, cooling_budget_kw=8)
        self.assertEqual(first["units"][name]["last_kj"], 0)
        self.assertEqual(reserved, 0)
        second, cells, reserved = step_cabin_coils(
            first, 10, now_s=1020,
            powered_nodes={coil_power_node(name)}, coolant_nodes=set(),
            equipment=equipment, cells=cells, cooling_budget_kw=8)
        self.assertEqual(second["units"][name]["last_kj"], 0)
        self.assertEqual(reserved, 0)
        third, cells, reserved = step_cabin_coils(
            second, 10, now_s=1030,
            powered_nodes={coil_power_node(name)},
            coolant_nodes={coil_coolant_node(name)},
            equipment=equipment, cells=cells, cooling_budget_kw=8)
        self.assertAlmostEqual(third["units"][name]["last_kj"],
                               MAX_UNIT_KW * 10)
        self.assertAlmostEqual(reserved, MAX_UNIT_KW * 10)
        self.assertLess(cells["PZ-HAB-01"]["temperature"], 303.15)
        self.assertEqual(third["units"][name]["cumulative_kj"],
                         third["meter"]["removed_kj"])
        self.assertTrue(validate_cabin_coils(third))

    def test_two_terminals_share_same_finite_arc_thermal_energy(self):
        a,b="HAB-01-CAB-01-FANCOIL","HAB-01-CAB-02-FANCOIL"
        original = initial_cabin_coils()
        original = command_cabin_coil(original, a, "on")
        original = command_cabin_coil(original, b, "on")
        equipment,cells=installed()
        before=cells["PZ-HAB-01"]["energy"]
        powered={coil_power_node(a),coil_power_node(b)}
        lt={coil_coolant_node(a),coil_coolant_node(b)}
        result,cells,reserved=step_cabin_coils(
            original,10,now_s=1010,powered_nodes=powered,
            coolant_nodes=lt,equipment=equipment,cells=cells,
            cooling_budget_kw=.40)
        self.assertAlmostEqual(reserved,4.0)
        self.assertAlmostEqual(before-cells["PZ-HAB-01"]["energy"],
                               result["meter"]["removed_kj"])
        self.assertAlmostEqual(result["meter"]["removed_kj"],4.0)
        self.assertAlmostEqual(result["units"][a]["last_kj"],2.0)
        self.assertAlmostEqual(result["units"][b]["last_kj"],2.0)
        self.assertEqual(cells["PZ-HAB-03"]["temperature"],303.15)
        self.assertTrue(validate_cabin_coils(result))

    def test_hot_unit_cools_only_to_arc_reference_temperature(self):
        name="HAB-01-CAB-01-FANCOIL"
        original=command_cabin_coil(initial_cabin_coils(),name,"on")
        equipment,cells=installed()
        cell=cells["PZ-HAB-01"]
        cell["temperature"]=293.15001
        cell["energy"]=(cell["capacity"]+cell["mass"])*cell["temperature"]
        result,cells,reserved=step_cabin_coils(
            original,10,now_s=1010,powered_nodes={coil_power_node(name)},
            coolant_nodes={coil_coolant_node(name)},equipment=equipment,
            cells=cells,cooling_budget_kw=100)
        self.assertGreater(result["units"][name]["last_kj"],0)
        self.assertLess(result["units"][name]["last_kj"],reserved)
        self.assertGreaterEqual(cells["PZ-HAB-01"]["temperature"],293.15)
        self.assertAlmostEqual(result["meter"]["removed_kj"],
                               result["units"][name]["last_kj"])

    def test_fault_no_source_no_capacity_and_replay_are_fail_closed(self):
        name="HAB-01-CAB-01-FANCOIL"
        ledger=command_cabin_coil(initial_cabin_coils(),name,"on")
        equipment,cells=installed()
        power={coil_power_node(name)}
        lt={coil_coolant_node(name)}
        equipment[name].condition="failed"
        failed,cells,_=step_cabin_coils(
            ledger,10,now_s=1010,powered_nodes=power,
            coolant_nodes=lt,equipment=equipment,cells=cells,
            cooling_budget_kw=5)
        self.assertEqual(failed["units"][name]["last_kj"],0)
        equipment[name].condition="serviceable"
        dark,cells,_=step_cabin_coils(
            failed,10,now_s=1020,powered_nodes=power,
            coolant_nodes=lt,equipment=equipment,cells=cells,
            cooling_budget_kw=0)
        self.assertEqual(dark["units"][name]["last_kj"],0)
        good,cells,_=step_cabin_coils(
            dark,10,now_s=1030,powered_nodes=power,
            coolant_nodes=lt,equipment=equipment,cells=cells,
            cooling_budget_kw=5)
        self.assertGreater(good["meter"]["removed_kj"],0)
        with self.assertRaises(CabinCoilError):
            step_cabin_coils(
                good,10,now_s=1030,powered_nodes=power,
                coolant_nodes=lt,equipment=equipment,cells=cells,
                cooling_budget_kw=5)
        tampered=copy.deepcopy(good)
        tampered["units"][name]["cumulative_kj"]+=1
        with self.assertRaises(CabinCoilError):
            validate_cabin_coils(tampered)
        broken=copy.deepcopy(good)
        broken["units"]["GHOST"]=broken["units"][name]
        with self.assertRaises(CabinCoilError):
            validate_cabin_coils(broken)


if __name__=="__main__":
    unittest.main()
