"""Pure original generator-room containment, finite source gas and permits."""
import unittest
from world.ship_generator_bay_service import (
    ROOMS, GeneratorBayError, initial_generator_bays, validate_generator_bays,
    survey_room, bleed_room, entry_ready, secure_room, enter_or_inspect,
    release_room)
from world.ship_propulsion_bay_service import bay_pressure, source_pressure


def measured(room, pressure=101000):
    return survey_room(initial_generator_bays(), room,
        volume_m3=ROOMS[room][5] * .75, pressure_pa=pressure,
        temperature_k=293.15, oxygen_fraction=.232, co2_fraction=.0004,
        smoke_fraction=0, skin_k=299, now_s=1000, hatch_closed=True)


def source():
    mass = 101325*950/(287.05*293.15)
    return {"mass_kg":mass,"oxygen_kg":mass*.232,"co2_kg":mass*.0004,
            "smoke_kg":0,"temperature_k":293.15,"volume_m3":950}


class GeneratorRoomService(unittest.TestCase):
    def test_all_three_original_rooms_have_separate_uninvented_charges(self):
        self.assertEqual(len(ROOMS),3)
        blank=initial_generator_bays()
        self.assertTrue(validate_generator_bays(blank))
        for room in ROOMS:
            self.assertFalse(entry_ready(blank,room,source_pa=101325,
                source_safe=True,hatch_sound=True,feeder_open=True,
                generator_stopped=True,now_s=1000))
            s=measured(room)
            self.assertGreater(s["rooms"][room]["initial_kg"],0)
            self.assertEqual(sum(v["gas"] is not None for v in
                s["rooms"].values()),1)
            with self.assertRaises(GeneratorBayError):
                survey_room(s,room,volume_m3=ROOMS[room][5]*.75,
                    pressure_pa=120000,temperature_k=293.15,
                    oxygen_fraction=.232,co2_fraction=.0004,
                    smoke_fraction=0,skin_k=299,now_s=1001,
                    hatch_closed=True)
            with self.assertRaises(GeneratorBayError):
                survey_room(blank,room,volume_m3=ROOMS[room][5]+1,
                    pressure_pa=101000,temperature_k=293.15,
                    oxygen_fraction=.232,co2_fraction=.0004,
                    smoke_fraction=0,skin_k=299,now_s=1000,
                    hatch_closed=True)

    def test_mixed_gas_mass_transfer_is_conserved_and_bounded(self):
        s=measured("GEN-B-ROOM",97000)
        src=source()
        gas=s["rooms"]["GEN-B-ROOM"]["gas"]
        mass=src["mass_kg"]+gas["mass_kg"]
        o2=src["oxygen_kg"]+gas["oxygen_kg"]
        s,src=bleed_room(s,"GEN-B-ROOM",kg=3,source=src,now_s=1001,
            source_safe=True,hatch_closed=True,generator_stopped=True,
            feeder_open=True)
        gas=s["rooms"]["GEN-B-ROOM"]["gas"]
        self.assertAlmostEqual(mass,src["mass_kg"]+gas["mass_kg"])
        self.assertAlmostEqual(o2,src["oxygen_kg"]+gas["oxygen_kg"])
        self.assertLess(bay_pressure(gas),source_pressure(src))
        self.assertEqual(s["rooms"]["GEN-B-ROOM"]["received_kg"],3)
        with self.assertRaises(GeneratorBayError):
            bleed_room(s,"GEN-B-ROOM",kg=100,source=src,now_s=1002,
                source_safe=True,hatch_closed=True,generator_stopped=True,
                feeder_open=True)

    def test_owner_pressure_fuse_and_cooldown_gates(self):
        room="GEN-M-ROOM"; s=measured(room)
        opts=dict(source_pa=101325,source_safe=True,hatch_sound=True,
                  feeder_open=True,generator_stopped=True,now_s=1000)
        self.assertTrue(entry_ready(s,room,**opts,permit_required=False))
        for override in ({"source_pa":111000},{"feeder_open":False},
                         {"generator_stopped":False},{"source_safe":False},
                         {"hatch_sound":False},{"now_s":1800}):
            self.assertFalse(entry_ready(s,room,**{**opts,**override},
                permit_required=False))
        s=secure_room(s,room,"#41",1000)
        self.assertTrue(entry_ready(s,room,**opts))
        with self.assertRaises(GeneratorBayError):
            secure_room(s,room,"#42",1000)
        s=enter_or_inspect(s,room,"#41")
        s=enter_or_inspect(s,room,"#41",inspect=True)
        with self.assertRaises(GeneratorBayError):
            release_room(s,room,"#41",hatch_closed=True,empty=False,
                repairs_active=False)
        s=release_room(s,room,"#41",hatch_closed=True,empty=True,
            repairs_active=False)
        self.assertEqual(s["rooms"][room]["entries"],1)
        self.assertIsNone(s["rooms"][room]["permit"])

    def test_toxic_original_room_stays_quarantined(self):
        room="GEN-A-ROOM"
        bad=survey_room(initial_generator_bays(),room,
            volume_m3=ROOMS[room][5]*.8,pressure_pa=101325,
            temperature_k=293.15,oxygen_fraction=.10,
            co2_fraction=.08,smoke_fraction=0,skin_k=295,
            now_s=1000,hatch_closed=True)
        self.assertFalse(entry_ready(bad,room,source_pa=101325,
            source_safe=True,hatch_sound=True,feeder_open=True,
            generator_stopped=True,now_s=1000,permit_required=False))
