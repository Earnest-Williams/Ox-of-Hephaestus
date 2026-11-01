"""Installed G19 original independently sealed rescue-bay life support."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells,
    initialize_nominal_atmosphere, set_component_condition,
    state,
)
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.models import WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_survival_air,
    survey_g19_survival_air, crew_physical_action, tick_continuous_physics,
    local_physics_readout, _clock,
)


class InstalledIndependentRescueAir(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker=build_ship()["watch"]
        self.now=1000
        self.sequence=1200

    def at(self, room):
        self.assertTrue(self.worker.move_to(find_ship_space(room),quiet=True))

    def action(self,name,value,request=None):
        if request is None:
            self.sequence+=1
            request=f"{self.sequence:032x}"
        return crew_physical_action(
            self.worker,request,"rescue_air",name,value)

    def tick(self,s):
        while s:
            dt=min(s,10)
            self.now+=dt
            tick_continuous_physics(now_game_time=self.now)
            s-=dt

    def test_two_original_bays_commission_and_remain_finite_without_grid_power(self):
        result=commission_g19_survival_air(operator_approved=True)
        self.assertEqual(result,{"commissioned":True,"packages":2})
        self.assertFalse(commission_g19_survival_air(
            operator_approved=True)["commissioned"])
        name="RESCUE-FWD-LSS"
        self.at("RESCUE-FWD")
        with self.assertRaises(PhysicsError):
            self.action(name,"scrub")
        survey_g19_survival_air(
            operator_approved=True,name=name,
            capacity_kg=.04,runtime_s=120)
        with self.assertRaises(PhysicsError):
            survey_g19_survival_air(
                operator_approved=True,name=name,
                capacity_kg=.04,runtime_s=120)
        before=state("pressure","PZ-BOW-RESCUE")
        gas_before=before.quantity
        oxygen_before=before.details["physics_oxygen_kg"]
        self.action(name,"scrub")
        # The original independent package cannot borrow energy from or
        # recharge the ship bus; this controlled outage leaves only the
        # attested finite internal run-time charge available.
        set_component_condition(
            "edge","EDGE-GEN-M","severed",operator=True)
        self.tick(10)
        meter=_clock().details["survival_air"]
        captured=meter["units"][name]["captured_kg"]
        self.assertGreater(captured,0)
        self.assertAlmostEqual(
            state("pressure","PZ-BOW-RESCUE").quantity+captured,gas_before,
            places=5)
        self.assertAlmostEqual(
            state("pressure","PZ-BOW-RESCUE").details["physics_oxygen_kg"],
            oxygen_before,places=7)
        self.assertAlmostEqual(
            meter["units"][name]["charge"]["runtime_remaining_s"],110)
        self.assertEqual(meter["units"]["RESCUE-AFT-LSS"]["captured_kg"],0)
        self.assertAlmostEqual(
            _clock().details["summary"]["survival_air_captured_co2_kg"],
            captured,places=6)

    def test_open_original_pressure_door_suspends_but_does_not_reset_air(self):
        commission_g19_survival_air(operator_approved=True)
        name="RESCUE-AFT-LSS"
        survey_g19_survival_air(
            operator_approved=True,name=name,
            capacity_kg=.08,runtime_s=200)
        self.at("RESCUE-AFT")
        self.action(name,"scrub")
        self.tick(10)
        charge=_clock().details["survival_air"]["units"][name]["charge"]
        before=charge["runtime_remaining_s"]
        absorbed=_clock().details["survival_air"]["meter"]["captured_kg"]
        door=state("access","ACC-RESCUE-AFT",lock=True)
        door.setting="open"
        door.revision+=1
        door.save(update_fields=["setting","revision"])
        self.tick(10)
        row=_clock().details["survival_air"]["units"][name]
        self.assertAlmostEqual(row["charge"]["runtime_remaining_s"],before)
        self.assertAlmostEqual(row["captured_kg"],absorbed)
        with self.assertRaises(PhysicsError):
            self.action(name,"scrub")
        door=state("access","ACC-RESCUE-AFT",lock=True)
        door.setting="closed"
        door.revision+=1
        door.save(update_fields=["setting","revision"])
        self.tick(10)
        after=_clock().details["survival_air"]["units"][name]
        self.assertLess(after["charge"]["runtime_remaining_s"],before)
        self.assertGreater(after["captured_kg"],absorbed)
        self.assertEqual(local_physics_readout(
            self.worker,"rescue_air:"+name)["mode"],"scrub")

    def test_craft_local_receipts_and_faulted_machine_cannot_be_rearmed(self):
        commission_g19_survival_air(operator_approved=True)
        name="RESCUE-FWD-LSS"
        survey_g19_survival_air(
            operator_approved=True,name=name,
            capacity_kg=.06,runtime_s=60)
        self.at("CMD-PRIMARY")
        with self.assertRaises(PermissionError):
            self.action(name,"scrub")
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker,"rescue_air:"+name)
        self.at("RESCUE-FWD")
        rid="e"*32
        original=self.action(name,"scrub",rid)
        self.assertEqual(self.action(name,"scrub",rid),original)
        self.assertEqual(WorkReceipt.objects.filter(pk=rid).count(),1)
        set_component_condition(
            "equipment",name,"failed",operator=True)
        self.tick(10)
        self.assertEqual(_clock().details["survival_air"]["units"][name][
            "last_capture_kg"],0)
        self.action(name,"off")
        with self.assertRaises(PhysicsError):
            self.action(name,"scrub")
        self.assertEqual(state("equipment",name).condition,"failed")
