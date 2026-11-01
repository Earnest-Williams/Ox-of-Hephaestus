"""Two-carrier incapacitated transfer through a real HAB door."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.ship_world import ensure_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator,
)
from world.continuous_ship_physics import (
    arm_continuous_physics, commission_g19_crew_physiology,
    commission_g19_medical, commission_g19_rescue, crew_physical_action,
    tick_continuous_physics, local_physics_readout, _clock, PhysicsError,
)
from world.ship_crew_access import CrewTransitError, traverse_canonical_exit
from world.models import CanonicalShipState, WorkReceipt


LINK = "ACC-HAB-04-MED-TREAT"
DIRECTION = "forward"


class InstalledCasualtyCarriage(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        # Original HAB medical feed is three isolators downstream of generator.
        for name in ("ISO-ROT-PWR-A", "ISO-HAB-04-A-IN",
                     "ISO-HAB-04-MED-TREAT-LP"):
            set_isolator(name, "closed", operator=True)
        crew = build_ship()
        self.lead, self.helper, self.patient = (
            crew["environment"], crew["watch"], crew["cargo"])
        self.control = crew["chief"]
        self.corridor = find_ship_space("HAB-04-COR")
        self.treatment = find_ship_space("HAB-04-MED-TREAT")
        for person in (self.lead, self.helper, self.patient, self.control):
            person.move_to(self.corridor, quiet=True)
        commission_g19_crew_physiology(
            actor_dbrefs=[
                self.lead.dbref, self.helper.dbref, self.patient.dbref,
                self.control.dbref], operator_approved=True)
        hp = CanonicalShipState.objects.get(pk="crew_health:" + self.patient.dbref)
        injury = dict(hp.details)
        injury.update(injury=.7, condition="incapacitated")
        hp.details = injury
        hp.condition = "incapacitated"
        hp.save(update_fields=["details", "condition"])
        commission_g19_medical(operator_approved=True, dressings=4, fluid_kg=2)
        self.assertTrue(commission_g19_rescue(operator_approved=True)["commissioned"])
        self.now = 1000
        self.sequence = 0

    def rid(self):
        self.sequence += 1
        return f"{self.sequence:032x}"

    def op(self, actor, action, target, value, request=None):
        return crew_physical_action(
            actor, request or self.rid(), action, target, value)

    def open_hatch(self):
        self.op(self.lead, "hatch", LINK, "open")

    def begin(self):
        self.open_hatch()
        return self.op(
            self.lead, "rescue", self.patient.dbref,
            f"{self.helper.dbref}:{LINK}:{DIRECTION}")

    def tick(self, seconds):
        while seconds:
            dt = min(10, seconds)
            self.now += dt
            tick_continuous_physics(now_game_time=self.now)
            seconds -= dt

    def test_patient_carried_through_real_open_hatch_on_ship_time(self):
        self.begin()
        self.assertEqual(self.patient.location, self.corridor)
        self.tick(20)
        self.assertEqual(self.patient.location, self.corridor)
        self.assertEqual(_clock().details["rescue"]["jobs"][
            self.patient.dbref]["remaining_s"], 10)
        self.tick(10)
        for person in (self.patient, self.lead, self.helper):
            self.assertEqual(person.location, self.treatment)
        self.assertEqual(self.control.location, self.corridor)
        self.assertEqual(_clock().details["rescue"]["completed"], 1)
        self.assertFalse(_clock().details["rescue"]["jobs"])
        self.assertEqual(CanonicalShipState.objects.get(
            pk="crew_health:" + self.patient.dbref).condition, "incapacitated")

    def test_passage_closure_pauses_real_occupants_and_restarts(self):
        self.begin()
        self.tick(10)
        self.op(self.control, "hatch", LINK, "closed")
        self.tick(50)
        self.assertEqual(self.patient.location, self.corridor)
        self.assertEqual(_clock().details["rescue"]["jobs"][
            self.patient.dbref]["remaining_s"], 20)
        self.op(self.control, "hatch", LINK, "open")
        self.tick(20)
        self.assertEqual(self.patient.location, self.treatment)

    def test_no_self_walk_or_conflicting_machine_actions_while_carried(self):
        self.begin()
        doorway = find_world_entity(f"access:{LINK}:forward")
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(
                self.helper, doorway, doorway.destination,
                request_id=self.rid())
        with self.assertRaises(PermissionError):
            self.op(self.helper, "power", "normal", "normal")
        with self.assertRaises(CrewTransitError):
            traverse_canonical_exit(
                self.patient, doorway, doorway.destination,
                request_id=self.rid())
        self.assertIn(self.patient.dbref,
                      local_physics_readout(self.lead, "rescue")["local_orders"])

    def test_cancel_and_global_request_replay_are_bounded(self):
        self.open_hatch()
        rid = "d"*32
        val = f"{self.helper.dbref}:{LINK}:{DIRECTION}"
        first = self.op(self.lead, "rescue", self.patient.dbref, val, request=rid)
        self.assertEqual(first, self.op(
            self.lead, "rescue", self.patient.dbref, val, request=rid))
        # Either original carrier can abandon a dangerous or stalled carry.
        self.op(self.helper, "rescue", self.patient.dbref, "cancel")
        with self.assertRaises((PermissionError, PhysicsError)):
            self.op(self.lead, "rescue", self.patient.dbref, "cancel")
        self.assertEqual(_clock().details["rescue"]["cancelled"], 1)
        self.assertEqual(_clock().details["rescue"]["completed"], 0)
        self.assertFalse(_clock().details["rescue"]["jobs"])
        self.assertEqual(WorkReceipt.objects.filter(request_id=rid).count(), 1)

    def test_unrated_routes_and_deceased_patients_are_refused(self):
        self.open_hatch()
        with self.assertRaises((PhysicsError, PermissionError, CrewTransitError)):
            self.op(self.lead, "rescue", self.patient.dbref,
                    f"{self.helper.dbref}:ACC-IX-A-ROT:forward")
        self.patient.db.ox_terminal_dead = True
        with self.assertRaises((PhysicsError, PermissionError)):
            self.op(self.lead, "rescue", self.patient.dbref,
                    f"{self.helper.dbref}:{LINK}:forward")
