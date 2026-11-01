"""G19 ten original portable pumps/fans in installed Evennia rooms."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_water,
    commission_g19_portable_damage, survey_g19_portable_damage,
    crew_physical_action, local_physics_readout,
    tick_continuous_physics, _clock,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.models import CanonicalShipState, WorkReceipt
from world.ship_world import ensure_canonical_ship, find_ship_space


class InstalledPortableEmergencyMachines(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True,now_game_time=1000)
        self.assertTrue(commission_g19_portable_damage(
            operator_approved=True)["commissioned"])
        self.worker=build_ship()["watch"]
        self.now=1000
        self.num=1400

    def at(self,room):
        self.assertTrue(self.worker.move_to(find_ship_space(room),quiet=True))

    def action(self,name,command,request_id=None):
        if request_id is None:
            self.num+=1
            request_id=f"{self.num:032x}"
        return crew_physical_action(
            self.worker,request_id,"portable_damage",name,command)

    def tick(self,seconds=10):
        self.now+=seconds
        return tick_continuous_physics(now_game_time=self.now)

    def test_fitted_fan_at_carried_rescue_site_captures_actual_smoke(self):
        name="DC-SMOKE-FAN-01"
        self.assertFalse(commission_g19_portable_damage(
            operator_approved=True)["commissioned"])
        survey_g19_portable_damage(
            operator_approved=True,name=name,battery_s=60,filter_kg=.05)
        self.at("CMD-PRIMARY")
        with self.assertRaises(PermissionError):
            self.action(name,"take")
        self.at("TRUNK-A-BOW")
        rid="e"*32
        first=self.action(name,"take",rid)
        self.assertEqual(first,self.action(name,"take",rid))
        self.assertEqual(WorkReceipt.objects.filter(pk=rid).count(),1)
        self.at("RESCUE-FWD")
        self.action(name,"place")
        self.action(name,"on")
        # Inject a bounded, mass-conserving pre-existing smoke casualty
        # into the REAL pressure cell. This is an operator test fixture.
        cell=state("pressure","PZ-BOW-RESCUE",lock=True)
        details=dict(cell.details)
        details["physics_oxygen_kg"]-=.1
        details["physics_smoke_kg"]+=.1
        cell.details=details
        cell.revision+=1
        cell.save(update_fields=["details","revision"])
        initial_smoke=details["physics_smoke_kg"]
        self.tick()
        record=_clock().details["portable_damage"]["units"][name]
        self.assertGreater(record["last_m3"],0)
        self.assertGreater(record["last_kg"],0)
        self.assertAlmostEqual(
            state("pressure","PZ-BOW-RESCUE").details["physics_smoke_kg"]
            + record["cumulative_kg"],initial_smoke,places=5)
        self.assertEqual(local_physics_readout(
            self.worker,"portable_damage:"+name)["mode"],"on")
        self.assertEqual(record["survey"]["battery_remaining_s"],50)

    def test_pump_requires_actual_open_wet_crossing_and_moves_finite_backlog(self):
        commission_g19_water(operator_approved=True)
        name="DC-PUMP-01"
        survey_g19_portable_damage(operator_approved=True,
                                    name=name,battery_s=50)
        # A genuine transferred wastewater backlog: one ledger loses the
        # same kilograms the contaminated local buffer gains.
        clock=_clock(lock=True)
        data=dict(clock.details)
        water=dict(data["water"])
        water["local"]={side:dict(items) for side,items in water["local"].items()}
        water["working_kg"]-=8
        water["local"]["A"]["grey"]+=8
        water["waste_train"]=dict(water["waste_train"])
        water["waste_train"]["A"]="off"
        water["waste_train"]["B"]="off"
        data["water"]=water
        clock.details=data
        clock.revision+=1
        clock.save(update_fields=["details","revision"])
        self.at("TRUNK-A-BOW")
        self.action(name,"take")
        station=state("equipment","WASTE-PROC-A").space_id
        self.at(station)
        self.action(name,"place")
        self.action(name,"route:A:grey")
        self.action(name,"on")
        # Closed rated crossing must not permit the machine to move even
        # one kilogram, regardless of the worker's start command.
        self.tick()
        self.assertEqual(_clock().details["portable_damage"]["meter"]["pumped_kg"],0)
        for edge in CanonicalShipState.objects.filter(category="isolator"):
            if (edge.reference.get("network") == "greywater"
                    and edge.condition in {"serviceable","degraded"}):
                set_isolator(edge.source_id,"open",operator=True)
        self.tick()
        ledger=_clock().details["portable_damage"]
        pumped=ledger["units"][name]["cumulative_kg"]
        self.assertGreater(pumped,0)
        w=_clock().details["water"]
        self.assertAlmostEqual(w["local"]["A"]["grey"]+pumped,8,places=4)
        self.assertAlmostEqual(w["fixed"]["grey"],pumped,places=4)
        self.assertGreater(pumped,0)
        self.assertEqual(local_physics_readout(
            self.worker,"portable_damage:"+name)["route"],["A","grey"])

    def test_failed_device_stays_off_after_original_repair(self):
        name="DC-SMOKE-FAN-03"
        survey_g19_portable_damage(operator_approved=True,
                                    name=name,battery_s=90,filter_kg=.04)
        self.at("ENG-LOCKER")
        self.action(name,"on")
        set_component_condition("equipment",name,"failed",operator=True)
        self.tick()
        row=_clock().details["portable_damage"]["units"][name]
        self.assertEqual(row["mode"],"off")
        self.assertEqual(row["survey"]["battery_remaining_s"],90)
        set_component_condition("equipment",name,"serviceable",operator=True)
        self.tick()
        self.assertEqual(_clock().details["portable_damage"]["units"][name]["mode"],"off")
