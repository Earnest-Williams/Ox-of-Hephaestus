"""Installed HAB-04 first aid with actual Evennia workers."""
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space
from world.full_ship_operations import install_candidate, install_pressure_cells, initialize_nominal_atmosphere, set_isolator
from world.continuous_ship_physics import arm_continuous_physics, commission_g19_medical, commission_g19_crew_physiology, crew_physical_action, tick_continuous_physics, _clock
from world.models import CanonicalShipState, WorkReceipt

class InstalledMedical(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        # Actual rotating HAB treatment bus has separate upstream and
        # room breakers; energy from GEN-M alone never closes them.
        for breaker in ("ISO-ROT-PWR-A", "ISO-HAB-04-A-IN",
                        "ISO-HAB-04-MED-TREAT-LP"):
            set_isolator(breaker, "closed", operator=True)
        crew = build_ship()
        self.medic, self.patient = crew["environment"], crew["cargo"]
        self.medic.move_to(find_ship_space("HAB-04-MED-PHARM"), quiet=True)
        self.patient.move_to(find_ship_space("HAB-04-MED-TREAT"), quiet=True)
        commission_g19_crew_physiology(actor_dbrefs=[self.medic.dbref, self.patient.dbref], operator_approved=True)
        health = CanonicalShipState.objects.get(pk="crew_health:" + self.patient.dbref)
        h = dict(health.details)
        h.update(injury=.30, condition="impaired")
        health.details, health.condition = h, "impaired"
        health.save(update_fields=["details", "condition"])
        self.now, self.serial = 1000, 0

    def action(self, target, value, request=None):
        self.serial += 1
        return crew_physical_action(self.medic, request or f"{self.serial:032x}", "medical", target, value)

    def tick(self, seconds):
        while seconds:
            dt = min(60, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def prepare(self):
        commission_g19_medical(operator_approved=True, dressings=4, fluid_kg=2)
        self.action("kit", "pickup:2")
        self.medic.move_to(find_ship_space("HAB-04-MED-TREAT"), quiet=True)
        self.action("kit", "deliver")

    def test_custody_and_deduplicated_actions(self):
        commission_g19_medical(operator_approved=True, dressings=4, fluid_kg=2)
        rid = "f"*32
        first = self.action("kit", "pickup:2", request=rid)
        self.assertEqual(first, self.action("kit", "pickup:2", request=rid))
        self.assertEqual(_clock().details["medical"]["pharmacy_dressings"], 2)
        self.assertEqual(WorkReceipt.objects.filter(request_id=rid).count(), 1)
        self.medic.move_to(find_ship_space("HAB-04-MED-TREAT"), quiet=True)
        self.action("kit", "deliver")
        self.assertEqual(_clock().details["medical"]["dressings"], 2)

    def test_stabilisation_pauses_when_attendant_leaves(self):
        self.prepare()
        self.action("care", self.patient.dbref)
        self.tick(120)
        self.medic.move_to(find_ship_space("HAB-04-MED-PHARM"), quiet=True)
        remaining = _clock().details["medical"]["cases"][self.patient.dbref]["remaining_s"]
        self.tick(60)
        self.assertEqual(_clock().details["medical"]["cases"][self.patient.dbref]["remaining_s"], remaining)
        self.medic.move_to(find_ship_space("HAB-04-MED-TREAT"), quiet=True)
        self.tick(180)
        self.assertEqual(_clock().details["medical"]["completed"], 1)
        self.assertLess(CanonicalShipState.objects.get(pk="crew_health:" + self.patient.dbref).details["injury"], .30)

    def test_followup_is_real_attended_clock_work(self):
        self.prepare()
        self.action("observe", self.patient.dbref)
        clinic = _clock().details["medical"]
        self.assertEqual(clinic["used_dressings"], 1)
        self.assertEqual(clinic["observations"][self.patient.dbref]["remaining_s"], 7200)
        self.tick(60)
        current = CanonicalShipState.objects.get(
            pk="crew_health:" + self.patient.dbref).details["injury"]
        self.assertLess(current, .30)
        self.medic.move_to(find_ship_space("HAB-04-MED-PHARM"), quiet=True)
        remaining = _clock().details["medical"]["observations"][
            self.patient.dbref]["remaining_s"]
        self.tick(60)
        self.assertEqual(_clock().details["medical"]["observations"][
            self.patient.dbref]["remaining_s"], remaining)
        self.assertEqual(CanonicalShipState.objects.get(
            pk="crew_health:" + self.patient.dbref).details["injury"], current)
        self.medic.move_to(find_ship_space("HAB-04-MED-TREAT"), quiet=True)
        self.action("discharge", self.patient.dbref)
        self.assertFalse(_clock().details["medical"]["observations"])
        self.assertEqual(_clock().details["medical"]["used_dressings"], 1)

    def test_actual_observation_bay_has_independent_power_and_stock(self):
        commission_g19_medical(operator_approved=True, dressings=4, fluid_kg=2)
        self.action("kit", "pickup:2")
        self.medic.move_to(
            find_ship_space("HAB-04-MED-OBS"), quiet=True)
        self.patient.move_to(
            find_ship_space("HAB-04-MED-OBS"), quiet=True)
        self.action("kit", "deliver")
        self.assertEqual(_clock().details["medical"]["obs_dressings"], 2)
        self.assertEqual(_clock().details["medical"]["dressings"], 0)
        with self.assertRaises(Exception):
            self.action("observe", self.patient.dbref)
        set_isolator("ISO-HAB-04-MED-OBS-LP", "closed", operator=True)
        started = self.action("observe", self.patient.dbref)
        self.assertEqual(started["status"], "succeeded")
        self.assertEqual(
            _clock().details["medical"]["observations"][
                self.patient.dbref]["room"], "HAB-04-MED-OBS")
        self.tick(60)
        before = CanonicalShipState.objects.get(
            pk="crew_health:" + self.patient.dbref).details["injury"]
        self.assertLess(before, .30)
        set_isolator("ISO-HAB-04-MED-OBS-LP", "open", operator=True)
        remaining = _clock().details["medical"]["observations"][
            self.patient.dbref]["remaining_s"]
        self.tick(60)
        self.assertEqual(_clock().details["medical"]["observations"][
            self.patient.dbref]["remaining_s"], remaining)
        self.assertEqual(CanonicalShipState.objects.get(
            pk="crew_health:" + self.patient.dbref).details["injury"], before)
        set_isolator("ISO-HAB-04-MED-OBS-LP", "closed", operator=True)
        self.tick(60)
        self.assertLess(CanonicalShipState.objects.get(
            pk="crew_health:" + self.patient.dbref).details["injury"], before)
        self.medic.move_to(find_ship_space("HAB-04-MED-TREAT"), quiet=True)
        with self.assertRaises(PermissionError):
            self.action("discharge", self.patient.dbref)
        self.medic.move_to(find_ship_space("HAB-04-MED-OBS"), quiet=True)
        self.action("discharge", self.patient.dbref)
        self.assertFalse(_clock().details["medical"]["observations"])
        self.assertEqual(_clock().details["medical"]["used_dressings"], 1)

    def test_lost_local_feeder_pauses_work_without_refund(self):
        self.prepare()
        self.action("care", self.patient.dbref)
        set_isolator("ISO-HAB-04-MED-TREAT-LP", "open", operator=True)
        self.tick(60)
        m = _clock().details["medical"]
        self.assertEqual(m["cases"][self.patient.dbref]["remaining_s"], 300)
        self.assertEqual(m["used_dressings"], 1)
