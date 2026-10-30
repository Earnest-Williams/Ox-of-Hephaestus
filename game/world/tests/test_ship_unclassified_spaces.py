"""Complete physical taxonomy and noninvented cargo/portal/void behaviour."""
import copy
import unittest
from world.ship_unclassified_spaces import (
    SECTORS, PERSONNEL_DOORS, FREIGHT_ROUTES, PORTALS, PORTAL_DOORS,
    VOIDS, NONPERSONNEL_LINKS, UnclassifiedSpaceError,
    initial_unclassified, validate_unclassified, cargo_signature,
    complete_manifest, survey_sector, permit_ready, secure_sector,
    note_entry, release_sector, inject_sector_leak, begin_sector_seal,
    cancel_sector_seal,
    tick_unclassified, certify_portal, invalidate_portal, portal_ready,
    inspect_void, breathing_sample, commit_breathing_sample,
    exchange_open_sector_hatch)
from world.ship_cargo_manifest import initial_cargo, declare_cargo_lot

def parked():
    return {f"DR-{n:02d}":{"rpm":0.0,"target_rpm":0.0,
        "hardlock":True,"brake":True,"freight_collar":False,
        "passenger_indexer":False,"indexing":False} for n in range(1,7)}

def cargo():
    # The canonical manifest always begins with positive unlocated onboard
    # mass. A sector with no STOWED lots remains genuinely empty.
    m=initial_cargo(1.0)
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
    def test_all_forty_eight_sector_atmospheres_remain_separately_conserved(self):
        """Six real drums, eight independent sectors apiece, zero borrowed air."""
        manifest=initial_cargo(1.0)
        manifest["verified_drums"]=sorted({sector[:5] for sector in SECTORS})
        ledger=initial_unclassified()
        for sector in SECTORS:
            ledger=survey_sector(
                ledger,manifest,parked(),sector,free_volume_m3=50,
                pressure_pa=101000,temperature_k=293.15,
                oxygen_fraction=.232,co2_fraction=.0004,
                smoke_fraction=0,cargo_class="empty",lot_ids=[],
                now_s=1000,hatch_closed=True)
        for drum in manifest["verified_drums"]:
            self.assertTrue(complete_manifest(ledger,manifest,drum))
        original={
            sector:ledger["sectors"][sector]["gas"]["mass_kg"]
            for sector in SECTORS}
        self.assertEqual(len(original),48)
        self.assertTrue(all(permit_ready(
            ledger,manifest,parked(),sector,
            source_pressure_pa=101000,source_safe=True,
            now_s=1000,permit_required=False) for sector in SECTORS))
        breached="DR-05-SEC-07"
        ledger=inject_sector_leak(ledger,breached,.037)
        ledger,loss,finished=tick_unclassified(ledger,60)
        self.assertAlmostEqual(loss,2.22)
        self.assertFalse(finished)
        self.assertAlmostEqual(
            original[breached]-ledger["sectors"][breached]["gas"]["mass_kg"],
            loss)
        for sector in SECTORS:
            if sector!=breached:
                self.assertAlmostEqual(
                    ledger["sectors"][sector]["gas"]["mass_kg"],
                    original[sector])
        self.assertAlmostEqual(
            sum(original.values())-
            sum(row["gas"]["mass_kg"]
                for row in ledger["sectors"].values()),
            loss)
        self.assertTrue(validate_unclassified(ledger))

    def test_all_twelve_berth_certificates_are_independent_and_revision_bound(self):
        """A stale P1 seal can never impersonate a different drum's P2."""
        ledger=initial_unclassified()
        manifest=initial_cargo(1.0)
        for i,portal in enumerate(PORTALS,1):
            manifest["port_contacts"][portal]={
                "docked":True,"berth_id":f"BERTH-{i:02d}"}
            ledger=certify_portal(
                ledger,manifest,parked(),portal,
                berth=f"BERTH-{i:02d}",real_hatch_closed=True,
                sound=True,machinery_healthy=True,now_s=1000,
                hatch_revision=i)
        self.assertEqual(sum(
            row["certified_berth"] is not None
            for row in ledger["portals"].values()),12)
        for i,portal in enumerate(PORTALS,1):
            proof=dict(hatch_revision=i,hatch_closed=True,
                       hatch_sound=True,handler_sound=True)
            self.assertTrue(portal_ready(ledger,manifest,portal,**proof))
            self.assertFalse(portal_ready(
                ledger,manifest,portal,
                **{**proof,"hatch_revision":i+1}))
        victim="DR-04-P2"
        ledger=invalidate_portal(ledger,victim)
        for i,portal in enumerate(PORTALS,1):
            result=portal_ready(
                ledger,manifest,portal,hatch_revision=i,
                hatch_closed=True,hatch_sound=True,handler_sound=True)
            self.assertEqual(result,portal!=victim)
        self.assertEqual(sum(
            row["certified_berth"] is not None
            for row in ledger["portals"].values()),11)
        self.assertTrue(all(row["gas"] is None
                            for row in ledger["sectors"].values()))

    def test_open_original_sector_hatch_conserves_real_gallery_air(self):
        ledger, manifest = survey_all()
        sector = "DR-01-SEC-01"
        # First exercise migration of an original v1 sealed charge without
        # changing its initial oxygen, pressure or surveyed room volume.
        legacy = copy.deepcopy(ledger)
        legacy["version"] = 1
        for row in legacy["sectors"].values():
            row.pop("gallery_net_kg")
        self.assertTrue(validate_unclassified(legacy))
        gas = legacy["sectors"][sector]["gas"]
        gallery = {
            "mass": 75.0, "oxygen": 17.4, "co2": .03, "smoke": .02,
            "temperature": 305.0, "volume": 50.0, "capacity": 1500.0}
        gallery["energy"] = (gallery["capacity"] + gallery["mass"])*gallery["temperature"]
        initial_mass = gas["mass_kg"] + gallery["mass"]
        initial_o2 = gas["oxygen_kg"] + gallery["oxygen"]
        initial_co2 = gas["co2_kg"] + gallery["co2"]
        initial_smoke = gas["smoke_kg"] + gallery["smoke"]
        updated, mixed = exchange_open_sector_hatch(legacy, sector, gallery, 10.0)
        new = updated["sectors"][sector]["gas"]
        self.assertEqual(updated["version"], 2)
        self.assertAlmostEqual(new["mass_kg"] + mixed["mass"], initial_mass)
        self.assertAlmostEqual(new["oxygen_kg"] + mixed["oxygen"], initial_o2)
        self.assertAlmostEqual(new["co2_kg"] + mixed["co2"], initial_co2)
        self.assertAlmostEqual(new["smoke_kg"] + mixed["smoke"], initial_smoke)
        self.assertAlmostEqual(
            new["mass_kg"] + updated["sectors"][sector]["lost_kg"]
            - updated["sectors"][sector]["gallery_net_kg"],
            updated["sectors"][sector]["initial_kg"])
        self.assertNotAlmostEqual(new["temperature_k"], gas["temperature_k"])
        self.assertTrue(validate_unclassified(updated))
        self.assertEqual(legacy["version"], 1)
        again, changed = exchange_open_sector_hatch(updated, sector, mixed, 0.0)
        self.assertEqual(again, updated)
        self.assertEqual(changed, mixed)
        with self.assertRaises(UnclassifiedSpaceError):
            exchange_open_sector_hatch(legacy, "DR-02-SEC-01", gallery, 10)

    def test_compound_open_hatch_shell_loss_bleeds_finite_gallery(self):
        ledger, _ = survey_all()
        sector = "DR-01-SEC-05"
        sample = ledger["sectors"][sector]["gas"]
        gallery = {
            "mass": 61.0, "oxygen": 61.0 * .232,
            "co2": 61.0 * .0004, "smoke": 0.0,
            "temperature": 293.15, "volume": 50.0, "capacity": 1500.0}
        gallery["energy"] = (
            gallery["capacity"] + gallery["mass"]) * gallery["temperature"]
        combined_start = sample["mass_kg"] + gallery["mass"]
        original_gallery = gallery["mass"]
        ledger = inject_sector_leak(ledger, sector, .7)
        vented = 0.0
        for _ in range(6):
            ledger, gallery = exchange_open_sector_hatch(
                ledger, sector, gallery, 10.0)
            ledger, loss, jobs = tick_unclassified(ledger, 10)
            self.assertEqual(jobs, ())
            vented += loss
            self.assertTrue(validate_unclassified(ledger))
        site = ledger["sectors"][sector]
        self.assertGreater(vented, 30)
        self.assertLess(gallery["mass"], original_gallery)
        self.assertGreater(site["gallery_net_kg"], 0)
        self.assertAlmostEqual(
            combined_start, gallery["mass"] + site["gas"]["mass_kg"]
            + vented, places=5)
        self.assertAlmostEqual(vented, site["lost_kg"], places=5)
        # Closing the actual rated hatch means the next shell loss is
        # debited exclusively from the sector's finite retained charge.
        closed = copy.deepcopy(gallery)
        ledger, extra, _ = tick_unclassified(ledger, 10)
        self.assertEqual(gallery, closed)
        self.assertAlmostEqual(
            combined_start, gallery["mass"]
            + ledger["sectors"][sector]["gas"]["mass_kg"]
            + vented + extra, places=5)

    def test_vented_empty_sector_does_not_freeze_open_hatch_physics(self):
        ledger, _ = survey_all()
        sector = "DR-01-SEC-08"
        emptied = copy.deepcopy(ledger)
        site = emptied["sectors"][sector]
        gas = site["gas"]
        site["lost_kg"] = gas["mass_kg"]
        gas["mass_kg"] = 0.0
        for component in ("oxygen_kg", "co2_kg", "smoke_kg"):
            gas[component] = 0.0
        self.assertTrue(validate_unclassified(emptied))
        gallery = {
            "mass": 61.0, "oxygen": 14.152, "co2": 0.025,
            "smoke": 0.0, "temperature": 293.15, "volume": 50.0,
            "capacity": 1500.0}
        gallery["energy"] = (
            gallery["capacity"] + gallery["mass"]) * gallery["temperature"]
        revised, after = exchange_open_sector_hatch(
            emptied, sector, gallery, 10)
        self.assertGreater(revised["sectors"][sector]["gas"]["mass_kg"], 0)
        self.assertLess(after["mass"], gallery["mass"])
        self.assertAlmostEqual(
            after["mass"] + revised["sectors"][sector]["gas"]["mass_kg"],
            gallery["mass"])
        self.assertEqual(emptied["sectors"][sector]["gas"]["mass_kg"], 0)
        self.assertTrue(validate_unclassified(revised))

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
    def test_stale_survey_never_traps_already_admitted_engineer(self):
        led,manifest=survey_all()
        sector="DR-01-SEC-02"
        led=secure_sector(led,sector,"#71",1000)
        conditions=dict(source_pressure_pa=101000,source_safe=True,
                        now_s=1650,permit_required=True)
        # An operator cannot start another admission using a ten-minute-old
        # survey; existing worker may return using the live conserved gas.
        self.assertFalse(permit_ready(
            led,manifest,parked(),sector,**conditions))
        self.assertTrue(permit_ready(
            led,manifest,parked(),sector,**conditions,
            allow_stale_retreat=True))
        self.assertFalse(permit_ready(
            led,manifest,parked(),sector,
            **{**conditions,"source_pressure_pa":110000},
            allow_stale_retreat=True))
        # A stopped, surveyed crew sector can become an emergency
        # co-rotating worksite after a bearing casualty. No fixed/rotary
        # crossing occurs to move back into its own DR-01-GALLERY.
        drifting=parked()
        drifting["DR-01"].update(
            rpm=.5,target_rpm=0,brake=False,hardlock=False)
        self.assertFalse(permit_ready(
            led,manifest,drifting,sector,**conditions))
        self.assertTrue(permit_ready(
            led,manifest,drifting,sector,**conditions,
            allow_stale_retreat=True))
        lost_manifest=copy.deepcopy(manifest)
        lost_manifest["verified_drums"]=[]
        self.assertFalse(permit_ready(
            led,lost_manifest,parked(),sector,**conditions))
        self.assertTrue(permit_ready(
            led,lost_manifest,parked(),sector,**conditions,
            allow_stale_retreat=True))
        with self.assertRaises(UnclassifiedSpaceError):
            permit_ready(led,manifest,parked(),sector,
                **{**conditions,"permit_required":False},
                allow_stale_retreat=True)
        no_permit=release_sector(
            led,sector,"#71",closed=True,empty=True)
        self.assertFalse(permit_ready(
            no_permit,manifest,parked(),sector,**conditions,
            allow_stale_retreat=True))

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
    def test_abandoned_patch_keeps_leak_and_consumes_no_material(self):
        ledger,manifest=survey_all()
        sector="DR-01-SEC-06"
        ledger=secure_sector(ledger,sector,"#317",1000)
        ledger=inject_sector_leak(ledger,sector,.003)
        ledger=begin_sector_seal(ledger,sector,"#317")
        ledger,escaped,finished=tick_unclassified(
            ledger,60,ready_seals={(sector,"#317")})
        self.assertAlmostEqual(escaped,.18)
        self.assertFalse(finished)
        self.assertEqual(ledger["sectors"][sector]["seal"]["remaining_s"],120)
        with self.assertRaises(UnclassifiedSpaceError):
            cancel_sector_seal(
                ledger,sector,"#318",hatch_closed=True,empty=True)
        with self.assertRaises(UnclassifiedSpaceError):
            cancel_sector_seal(
                ledger,sector,"#317",hatch_closed=True,empty=False)
        ledger=cancel_sector_seal(
            ledger,sector,"#317",hatch_closed=True,empty=True)
        self.assertIsNone(ledger["sectors"][sector]["seal"])
        self.assertEqual(ledger["sectors"][sector]["leak_kg_s"],.003)
        self.assertAlmostEqual(ledger["sectors"][sector]["lost_kg"],.18)
        self.assertEqual(ledger["sectors"][sector]["seals_completed"],0)
        ledger=release_sector(ledger,sector,"#317",closed=True,empty=True)
        self.assertIsNone(ledger["sectors"][sector]["permit"])
        ledger,again,finished=tick_unclassified(ledger,60)
        self.assertAlmostEqual(again,.18)
        self.assertFalse(finished)

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
                real_hatch_closed=True,sound=True,machinery_healthy=True,now_s=1000,hatch_revision=5)
        led=certify_portal(led,m,parked(),"DR-01-P1",berth="BERTH-A",
                real_hatch_closed=True,sound=True,machinery_healthy=True,now_s=1000,hatch_revision=5)
        safe=dict(hatch_revision=5,hatch_closed=True,
                  hatch_sound=True,handler_sound=True)
        self.assertTrue(portal_ready(led,m,"DR-01-P1",**safe))
        self.assertFalse(portal_ready(led,m,"DR-01-P2",**safe))
        self.assertFalse(portal_ready(led,m,"DR-01-P1",
                         **{**safe,"hatch_revision":6}))
        led=invalidate_portal(led,"DR-01-P1")
        self.assertFalse(portal_ready(led,m,"DR-01-P1",**safe))
        self.assertIsNone(led["sectors"]["DR-01-SEC-01"]["gas"])
    def test_real_unsuited_breathing_consumes_sector_oxygen_and_adds_same_co2(self):
        from world.ship_crew_physiology import step_crew_in_space
        from world.ship_crew_exposure import initial_exposure
        ledger,manifest=survey_all()
        sector="DR-01-SEC-01"
        original=ledger["sectors"][sector]["gas"]
        before_mass=original["mass_kg"]
        before_o2=original["oxygen_kg"]
        before_co2=original["co2_kg"]
        health,sample,breath=step_crew_in_space(
            initial_exposure(),breathing_sample(ledger,sector),10)
        self.assertGreater(breath["o2_used_kg"],0)
        self.assertGreater(breath["metabolic_heat_kj"],0)
        ledger=commit_breathing_sample(ledger,sector,sample)
        gas=ledger["sectors"][sector]["gas"]
        self.assertAlmostEqual(gas["mass_kg"],before_mass)
        self.assertAlmostEqual(before_o2-gas["oxygen_kg"],breath["o2_used_kg"])
        self.assertAlmostEqual(gas["co2_kg"]-before_co2,breath["co2_added_kg"])
        self.assertGreater(gas["temperature_k"],293.15)
        self.assertEqual(health["condition"],"fit")
        with self.assertRaises(UnclassifiedSpaceError):
            commit_breathing_sample(ledger,sector,{**sample,
                "oxygen":sample["oxygen"]+0.5})
        self.assertIsNone(breathing_sample(initial_unclassified(),sector))

    def test_non_habitable_void_inspection_never_creates_pressure_cell(self):
        led=initial_unclassified()
        for room in VOIDS:
            led=inspect_void(led,room,1000)
            self.assertEqual(led["voids"][room]["inspections"],1)
        self.assertEqual(len(led["sectors"]),48)
        self.assertTrue(validate_unclassified(led))
