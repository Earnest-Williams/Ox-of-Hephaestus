"""Complete physical taxonomy and noninvented cargo/portal/void behaviour."""
import copy
import unittest
from world.ship_unclassified_spaces import (
    SECTORS, PERSONNEL_DOORS, FREIGHT_ROUTES, PORTALS, PORTAL_DOORS,
    VOIDS, NONPERSONNEL_LINKS, UnclassifiedSpaceError,
    initial_unclassified, validate_unclassified, cargo_signature,
    complete_manifest, survey_sector, permit_ready, secure_sector,
    note_entry, release_sector, inject_sector_leak, begin_sector_seal,
    tick_unclassified, certify_portal, invalidate_portal, portal_ready,
    inspect_void)
from world.ship_cargo_manifest import initial_cargo, declare_cargo_lot

def parked():
    return {f"DR-{n:02d}":{"rpm":0.0,"target_rpm":0.0,
        "hardlock":True,"brake":True,"freight_collar":False,
        "passenger_indexer":False,"indexing":False} for n in range(1,7)}

def cargo():
    m=initial_cargo(0)
    m["verified_drums"]=["DR-01"]
    return m

def survey_all(manifest=None):
    m=manifest or cargo()
    led=initial_unclassified()
    for sector in SECTORS[:8]:
        led=survey_sector(led,m,parked(),sector,
            free_volume_m3=50,pressure_pa=101000,temperature_k=293.15,
            oxygen_fraction=.232,co2_fraction=.0004,smoke_fraction=0,
            cargo_class="empty",lot_ids=[],now_s=1000,hatch_closed=True)
    return led,m

class UnclassifiedTaxonomy(unittest.TestCase):
    def test_exact_sixty_three_and_original_handling_routes(self):
        self.assertEqual((len(SECTORS),len(PORTALS),len(VOIDS)),(48,12,3))
        self.assertEqual((len(PERSONNEL_DOORS),len(FREIGHT_ROUTES),
                          len(PORTAL_DOORS)),(48,48,12))
        self.assertEqual(len(NONPERSONNEL_LINKS),62)
        self.assertIsNone(VOIDS["WR-TRIM-TANK-BAY"]["hatch"])
        self.assertTrue(validate_unclassified(initial_unclassified()))
        self.assertTrue(all(x["gas"] is None for x in
            initial_unclassified()["sectors"].values()))
    def test_positive_gas_is_per_sector_and_never_regenerated(self):
        l,m=survey_all()
        self.assertEqual(sum(x["gas"] is not None for x in l["sectors"].values()),8)
        gas=l["sectors"]["DR-01-SEC-01"]["gas"]
        with self.assertRaises(UnclassifiedSpaceError):
            survey_sector(l,m,parked(),"DR-01-SEC-01",
                free_volume_m3=50,pressure_pa=123000,temperature_k=293.15,
                oxygen_fraction=.232,co2_fraction=.0004,smoke_fraction=0,
                cargo_class="empty",lot_ids=[],now_s=1001,hatch_closed=True)
        self.assertGreater(gas["mass_kg"],0)
        self.assertEqual(initial_unclassified()["sectors"]["DR-01-SEC-01"]["initial_kg"],0)
    def test_full_drum_manifest_before_authorised_admission(self):
        l,m=survey_all()
        self.assertTrue(complete_manifest(l,m,"DR-01"))
        row=dict(source_pressure_pa=101000,source_safe=True,now_s=1000,
                 permit_required=False)
        self.assertTrue(permit_ready(l,m,parked(),"DR-01-SEC-01",**row))
        self.assertFalse(permit_ready(l,m,parked(),"DR-01-SEC-09",**row))
        self.assertFalse(permit_ready(l,m,parked(),"DR-02-SEC-01",**row))
        self.assertFalse(permit_ready(l,m,parked(),"DR-01-SEC-01",
            **{**row,"source_pressure_pa":107000}))
        stopped=parked()
        stopped["DR-01"]["rpm"]=1.5
        self.assertFalse(permit_ready(l,m,stopped,"DR-01-SEC-01",**row))
    def test_manifest_change_and_inert_or_hazardous_contents_block_entry(self):
        l,m=survey_all()
        m2=copy.deepcopy(m)
        m2["verified_drums"]=[]
        self.assertFalse(complete_manifest(l,m2,"DR-01"))
        l["sectors"]["DR-01-SEC-01"]["class"]="inert_cargo"
        self.assertFalse(permit_ready(l,m,parked(),"DR-01-SEC-01",
            source_pressure_pa=101000,source_safe=True,now_s=1000,
            permit_required=False))
        l["sectors"]["DR-01-SEC-01"]["class"]="hazardous_cargo"
        self.assertFalse(permit_ready(l,m,parked(),"DR-01-SEC-01",
            source_pressure_pa=101000,source_safe=True,now_s=1000,
            permit_required=False))
        l["sectors"]["DR-01-SEC-01"]["class"]="empty"
        m2=copy.deepcopy(m)
        m2["lots"]["BOX1"]={"drum":"DR-01","location":"DR-01",
             "mass_kg":100,"kind":"sled","restrained":True,
             "azimuth_rad":0.0,"radius_m":5}
        self.assertFalse(complete_manifest(l,m2,"DR-01"))
    def test_owned_entry_and_finite_patch_without_air_replacement(self):
        led,m=survey_all()
        row="DR-01-SEC-01"
        led=secure_sector(led,row,"#22",1000)
        led=note_entry(led,row,"#22")
        led=inject_sector_leak(led,row,.01)
        before=led["sectors"][row]["gas"]["mass_kg"]
        led,leak,finished=tick_unclassified(led,60)
        self.assertAlmostEqual(leak,.6)
        self.assertFalse(finished)
        led=begin_sector_seal(led,row,"#22")
        for _ in range(3):
            led,_,finished=tick_unclassified(led,60,
                 ready_seals={(row,"#22")})
        self.assertEqual(finished,((row,"#22",2.0),))
        self.assertEqual(led["sectors"][row]["leak_kg_s"],0)
        self.assertAlmostEqual(before-led["sectors"][row]["gas"]["mass_kg"],2.4)
        with self.assertRaises(UnclassifiedSpaceError):
            release_sector(led,row,"#33",closed=True,empty=True)
        led=release_sector(led,row,"#22",closed=True,empty=True)
        self.assertIsNone(led["sectors"][row]["permit"])
    def test_large_leak_has_no_internal_magic_patch(self):
        led,m=survey_all()
        row="DR-01-SEC-02"
        led=inject_sector_leak(led,row,.2)
        led=secure_sector(led,row,"#9",1000)
        with self.assertRaises(UnclassifiedSpaceError):
            begin_sector_seal(led,row,"#9")
    def test_loading_portal_requires_real_berth_approval_not_breathable_air(self):
        led=initial_unclassified()
        m=cargo()
        m["port_contacts"]["DR-01-P1"]={"docked":True,"berth_id":"BERTH-A"}
        with self.assertRaises(UnclassifiedSpaceError):
            certify_portal(led,m,parked(),"DR-01-P1",berth="WRONG",
                real_hatch_closed=True,sound=True,machinery_healthy=True,now_s=1000)
        led=certify_portal(led,m,parked(),"DR-01-P1",berth="BERTH-A",
                real_hatch_closed=True,sound=True,machinery_healthy=True,now_s=1000)
        self.assertTrue(portal_ready(led,m,"DR-01-P1"))
        self.assertFalse(portal_ready(led,m,"DR-01-P2"))
        led=invalidate_portal(led,"DR-01-P1")
        self.assertFalse(portal_ready(led,m,"DR-01-P1"))
        self.assertIsNone(led["sectors"]["DR-01-SEC-01"]["gas"])
    def test_non_habitable_void_inspection_never_creates_pressure_cell(self):
        led=initial_unclassified()
        for room in VOIDS:
            led=inspect_void(led,room,1000)
            self.assertEqual(led["voids"][room]["inspections"],1)
        self.assertEqual(len(led["sectors"]),48)
        self.assertTrue(validate_unclassified(led))
