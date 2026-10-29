"""G19 original exterior crawlers and inspection robots: installed rail/airlock proof."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition,
)
from world.continuous_ship_physics import (
    PhysicsError, _clock, arm_continuous_physics, tick_continuous_physics,
    commission_g19_eva, commission_g19_exterior_mobile,
    survey_g19_exterior_mobile, crew_physical_action, local_physics_readout,
)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.models import WorkReceipt


class InstalledExteriorMobile(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True,now_game_time=1000)
        for br in ("ISO-GEN-M","ISO-DB-A-BOW","ISO-DB-A-AFT",
                   "ISO-DB-A-HAB-HUB-SERVICES"):
            set_isolator(br,"closed",operator=True)
        commission_g19_eva(operator_approved=True)
        self.assertTrue(commission_g19_exterior_mobile(operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_exterior_mobile(operator_approved=True)["commissioned"])
        self.worker=build_ship()["watch"]
        self.now=1000
        self.sequence=100

    def rid(self):
        self.sequence+=1
        return f"{self.sequence:032x}"

    def at(self,room):
        self.assertTrue(self.worker.move_to(find_ship_space(room),quiet=True))

    def act(self,action,target,value,rid=None):
        return crew_physical_action(self.worker,rid or self.rid(),action,target,value)

    def tick(self,n):
        while n:
            dt=min(60,n)
            self.now+=dt
            tick_continuous_physics(now_game_time=self.now)
            n-=dt

    def ready_forward_airlock(self):
        self.at("ENG-LOCKER")
        self.act("eva","INV-DC-CONSUMABLES","stage:0.75")
        self.at("TRUNK-B-BOW")
        self.act("eva","EVA-FWD","inner_open")
        link=find_world_entity("access:ACC-EVA-FWD:forward")
        outcome=traverse_canonical_exit(
            self.worker,link,link.destination,request_id=self.rid())
        self.assertEqual(outcome["status"],"succeeded")
        self.act("eva","EVA-FWD","inner_close")
        self.act("eva","EVA-FWD","checkout")
        self.act("switch","ISO-AIR-FIXED-EVA-FWD","closed")
        self.act("switch","ISO-LP-EVA-FWD","closed")
        self.act("eva","EVA-FWD","pumpdown")
        self.tick(90)
        self.act("eva","EVA-FWD","outer_open")

    def ready_aft_airlock(self):
        self.at("ENG-LOCKER")
        self.act("eva","INV-DC-CONSUMABLES","stage:0.75")
        self.at("TRUNK-B-AFT")
        self.act("eva","EVA-AFT","inner_open")
        link=find_world_entity("access:ACC-EVA-AFT:forward")
        outcome=traverse_canonical_exit(
            self.worker,link,link.destination,request_id=self.rid())
        self.assertEqual(outcome["status"],"succeeded")
        self.act("eva","EVA-AFT","inner_close")
        self.act("eva","EVA-AFT","checkout")
        self.act("switch","ISO-AIR-FIXED-EVA-AFT","closed")
        self.act("switch","ISO-LP-EVA-AFT","closed")
        self.act("eva","EVA-AFT","pumpdown")
        self.tick(90)
        self.act("eva","EVA-AFT","outer_open")

    def mobile(self,key):
        return _clock().details["exterior_mobile"]["units"][key]

    def test_robot_lives_on_true_rail_and_returns_observed_rotor_telemetry(self):
        name="DRUM-INSPECT-ROBOT-1"
        survey_g19_exterior_mobile(
            operator_approved=True,name=name,battery_kwh=1.0)
        self.at("CMD-PRIMARY")
        with self.assertRaises(PermissionError):
            self.act("exterior_mobile",name,"launch")
        self.ready_forward_airlock()
        rid="f"*32
        first=self.act("exterior_mobile",name,"launch",rid)
        self.assertEqual(first,self.act("exterior_mobile",name,"launch",rid))
        self.assertEqual(WorkReceipt.objects.filter(pk=rid).count(),1)
        self.assertEqual(self.mobile(name)["position"],"EVA-FWD")
        self.tick(40)
        self.assertEqual(self.mobile(name)["position"],"EVA-FWD")
        self.tick(10)
        self.assertEqual(self.mobile(name)["position"],"EXT-BOW")
        self.act("exterior_mobile",name,"move:EXT-DR01")
        self.tick(30)
        self.assertEqual(self.mobile(name)["position"],"EXT-DR01")
        self.act("exterior_mobile",name,"scan")
        self.tick(20)
        result=local_physics_readout(self.worker,"exterior_mobile:"+name)
        self.assertEqual(result["sample"]["drum"],"DR-01")
        self.assertEqual(result["sample"]["site"],"EXT-DR01")
        self.assertEqual(result["sample"]["observed_surface"],"EXT-DR01-SKIN")
        self.assertTrue(result["sample"]["hardlock"])
        self.assertEqual(self.mobile(name)["scans"],1)
        self.assertGreater(self.mobile(name)["used_kwh"],0)
        # The original reverse rail link is physical; returning is timed.
        self.act("exterior_mobile",name,"move:EXT-BOW")
        self.tick(30)
        self.assertEqual(self.mobile(name)["position"],"EXT-BOW")
        self.act("exterior_mobile",name,"dock")
        self.tick(50)
        self.assertEqual(self.mobile(name)["position"],"EVA-FWD")
        self.assertEqual(_clock().details["exterior_mobile"]["meter"]["sections"],4)

    def test_original_crawler_failure_latches_and_repair_can_resume(self):
        name="EVA-CRAWLER-1"
        survey_g19_exterior_mobile(operator_approved=True,
                                   name=name,battery_kwh=3.0)
        self.ready_forward_airlock()
        self.act("exterior_mobile",name,"launch")
        self.tick(10)
        used=self.mobile(name)["used_kwh"]
        self.assertGreater(used,0)
        set_component_condition("equipment",name,"failed",operator=True)
        self.tick(10)
        self.assertTrue(self.mobile(name)["fault_latched"])
        self.assertTrue(self.mobile(name)["held"])
        self.assertEqual(self.mobile(name)["position"],"EVA-FWD")
        self.assertEqual(self.mobile(name)["used_kwh"],used)
        set_component_condition("equipment",name,"serviceable",operator=True)
        self.tick(10)
        self.assertEqual(self.mobile(name)["used_kwh"],used)
        with self.assertRaises(PhysicsError):
            self.act("exterior_mobile",name,"continue")
        self.act("exterior_mobile",name,"reset")
        self.assertTrue(self.mobile(name)["held"])
        self.act("exterior_mobile",name,"continue")
        self.tick(40)
        self.assertEqual(self.mobile(name)["position"],"EXT-BOW")
        self.assertGreater(self.mobile(name)["used_kwh"],used)
        # The same installed machine cannot be assigned to a human
        # EVA route while it is away conducting an unmanned mission.
        outer=find_world_entity("access:ACC-EVA-FWD-EXT:forward")
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(
                self.worker,outer,outer.destination,request_id=self.rid())

    def test_aft_robot_and_crawler_use_original_dock_with_shared_berth(self):
        robot="DRUM-INSPECT-ROBOT-2"
        crawler="EVA-CRAWLER-2"
        survey_g19_exterior_mobile(operator_approved=True,
                                   name=robot,battery_kwh=1.5)
        survey_g19_exterior_mobile(operator_approved=True,
                                   name=crawler,battery_kwh=3.0)
        self.ready_aft_airlock()
        self.act("exterior_mobile",robot,"launch")
        with self.assertRaises(PhysicsError):
            self.act("exterior_mobile",crawler,"launch")
        self.tick(50)
        self.assertEqual(self.mobile(robot)["position"],"EXT-AFT")
        with self.assertRaises(PhysicsError):
            self.act("exterior_mobile",crawler,"launch")
        self.act("exterior_mobile",robot,"move:EXT-DR06")
        self.tick(30)
        self.assertEqual(self.mobile(robot)["position"],"EXT-DR06")
        self.act("exterior_mobile",crawler,"launch")
        self.tick(50)
        self.assertEqual(self.mobile(crawler)["position"],"EXT-AFT")
        self.assertAlmostEqual(
            self.mobile(crawler)["used_kwh"] +
            self.mobile(crawler)["charge"]["remaining_kwh"],3.0,places=6)

    def test_unpressurised_outer_hatch_is_not_a_magic_deployment(self):
        name="DRUM-INSPECT-ROBOT-2"
        survey_g19_exterior_mobile(
            operator_approved=True,name=name,battery_kwh=.5)
        self.at("EVA-AFT")
        with self.assertRaises(PhysicsError):
            self.act("exterior_mobile",name,"launch")
        self.assertEqual(self.mobile(name)["position"],"EVA-AFT")
        self.assertEqual(self.mobile(name)["used_kwh"],0)
