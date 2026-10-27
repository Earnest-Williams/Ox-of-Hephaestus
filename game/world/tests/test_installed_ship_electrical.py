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
    commission_g19_water, survey_g19_water_material,
    survey_g19_electrical_source, survey_g19_electrical_worksite,
    configure_g19_electrical_fault, commission_commercial_port,
    commission_ftl_route, survey_g19_refuge_sorbent,
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

    def test_second_stage_equipment_feeders_installed_from_authentic_rooms(self):
        from world.ship_equipment_services import (
            SERVICE_LOADS, service_specs, service_ids)
        commission_g19_electrical(operator_approved=True)
        self.assertEqual(len(SERVICE_LOADS), 26)
        specs = service_specs()
        self.assertEqual(len(specs), 78)
        for key, authored in specs.items():
            row = CanonicalShipState.objects.get(pk=key)
            self.assertEqual(row.reference, authored["reference"])
            self.assertEqual(row.space_id, authored["space_id"])
        self.assertFalse(commission_g19_electrical(
            operator_approved=True)["commissioned"])
        self.assertEqual(CanonicalShipState.objects.filter(
            source_model="g19-operating-equipment/1").count(), len(specs))
        self.assertEqual(
            state("isolator", service_ids("SHOP-CNC-MILL")[2]).setting,
            "closed")

    def test_preexisting_equipment_faults_survive_service_control_enrolment(self):
        # A previously armed ship predating these service controller fields
        # may legitimately have no physics state for a cargo or tool unit.
        unit = state("equipment", "DR-02-CARGO-GAS")
        original = dict(unit.details)
        for key in ("physics_online", "physics_commanded_on",
                    "physics_startup_s"):
            original.pop(key, None)
        unit.details = original
        unit.save(update_fields=["details"])
        shop = state("equipment", "SHOP-GRINDER")
        damage = dict(shop.details)
        for key in ("physics_online", "physics_commanded_on",
                    "physics_startup_s"):
            damage.pop(key, None)
        shop.details = damage
        shop.condition = "failed"
        shop.save(update_fields=["details", "condition"])
        commission_g19_electrical(operator_approved=True)
        recovered = state("equipment", "DR-02-CARGO-GAS")
        self.assertTrue(recovered.details["physics_commanded_on"])
        self.assertTrue(recovered.details["physics_online"])
        self.assertEqual(recovered.details["physics_startup_s"], 0)
        failed = state("equipment", "SHOP-GRINDER")
        self.assertFalse(failed.details["physics_online"])
        self.assertFalse(failed.details["physics_commanded_on"])
        self.assertEqual(failed.condition, "failed")
        self.assertFalse(commission_g19_electrical(
            operator_approved=True)["commissioned"])
        self.assertEqual(state("equipment", "SHOP-GRINDER").condition, "failed")

    def test_machine_shop_power_loss_latches_attended_restart_and_history(self):
        from world.ship_equipment_services import service_ids
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-LP-SHOP-MECH")
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        self.crew_at("SHOP-MECH")
        machine = "SHOP-CNC-MILL"
        self.assertFalse(local_physics_readout(
            self.worker, machine)["operating"])
        start = crew_physical_action(
            self.worker, "1" * 32, "plant", machine, "on")
        self.assertEqual(start["status"], "succeeded")
        first = tick_continuous_physics(now_game_time=1010)
        self.assertEqual(first["active_workshop_machines"], 1)
        self.assertTrue(local_physics_readout(
            self.worker, machine)["operating"])
        breaker = service_ids(machine)[2]
        set_isolator(breaker, "open", operator=True)
        interrupted = tick_continuous_physics(now_game_time=1020)
        self.assertEqual(interrupted["active_workshop_machines"], 0)
        self.assertTrue(local_physics_readout(
            self.worker, machine)["restart_required"])
        set_isolator(breaker, "closed", operator=True)
        restored_power = tick_continuous_physics(now_game_time=1030)
        self.assertEqual(restored_power["active_workshop_machines"], 0)
        self.assertTrue(local_physics_readout(
            self.worker, machine)["feeder_conducting"])
        receipt = crew_physical_action(
            self.worker, "2" * 32, "plant", machine, "on")
        self.assertEqual(receipt["status"], "succeeded")
        restart = tick_continuous_physics(now_game_time=1040)
        self.assertEqual(restart["active_workshop_machines"], 1)
        machine_state = local_physics_readout(self.worker, machine)
        self.assertEqual(machine_state["runtime_s"], 20)
        self.assertEqual(machine_state["outage_s"], 20)
        self.assertFalse(machine_state["restart_required"])
        self.assertEqual(crew_physical_action(
            self.worker, "2" * 32, "plant", machine, "on"), receipt)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1040)["advanced"])
        self.assertFalse(commission_g19_electrical(
            operator_approved=True)["commissioned"])
        retained = local_physics_readout(self.worker, machine)
        self.assertEqual(retained["runtime_s"], 20)
        self.assertEqual(retained["outage_s"], 20)

    def test_cargo_and_cultivation_branches_stop_one_service_not_ship_power(self):
        from world.ship_equipment_services import SERVICE_LOADS, service_ids
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-08-GROW-LP")
        self.line_up_real_feeder("NODE-GEN-M", "NODE-DR-03-SVC-DB")
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        live = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(live["power_assured"])
        self.assertEqual(live["active_cultivation_bays"], 1)
        self.assertEqual(live["active_cargo_environment_pairs"], 1)
        grow_breaker = service_ids("GROW-3-NUTRIENT")[2]
        set_isolator(grow_breaker, "open", operator=True)
        crop_out = tick_continuous_physics(now_game_time=1020)
        self.assertEqual(crop_out["active_cultivation_bays"], 0)
        self.assertEqual(crop_out["active_cargo_environment_pairs"], 1)
        self.assertTrue(crop_out["power_assured"])
        self.crew_at(SERVICE_LOADS["GROW-3-CTRL"][0])
        self.assertTrue(local_physics_readout(
            self.worker, "GROW-3-CTRL")["operating"])
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "DR-03-CARGO-HX")
        set_isolator(grow_breaker, "closed", operator=True)
        cargo_breaker = service_ids("DR-03-CARGO-GAS")[2]
        set_isolator(cargo_breaker, "open", operator=True)
        cargo_out = tick_continuous_physics(now_game_time=1030)
        self.assertEqual(cargo_out["active_cultivation_bays"], 1)
        self.assertEqual(cargo_out["active_cargo_environment_pairs"], 0)
        self.assertTrue(cargo_out["power_assured"])
        set_isolator(cargo_breaker, "closed", operator=True)
        restart = tick_continuous_physics(now_game_time=1040)
        self.assertEqual(restart["active_cultivation_bays"], 1)
        self.assertEqual(restart["active_cargo_environment_pairs"], 1)

    def test_auxiliary_harnesses_installed_once_and_individually_fused(self):
        commission_g19_electrical(operator_approved=True)
        from world.ship_auxiliary_electrical import _specs, LOCAL_LOADS, MOTORS
        expected = _specs()
        for key, spec in expected.items():
            row = CanonicalShipState.objects.get(pk=key)
            self.assertEqual(row.reference, spec["reference"])
        self.assertEqual(len(expected), 3 * len(MOTORS) + 6 * len(LOCAL_LOADS) + 4)
        self.assertFalse(commission_g19_electrical(
            operator_approved=True)["commissioned"])
        self.assertEqual(CanonicalShipState.objects.filter(
            source_model="g19-electrical-aux/1").count(), len(expected))

    def test_refuge_backup_finite_island_and_replay(self):
        commission_g19_electrical(operator_approved=True)
        name = "HAB-04-REFUGE-BAT"
        survey_g19_electrical_source(
            operator_approved=True, source=name,
            capacity_kwh=1.0, initial_kwh=.06)
        self.crew_at("HAB-04-REFUGE")
        result = crew_physical_action(
            self.worker, "a" * 32, "power", name, "reserve")
        self.assertEqual(result["status"], "succeeded")
        before = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["local_backup"]
        self.assertEqual(before["meter"]["delivered_kwh"], 0)
        tick_continuous_physics(now_game_time=1010)
        after = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["local_backup"]
        self.assertAlmostEqual(after["meter"]["delivered_kwh"], 10 / 360)
        self.assertAlmostEqual(after["units"][name]["charge_kwh"], .06 - 10 / 360)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1010)["advanced"])
        replay = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["local_backup"]
        self.assertEqual(after, replay)
        self.assertEqual(crew_physical_action(
            self.worker, "a" * 32, "power", name, "reserve"), result)

    def test_refuge_scrubber_media_replacement_debits_actual_local_stock(self):
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        pack = "HAB-04-REFUGE-AIR"
        survey_g19_refuge_sorbent(
            operator_approved=True, pack_id=pack,
            remaining_capacity_kg=.008)
        self.crew_at("HAB-04-REFUGE")
        normal = "ISO-PWR-" + pack
        local = "ISO-G19-LOCAL-HAB-04-REFUGE-BAT"
        source = state("inventory", "INV-DC-CONSUMABLES")
        start_stock = source.quantity
        # An inaccessible/unsurveyed store cannot magically restore a
        # component, even if the technician stands beside the appliance.
        set_isolator(normal, "open", operator=True)
        set_isolator(local, "open", operator=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "a" * 32, "service", pack, "refill:4")
        with self.assertRaises(PhysicsError):
            survey_g19_water_material(
                operator_approved=True, source="INV-DC-CONSUMABLES",
                room_id="HAB-04-REFUGE", verified_kg=1600)
        survey_g19_water_material(
            operator_approved=True, source="INV-DC-CONSUMABLES",
            room_id="HAB-04-REFUGE", verified_kg=8)
        set_isolator(normal, "closed", operator=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "b" * 32, "service", pack, "refill:4")
        set_isolator(normal, "open", operator=True)
        set_isolator(local, "closed", operator=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "c" * 32, "service", pack, "refill:4")
        set_isolator(local, "open", operator=True)
        receipt = crew_physical_action(
            self.worker, "d" * 32, "service", pack, "refill:4")
        self.assertEqual(receipt["status"], "succeeded")
        updated = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details
        bank = updated["refuge_scrubbers"]["units"][pack]
        self.assertAlmostEqual(bank["capacity_kg"], 4.008)
        self.assertAlmostEqual(
            updated["refuge_media_service"]["meter"]["fresh_installed_kg"], 4.0)
        self.assertAlmostEqual(state(
            "inventory", "INV-DC-CONSUMABLES").quantity,
            start_stock - 0.004)
        self.assertAlmostEqual(
            updated["water"]["source_surveys"][
                "INV-DC-CONSUMABLES"]["HAB-04-REFUGE"], 4.0)
        local = local_physics_readout(self.worker, pack)
        self.assertTrue(local["media_surveyed"])
        self.assertAlmostEqual(local["media_available_kg"], 4.008)
        self.assertAlmostEqual(local["locally_surveyed_replacement_kg"], 4.0)
        self.assertTrue(local["normal_fuse_open"])
        self.assertTrue(local["local_dc_fuse_open"])
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "HAB-08-REFUGE-AIR")
        self.assertEqual(crew_physical_action(
            self.worker, "d" * 32, "service", pack, "refill:4"), receipt)
        self.assertAlmostEqual(
            state("inventory", "INV-DC-CONSUMABLES").quantity,
            start_stock - 0.004)
        commission_g19_electrical(operator_approved=True)
        recovered = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details
        self.assertAlmostEqual(
            recovered["refuge_scrubbers"]["units"][pack]["capacity_kg"],
            4.008)

    def test_refuge_battery_runs_finite_actual_co2_capture_with_no_replay(self):
        commission_g19_electrical(operator_approved=True)
        battery = "HAB-04-REFUGE-BAT"
        pack = "HAB-04-REFUGE-AIR"
        survey_g19_electrical_source(
            operator_approved=True, source=battery,
            capacity_kwh=1.0, initial_kwh=0.10)
        survey_g19_refuge_sorbent(
            operator_approved=True, pack_id=pack,
            remaining_capacity_kg=0.008)
        with self.assertRaises(PhysicsError):
            survey_g19_refuge_sorbent(
                operator_approved=True, pack_id=pack,
                remaining_capacity_kg=0.008)
        pressure = state("pressure", "PZ-HAB-04")
        original = dict(pressure.details)
        self.assertGreater(original["physics_oxygen_kg"], 1.0)
        pressure.details = dict(
            original,
            physics_oxygen_kg=original["physics_oxygen_kg"] - 1,
            physics_co2_kg=original["physics_co2_kg"] + 1)
        pressure.save(update_fields=["details"])
        co2_before = pressure.details["physics_co2_kg"]
        gas_before = pressure.quantity
        self.crew_at("HAB-04-REFUGE")
        receipt = crew_physical_action(
            self.worker, "e" * 32, "power", battery, "reserve")
        self.assertEqual(receipt["status"], "succeeded")
        powered = tick_continuous_physics(now_game_time=1010)
        self.assertAlmostEqual(powered["refuge_co2_captured_kg"], .004)
        air = state("pressure", "PZ-HAB-04")
        self.assertAlmostEqual(
            air.details["physics_co2_kg"], co2_before - .004, places=7)
        self.assertAlmostEqual(air.quantity, gas_before - .004, places=7)
        clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        self.assertAlmostEqual(clock.details["refuge_scrubbers"][
            "meter"]["captured_kg"], .004)
        self.assertEqual(
            clock.details["local_backup"]["last"][
                "active_local_consumers"][battery], pack)
        self.assertEqual(crew_physical_action(
            self.worker, "e" * 32, "power", battery, "reserve"), receipt)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1010)["advanced"])
        set_isolator(
            "ISO-G19-LOCAL-" + battery, "open", operator=True)
        blocked = tick_continuous_physics(now_game_time=1020)
        self.assertEqual(blocked["refuge_co2_captured_kg"], 0)
        self.assertAlmostEqual(
            state("pressure", "PZ-HAB-04").quantity, gas_before - .004,
            places=7)
        set_isolator(
            "ISO-G19-LOCAL-" + battery, "closed", operator=True)
        restored = tick_continuous_physics(now_game_time=1030)
        self.assertAlmostEqual(restored["refuge_co2_captured_kg"], .004)
        empty = tick_continuous_physics(now_game_time=1040)
        self.assertEqual(empty["refuge_co2_captured_kg"], 0)
        clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        self.assertAlmostEqual(clock.details["refuge_scrubbers"][
            "meter"]["captured_kg"], .008)
        self.assertEqual(clock.details["refuge_scrubbers"]["last"][
            "blocked"][pack], "sorbent_exhausted")
        self.assertAlmostEqual(
            state("pressure", "PZ-HAB-04").quantity, gas_before - .008,
            places=7)
        self.assertFalse(commission_g19_electrical(
            operator_approved=True)["commissioned"])
        again = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        self.assertEqual(again.details["refuge_scrubbers"][
            "meter"]["captured_kg"], clock.details["refuge_scrubbers"][
            "meter"]["captured_kg"])

    def test_unsurveyed_refuge_scrubber_cannot_supply_invisible_co2_sink(self):
        commission_g19_electrical(operator_approved=True)
        battery = "HAB-08-REFUGE-BAT"
        survey_g19_electrical_source(
            operator_approved=True, source=battery,
            capacity_kwh=1.0, initial_kwh=0.05)
        self.crew_at("HAB-08-REFUGE")
        crew_physical_action(
            self.worker, "f" * 32, "power", battery, "reserve")
        pressure = state("pressure", "PZ-HAB-08")
        gas = dict(pressure.details)
        self.assertGreater(gas["physics_oxygen_kg"], 1)
        pressure.details = dict(
            gas, physics_oxygen_kg=gas["physics_oxygen_kg"] - 1.0,
            physics_co2_kg=gas["physics_co2_kg"] + 1.0)
        pressure.save(update_fields=["details"])
        before = pressure.quantity
        before_co2 = pressure.details["physics_co2_kg"]
        tick = tick_continuous_physics(now_game_time=1010)
        self.assertEqual(tick["refuge_co2_captured_kg"], 0)
        actual = state("pressure", "PZ-HAB-08")
        self.assertAlmostEqual(actual.quantity, before)
        self.assertAlmostEqual(actual.details["physics_co2_kg"], before_co2)
        ledger = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["refuge_scrubbers"]
        self.assertEqual(ledger["units"], {})

    def test_motor_trip_is_local_not_a_shipwide_blackout(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-B", "NODE-LP-WATER-FWD")
        from world.ship_auxiliary_electrical import motor_power
        from world.continuous_ship_physics import _power
        def ready():
            clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
            equipment = {row.source_id: row for row in CanonicalShipState.objects.filter(
                category="equipment")}
            edges = {row.source_id: row for row in CanonicalShipState.objects.filter(
                category="edge")}
            switches = {row.source_id: row for row in CanonicalShipState.objects.filter(
                category="isolator")}
            bus = _power(equipment, list(edges.values()), switches,
                         clock.details["load_profile"],
                         ledger=clock.details["electrical"])
            return motor_power("FIRE-PUMP-FWD", nodes=bus["nodes"],
                               equipment=equipment, edges=edges,
                               switches=switches)
        self.assertTrue(ready())
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-FWD", "open", operator=True)
        self.assertFalse(ready())

    def test_protected_fire_pump_transfer_is_not_a_hidden_main_bus_tie(self):
        from world.continuous_ship_physics import _power
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder(
            "NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        # This actual protected MSB feed has a distinct breaker from
        # the HAB-03 detector's own protected panel.
        self.line_up_real_feeder("NODE-GEN-M", "PWR-PROT")
        def power_status():
            clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
            equipment = {row.source_id: row for row in CanonicalShipState.objects.filter(
                category="equipment")}
            edges = list(CanonicalShipState.objects.filter(category="edge"))
            switches = {row.source_id: row for row in CanonicalShipState.objects.filter(
                category="isolator")}
            return _power(equipment, edges, switches, clock.details["load_profile"],
                          ledger=clock.details["electrical"])
        before = power_status()
        self.assertIn("PWR-PROT", before["nodes"])
        self.assertNotIn("NODE-LP-WATER-FWD", before["nodes"])
        self.crew_at("WATER-FWD")
        self.assertEqual(crew_physical_action(
            self.worker, "b" * 32, "power", "FIRE-PUMP-FWD",
            "select:protected")["status"], "succeeded")
        local = local_physics_readout(self.worker, "FIRE-PUMP-FWD")
        self.assertEqual(local["source_selection"], "protected")
        self.assertTrue(local["feeder_conducting"])
        self.assertFalse(local["upstream_panel_energised"])
        self.assertEqual(state("edge", "EDGE-G19-MOTOR-FIRE-PUMP-FWD").setting,
                         "standby")
        self.assertEqual(state("edge", "EDGE-G19-PROT-FIRE-PUMP-FWD").setting,
                         "available")
        self.assertNotIn("PWR-MSB-B", power_status()["main_nodes"])
        # A local protected breaker opening makes only the alternate motor
        # inoperable; it does not alter source-generator output or MSB-A.
        set_isolator("ISO-G19-PROT-FIRE-PUMP-FWD", "open", operator=True)
        self.assertFalse(local_physics_readout(
            self.worker, "FIRE-PUMP-FWD")["feeder_conducting"])
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                self.worker, "c" * 32, "power", "FIRE-PUMP-FWD",
                "select:protected")
        set_isolator("ISO-G19-PROT-FIRE-PUMP-FWD", "closed", operator=True)
        self.assertTrue(local_physics_readout(
            self.worker, "FIRE-PUMP-FWD")["feeder_conducting"])
        self.assertEqual(crew_physical_action(
            self.worker, "d" * 32, "power", "FIRE-PUMP-FWD",
            "select:normal")["status"], "succeeded")
        self.assertEqual(local_physics_readout(
            self.worker, "FIRE-PUMP-FWD")["source_selection"], "normal")
        self.assertFalse(local_physics_readout(
            self.worker, "FIRE-PUMP-FWD")["feeder_conducting"])

    def test_local_charger_uses_generator_cartridges_and_never_replays(self):
        commission_g19_electrical(operator_approved=True)
        name = "IX-A-LOCAL-BAT"
        survey_g19_electrical_source(
            operator_approved=True, source=name,
            capacity_kwh=1., initial_kwh=0.)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-LP-HUB-FIXED-A")
        self.crew_at("HUB-FIXED-A")
        receipt = crew_physical_action(
            self.worker, "e" * 32, "power", name, "charge")
        self.assertEqual(receipt["status"], "succeeded")
        stock_before = state("inventory", "INV-GEN-CART").quantity * 1000.0
        tick_continuous_physics(now_game_time=1010)
        clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        unit = clock.details["local_backup"]["units"][name]
        charging = clock.details["local_backup"]["meter"]["charged_kwh"]
        self.assertGreater(charging, 0)
        self.assertAlmostEqual(charging, 2.0 * 10 / 3600.0)
        self.assertAlmostEqual(unit["charge_kwh"], charging)
        self.assertAlmostEqual(unit["charged_kwh"], charging)
        energy = clock.details["electrical"]["last"]
        self.assertAlmostEqual(energy["local_battery_recharged_kwh"], charging)
        self.assertGreater(energy["generator_cartridge_consumed_kg"], 0)
        self.assertAlmostEqual(
            stock_before - state("inventory", "INV-GEN-CART").quantity * 1000,
            energy["generator_cartridge_consumed_kg"])
        readout = local_physics_readout(self.worker, name)
        self.assertTrue(readout["charger_fuse_closed"])
        self.assertEqual(readout["mode"], "charge")
        self.assertEqual(crew_physical_action(
            self.worker, "e" * 32, "power", name, "charge"), receipt)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1010)["advanced"])
        after = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        self.assertEqual(after.details["local_backup"], clock.details["local_backup"])
        # The dedicated charger fuse removes recharge without disabling
        # the protected/local emergency discharge conductor.
        set_isolator("ISO-G19-CHARGE-" + name, "open", operator=True)
        tick_continuous_physics(now_game_time=1020)
        still = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        self.assertAlmostEqual(
            still.details["local_backup"]["units"][name]["charge_kwh"], charging)
        self.assertEqual(still.details["local_backup"]["last"][
            "grid_charge_requested_mw"], 0)

    def test_normal_fire_pump_actual_mist_stops_on_local_motor_fuse(self):
        from world.continuous_ship_physics import _reachable
        commission_g19_electrical(operator_approved=True)
        # The forward pump has a real B-side supply. A single 0.65 MW
        # generator can meet the essential operating schedule without
        # implying that the independent protected transfer is selected.
        self.line_up_real_feeder("NODE-GEN-B", "NODE-LP-WATER-FWD")
        clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        data = dict(clock.details)
        data["load_profile"] = "essential"
        clock.details = data
        clock.save(update_fields=["details"])
        # Exclude the other independently breakered pump throughout this
        # test so it cannot conceal a failed forward motor.
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-AFT", "open", operator=True)
        fire_edges = [
            edge for edge in CanonicalShipState.objects.filter(category="edge")
            if edge.reference.get("network") == "fire_main"
        ]
        self.assertTrue(fire_edges)
        for edge in fire_edges:
            for identifier in edge.reference["isolator_ids"]:
                kind = state("isolator", identifier).reference["kind"].lower()
                selected = ("open" if "valve" in kind or "damper" in kind
                            else "closed")
                set_isolator(identifier, selected, operator=True)
        switches = {x.source_id: x for x in
                    CanonicalShipState.objects.filter(category="isolator")}
        reachable = _reachable(
            fire_edges, switches, "fire_main", ["NODE-FIRE-PUMP-FWD"])
        mist_nodes = sorted(
            n for n in reachable
            if n.startswith("NODE-HAB-") and n.endswith("-FIRE-MIST"))
        self.assertTrue(mist_nodes, "No authored fire-main route to HAB mist")
        zone = "PZ-" + mist_nodes[0][5:-10]
        from world.continuous_ship_physics import configure_scenario_casualty
        configure_scenario_casualty(
            zone, fire_fuel_kg=5.0, fire_burn_kg_s=0.1, operator=True)
        cell = state("pressure", zone)
        cell.details = dict(cell.details, physics_mist_kg_s=0.5)
        cell.save(update_fields=["details"])
        before = state("inventory", "INV-WATER-NORMAL").quantity
        live = tick_continuous_physics(now_game_time=1010)
        after = state("inventory", "INV-WATER-NORMAL").quantity
        self.assertTrue(live["power_assured"])
        self.assertLess(after, before)
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-FWD", "open", operator=True)
        isolated = tick_continuous_physics(now_game_time=1020)
        self.assertTrue(isolated["power_assured"])
        self.assertAlmostEqual(
            state("inventory", "INV-WATER-NORMAL").quantity, after)
        set_isolator("ISO-G19-MOTOR-FIRE-PUMP-FWD", "closed", operator=True)
        restored = tick_continuous_physics(now_game_time=1030)
        self.assertTrue(restored["power_assured"])
        self.assertLess(
            state("inventory", "INV-WATER-NORMAL").quantity, after)

    def test_lt_motor_fuse_controls_real_propulsion_heat_sink_and_room_cooling(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-LP-ROTARY-UTIL-A")
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        # These are original physical coolant valves, not invented
        # thermal connections. Establish a conducting plant outlet.
        coolant_edges = [
            edge for edge in CanonicalShipState.objects.filter(category="edge")
            if edge.reference.get("network") == "lt_cooling"
        ]
        self.assertTrue(coolant_edges)
        for edge in coolant_edges:
            for isolator_id in edge.reference["isolator_ids"]:
                kind = state("isolator", isolator_id).reference["kind"].lower()
                position = ("open" if "valve" in kind or "damper" in kind
                            else "closed")
                set_isolator(isolator_id, position, operator=True)
        clock = CanonicalShipState.objects.get(pk="meta:continuous-physics")
        details = dict(clock.details)
        motion = dict(details["motion"])
        motion["drive_heat_kj"] = 100000.0
        details["motion"] = motion
        clock.details = details
        clock.save(update_fields=["details"])
        first = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(first["power_assured"])
        self.assertLess(first["drive_heat_kj"], 100000.0)
        self.assertGreater(first["cooling_kw"], 0.0)
        fuse = "ISO-G19-MOTOR-LT-PLANT"
        set_isolator(fuse, "open", operator=True)
        stopped = tick_continuous_physics(now_game_time=1020)
        self.assertTrue(stopped["power_assured"])
        self.assertEqual(stopped["cooling_kw"], 0.0)
        self.assertAlmostEqual(
            stopped["drive_heat_kj"], first["drive_heat_kj"], places=4)
        set_isolator(fuse, "closed", operator=True)
        restored = tick_continuous_physics(now_game_time=1030)
        self.assertGreater(restored["cooling_kw"], 0.0)
        self.assertLess(restored["drive_heat_kj"], stopped["drive_heat_kj"])

    def test_one_hab_air_handler_trip_stops_forced_flow_without_isolating_ducts(self):
        commission_g19_electrical(operator_approved=True)
        # B ECLSS and its local HAB-08 air handler share genuine A-board
        # supply but have two distinct fitted motor branch breakers.
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-08-ECLSS-B-LP")
        tick = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(tick["ventilation_powered"])
        self.assertTrue(tick["power_assured"])
        set_isolator("ISO-G19-MOTOR-HAB-08-AHU", "open", operator=True)
        stopped = tick_continuous_physics(now_game_time=1020)
        self.assertFalse(stopped["ventilation_powered"])
        self.assertTrue(stopped["power_assured"])
        # The physical atmosphere duct edge remains intact, allowing
        # passive pressure equalisation during an actual hull casualty.
        self.assertEqual(state("edge", "EDGE-ECLSS-B-AIR").setting,
                         "available")
        self.crew_at("HAB-08-SERVICE-GALLERY")
        status = local_physics_readout(self.worker, "HAB-08-AHU")
        self.assertFalse(status["feeder_conducting"])
        crew_physical_action(self.worker, "7" * 32, "switch",
                             "ISO-G19-MOTOR-HAB-08-AHU", "closed")
        resumed = tick_continuous_physics(now_game_time=1030)
        self.assertTrue(resumed["ventilation_powered"])

    def test_ftl_control_requires_real_b_feeder_and_aborts_on_trip(self):
        commission_g19_electrical(operator_approved=True)
        # The FTL station uses a B-side feed; the main A source and an
        # independent real consumer establish the selected ship load.
        self.line_up_real_feeder("NODE-GEN-B", "NODE-LP-FTL-SVC")
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        commissioned = commission_ftl_route(
            operator_approved=True, route_id="AUX01",
            destination="DISTANT", distance_ly=.5, cruise_c=5)
        self.assertEqual(commissioned["status"], "planned")
        officer = build_ship()["officer"]
        officer.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        fuse = "ISO-G19-MOTOR-FTL-TRANSLATION-FIELD"
        set_isolator(fuse, "open", operator=True)
        with self.assertRaises(PhysicsError):
            crew_physical_action(
                officer, "a" * 32, "ftl", "AUX01", "engage")
        set_isolator(fuse, "closed", operator=True)
        started = crew_physical_action(
            officer, "b" * 32, "ftl", "AUX01", "engage")
        self.assertEqual(started["status"], "succeeded")
        # A real circuit failure during the engaged leg aborts *without*
        # advancing position or creating fuel beyond the existing ledger.
        before = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["motion"]
        set_isolator(fuse, "open", operator=True)
        tick_continuous_physics(now_game_time=1010)
        after = CanonicalShipState.objects.get(
            pk="meta:continuous-physics").details["motion"]
        self.assertEqual(after["ftl_leg"]["status"], "aborted")
        self.assertEqual(after["ftl_leg"]["reason"], "field_failure")
        self.assertEqual(after["position_m"], before["position_m"])
        self.assertEqual(after["ftl_fuel_kg"], before["ftl_fuel_kg"])

    def test_workshop_rotor_redundant_drive_fuses_do_not_blackout_ship(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-WR-PWR-IF")
        # The rotary interface itself is not a consuming load. Confirm that
        # the generator also actually serves an intact branch before asserting
        # the whole selected ship schedule is assured.
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        self.crew_at("WR-ROTOR-MACHINERY")
        self.assertTrue(local_physics_readout(
            self.worker, "WR-DRIVE-A")["feeder_conducting"])
        self.assertTrue(local_physics_readout(
            self.worker, "WR-DRIVE-B")["feeder_conducting"])
        set_isolator("ISO-G19-MOTOR-WR-DRIVE-A", "open", operator=True)
        self.assertFalse(local_physics_readout(
            self.worker, "WR-DRIVE-A")["feeder_conducting"])
        self.assertTrue(local_physics_readout(
            self.worker, "WR-DRIVE-B")["feeder_conducting"])
        first = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(first["power_assured"])
        self.assertGreater(first["available_mw"], 0)
        set_isolator("ISO-G19-MOTOR-WR-DRIVE-B", "open", operator=True)
        self.assertFalse(local_physics_readout(
            self.worker, "WR-DRIVE-B")["feeder_conducting"])
        second = tick_continuous_physics(now_game_time=1020)
        self.assertTrue(second["power_assured"])

    def test_eclss_motor_is_independently_shed_without_disabling_main_bus(self):
        commission_g19_electrical(operator_approved=True)
        # ECLSS-A was physically refitted to HAB-06's B-fed panel,
        # while ECLSS-B uses HAB-08's A panel. Do not silently crossfeed.
        self.line_up_real_feeder(
            "NODE-GEN-B", "NODE-HAB-06-ECLSS-A-LP")
        self.line_up_real_feeder(
            "NODE-GEN-M", "NODE-HAB-08-ECLSS-B-LP")
        first = tick_continuous_physics(now_game_time=1010)
        self.assertTrue(first["ventilation_powered"])
        self.assertTrue(first["power_assured"])
        set_isolator("ISO-G19-MOTOR-ECLSS-A", "open", operator=True)
        second = tick_continuous_physics(now_game_time=1020)
        self.assertTrue(second["power_assured"])
        self.assertGreater(second["available_mw"], 0)
        # The opposite train may remain energised through its independent
        # protected route. Disconnect both motor branches before claiming a
        # whole-ship ventilation outage.
        set_isolator("ISO-G19-MOTOR-ECLSS-B", "open", operator=True)
        third = tick_continuous_physics(now_game_time=1030)
        self.assertFalse(third["ventilation_powered"])
        self.assertTrue(third["power_assured"])
        self.crew_at("HAB-06-ECLSS-A")
        local = local_physics_readout(self.worker, "ECLSS-A")
        self.assertFalse(local["feeder_conducting"])
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "ECLSS-B")

    def test_motor_overcurrent_trip_is_local_and_resets_only_after_clearance(self):
        commission_g19_electrical(operator_approved=True)
        name = "LT-PLANT"
        breaker_id = "ISO-G19-MOTOR-" + name
        self.line_up_real_feeder("NODE-GEN-M", "NODE-LP-ROTARY-UTIL-A")
        self.assertEqual(state("isolator", breaker_id).setting, "closed")
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id=breaker_id,
            rating_mw=.01, measured_mw=.05)
        tick_continuous_physics(now_game_time=1010)
        self.assertEqual(state("isolator", breaker_id).setting, "open")
        self.assertTrue(state("isolator", breaker_id).details[
            "physics_power_trip_latched"])
        self.crew_at("ROTARY-UTIL-A")
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.worker, "1" * 32, "power",
                                 breaker_id, "reset")
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id=breaker_id,
            rating_mw=.01, measured_mw=0)
        self.assertEqual(crew_physical_action(
            self.worker, "2" * 32, "power", breaker_id, "reset")[
            "status"], "succeeded")
        self.assertEqual(state("isolator", breaker_id).setting, "open")
        self.assertEqual(crew_physical_action(
            self.worker, "3" * 32, "switch", breaker_id, "closed")[
            "status"], "succeeded")
        self.assertEqual(state("isolator", breaker_id).setting, "closed")
        local = local_physics_readout(self.worker, name)
        self.assertTrue(local["feeder_conducting"])
        self.assertTrue(local["upstream_panel_energised"])

    def test_local_refuge_fuse_trip_stops_finite_backup(self):
        commission_g19_electrical(operator_approved=True)
        name = "HAB-04-REFUGE-BAT"
        breaker = "ISO-G19-LOCAL-" + name
        survey_g19_electrical_source(
            operator_approved=True, source=name,
            capacity_kwh=.2, initial_kwh=.1)
        self.crew_at("HAB-04-REFUGE")
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker, "HAB-08-REFUGE-BAT")
        crew_physical_action(self.worker, "4" * 32, "power", name, "reserve")
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id=breaker,
            rating_mw=.001, measured_mw=.01)
        tick_continuous_physics(now_game_time=1010)
        local = local_physics_readout(self.worker, name)
        self.assertFalse(local["fuse_closed"])
        self.assertFalse(local["last_tick_battery_active"])
        self.assertAlmostEqual(local["charge_kwh"], .1)
        configure_g19_electrical_fault(
            operator_approved=True, breaker_id=breaker,
            rating_mw=.001, measured_mw=0)
        crew_physical_action(self.worker, "5" * 32, "power", breaker, "reset")
        crew_physical_action(self.worker, "6" * 32, "switch", breaker, "closed")
        tick_continuous_physics(now_game_time=1020)
        local = local_physics_readout(self.worker, name)
        self.assertTrue(local["last_tick_battery_active"])
        self.assertLess(local["charge_kwh"], .1)

    def test_suited_bearing_battery_requires_real_survey(self):
        from world.continuous_ship_physics import survey_g19_electrical_worksite
        commission_g19_electrical(operator_approved=True)
        name = "BE-01-BAT"
        survey_g19_electrical_source(
            operator_approved=True, source=name,
            capacity_kwh=1.0, initial_kwh=.5)
        self.crew_at("BE-01-SVC")
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.worker, "7" * 32, "power", name, "reserve")
        survey_g19_electrical_worksite(
            operator_approved=True, room_id="BE-01-SVC")
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.worker, "8" * 32, "power", name, "reserve")
        self.worker.db.ox_suit_verified = True
        self.assertEqual(crew_physical_action(
            self.worker, "9" * 32, "power", name, "reserve")["status"],
            "succeeded")
        self.assertEqual(local_physics_readout(
            self.worker, name)["mode"], "reserve")

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

    def test_generator_draws_finite_authored_cartridge_stock_without_losing_ship_mass(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder(
            "NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        before_stock = state("inventory", "INV-GEN-CART").quantity * 1000.0
        tick = tick_continuous_physics(now_game_time=1010)
        e = tick["electrical"]
        used = e["last"]["generator_cartridge_consumed_kg"]
        self.assertGreater(used, 0)
        self.assertAlmostEqual(used, 1.35 * 10 / 3600 * 2.0, places=6)
        physical_remaining = state(
            "inventory", "INV-GEN-CART").quantity * 1000.0
        self.assertAlmostEqual(physical_remaining, before_stock - used)
        self.assertAlmostEqual(
            physical_remaining + e["spent_cartridge_housings_kg"],
            before_stock)
        ship_mass = tick["ship_current_mass_kg"]
        self.assertFalse(tick_continuous_physics(
            now_game_time=1010)["advanced"])
        again = tick_continuous_physics(now_game_time=1020)
        self.assertAlmostEqual(again["ship_current_mass_kg"], ship_mass)
        self.assertGreater(again["electrical"][
            "spent_cartridge_housings_kg"], e["spent_cartridge_housings_kg"])

    def test_fitted_battery_charging_consumes_real_generator_cartridges(self):
        commission_g19_electrical(operator_approved=True)
        self.line_up_real_feeder("NODE-GEN-M", "NODE-HAB-03-FIRE-DETECT")
        self.line_up_real_feeder("NODE-GEN-M", "PWR-PROT")
        set_isolator("ISO-BAT-COMMON-PROT", "closed", operator=True)
        survey_g19_electrical_source(
            operator_approved=True, source="BAT-COMMON-PROT",
            capacity_kwh=12000, initial_kwh=1000,
            max_charge_mw=.2, max_discharge_mw=.2)
        self.crew_at("PWR-AFT")
        work = crew_physical_action(
            self.worker, "f" * 32, "power", "BAT-COMMON-PROT", "charge")
        self.assertEqual(work["status"], "succeeded")
        original = state("inventory", "INV-GEN-CART").quantity * 1000.0
        tick = tick_continuous_physics(now_game_time=1010)
        meter = tick["electrical"]["meter"]
        self.assertAlmostEqual(meter["battery_charge_kwh"], .2 * 10 / 3.6)
        self.assertAlmostEqual(
            meter["generation_kwh"], meter["served_kwh"] + meter["battery_charge_kwh"])
        consumed = tick["electrical"]["last"]["generator_cartridge_consumed_kg"]
        self.assertAlmostEqual(consumed, meter["generation_kwh"] / 1000.0 * 2.0)
        self.assertAlmostEqual(
            original - state("inventory", "INV-GEN-CART").quantity * 1000.0,
            consumed, places=6)
        self.assertAlmostEqual(
            tick["electrical"]["spent_cartridge_housings_kg"], consumed)
        self.assertFalse(tick_continuous_physics(now_game_time=1010)["advanced"])

    def test_actual_mooring_shore_power_import_interlocks_and_safe_undock(self):
        commission_g19_electrical(operator_approved=True)
        survey_g19_electrical_source(
            operator_approved=True, source="SHORE-PWR", rated_mw=2.0)
        self.line_up_real_feeder(
            "PWR-MSB-B", "NODE-PWR-HAB-03-CAB-07-FANCOIL")
        set_isolator("ISO-SHORE-PWR", "closed", operator=True)
        commission_commercial_port(
            operator_approved=True, operation="dock",
            portal_id="DR-01-P1", berth_id="POWER-TEST-BERTH")
        self.crew_at("DOCK-FWD")
        connected = crew_physical_action(
            self.worker, "9" * 31 + "a", "power", "SHORE-PWR", "connect")
        self.assertEqual(connected["status"], "succeeded")
        self.assertEqual(crew_physical_action(
            self.worker, "9" * 31 + "a",
            "power", "SHORE-PWR", "connect"), connected)
        before_fuel = state("inventory", "INV-GEN-CART").quantity
        tick = tick_continuous_physics(now_game_time=1010)
        meter = tick["electrical"]["meter"]
        self.assertAlmostEqual(meter["shore_import_kwh"], 1.35 * 10 / 3.6)
        self.assertAlmostEqual(meter["generation_kwh"], 0)
        self.assertEqual(state("inventory", "INV-GEN-CART").quantity, before_fuel)
        with self.assertRaises(PhysicsError):
            commission_commercial_port(
                operator_approved=True, operation="undock",
                portal_id="DR-01-P1", berth_id="POWER-TEST-BERTH")
        survey_g19_electrical_worksite(
            operator_approved=True, room_id="GEN-M-ROOM")
        self.worker.db.ox_suit_verified = True
        self.crew_at("GEN-M-ROOM")
        with self.assertRaisesRegex(PhysicsError, "shore power"):
            crew_physical_action(self.worker, "9" * 31 + "b",
                                 "switch", "ISO-GEN-M", "closed")
        self.crew_at("DOCK-FWD")
        disconnected = crew_physical_action(
            self.worker, "9" * 31 + "c", "power", "SHORE-PWR", "disconnect")
        self.assertEqual(disconnected["status"], "succeeded")
        released = commission_commercial_port(
            operator_approved=True, operation="undock",
            portal_id="DR-01-P1", berth_id="POWER-TEST-BERTH")
        self.assertEqual(released["docked"], [])

    def test_generator_cartridge_magazine_tamper_fails_before_any_energy_tick(self):
        commission_g19_electrical(operator_approved=True)
        stock = state("inventory", "INV-GEN-CART")
        stock.quantity += 1
        stock.save(update_fields=["quantity"])
        with self.assertRaises(PhysicsError):
            tick_continuous_physics(now_game_time=1010)
        self.assertEqual(
            CanonicalShipState.objects.get(
                pk="meta:continuous-physics").details["last_game_time"], 1000)

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
