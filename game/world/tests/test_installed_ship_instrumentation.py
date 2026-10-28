"""G19 real 116-panel installed Evennia instrumentation and casualty tests.

Uses actual ship rooms, power nodes, pressure cells and individual breakers.
No 40-person voyage, automatic rescue, virtual camera or global fault oracle.
"""
from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state,
)
from world.ship_world import build_canonical_ship, find_ship_space
from world.models import CanonicalShipState, WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    commission_g19_instrumentation, tick_continuous_physics,
    local_physics_readout, crew_physical_action,
)
from world.ship_instrumentation import alarm_key


class InstalledInstrumentationTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        commission_g19_electrical(operator_approved=True)

    def at(self, room):
        real = find_ship_space(room)
        self.assertIsNotNone(real, room)
        self.assertTrue(self.worker.move_to(real, quiet=True))

    def ledger(self):
        return CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["instrumentation"]

    def energize(self, destination, *, source="NODE-GEN-M"):
        set_isolator("ISO-GEN-M", "closed", operator=True)
        edges = list(CanonicalShipState.objects.filter(
            category="edge", reference__network="power"))
        graph = defaultdict(list)
        for e in edges:
            if e.condition in {"faulted", "failed", "jammed", "severed", "destroyed"
                              } or e.setting != "available":
                continue
            a, b = e.reference["from_node"], e.reference["to_node"]
            graph[a].append((b, e))
            if e.reference["kind"] in {"bridge_feeder", "cross_tie"}:
                graph[b].append((a, e))
        q, seen, previous = deque([source]), {source}, {}
        while q and destination not in seen:
            for nxt, e in graph[q.popleft()]:
                if nxt not in seen:
                    seen.add(nxt)
                    previous[nxt] = (e, e.reference["from_node"],
                                     e.reference["to_node"])
                    q.append(nxt)
        self.assertIn(destination, seen, "No real original power route")
        node = destination
        while node != source:
            e, a, b = previous[node]
            for iso in e.reference["isolator_ids"]:
                if state("isolator", iso).setting != "closed":
                    set_isolator(iso, "closed", operator=True)
            node = a if node == b else b

    def mutate_gas(self, zone, *, smoke=None, burn=None, fuel=None, leak=None):
        cell = state("pressure", zone, lock=True)
        changes = {}
        for name, value in (
                ("physics_smoke_kg", smoke), ("physics_burn_kg_s", burn),
                ("physics_fuel_kg", fuel), ("physics_leak_kg_s", leak)):
            if value is not None:
                changes[name] = value
        details = dict(cell.details)
        details.update(changes)
        cell.details = details
        cell.revision += 1
        cell.save(update_fields=["details", "revision"])

    def test_full_116_panel_as_built_commission_and_no_reset(self):
        with self.assertRaises(PermissionError):
            commission_g19_instrumentation()
        self.assertEqual(
            commission_g19_instrumentation(operator_approved=True)[
                "fitted_panels"], 116)
        self.assertEqual(len(self.ledger()["panels"]), 116)
        self.assertEqual(
            commission_g19_instrumentation(operator_approved=True),
            {"commissioned": False, "fitted_panels": 116})
        self.assertEqual(self.ledger()["sample_count"], 0)
        self.at("ENG-CONTROL")
        with self.assertRaises(PhysicsError):
            local_physics_readout(self.worker, "instruments")

    def test_powered_control_station_shows_only_its_real_zone_and_age(self):
        commission_g19_instrumentation(operator_approved=True)
        self.energize("NODE-LP-ENG-CONTROL")
        self.at("ENG-CONTROL")
        first = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(first["advanced"])
        self.assertGreaterEqual(first["instrument_panels_online"], 1)
        face = local_physics_readout(self.worker, "panel:LP-ENG-CONTROL")
        self.assertEqual(face["status"], "online")
        self.assertEqual(face["age_s"], 0)
        self.assertEqual(face["room"], "ENG-CONTROL")
        self.assertIn("pressure_kpa", face["measurements"])
        self.assertIn("LP-ENG-CONTROL",
                      local_physics_readout(self.worker, "instruments")["panels"])
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "panel:LP-GEN-M-ROOM")
        self.assertFalse(tick_continuous_physics(
            now_game_time=1010)["advanced"])
        self.assertEqual(self.ledger()["sample_count"], 1)

    def test_real_machine_fault_acknowledgement_never_repairs_machine(self):
        commission_g19_instrumentation(operator_approved=True)
        self.energize("NODE-LP-SHOP-MECH")
        set_component_condition("equipment", "SHOP-CNC-MILL", "failed",
                                operator=True)
        self.at("SHOP-MECH")
        tick_continuous_physics(now_game_time=1010)
        key = alarm_key("LP-SHOP-MECH", "MACHINE_FAULT", "SHOP-CNC-MILL")
        self.assertTrue(self.ledger()["alarms"][key]["active"])
        record = local_physics_readout(self.worker, "diagnose:" + key)
        self.assertEqual(record["family"], "maintenance")
        self.assertTrue(record["does_not_isolate_or_repair"])
        receipt = crew_physical_action(
            self.worker, "1" * 32, "instrument", "LP-SHOP-MECH", "ack:" + key)
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(crew_physical_action(
            self.worker, "1" * 32, "instrument", "LP-SHOP-MECH",
            "ack:" + key), receipt)
        self.assertEqual(state("equipment", "SHOP-CNC-MILL").condition, "failed")
        self.assertTrue(self.ledger()["alarms"][key]["active"])
        self.assertEqual(self.ledger()["alarms"][key]["ack_by"], self.worker.dbref)
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.worker, "2" * 32, "instrument",
                                 "LP-SHOP-MECH", "ack:" + key)
        set_component_condition("equipment", "SHOP-CNC-MILL", "serviceable",
                                operator=True)
        tick_continuous_physics(now_game_time=1020)
        self.assertTrue(self.ledger()["alarms"][key]["active"])
        tick_continuous_physics(now_game_time=1030)
        self.assertFalse(self.ledger()["alarms"][key]["active"])
        self.assertEqual(self.ledger()["alarms"][key]["ack_by"], self.worker.dbref)

    def test_real_panel_power_loss_does_not_clear_stale_fault(self):
        commission_g19_instrumentation(operator_approved=True)
        self.energize("NODE-LP-SHOP-MECH")
        self.at("SHOP-MECH")
        set_component_condition("equipment", "SHOP-CNC-MILL", "failed",
                                operator=True)
        tick_continuous_physics(now_game_time=1010)
        key = alarm_key("LP-SHOP-MECH", "MACHINE_FAULT", "SHOP-CNC-MILL")
        set_isolator("ISO-GEN-M", "open", operator=True)
        tick_continuous_physics(now_game_time=1020)
        self.assertTrue(self.ledger()["alarms"][key]["active"])
        dark = alarm_key("LP-SHOP-MECH", "INSTRUMENT_LOST", "LP-SHOP-MECH")
        self.assertTrue(self.ledger()["alarms"][dark]["active"])
        self.assertEqual(self.ledger()["panels"]["LP-SHOP-MECH"]["last_good_s"], 1010)
        with self.assertRaises(PhysicsError):
            local_physics_readout(self.worker, "panel:LP-SHOP-MECH")
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.worker, "3" * 32, "instrument",
                                 "LP-SHOP-MECH", "ack:" + key)

    def test_sensed_hab_fire_is_not_globally_visible_without_real_relay(self):
        commission_g19_instrumentation(operator_approved=True)
        self.energize("NODE-LP-HAB-01-FOOD-STORES")
        self.energize("NODE-LP-ENG-CONTROL")
        self.energize("NODE-HAB-01-COMMS-NODE")
        self.energize("NODE-HAB-01-FIRE-DETECT")
        self.mutate_gas("PZ-HAB-01", burn=.05, fuel=2.0, smoke=.5)
        tick_continuous_physics(now_game_time=1010)
        self.at("HAB-01-FOOD-STORES")
        alarms = local_physics_readout(self.worker, "alarms")["alarms"]
        self.assertTrue(any(a["code"] == "FIRE" for a in alarms.values()))
        self.at("ENG-CONTROL")
        bridge = local_physics_readout(self.worker, "alarm_bridge")
        self.assertIn("FIRE", bridge["alerts_by_arc"]["HAB-01"])
        self.assertNotIn("HAB-01", bridge["lost_protected_links"])
        set_component_condition("equipment", "HAB-01-COMMS-NODE", "failed",
                                operator=True)
        bridge = local_physics_readout(self.worker, "alarm_bridge")
        self.assertIn("HAB-01", bridge["lost_protected_links"])
        self.assertNotIn("HAB-01", bridge["alerts_by_arc"])
        self.at("HAB-01-FOOD-STORES")
        with self.assertRaises(PhysicsError):
            local_physics_readout(self.worker, "alarm_bridge")

    def test_cleared_hab_fire_requires_two_good_physical_samples(self):
        commission_g19_instrumentation(operator_approved=True)
        self.energize("NODE-LP-HAB-01-FOOD-STORES")
        self.mutate_gas("PZ-HAB-01", burn=.05, fuel=2.0, smoke=.2)
        tick_continuous_physics(now_game_time=1010)
        key = alarm_key("HAB-01-FOOD-STORES-LP", "FIRE", "PZ-HAB-01")
        self.assertTrue(self.ledger()["alarms"][key]["active"])
        self.mutate_gas("PZ-HAB-01", burn=0, fuel=0, smoke=0)
        tick_continuous_physics(now_game_time=1020)
        self.assertTrue(self.ledger()["alarms"][key]["active"])
        tick_continuous_physics(now_game_time=1030)
        self.assertFalse(self.ledger()["alarms"][key]["active"])
        self.assertEqual(
            self.ledger()["history"][-1]["transition"], "resolved")

    def test_survey_required_for_bare_flywheel_bay_not_fictional_sensor(self):
        commission_g19_instrumentation(operator_approved=True)
        self.at("F1-BAY")
        with self.assertRaises((PermissionError, PhysicsError)):
            local_physics_readout(self.worker, "panel:LP-F1-BAY")
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "panel:LP-F2-BAY")

    def test_real_source_panel_cannot_be_teleported_by_recommission(self):
        commission_g19_instrumentation(operator_approved=True)
        set_component_condition("equipment", "LP-ENG-CONTROL", "failed",
                                operator=True)
        commission_g19_instrumentation(operator_approved=True)
        self.assertEqual(state("equipment", "LP-ENG-CONTROL").condition, "failed")
