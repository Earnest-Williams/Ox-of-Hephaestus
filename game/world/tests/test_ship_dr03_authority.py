"""Drum-3 one-valve, local-priority policy."""
from types import SimpleNamespace
import unittest
from world.ship_dr03_authority import (
    DrumControlError, KEY, ROOM, SCHEMA, STATION, TARGET, control_ref,
    validate_control, next_authority, request_id_valid, check_lt_interlocks,
)

class DrumControlPolicyTests(unittest.TestCase):
    def test_only_real_valve_and_local_possession(self):
        ref=control_ref()
        self.assertEqual(ref["target"],TARGET)
        self.assertFalse(ref["other_isolators_enabled"])
        row=SimpleNamespace(key=KEY,category="control",source_id="DR-03-LT-IF",
            source_model=SCHEMA,space_id=ROOM,reference=ref,condition="serviceable",
            setting="remote",details={"holder":None,"epoch":0})
        self.assertTrue(validate_control(row))
        self.assertEqual(next_authority("remote",None,"#22","takeover"),("local","#22",True))
        with self.assertRaises(DrumControlError):
            next_authority("local","#22","#23","takeover")
        with self.assertRaises(DrumControlError):
            next_authority("local","#22","#23","handback")
        self.assertEqual(next_authority("local","#22","#22","handback"),("remote",None,True))
        row.reference=dict(ref,target="ISO-GEN-M")
        with self.assertRaises(DrumControlError):
            validate_control(row)

    def test_faults_repair_padlocks_and_request_ids(self):
        for token in ("","b"*31,"X"*32,None):
            with self.assertRaises(DrumControlError):
                request_id_valid(token)
        self.assertEqual(request_id_valid("b"*32),"b"*32)
        iso=SimpleNamespace(category="isolator",source_id=TARGET,
            condition="serviceable",reference={"remote_operable":True,
                "manual_operation":True},details={})
        self.assertTrue(check_lt_interlocks(iso,{},value="closed"))
        with self.assertRaises(DrumControlError):
            check_lt_interlocks(iso,{"fault_cases":{"cases":{
                "a":{"feeders":[TARGET],"stage":"repairing"}}}},value="closed")
        iso.details["physics_power_trip_latched"]=True
        with self.assertRaises(DrumControlError):
            check_lt_interlocks(iso,{},value="closed")
        iso.details.clear()
        iso.condition="severed"
        with self.assertRaises(DrumControlError):
            check_lt_interlocks(iso,{},value="open")
