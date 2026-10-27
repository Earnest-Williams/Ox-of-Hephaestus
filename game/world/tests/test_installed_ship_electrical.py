"""Installed-world G19 electrical operation and casualty tests (no voyage)."""
from __future__ import annotations

from collections import defaultdict, deque
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state, set_component_condition, set_isolator,
)
from world.ship_world import build_canonical_ship, find_ship_space
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    survey_g19_electrical_source, survey_g19_electrical_worksite,
    configure_g19_electrical_fault,
    crew_physical_action, tick_continuous_physics, local_physics_readout,
)


class InstalledElectricalTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]

    def crew_at(self, room):
        location = find_ship_space(room)
        self.assertIsNotNone(location, room)
        self.worker.move_to(location, quiet=True)

    def line_up_real_feeder(self, start, destination):
        """Operator test fixture: energise the authentic connected conductor path.

        A newly installed v0.5 ship begins with 461 OPEN breaker contacts.
        Tests must prove an actual route and close its individually fitted
        isolators; physically disconnected loads are never assumed online.
        """
        edges = list(CanonicalShipState.objects.filter(category="edge",
                           reference__network="power"))
        graph = defaultdict(list)
        for edge in edges:
            if edge.setting != "available" or edge.condition in {
                    "faulted", "failed", "severed", "destroyed", "jammed"}:
                continue
            spec = edge.reference
            graph[spec["from_node"]].append((spec["to_node"], edge))
            if spec["kind"] in {"bridge_feeder", "cross_tie"}:
                graph[spec["to_node"]].append((spec["from_node"], edge))
        visited = {start}
        previous = {}
        queue = deque([start])
        while queue and destination not in visited:
            for nxt, segment in graph[queue.popleft()]:
                if nxt not in visited:
                    visited.add(nxt)
                    previous[nxt] = segment, segment.reference["from_node"], segment.reference["to_node"]
                    queue.append(nxt)
        self.assertIn(destination, visited, "No real power path to requested load")
        position = destination
        while position != start:
            segment, a, b = previous[position]
            for isolator_id in segment.reference["isolator_ids"]:
                if state("isolator", isolator_id).setting != "closed":
                    set_isolator(isolator_id, "closed", operator=True)
            position = a if position == b else b

    def test_full_authored_graph_and_nonresetting_commission(self):
        result = commission_g19_electrical(operator_approved=True)
        self.assertEqual((result["nodes"], result["feeders"], result["breakers"]),
                         (438, 450, 466))
        self.assertEqual(result["rated_battery_kwh"], 0)
        self.assertFalse(commission_g19_electrical(operator_approved=True)["commissioned"])
        # A main-generator feeder must be physically selected; the authored
        # cold condition is never promoted to a closed contact by commissioning.
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        tick = tick_continuous_physics(now_game_time=1010)
        self.assertIn("electrical", tick)
        self.assertGreater(tick["electrical"]["meter"]["served_kwh"], 0)
        self.assertEqual(tick["electrical"]["meter"]["battery_discharge_kwh"], 0)
        self.assertEqual(tick["electrical"]["meter"]["shore_import_kwh"], 0)

    def test_generator_feeder_failure_browns_out_normal_work(self):
        commission_g19_electrical(operator_approved=True)
        set_component_condition("edge", "EDGE-GEN-M", "severed", operator=True)
        tick = tick_continuous_physics(now_game_time=1010)
        self.assertLessEqual(tick["available_mw"], 0.65)
        self.assertFalse(tick["power_assured"])
        self.assertGreater(tick["electrical"]["meter"]["unserved_kwh"], 0)
        self.assertFalse(tick_continuous_physics(now_game_time=1010)["advanced"])

    def test_damaged_main_switchboard_really_disconnects_downstream_branch(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder(
            "NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        energised = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(energised["power_assured"])
        set_component_condition("equipment", "MSB-A", "failed",
                                operator=True)
        damaged = tick_continuous_physics(now_game_time=1020)
        self.assertNotIn("GEN-M", damaged["electrical"]["last"]["sources"])
        self.assertFalse(damaged["power_assured"])
        self.assertFalse(damaged["electrical"]["last"]["main_a"])
        self.assertEqual(damaged["electrical"]["last"][
                         "generator_delivered_mw"], 0)

    def test_real_breaker_overload_trips_and_requires_reset(self):
        commission_g19_electrical(operator_approved=True)
        breaker = state("isolator", "ISO-GEN-M")
        self.assertEqual(breaker.reference["network"], "power")
        if breaker.setting != "closed":
            set_isolator("ISO-GEN-M", "closed", operator=True)
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id="ISO-GEN-M",
            rating_mw=1.0, measured_mw=2.0)
        tick = tick_continuous_physics(now_game_time=1010)
        opened = state("isolator", "ISO-GEN-M")
        self.assertEqual(opened.setting, "open")
        self.assertTrue(opened.details["physics_power_trip_latched"])
        self.assertLessEqual(tick["available_mw"], .65)
        self.crew_at(opened.space_id)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "9" * 32, "switch", "ISO-GEN-M", "closed")
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "8" * 32, "power", "ISO-GEN-M", "reset")
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id="ISO-GEN-M",
            rating_mw=1.0, measured_mw=0)
        # The installed generator is in an unpressurised space. The engineer
        # cannot reset its switchgear without a separate positive site survey
        # and individually verified protective equipment.
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "6" * 32, "power", "ISO-GEN-M", "reset")
        surveyed = survey_g19_electrical_worksite(
            operator_approved=True, room_id=opened.space_id)
        self.assertTrue(surveyed["changed"])
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "5" * 32, "power", "ISO-GEN-M", "reset")
        self.worker.db.ox_suit_verified = True
        result = crew_physical_action(
            self.worker, "7" * 32, "power", "ISO-GEN-M", "reset")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(
            crew_physical_action(self.worker, "7" * 32,
                                 "power", "ISO-GEN-M", "reset"), result)
        self.assertIsNone(state("isolator", "ISO-GEN-M").details.get(
            "physics_power_trip_latched"))
        self.assertEqual(WorkReceipt.objects.get(pk="7" * 32).operation, "power")
        # Reset releases the latch; it NEVER recloses the actual contacts.
        self.assertEqual(state("isolator", "ISO-GEN-M").setting, "open")

    def test_meter_advances_once_only_and_persists_exactly(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        first = tick_continuous_physics(now_game_time=1010)
        energy = first["electrical"]["meter"]
        self.assertFalse(tick_continuous_physics(now_game_time=1010)["advanced"])
        self.assertEqual(CanonicalShipState.objects.get(pk="meta:continuous-physics").details["electrical"]["meter"],
                         energy)
        second = tick_continuous_physics(now_game_time=1020)
        self.assertGreater(second["electrical"]["meter"]["served_kwh"],
                           energy["served_kwh"])

    def test_operator_cannot_invent_a_battery_or_unapproved_source(self):
        commission_g19_electrical(operator_approved=True)
        with self.assertRaises(PermissionError):
            survey_g19_electrical_source(
                source="BAT-COMMON-PROT", capacity_kwh=3, initial_kwh=2,
                max_charge_mw=.3, max_discharge_mw=.3)
        with self.assertRaises(PhysicsError):
            survey_g19_electrical_source(
                operator_approved=True, source="BAT-UNAUTHORISED",
                capacity_kwh=3, initial_kwh=2,
                max_charge_mw=.3, max_discharge_mw=.3)

    def test_power_readout_is_local_and_does_not_oracle_other_rooms(self):
        commission_g19_electrical(operator_approved=True)
        self.crew_at(state("equipment", "GEN-M").space_id)
        board = local_physics_readout(self.worker, "power")
        self.assertIn("meters_kwh", board)
        local_node = local_physics_readout(self.worker, "NODE-GEN-M")
        self.assertEqual(local_node["scope"],
                         "physically_local_actual_power_circuit")
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "NODE-HAB-03-CAB-07-LP")

    def test_tie_requires_elapsed_synchronisation_and_live_source(self):
        commission_g19_electrical(operator_approved=True)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        tie = state("edge", "EDGE-MSB-XTIE")
        self.assertEqual(tie.reference["network"], "power")
        self.assertEqual(tie.setting, "standby")
        for name in tie.reference["isolator_ids"]:
            set_isolator(name, "closed", operator=True)
        self.crew_at(state("isolator", tie.reference["isolator_ids"][0]).space_id)
        issued = crew_physical_action(
            self.worker, "1" * 32, "power", "EDGE-MSB-XTIE", "sync")
        self.assertEqual(issued["status"], "succeeded")
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "2" * 32, "power", "EDGE-MSB-XTIE", "close")
        tick_continuous_physics(now_game_time=1015)
        result = crew_physical_action(
            self.worker, "3" * 32, "power", "EDGE-MSB-XTIE", "close")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(state("edge", "EDGE-MSB-XTIE").setting, "available")

    def test_cabin_refit_panel_is_not_the_fan_coil_source(self):
        from world.continuous_ship_physics import _power
        commission_g19_electrical(operator_approved=True)
        # The SG2 cabin corridor is physically wired to the B distribution,
        # not the main A board. Line up both real sibling branch circuits.
        self.line_up_real_feeder("NODE-GEN-B", "NODE-HAB-03-CAB-07-LP")
        self.line_up_real_feeder("NODE-GEN-B",
                                "NODE-PWR-HAB-03-CAB-07-FANCOIL")
        def current():
            clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
            return _power(
                {r.source_id: r for r in CanonicalShipState.objects.filter(
                    category="equipment")},
                list(CanonicalShipState.objects.filter(category="edge")),
                {r.source_id: r for r in CanonicalShipState.objects.filter(
                    category="isolator")}, clock.details["load_profile"],
                ledger=clock.details["electrical"])
        prior = current()
        self.assertIn("NODE-HAB-03-CAB-07-LP", prior["nodes"])
        self.assertIn("NODE-PWR-HAB-03-CAB-07-FANCOIL", prior["nodes"])
        set_isolator("ISO-HAB-03-CAB-07-LP", "open", operator=True)
        after = current()
        self.assertNotIn("NODE-HAB-03-CAB-07-LP", after["nodes"])
        self.assertIn("NODE-PWR-HAB-03-CAB-07-FANCOIL", after["nodes"])

    def test_common_operational_battery_serves_real_b_bus_and_expires(self):
        commission_g19_electrical(operator_approved=True)
        with self.assertRaises(PhysicsError):
            survey_g19_electrical_source(
                operator_approved=True, source="BAT-COMMON-OPS",
                capacity_kwh=8001, initial_kwh=10,
                max_charge_mw=.2, max_discharge_mw=.8)
        survey_g19_electrical_source(
            operator_approved=True, source="BAT-COMMON-OPS",
            capacity_kwh=8000, initial_kwh=10,
            max_charge_mw=.2, max_discharge_mw=.8)
        self.line_up_real_feeder(
            "PWR-MSB-B", "NODE-PWR-HAB-03-CAB-07-FANCOIL")
        set_isolator("ISO-BAT-COMMON-OPS", "closed", operator=True)
        self.crew_at("PWR-AFT")
        self.assertEqual(crew_physical_action(
            self.worker, "d" * 32, "power", "BAT-COMMON-OPS",
            "discharge")["status"], "succeeded")
        first = tick_continuous_physics(now_game_time=1010)
        self.assertAlmostEqual(first["available_mw"], .8)
        self.assertAlmostEqual(first["electrical"]["meter"][
                               "battery_discharge_kwh"], .8 * 10 / 3.6)
        clock = CanonicalShipState.objects.get(
            pk="meta:continuous-physics")
        self.assertTrue(clock.details["electrical"]["last"]["main_b"])
        self.assertFalse(clock.details["electrical"]["last"]["main_a"])
        # Only 10 kWh were measured. A prolonged demand cannot
        # mint energy, and advancing one time twice never charges twice.
        for i in range(2, 8):
            tick_continuous_physics(now_game_time=1000 + i * 10)
        stock = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details[
                "electrical"]["banks"]["BAT-COMMON-OPS"]
        self.assertLess(stock["charge_kwh"], 1e-8)
        self.assertAlmostEqual(
            stock["discharged_kwh"] + stock["charge_kwh"], 10)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1070)["advanced"])

    def test_protected_battery_does_not_create_hidden_msb_backfeed(self):
        from world.continuous_ship_physics import _power
        commission_g19_electrical(operator_approved=True)
        survey_g19_electrical_source(
            operator_approved=True, source="BAT-COMMON-PROT",
            capacity_kwh=12000, initial_kwh=1,
            max_charge_mw=.2, max_discharge_mw=.8)
        set_isolator("ISO-BAT-COMMON-PROT", "closed", operator=True)
        self.crew_at("PWR-AFT")
        crew_physical_action(
            self.worker, "e" * 32, "power", "BAT-COMMON-PROT",
            "discharge")
        electrical = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["electrical"]
        dispatch = _power(
            {r.source_id: r for r in
             CanonicalShipState.objects.filter(category="equipment")},
            list(CanonicalShipState.objects.filter(category="edge")),
            {r.source_id: r for r in
             CanonicalShipState.objects.filter(category="isolator")},
            "essential", ledger=electrical)
        self.assertIn("PWR-PROT", dispatch["nodes"])
        self.assertNotIn("PWR-MSB-A", dispatch["nodes"])
        self.assertNotIn("PWR-MSB-B", dispatch["nodes"])
        # No invented outgoing node/feeder is claimed for the isolated
        # protected bus; a connected distribution load is still necessary.
        self.assertFalse(dispatch["has_live_load"])

    def test_real_flywheel_bay_works_only_when_surveyed_suited_and_connected(self):
        commission_g19_electrical(operator_approved=True)
        with self.assertRaises(PhysicsError):
            survey_g19_electrical_source(
                operator_approved=True, source="F1-FW-01",
                capacity_kwh=3906.26, initial_kwh=1,
                max_charge_mw=.2, max_discharge_mw=.8)
        survey = survey_g19_electrical_source(
            operator_approved=True, source="F1-FW-01",
            capacity_kwh=3906.25, initial_kwh=10,
            max_charge_mw=.2, max_discharge_mw=.8)
        self.assertTrue(survey["rated"])
        self.crew_at("F1-BAY")
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "a" * 32, "power", "F1-FW-01", "discharge")
        self.assertTrue(survey_g19_electrical_worksite(
            operator_approved=True, room_id="F1-BAY")["changed"])
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "b" * 32, "power", "F1-FW-01", "discharge")
        self.worker.db.ox_suit_verified = True
        self.assertEqual(
            crew_physical_action(self.worker, "c" * 32, "power",
                                 "F1-FW-01", "discharge")["status"],
            "succeeded")
        # The bank's actual A infeed is fitted; no free energy flows until
        # the individual module feeder and a genuine downstream load are on.
        self.line_up_real_feeder("PWR-MSB-A", "NODE-HAB-03-FIRE-DETECT")
        set_isolator("ISO-PWR-F1-FW-01", "closed", operator=True)
        first = tick_continuous_physics(now_game_time=1010)
        self.assertAlmostEqual(first["available_mw"], .8)
        self.assertAlmostEqual(
            first["electrical"]["meter"]["flywheel_discharge_kwh"],
            .8 * 10 / 3.6)
        held = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["electrical"][
                "flywheels"]["F1-FW-01"]["charge_kwh"]
        self.assertLess(held, 10)
        set_isolator("ISO-F1-BUS-IN-1", "open", operator=True)
        off = tick_continuous_physics(now_game_time=1020)
        self.assertEqual(off["available_mw"], 0)
        self.assertAlmostEqual(CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["electrical"][
                "flywheels"]["F1-FW-01"]["charge_kwh"], held)

    def test_nonresetting_electrical_migration_preserves_real_old_meter(self):
        commission_g19_electrical(operator_approved=True)
        row = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        details = dict(row.details)
        original = dict(details["electrical"])
        original["version"] = 1
        del original["flywheels"]
        del original["meter"]["flywheel_charge_kwh"]
        del original["meter"]["flywheel_discharge_kwh"]
        original["meter"]["served_kwh"] = 47.5
        details["electrical"] = original
        row.details = details
        row.save(update_fields=["details"])
        migrated = commission_g19_electrical(operator_approved=True)
        self.assertTrue(migrated["migrated"])
        stored = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["electrical"]
        self.assertEqual(stored["version"], 2)
        self.assertEqual(stored["meter"]["served_kwh"], 47.5)
        self.assertFalse(commission_g19_electrical(
            operator_approved=True)["commissioned"])

    def test_generator_trips_do_not_destroy_real_refit_buses(self):
        commission_g19_electrical(operator_approved=True)
        node_ids = {r.source_id for r in
                    CanonicalShipState.objects.filter(category="node",
                        reference__network="power")}
        self.assertIn("NODE-PWR-HAB-03-CAB-07-FANCOIL", node_ids)
        self.assertIn("NODE-HAB-03-CAB-07-LP", node_ids)
        self.assertIn("PWR-MSB-A", node_ids)
        self.assertIn("PWR-MSB-B", node_ids)
        self.assertIn("PWR-PROT", node_ids)
        self.assertEqual(CanonicalShipState.objects.filter(
            category="edge", reference__network="power").count(), 450)


if __name__ == "__main__":
    import unittest
    unittest.main()
