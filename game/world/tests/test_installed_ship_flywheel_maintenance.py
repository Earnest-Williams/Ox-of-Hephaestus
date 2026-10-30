"""G19 real vacuum flywheel maintenance, shared spares, suits and lockout."""
from collections import defaultdict, deque
from evennia.utils.test_resources import EvenniaTestCase
from world.bootstrap import build_ship
from world.ship_world import build_canonical_ship, find_ship_space, find_world_entity
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_water,
    commission_g19_repairs, commission_g19_electrical, commission_g19_eva,
    commission_g19_crew_physiology, commission_g19_flywheel_access,
    commission_g19_flywheel_service, survey_g19_flywheel_access,
    survey_g19_electrical_worksite, survey_g19_repair_site,
    survey_g19_electrical_source, survey_g19_water_material,
    crew_physical_action, tick_continuous_physics, _clock,
    local_physics_readout,
)
from world.ship_crew_access import traverse_canonical_exit
from world.models import WorkReceipt, CanonicalShipState


class InstalledFlywheelMaintenance(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_flywheel_access(operator_approved=True)
        self.worker = build_ship()["watch"]
        # Legacy bootstrap crew begins in the small prototype room graph;
        # enrol only after moving the actual character into the canonical ship.
        self.assertTrue(self.worker.move_to(
            find_ship_space("CMD-PRIMARY"), quiet=True))
        commission_g19_crew_physiology(
            actor_dbrefs=[self.worker.dbref], operator_approved=True)
        for bay in ("F1-BAY", "F2-BAY"):
            survey_g19_flywheel_access(bay_id=bay, operator_approved=True)
            survey_g19_electrical_worksite(
                room_id=bay, operator_approved=True)
            survey_g19_repair_site(
                room_id=bay, work_class="suited_service",
                operator_approved=True)
        self.assertTrue(commission_g19_flywheel_service(
            operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_flywheel_service(
            operator_approved=True)["commissioned"])
        for name, charge in (("F1-FW-01", 0), ("F1-FW-02", 10)):
            survey_g19_electrical_source(
                operator_approved=True, source=name,
                capacity_kwh=3906.25, initial_kwh=charge,
                max_charge_mw=.2, max_discharge_mw=.8)
        self.now = 1000
        self.serial = 100

    def request(self):
        self.serial += 1
        return f"{self.serial:032x}"

    def act(self, kind, target, value, request_id=None):
        return crew_physical_action(
            self.worker, request_id or self.request(), kind, target, value)

    def at(self, room):
        self.assertTrue(self.worker.move_to(find_ship_space(room), quiet=True))

    def gear(self):
        self.at("ENG-LOCKER")
        self.act("eva", "INV-DC-CONSUMABLES", "stage:0.75")
        self.at("EVA-FWD")
        self.act("eva", "EVA-FWD", "checkout")

    def stock(self):
        self.at("TOOL-CRIB")
        self.act("repair", "TOOL-CRIB", "pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=4)
        self.at("STORE-CRIT-SPARES")
        self.act("repair", "INV-SPARES", "pickup:3")

    def enter(self, through_lock=False):
        self.at("TRUNK-A-F1")
        if through_lock:
            exit_obj = find_world_entity("access:ACC-F1-BAY:forward")
            result = traverse_canonical_exit(
                self.worker, exit_obj, exit_obj.destination,
                request_id=self.request())
            self.assertEqual(result["status"], "queued")
            self.tick(180)
        else:
            # Airlock admission is independently proven by the hatch suite.
            self.at("F1-BAY")
        self.assertEqual(self.worker.location, find_ship_space("F1-BAY"))

    def tick(self, seconds):
        while seconds > 0:
            delta = min(60, seconds)
            self.now += delta
            tick_continuous_physics(now_game_time=self.now)
            seconds -= delta

    def fitted_load_path(self, start, end):
        """Close ONLY the actual installed linked conductors to a ship load."""
        graph = defaultdict(list)
        for edge in CanonicalShipState.objects.filter(category="edge",
                                                   reference__network="power"):
            if edge.condition in {"faulted", "failed", "severed", "jammed"}:
                continue
            if edge.setting != "available":
                continue
            attrs = edge.reference
            graph[attrs["from_node"]].append((attrs["to_node"], edge))
            if attrs["kind"] in {"bridge_feeder", "cross_tie"}:
                graph[attrs["to_node"]].append((attrs["from_node"], edge))
        prev = {}
        seen = {start}
        queue = deque([start])
        while queue and end not in seen:
            node = queue.popleft()
            for neighbor, edge in graph[node]:
                if neighbor not in seen:
                    prev[neighbor] = (node, edge)
                    seen.add(neighbor)
                    queue.append(neighbor)
        self.assertIn(end, seen, "No actual power route to that shipboard load")
        node = end
        while node != start:
            former, edge = prev[node]
            for breaker_id in edge.reference["isolator_ids"]:
                if state("isolator", breaker_id).setting != "closed":
                    set_isolator(breaker_id, "closed", operator=True)
            node = former

    def test_charged_rotor_distributes_real_kwh_before_measured_safe_lockout(self):
        name = "F1-FW-02"
        self.gear()
        self.enter(through_lock=True)
        self.fitted_load_path("PWR-MSB-A", "NODE-HAB-03-FIRE-DETECT")
        set_isolator("ISO-GEN-M", "open", operator=True)
        self.act("switch", "ISO-PWR-F1-FW-02", "closed")
        stored = _clock().details["electrical"]["flywheels"][name]
        self.assertEqual(stored["charge_kwh"], 10)
        with self.assertRaises(PhysicsError):
            self.act("flywheel_service", name, "lock")
        started = self.act("flywheel_service", name, "rundown")
        self.assertEqual(started, self.act(
            "flywheel_service", name, "rundown",
            request_id=started["request_id"]))
        with self.assertRaises(PhysicsError):
            self.act("power", name, "standby")
        self.tick(10)
        d = _clock().details
        delivered = d["electrical"]["meter"]["flywheel_discharge_kwh"]
        self.assertGreater(delivered, 1)
        self.assertAlmostEqual(10 - d["electrical"]["flywheels"][
            name]["charge_kwh"], delivered, delta=.00001)
        # Disconnecting the real module feeder halts the metered job;
        # it cannot erase the still spinning rotor's energy.
        self.act("switch", "ISO-PWR-F1-FW-02", "open")
        self.tick(10)
        paused = _clock().details
        self.assertAlmostEqual(paused["electrical"][
            "flywheels"][name]["charge_kwh"], 10-delivered, delta=.00001)
        self.assertEqual(paused["flywheel_service"]["rundown_finished"], 0)
        self.act("switch", "ISO-PWR-F1-FW-02", "closed")
        self.tick(60)
        d = _clock().details
        self.assertFalse(d["flywheel_service"]["rundowns"])
        self.assertEqual(d["flywheel_service"]["rundown_finished"], 1)
        self.assertAlmostEqual(
            d["flywheel_service"]["rundown_delivered_kwh"], 10, delta=.00001)
        self.assertAlmostEqual(
            d["electrical"]["meter"]["flywheel_discharge_kwh"], 10,
            delta=.00001)
        self.assertAlmostEqual(
            d["electrical"]["flywheels"][name]["charge_kwh"], 0,
            delta=.00001)
        self.assertEqual(d["electrical"]["flywheels"][name]["mode"], "standby")
        self.act("switch", "ISO-PWR-F1-FW-02", "open")
        self.act("flywheel_service", name, "lock")
        self.assertIn(name, _clock().details["flywheel_service"]["permits"])

    def test_halt_supervised_discharge_retains_unspent_energy(self):
        name = "F1-FW-02"
        self.gear()
        self.enter()
        self.fitted_load_path("PWR-MSB-A", "NODE-HAB-03-FIRE-DETECT")
        set_isolator("ISO-GEN-M", "open", operator=True)
        self.act("switch", "ISO-PWR-F1-FW-02", "closed")
        self.act("flywheel_service", name, "rundown")
        self.tick(10)
        charge = _clock().details["electrical"]["flywheels"][name]["charge_kwh"]
        self.act("flywheel_service", name, "halt")
        self.assertEqual(_clock().details["flywheel_service"]["rundown_halted"], 1)
        self.tick(20)
        self.assertAlmostEqual(
            _clock().details["electrical"]["flywheels"][name]["charge_kwh"],
            charge, delta=.000001)
        self.assertEqual(
            _clock().details["electrical"]["flywheels"][name]["mode"],
            "standby")
        with self.assertRaises(PhysicsError):
            self.act("flywheel_service", name, "lock")


    def test_real_suited_entry_failed_module_repair_and_release(self):
        self.stock()
        set_component_condition("equipment", "F1-FW-01", "failed",
                                operator=True)
        self.gear()
        self.enter(through_lock=True)
        with self.assertRaises(PhysicsError):
            self.act("repair", "equipment:F1-FW-01", "start")
        receipt = self.act("flywheel_service", "F1-FW-01", "lock")
        self.assertEqual(receipt, self.act(
            "flywheel_service", "F1-FW-01", "lock",
            request_id=receipt["request_id"]))
        self.act("repair", "equipment:F1-FW-01", "start")
        self.tick(300)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:F1-FW-01"]["remaining_s"], 300)
        with self.assertRaises(PhysicsError):
            self.act("flywheel_service", "F1-FW-01", "release")
        self.tick(300)
        self.assertEqual(state("equipment", "F1-FW-01").condition, "serviceable")
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 3)
        self.assertEqual(_clock().details["repairs"]["completed"], 1)
        self.assertIn("F1-FW-01", _clock().details["flywheel_service"]["permits"])
        with self.assertRaises(PhysicsError):
            self.act("switch", "ISO-PWR-F1-FW-01", "closed")
        self.act("flywheel_service", "F1-FW-01", "release")
        self.act("switch", "ISO-PWR-F1-FW-01", "closed")
        self.assertEqual(state("isolator", "ISO-PWR-F1-FW-01").setting, "closed")
        self.assertEqual(_clock().details["electrical"][
            "flywheels"]["F1-FW-01"]["mode"], "standby")
        self.assertEqual(WorkReceipt.objects.filter(
            operation="flywheel_service").count(), 2)

    def test_fake_suit_flag_and_charged_rotor_cannot_get_padlock(self):
        self.at("F1-BAY")
        self.worker.db.ox_suit_verified = True
        with self.assertRaises(PhysicsError):
            self.act("flywheel_service", "F1-FW-01", "lock")
        self.gear()
        self.enter()
        with self.assertRaises(PhysicsError):
            self.act("flywheel_service", "F1-FW-02", "lock")
        self.assertEqual(_clock().details["electrical"]["flywheels"][
            "F1-FW-02"]["charge_kwh"], 10)
        self.act("flywheel_service", "F1-FW-01", "lock")
        for mode in ("charge", "discharge"):
            with self.assertRaises(PhysicsError):
                self.act("power", "F1-FW-01", mode)
        with self.assertRaises(PhysicsError):
            self.act("switch", "ISO-PWR-F1-FW-01", "closed")
        survey = local_physics_readout(self.worker, "flywheel_service")
        self.assertEqual(survey["modules"]["F1-FW-01"]["lockout_owner"],
                         self.worker.dbref)

    def test_failed_breaker_halts_repair_without_refunding_spares(self):
        self.stock()
        set_component_condition("equipment", "F1-FW-01", "failed", operator=True)
        self.gear()
        self.enter()
        self.act("flywheel_service", "F1-FW-01", "lock")
        self.act("repair", "equipment:F1-FW-01", "start")
        self.tick(60)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:F1-FW-01"]["remaining_s"], 540)
        set_component_condition(
            "isolator", "ISO-PWR-F1-FW-01", "failed", operator=True)
        self.tick(120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:F1-FW-01"]["remaining_s"], 540)
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 0)
        self.assertIn("F1-FW-01", _clock().details["flywheel_service"]["permits"])
        set_component_condition(
            "isolator", "ISO-PWR-F1-FW-01", "serviceable", operator=True)
        self.tick(540)
        self.assertEqual(state("equipment", "F1-FW-01").condition, "serviceable")

    def test_bank_switchboard_requires_both_infeeds_and_32_module_open_contacts(self):
        self.stock()
        self.gear()
        self.enter()
        set_component_condition("equipment", "F1-BUS", "failed", operator=True)
        with self.assertRaises(PhysicsError):
            self.act("repair", "equipment:F1-BUS", "start")
        self.assertEqual(state("isolator", "ISO-F1-BUS-IN-1").setting, "closed")
        self.act("switch", "ISO-F1-BUS-IN-1", "open")
        self.act("repair", "equipment:F1-BUS", "start")
        self.assertIn("equipment:F1-BUS", _clock().details["repairs"]["jobs"])
