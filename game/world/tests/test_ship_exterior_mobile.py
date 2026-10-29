"""G19 pure mobile hardware test: no invented rail, battery, scan or repair."""
import copy
import unittest
from types import SimpleNamespace
from world.ship_exterior_mobile import (
    CRAWLERS, ROBOTS, FITTED, MobileExteriorError, original_routes,
    original_scan_stations,
    initial_exterior_mobile, validate_exterior_mobile, survey_exterior_mobile,
    mobile_move, step_exterior_mobile,
)

ANCHORS = {"EVA-FWD": "EXT-BOW", "EVA-AFT": "EXT-AFT"}
REFERENCE = {
    "spaces": [{"id": k, "pressure_zone": "VACUUM"}
               for k in ("EXT-BOW", "EXT-DR01", "EXT-DR01-SKIN", "EXT-CENTRAL", "EXT-AFT")],
    "access_links": [
        {"id": "ACC-EXT-BOW-EXT-DR01", "kind": "eva_rail",
         "from": "EXT-BOW", "to": "EXT-DR01"},
        {"id": "ACC-EXT-DR01-EXT-CENTRAL", "kind": "eva_rail",
         "from": "EXT-DR01", "to": "EXT-CENTRAL"},
        {"id": "ACC-EXT-DR01-EXT-DR01-SKIN",
         "kind": "eva_work_platform_transfer",
         "from": "EXT-DR01", "to": "EXT-DR01-SKIN"},
        {"id": "ACC-EXT-CENTRAL-EXT-AFT", "kind": "eva_rail",
         "from": "EXT-CENTRAL", "to": "EXT-AFT"},
    ],
}
ROUTES = original_routes(REFERENCE)
ACCESS = {link: True for link in ROUTES.values()}
LOCKS = {"EVA-FWD": True, "EVA-AFT": True}


class ExteriorMobileTests(unittest.TestCase):
    def setUp(self):
        self.equipment = {
            name: SimpleNamespace(space_id=home, condition="serviceable")
            for name, home in FITTED.items()}
        self.rotors = {"DR-01": {
            "rpm": 0.0, "target_rpm": 0.0, "hardlock": True,
            "brake": True, "indexing": False, "freight_collar": False,
            "passenger_indexer": False, "condition": "serviceable"}}
        self.name = "DRUM-INSPECT-ROBOT-1"
        self.state = survey_exterior_mobile(
            initial_exterior_mobile(), self.name, battery_kwh=1.0)

    def action(self, value, name=None, *, routes=ROUTES, access=ACCESS,
               locks=LOCKS, motion=True):
        self.state = mobile_move(
            self.state, name or self.name, value,
            routes=routes, rail_access=access, rotors=self.rotors,
            lock_ready=locks, motion_safe=motion)

    def tick(self, now, seconds=10, *, locks=LOCKS, access=ACCESS, motion=True):
        self.state = step_exterior_mobile(
            self.state, seconds, now_s=now,
            equipment=self.equipment, routes=ROUTES, rail_access=access,
            rotors=self.rotors, lock_ready=locks, motion_safe=motion)
        return self.state

    def test_only_four_original_and_no_phantom_survey_or_power(self):
        self.assertEqual((len(CRAWLERS), len(ROBOTS), len(FITTED)), (2, 2, 4))
        self.assertTrue(validate_exterior_mobile(initial_exterior_mobile()))
        with self.assertRaises(MobileExteriorError):
            survey_exterior_mobile(self.state, self.name, battery_kwh=2)
        with self.assertRaises(MobileExteriorError):
            survey_exterior_mobile(initial_exterior_mobile(),
                                   "EVA-CRAWLER-1", battery_kwh=100)
        with self.assertRaises(MobileExteriorError):
            self.action("scan")
        with self.assertRaises(MobileExteriorError):
            self.action("launch", locks={})

    def test_original_rail_requires_real_link_and_finite_elapsed_time(self):
        self.action("launch")
        self.tick(1010)
        self.assertEqual(self.state["units"][self.name]["position"], "EVA-FWD")
        self.tick(1020)
        self.tick(1030)
        self.tick(1040)
        self.tick(1050)
        self.assertEqual(self.state["units"][self.name]["position"], "EXT-BOW")
        with self.assertRaises(MobileExteriorError):
            self.action("move:EXT-AFT")  # Not a single original rail link.
        self.action("move:EXT-DR01")
        for now in (1060,1070,1080):
            self.tick(now)
        self.assertEqual(self.state["units"][self.name]["position"], "EXT-DR01")
        self.assertEqual(self.state["meter"]["sections"], 2)
        self.assertGreater(self.state["meter"]["energy_kwh"], 0)
        self.assertAlmostEqual(
            self.state["meter"]["energy_kwh"] +
            self.state["units"][self.name]["charge"]["remaining_kwh"], 1.0)
        self.assertTrue(validate_exterior_mobile(self.state))
        with self.assertRaises(MobileExteriorError):
            self.tick(1080)

    def test_robot_survey_gives_telemetry_not_free_hull_repair(self):
        self.action("launch")
        for now in (1010, 1020, 1030, 1040, 1050):
            self.tick(now)
        self.action("move:EXT-DR01")
        for now in (1060, 1070, 1080):
            self.tick(now)
        self.action("scan")
        self.tick(1090)
        self.assertIsNone(self.state["units"][self.name]["sample"])
        self.tick(1100)
        row = self.state["units"][self.name]
        self.assertEqual(row["sample"]["drum"], "DR-01")
        self.assertEqual(row["sample"]["site"], "EXT-DR01")
        self.assertEqual(row["sample"]["observed_surface"], "EXT-DR01-SKIN")
        self.assertEqual(row["sample"]["evidence"],
                         "observed_existing_rotor_telemetry_at_skin")
        self.assertEqual(self.state["meter"]["scans"], 1)

    def test_spinning_drum_blocks_proximate_scan_not_fixed_rail(self):
        self.action("launch")
        for now in (1010,1020,1030,1040,1050):
            self.tick(now)
        self.rotors["DR-01"]["rpm"] = 1.2
        self.rotors["DR-01"]["hardlock"] = False
        self.action("move:EXT-DR01")
        for now in (1060,1070,1080):
            self.tick(now)
        self.assertEqual(self.state["units"][self.name]["position"],"EXT-DR01")
        with self.assertRaises(MobileExteriorError):
            self.action("scan")
        self.rotors["DR-01"]["rpm"] = 0.0
        self.rotors["DR-01"]["hardlock"] = True
        self.action("scan")
        self.rotors["DR-01"]["rpm"] = 2.0
        self.tick(1090)
        self.assertEqual(self.state["units"][self.name]["scans"],0)
        self.assertEqual(self.state["last"]["blocked"],[self.name+":rotor"])

    def test_fault_latched_no_automatic_restart_and_measured_recovery(self):
        self.action("launch")
        self.tick(1010)
        spent = self.state["meter"]["energy_kwh"]
        self.equipment[self.name].condition = "failed"
        self.tick(1020)
        row = self.state["units"][self.name]
        self.assertEqual(row["position"], "EVA-FWD")
        self.assertTrue(row["fault_latched"])
        self.assertTrue(row["held"])
        self.assertAlmostEqual(self.state["meter"]["energy_kwh"], spent)
        self.equipment[self.name].condition = "serviceable"
        self.tick(1030)
        self.assertEqual(self.state["units"][self.name]["position"], "EVA-FWD")
        with self.assertRaises(MobileExteriorError):
            self.action("continue")
        self.action("reset")
        self.action("continue")
        for now in (1040,1050,1060,1070):
            self.tick(now)
        self.assertEqual(self.state["units"][self.name]["position"], "EXT-BOW")

    def test_locked_outer_hatch_pauses_launch_and_dock_without_teleport(self):
        self.action("launch")
        self.tick(1010,locks={})
        self.assertEqual(self.state["units"][self.name]["position"],"EVA-FWD")
        self.assertEqual(self.state["meter"]["energy_kwh"],0)
        for t in (1020,1030,1040,1050,1060):
            self.tick(t)
        self.action("dock")
        self.tick(1070,locks={})
        self.assertEqual(self.state["units"][self.name]["position"],"EXT-BOW")
        for t in (1080,1090,1100,1110,1120):
            self.tick(t)
        self.assertEqual(self.state["units"][self.name]["position"],"EVA-FWD")

    def test_same_real_rail_span_and_outer_anchor_cannot_be_double_booked(self):
        self.state = survey_exterior_mobile(
            self.state,"EVA-CRAWLER-1",battery_kwh=2.0)
        self.action("launch")
        with self.assertRaises(MobileExteriorError):
            self.action("launch",name="EVA-CRAWLER-1")
        for clock in (1010,1020,1030,1040,1050):
            self.tick(clock)
        # The inspection robot occupies the original exterior bow berth.
        with self.assertRaises(MobileExteriorError):
            self.action("launch",name="EVA-CRAWLER-1")
        self.action("move:EXT-DR01")
        self.action("launch",name="EVA-CRAWLER-1")
        self.tick(1060)
        self.assertEqual(self.state["units"][self.name]["position"],"EXT-BOW")
        self.assertEqual(self.state["units"]["EVA-CRAWLER-1"]["position"],"EVA-FWD")

    def test_converging_original_rail_segments_reserve_one_arrival_station(self):
        aft="DRUM-INSPECT-ROBOT-2"
        self.state=survey_exterior_mobile(self.state,aft,battery_kwh=2.0)
        self.action("launch")
        self.action("launch",name=aft)
        for now in (1010,1020,1030,1040,1050):
            self.tick(now)
        self.assertEqual(self.state["units"][aft]["position"],"EXT-AFT")
        self.action("move:EXT-CENTRAL",name=aft)
        for now in (1060,1070,1080):
            self.tick(now)
        self.action("move:EXT-DR01",name=aft)
        with self.assertRaises(MobileExteriorError):
            self.action("move:EXT-DR01")
        for now in (1090,1100,1110):
            self.tick(now)
        self.assertEqual(self.state["units"][aft]["position"],"EXT-DR01")
        self.assertEqual(self.state["units"][self.name]["position"],"EXT-BOW")

    def test_true_as_built_first_rail_is_supported_by_test_itinerary(self):
        from world.ship_model import load_ship_model
        model=load_ship_model()
        rail = next(x for x in model.access_links
                    if x.id=="ACC-EXT-BOW-EXT-DR01")
        self.assertEqual(original_scan_stations(REFERENCE),
                         {"EXT-DR01":"EXT-DR01-SKIN"})
        self.assertEqual(
            (rail.from_id,rail.to_id,rail.kind),
            ("EXT-BOW","EXT-DR01","eva_rail"))

    def test_rail_source_must_be_original_vacuum_geometry(self):
        wrong=copy.deepcopy(REFERENCE)
        wrong["spaces"][1]["pressure_zone"]="PZ-DR-01"
        with self.assertRaises(MobileExteriorError):
            original_routes(wrong)
        forged=copy.deepcopy(self.state)
        forged["units"][self.name]["charge"]["remaining_kwh"]+=1
        with self.assertRaises(MobileExteriorError):
            validate_exterior_mobile(forged)


if __name__=="__main__":
    unittest.main()
