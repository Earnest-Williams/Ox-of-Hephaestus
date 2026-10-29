"""Bounded gas, original industrial topology and damaged worksite receipts."""
import unittest
from world.ship_industrial_access import (
    SITES, DOORS, IndustrialAccessError, initial_industrial,
    validate_industrial,positive_survey,bleed,enterable,secure,inspect,release,
    attest_leak,begin_seal,tick)
from world.ship_propulsion_bay_service import bay_pressure,source_pressure

def sample(room,p=101000):
    return positive_survey(initial_industrial(),room,
        volume_m3=SITES[room]["max_m3"]*.7,pressure_pa=p,
        temperature_k=293.15,oxygen_fraction=.232,
        co2_fraction=.0004,smoke_fraction=0,skin_k=299,
        now_s=1000,hatch_closed=True)

def source():
    m=101325*1000/(287.05*293.15)
    return dict(mass_kg=m,oxygen_kg=m*.232,co2_kg=m*.0004,
                smoke_kg=0,temperature_k=293.15,volume_m3=1000)

class IndustrialAccessPure(unittest.TestCase):
    def test_authored_sixteen_sites_separate_no_breathable_default(self):
        self.assertEqual(len(SITES),16)
        self.assertEqual(len(DOORS),16)
        self.assertEqual(sum(x["drum"] is not None for x in SITES.values()),12)
        self.assertEqual(sum(x["drum"] is None for x in SITES.values()),4)
        self.assertTrue(validate_industrial(initial_industrial()))
        for room in SITES:
            self.assertFalse(enterable(initial_industrial(),room,
                source_pa=101325,source_safe=True,hatch_sound=True,
                isolated=True,now_s=1000,need_permit=False))
            led=sample(room)
            self.assertEqual(sum(v["gas"] is not None for v in led["sites"].values()),1)
            self.assertGreater(led["sites"][room]["initial_kg"],0)
            with self.assertRaises(IndustrialAccessError):
                positive_survey(led,room,volume_m3=SITES[room]["max_m3"]*.7,
                    pressure_pa=121000,temperature_k=293.15,
                    oxygen_fraction=.232,co2_fraction=.0004,
                    smoke_fraction=0,skin_k=299,now_s=1001,hatch_closed=True)

    def test_positive_single_upstream_bleed_meters_species_and_mass(self):
        room="FTL-SVC"
        led=sample(room,97500)
        src=source()
        before=led["sites"][room]["gas"]["mass_kg"]+src["mass_kg"]
        before_o2=led["sites"][room]["gas"]["oxygen_kg"]+src["oxygen_kg"]
        led,src=bleed(led,room,kg=2,source=src,source_safe=True,
                      hatch_closed=True,isolated=True,now_s=1001)
        g=led["sites"][room]["gas"]
        self.assertAlmostEqual(before,g["mass_kg"]+src["mass_kg"])
        self.assertAlmostEqual(before_o2,g["oxygen_kg"]+src["oxygen_kg"])
        self.assertLess(bay_pressure(g),source_pressure(src))
        with self.assertRaises(IndustrialAccessError):
            bleed(led,room,kg=70,source=src,source_safe=True,
                  hatch_closed=True,isolated=True,now_s=1002)

    def test_suit_does_not_bypass_unsafe_hatch_or_bad_air(self):
        room="THERM-HT"
        led=sample(room)
        ok=dict(source_pa=101325,source_safe=True,hatch_sound=True,
                isolated=True,now_s=1000,need_permit=False)
        self.assertTrue(enterable(led,room,**ok))
        for wrong in ({"isolated":False},{"source_pa":105000},
                      {"source_safe":False},{"hatch_sound":False},
                      {"now_s":2000}):
            self.assertFalse(enterable(led,room,**{**ok,**wrong}))
        row=led["sites"][room]
        self.assertEqual(row["skin_k"],299)
        toxic=positive_survey(initial_industrial(),room,
            volume_m3=SITES[room]["max_m3"]*.6,pressure_pa=101325,
            temperature_k=293.15,oxygen_fraction=.08,co2_fraction=.14,
            smoke_fraction=0,skin_k=310,now_s=1000,hatch_closed=True)
        self.assertFalse(enterable(toxic,room,**ok))

    def test_leak_to_space_then_real_work_and_finite_required_patch(self):
        room="BE-01-SVC"
        led=secure(sample(room),room,"#123",1000)
        led=inspect(led,room,"#123",entry=True)
        led=attest_leak(led,room,leak_kg_s=.01)
        before=led["sites"][room]["gas"]["mass_kg"]
        led,lost,finished=tick(led,60)
        self.assertAlmostEqual(lost,.6)
        self.assertAlmostEqual(led["sites"][room]["gas"]["mass_kg"],before-lost)
        self.assertFalse(finished)
        self.assertFalse(enterable(led,room,source_pa=101325,source_safe=True,
            hatch_sound=True,isolated=True,now_s=1060))
        led=begin_seal(led,room,"#123")
        with self.assertRaises(IndustrialAccessError):
            release(led,room,"#123",hatch_closed=True,no_crew=True,
                    repairs_active=False)
        lost_again=0
        for _ in range(3):
            led,leaked,done=tick(led,60,ready_workers={(room,"#123")})
            lost_again+=leaked
        self.assertAlmostEqual(lost_again,1.8)
        self.assertEqual(len(done),1)
        self.assertEqual(done[0],(room,"#123",2.0))
        self.assertEqual(led["sites"][room]["leak_kg_s"],0)
        led,nothing,done=tick(led,60)
        self.assertEqual(nothing,0)
        self.assertFalse(done)
        self.assertAlmostEqual(led["sites"][room]["lost_kg"],lost+lost_again)
        self.assertTrue(validate_industrial(led))

    def test_large_fault_is_not_magic_hull_patch(self):
        led=attest_leak(sample("REACTION-SVC"),"REACTION-SVC",leak_kg_s=.20)
        led=secure(led,"REACTION-SVC","#77",1000)
        with self.assertRaises(IndustrialAccessError):
            begin_seal(led,"REACTION-SVC","#77")
        with self.assertRaises(IndustrialAccessError):
            secure(led,"THERM-HT","#77",1000)
