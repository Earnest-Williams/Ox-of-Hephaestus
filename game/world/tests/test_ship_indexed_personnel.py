"""Finite personnel carriage tests; no Evennia or voyage needed."""
import copy
import unittest
from types import SimpleNamespace

from world.ship_indexed_personnel import (
    IndexedTransferError, link_contract, initial_personnel_transfers,
    validate_personnel_transfers, begin_personnel_transfer,
    step_personnel_transfers, finish_personnel_transfer,
    indexed_mechanism_ready,
)
from world.ship_motion_machinery import initial_rotors, set_rotor_command


class IndexedPersonTransferTests(unittest.TestCase):
    def test_exact_nine_authored_links_and_times(self):
        for i in range(1, 7):
            spec = link_contract(f"ACC-DR-{i:02d}-LOCK-ROT")
            self.assertEqual(spec["seconds"], 180)
        for station in "AB":
            spec = link_contract(f"ACC-IX-{station}-ROT")
            self.assertEqual(spec["seconds"], 300)
        workshop = link_contract("ACC-WR-IX-HUB")
        self.assertEqual(workshop["rotor"], "WR-01")
        self.assertEqual(workshop["seconds"], 20)
        self.assertEqual(workshop["fixed_hatch"], "ACC-WR-FIXED-IX")
        with self.assertRaises(IndexedTransferError):
            link_contract("ACC-DR-07-LOCK-ROT")
        with self.assertRaises(IndexedTransferError):
            link_contract("ACC-DR-01-FREIGHT-CAPTURE")

    def test_timed_bidirectional_transfer_and_receipt_identity(self):
        empty = initial_personnel_transfers()
        spec = link_contract("ACC-DR-01-LOCK-ROT")
        job = begin_personnel_transfer(
            empty, link=spec["link"], actor="#42",
            origin=spec["from"], destination=spec["to"], request_id="1" * 32)
        self.assertFalse(empty["jobs"])
        for _ in range(2):
            job, candidates = step_personnel_transfers(
                job, 60, ready_links={spec["link"]})
            self.assertFalse(candidates)
        job, candidates = step_personnel_transfers(
            job, 60, ready_links={spec["link"]})
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["to"], spec["to"])
        with self.assertRaises(IndexedTransferError):
            finish_personnel_transfer(job, rotor="DR-01", request_id="2" * 32)
        job = finish_personnel_transfer(
            job, rotor="DR-01", request_id="1" * 32)
        self.assertEqual(job["completed"], 1)
        self.assertFalse(job["jobs"])
        return_trip = begin_personnel_transfer(
            job, link=spec["link"], actor="#42",
            origin=spec["to"], destination=spec["from"], request_id="2" * 32)
        self.assertEqual(return_trip["jobs"]["DR-01"]["to"], spec["from"])

    def test_pause_when_power_door_or_indexer_fails(self):
        spec = link_contract("ACC-IX-A-ROT")
        job = begin_personnel_transfer(
            initial_personnel_transfers(), link=spec["link"],
            actor="#9", origin=spec["from"], destination=spec["to"],
            request_id="a" * 32)
        for _ in range(9):
            job, candidates = step_personnel_transfers(
                job, 60, ready_links=set())
            self.assertEqual(job["jobs"]["HAB"]["remaining_s"], 300)
            self.assertFalse(candidates)
        job, _ = step_personnel_transfers(
            job, 60, ready_links={spec["link"]})
        self.assertEqual(job["jobs"]["HAB"]["remaining_s"], 240)

    def test_rotor_is_exclusive_and_corruption_refused(self):
        c = link_contract("ACC-IX-A-ROT")
        state = begin_personnel_transfer(
            initial_personnel_transfers(), link=c["link"], actor="#1",
            origin=c["from"], destination=c["to"], request_id="b" * 32)
        d = link_contract("ACC-IX-B-ROT")
        with self.assertRaises(IndexedTransferError):
            begin_personnel_transfer(
                state, link=d["link"], actor="#2",
                origin=d["from"], destination=d["to"], request_id="c" * 32)
        corrupt = copy.deepcopy(state)
        corrupt["jobs"]["HAB"]["remaining_s"] = -3
        with self.assertRaises(IndexedTransferError):
            validate_personnel_transfers(corrupt)
        with self.assertRaises(IndexedTransferError):
            finish_personnel_transfer(
                state, rotor="HAB", request_id="b" * 32)

    def test_mechanism_needs_closed_fixed_hatch_and_sound_installed_hardware(self):
        spec = link_contract("ACC-DR-01-LOCK-ROT")
        def access(id, kind, a, b, seconds):
            return SimpleNamespace(
                setting="closed", condition="serviceable",
                reference={"kind":kind, "from":a, "to":b,
                           "pressure_boundary":True, "traverse_time_s":seconds})
        doors = {
            spec["link"]:access(spec["link"], "indexed_rotary_transfer",
                                spec["from"], spec["to"], 180),
            spec["fixed_hatch"]:access(spec["fixed_hatch"], "pressure_door",
                                      "TRUNK-A-DR-01", spec["from"], 20),
        }
        equip = {name:SimpleNamespace(condition="serviceable")
                 for name in spec["hardware"]}
        zones = {spec["from"]:"PZ-DR-01-LOCK", spec["to"]:"PZ-DR-01-SVC"}
        press = {zone:SimpleNamespace(
            quantity=100, details={"gas_volume_m3":100, "temperature_k":293})
                 for zone in zones.values()}
        rotors = initial_rotors()
        def ready(rows=rotors):
            return indexed_mechanism_ready(
                spec["link"], rotors=rows, equipment=equip, access=doors,
                pressure=press, room_zones=zones,
                pressure_safe=lambda _:True, powered=True)
        self.assertFalse(ready())
        rotors = set_rotor_command(rotors, "DR-01", "passenger_extend")
        self.assertTrue(ready(rotors))
        doors[spec["fixed_hatch"]].setting = "open"
        self.assertFalse(ready(rotors))
        doors[spec["fixed_hatch"]].setting = "closed"
        equip[spec["hardware"][0]].condition = "failed"
        self.assertFalse(ready(rotors))
        equip[spec["hardware"][0]].condition = "serviceable"
        self.assertFalse(indexed_mechanism_ready(
            spec["link"], rotors=rotors, equipment=equip, access=doors,
            pressure=press, room_zones=zones,
            pressure_safe=lambda _:True, powered=False))


if __name__ == "__main__":
    unittest.main()
