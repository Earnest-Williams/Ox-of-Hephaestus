"""Installed original portable CO2 scrubber: cargo, real gas and receipt custody."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, state,
)
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.models import WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_portable_air,
    survey_g19_portable_air, crew_physical_action, tick_continuous_physics,
    local_physics_readout, _clock,
)


class InstalledPortableAir(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True,now_game_time=1000)
        self.worker=build_ship()["watch"]
        self.now=1000
        self.sequence=600
        commission_g19_portable_air(operator_approved=True)

    def at(self,room):
        self.assertTrue(self.worker.move_to(find_ship_space(room),quiet=True))

    def action(self,name,operation,request=None):
        if request is None:
            self.sequence+=1
            request=f"{self.sequence:032x}"
        return crew_physical_action(self.worker,request,
                                    "portable_air",name,operation)

    def test_actual_crew_carries_to_safe_gas_and_finite_capture(self):
        name="PORT-SCRUB-01"
        survey_g19_portable_air(operator_approved=True,
                                name=name,media_kg=.05,battery_s=30)
        self.at("CMD-PRIMARY")
        with self.assertRaises(PermissionError):
            self.action(name,"take")
        self.at("TRUNK-A-BOW")
        rid="b"*32
        first=self.action(name,"take",rid)
        self.assertEqual(self.action(name,"take",rid),first)
        self.assertEqual(WorkReceipt.objects.filter(pk=rid).count(),1)
        self.at("RESCUE-FWD")
        self.action(name,"place")
        self.action(name,"on")
        gas=state("pressure","PZ-BOW-RESCUE").quantity
        self.now+=10
        tick_continuous_physics(now_game_time=self.now)
        ledger=_clock().details["portable_air"]
        captured=ledger["units"][name]["captured_kg"]
        self.assertGreater(captured,0)
        self.assertAlmostEqual(state("pressure","PZ-BOW-RESCUE").quantity+captured,gas,places=5)
        self.assertEqual(ledger["units"][name]["survey"]["battery_remaining_s"],20)
        self.assertEqual(local_physics_readout(self.worker,
                                               "portable_air:"+name)["mode"],"on")

    def test_failed_machine_stops_without_resetting_charge(self):
        name="PORT-SCRUB-02"
        survey_g19_portable_air(operator_approved=True,
                                name=name,media_kg=.03,battery_s=60)
        self.at("ENG-LOCKER")
        self.action(name,"on")
        set_component_condition("equipment",name,"failed",operator=True)
        self.now+=10
        tick_continuous_physics(now_game_time=self.now)
        row=_clock().details["portable_air"]["units"][name]
        self.assertEqual(row["last_capture_kg"],0)
        self.assertEqual(row["survey"]["battery_remaining_s"],60)
        self.action(name,"off")
        with self.assertRaises(PhysicsError):
            self.action(name,"on")
