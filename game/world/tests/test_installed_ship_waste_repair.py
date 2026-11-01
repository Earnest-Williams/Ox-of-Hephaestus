"""Full installed-world G19 port-side waste shipment and equipment restoration."""
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    arm_continuous_physics, commission_g19_water,
    commission_g19_repairs, survey_g19_repair_site,
    commission_commercial_port,
    commission_waste_acceptance, survey_waste_freight_route,
    survey_g19_water_material, crew_physical_action, _clock,
    tick_continuous_physics, PhysicsError, local_physics_readout,
)
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.ship_world import ensure_canonical_ship, find_ship_space
from world.models import WorkReceipt, CanonicalShipEvent, CanonicalShipState
from world.ship_crew_access import CrewTransitError


class InstalledWasteAndRepairTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000.0)
        self.assertTrue(commission_g19_water(operator_approved=True)["commissioned"])
        self.assertTrue(commission_g19_repairs(operator_approved=True)["commissioned"])
        self.assertFalse(commission_g19_repairs(operator_approved=True)["commissioned"])
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.crew = build_ship()
        self.tech, self.cargo = self.crew["watch"], self.crew["cargo"]

    def _action(self, actor, token, action, target, value):
        return crew_physical_action(
            actor, token * 32, action, target, value)

    def _tick(self, seconds, start=1000.0):
        now = start
        for _ in range(int(seconds / 60)):
            now += 60
            tick_continuous_physics(now_game_time=now)
        return now

    def _toolkit(self):
        self.tech.move_to(find_ship_space("TOOL-CRIB"), quiet=True)
        receipt = self._action(self.tech, "0", "repair", "TOOL-CRIB",
                               "pickup_toolkit")
        self.assertEqual(receipt["status"], "succeeded")
        return receipt

    def _line_up_original_power_path(self, source, load):
        """Close the installed conductive path; never invent a live consumer.

        Original generator B must supply an authentic room feeder to count
        as positive delivered power, not merely appear as an online unit.
        """
        from collections import defaultdict, deque

        graph = defaultdict(list)
        for edge in CanonicalShipState.objects.filter(
                category="edge", reference__network="power"):
            if edge.setting != "available" or edge.condition in {
                    "faulted", "failed", "severed", "destroyed", "jammed"}:
                continue
            spec = edge.reference
            graph[spec["from_node"]].append((spec["to_node"], edge))
            if spec["kind"] in {"bridge_feeder", "cross_tie"}:
                graph[spec["to_node"]].append((spec["from_node"], edge))
        visited = {source}
        previous = {}
        queue = deque([source])
        while queue and load not in visited:
            for following, conductor in graph[queue.popleft()]:
                if following not in visited:
                    visited.add(following)
                    previous[following] = conductor
                    queue.append(following)
        self.assertIn(load, visited, "No original conductive generator-to-load route")
        node = load
        while node != source:
            edge = previous[node]
            for isolator_id in edge.reference["isolator_ids"]:
                if state("isolator", isolator_id).setting != "closed":
                    set_isolator(isolator_id, "closed", operator=True)
            spec = edge.reference
            node = (spec["from_node"] if node == spec["to_node"]
                    else spec["to_node"])

    def _industrial(self):
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="SPARES-CENTRAL", verified_kg=4)
        self.tech.move_to(find_ship_space("SPARES-CENTRAL"), quiet=True)
        self._action(self.tech, "a", "waste", "IND-SCRAP-HOLD-A",
                     "deposit:INV-SPARES:2")
        self.assertAlmostEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002, places=6)

    def test_real_berth_cassette_haul_offload_return_and_departure_mass(self):
        self._industrial()
        self.assertEqual(_clock().details["water"]["cassettes"]["industrial"]["A"], 2)
        commission_waste_acceptance(
            operator_approved=True, acceptance_id="BERTH-IND-A",
            portal_id="DR-01-P1", berth_id="YARD-IND",
            category="industrial", limit_kg=5000)
        route = survey_waste_freight_route(
            operator_approved=True, receiver_id="IND-SCRAP-HOLD-A",
            portal_id="DR-01-P1")
        self.assertGreater(route["segments"], 2)
        first = self._action(
            self.tech, "b", "waste", "IND-SCRAP-HOLD-A",
            "stage:BERTH-IND-A")
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(self._action(
            self.tech, "b", "waste", "IND-SCRAP-HOLD-A",
            "stage:BERTH-IND-A"), first)
        self.tech.move_to(find_ship_space("DR-01-FREIGHT-LOCK"), quiet=True)
        with self.assertRaises(PhysicsError):
            self._action(self.tech, "c", "wasteport", "IND-SCRAP-HOLD-A", "haul")
        self._action(self.tech, "d", "rotor", "DR-01", "freight_extend")
        self._action(self.tech, "e", "wasteport", "IND-SCRAP-HOLD-A", "capture_open")
        self._action(self.tech, "c", "wasteport", "IND-SCRAP-HOLD-A", "haul")
        mass_before = _clock().details["motion"]["dry_mass_kg"]
        self._tick(240)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["jobs"][
                "IND-SCRAP-HOLD-A"]["phase"], "port_ready")
        self.assertEqual(
            _clock().details["water"]["cassettes"]["industrial"]["A"], 0)
        self.assertAlmostEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002, places=6)
        self.assertEqual(_clock().details["motion"]["dry_mass_kg"], mass_before)
        self._action(self.tech, "f", "wasteport", "IND-SCRAP-HOLD-A", "capture_close")
        self._action(self.tech, "0", "rotor", "DR-01", "freight_retract")
        commission_commercial_port(
            operator_approved=True, operation="dock",
            portal_id="DR-01-P1", berth_id="YARD-IND")
        with self.assertRaises(PhysicsError):
            commission_commercial_port(
                operator_approved=True, operation="undock",
                portal_id="DR-01-P1", berth_id="YARD-IND")
        self.cargo.move_to(find_ship_space("CARGO-CTRL-FWD"), quiet=True)
        self._action(self.cargo, "1", "wasteport", "IND-SCRAP-HOLD-A", "offload")
        tick_continuous_physics(now_game_time=1300)
        self.assertEqual(
            state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, .002)
        tick_continuous_physics(now_game_time=1310)
        self.assertEqual(state("inventory", "INV-INDUSTRIAL-SCRAP").quantity, 0)
        self.assertAlmostEqual(
            _clock().details["motion"]["dry_mass_kg"], mass_before - 2)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["delivered_kg"]["industrial"], 2)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["jobs"][
                "IND-SCRAP-HOLD-A"]["phase"], "return_ready")
        commission_commercial_port(
            operator_approved=True, operation="undock",
            portal_id="DR-01-P1", berth_id="YARD-IND")
        self._action(self.tech, "2", "rotor", "DR-01", "freight_extend")
        self._action(self.tech, "3", "wasteport", "IND-SCRAP-HOLD-A", "capture_open")
        self._action(self.tech, "4", "wasteport", "IND-SCRAP-HOLD-A", "return")
        self._tick(240, start=1310)
        self.assertFalse(_clock().details["water"]["waste_offload"]["jobs"])
        self.assertEqual(_clock().details["water"]["cassettes"]["industrial"]["A"], 0)
        self.assertEqual(
            _clock().details["water"]["waste_offload"]["acceptances"][
                "BERTH-IND-A"]["accepted_kg"], 2)
        self.assertFalse(WorkReceipt.objects.filter(pk="e" * 32).count() > 1)

    def test_cross_class_acceptance_and_nonlocal_work_are_denied(self):
        self._industrial()
        commission_waste_acceptance(
            operator_approved=True, acceptance_id="BERTH-HAZ",
            portal_id="DR-02-P1", berth_id="YARD-HAZ",
            category="hazardous", limit_kg=50)
        survey_waste_freight_route(
            operator_approved=True, receiver_id="IND-SCRAP-HOLD-A",
            portal_id="DR-02-P1")
        with self.assertRaises(PhysicsError):
            self._action(self.tech, "5", "waste", "IND-SCRAP-HOLD-A",
                         "stage:BERTH-HAZ")
        self.assertFalse(WorkReceipt.objects.filter(pk="5" * 32).exists())
        commission_waste_acceptance(
            operator_approved=True, acceptance_id="BERTH-IND",
            portal_id="DR-02-P1", berth_id="YARD-IND",
            category="industrial", limit_kg=200)
        self._action(self.tech, "7", "waste", "IND-SCRAP-HOLD-A",
                     "stage:BERTH-IND")
        with self.assertRaises(PermissionError):
            self._action(self.cargo, "6", "wasteport",
                         "IND-SCRAP-HOLD-A", "offload")

    def test_crew_carried_spares_repair_failed_water_processor_after_real_work(self):
        self._toolkit()
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._action(self.tech, "a", "water", "WATER-PROC-A", "off")
        set_component_condition("equipment", "WATER-PROC-A",
                                "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=4)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        original = state("inventory", "INV-SPARES").quantity
        issued = self._action(self.tech, "b", "repair", "INV-SPARES", "pickup:3")
        self.assertEqual(issued["status"], "succeeded")
        self.assertEqual(self._action(
            self.tech, "b", "repair", "INV-SPARES", "pickup:3"), issued)
        self.assertAlmostEqual(state("inventory", "INV-SPARES").quantity,
                               original - .003, places=7)
        with self.assertRaises(PermissionError):
            self._action(self.tech, "c", "repair",
                         "equipment:WATER-PROC-A", "start")
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._action(self.tech, "d", "repair",
                     "equipment:WATER-PROC-A", "start")
        self.assertEqual(state("equipment", "WATER-PROC-A").condition, "failed")
        tick_continuous_physics(now_game_time=1060)
        remaining = _clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"]
        self.assertEqual(remaining, 540)
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        tick_continuous_physics(now_game_time=1120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"], 540)
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._tick(540, start=1120)
        self.assertEqual(state("equipment", "WATER-PROC-A").condition, "serviceable")
        self.assertFalse(_clock().details["repairs"]["jobs"])
        self.assertEqual(_clock().details["repairs"]["completed"], 1)
        self.assertEqual(_clock().details["repairs"]["installed_kg"], 3.0)
        self.assertEqual(_clock().details["water"]["water_train"]["A"], "off")
        self.assertEqual(state("equipment", "WATER-PROC-A").details[
            "repair_cumulative_kg"], 3)
        # A reusable tool roll returns to the real crib after maintenance,
        # rather than being regenerated or remaining remotely available.
        self.tech.move_to(find_ship_space("TOOL-CRIB"), quiet=True)
        self._action(self.tech, "e", "repair", "TOOL-CRIB", "return_toolkit")
        self.assertEqual(_clock().details["repairs"]["toolkits_at_crib"], 6)
        self.assertEqual(_clock().details["repairs"]["toolkit_carriers"], [])


    def test_damaged_access_door_is_repaired_at_actual_safe_endpoint(self):
        self._toolkit()
        door = state("access", "ACC-STORE-FLUID-AFT")
        self.assertIsNone(door.space_id)
        set_component_condition(
            "access", "ACC-STORE-FLUID-AFT", "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=3)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self._action(self.tech, "9", "repair", "INV-SPARES", "pickup:3")
        self.tech.move_to(find_ship_space("CMD-PRIMARY"), quiet=True)
        with self.assertRaises(PermissionError):
            self._action(self.tech, "8", "repair",
                         "access:ACC-STORE-FLUID-AFT", "start")
        self.tech.move_to(find_ship_space("TRUNK-A-AFT"), quiet=True)
        self._action(self.tech, "7", "repair",
                     "access:ACC-STORE-FLUID-AFT", "start")
        self._tick(600)
        repaired = state("access", "ACC-STORE-FLUID-AFT")
        self.assertEqual(repaired.condition, "serviceable")
        self.assertNotEqual(repaired.setting, "open")
        self.assertEqual(_clock().details["repairs"]["completed"], 1)

    def test_incapacitated_worker_cannot_progress_or_issue_repair_work(self):
        self._toolkit()
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        self._action(self.tech, "a", "water", "WATER-PROC-A", "off")
        set_component_condition("equipment", "WATER-PROC-A",
                                "failed", operator=True)
        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=3)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        self._action(self.tech, "b", "repair", "INV-SPARES", "pickup:3")
        self.tech.move_to(find_ship_space("HAB-06-ECLSS-A"), quiet=True)
        started = self._action(self.tech, "c", "repair",
                               "equipment:WATER-PROC-A", "start")
        health = CanonicalShipState.objects.create(
            key="crew_health:" + str(self.tech.dbref),
            category="crew_health", source_id=str(self.tech.dbref),
            source_model="ox.g19.crew-health", condition="incapacitated")
        with self.assertRaises(CrewTransitError):
            self._action(self.tech, "d", "repair",
                         "equipment:WATER-PROC-A", "join")
        with self.assertRaises(CrewTransitError):
            self._action(self.tech, "e", "wasteport",
                         "IND-SCRAP-HOLD-A", "pause")
        self.assertEqual(self._action(self.tech, "c", "repair",
                                      "equipment:WATER-PROC-A", "start"), started)
        tick_continuous_physics(now_game_time=1060)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"], 600)
        health.condition = "serviceable"
        health.save(update_fields=["condition"])
        tick_continuous_physics(now_game_time=1120)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:WATER-PROC-A"]["remaining_s"], 540)

    def test_failed_generator_needs_isolation_and_never_restarts_after_repair(self):
        """Generator B repair uses the ORIGINAL rated hatch and issued EVA suit.

        A legacy personnel flag or a repair-site survey is not permission to
        enter the as-fitted unclassified machinery room. The actual generator
        must be tripped, the gas positively surveyed, and the suited worker
        must acquire and retain a personal generator-bay permit throughout
        finite-parts work. Repair must never silently energize the source.
        """
        from world.continuous_ship_physics import (
            commission_g19_electrical, commission_g19_eva,
            commission_g19_crew_physiology, commission_g19_generator_bays,
            survey_g19_generator_room,
        )
        from world.ship_generator_bay_service import ROOMS
        from world.ship_world import find_world_entity
        from world.ship_crew_access import traverse_canonical_exit

        self._toolkit()
        self.tech.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.tech.dbref])
        commission_g19_generator_bays(operator_approved=True)

        serial = 43000
        def ident():
            nonlocal serial
            serial += 1
            return f"{serial:032x}"

        def act(kind, target, value, request_id=None):
            return crew_physical_action(
                self.tech, request_id or ident(), kind, target, value)

        def transit(link, direction):
            exit_obj = find_world_entity(f"access:{link}:{direction}")
            self.assertIsNotNone(exit_obj)
            result = traverse_canonical_exit(
                self.tech, exit_obj, exit_obj.destination, request_id=ident())
            self.assertEqual(result["status"], "succeeded")
            return result

        room, hatch, trunk = "GEN-B-ROOM", "ACC-GEN-B-ROOM", "TRUNK-B-AFT"
        self.assertEqual(
            act("generator_bay", room, "trip")["status"], "succeeded")
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "open")
        self.assertFalse(state("equipment", "GEN-B").details["physics_online"])
        set_component_condition("equipment", "GEN-B", "failed", operator=True)
        self.assertEqual(
            survey_g19_generator_room(
                operator_approved=True, room_id=room,
                volume_m3=ROOMS[room][5] * .75,
                pressure_pa=101000, temperature_k=293.15,
                oxygen_mass_fraction=.232, co2_mass_fraction=.0004,
                smoke_mass_fraction=0, skin_temperature_k=299)["room"],
            room)
        # The worksite attestation describes the existing machine and
        # cannot create a suit, breathing gas or a generator-room permit.
        self.assertFalse(survey_g19_repair_site(
            operator_approved=True, room_id=room,
            work_class="suited_service")["changed"])

        survey_g19_water_material(
            operator_approved=True, source="INV-SPARES",
            room_id="STORE-CRIT-SPARES", verified_kg=4)
        self.tech.move_to(find_ship_space("STORE-CRIT-SPARES"), quiet=True)
        original_stock = state("inventory", "INV-SPARES").quantity
        self.assertEqual(act(
            "repair", "INV-SPARES", "pickup:3")["status"], "succeeded")
        self.assertAlmostEqual(
            state("inventory", "INV-SPARES").quantity, original_stock - .003,
            places=7)

        self.tech.move_to(find_ship_space(trunk), quiet=True)
        self.tech.db.ox_suit_verified = True
        rejected = ident()
        with self.assertRaises((PhysicsError, PermissionError)):
            act("repair", "equipment:GEN-B", "start", request_id=rejected)
        self.assertFalse(WorkReceipt.objects.filter(pk=rejected).exists())
        self.tech.db.ox_suit_verified = False
        with self.assertRaises(PhysicsError):
            act("generator_bay", room, "secure")

        # Check out one of the four real suits, carrying finite issued
        # oxygen through the original aft EVA pressure boundary.
        self.tech.move_to(find_ship_space("ENG-LOCKER"), quiet=True)
        self.assertEqual(act(
            "eva", "INV-DC-CONSUMABLES", "stage:0.75")["status"],
            "succeeded")
        self.tech.move_to(find_ship_space("TRUNK-B-AFT"), quiet=True)
        self.assertEqual(
            act("eva", "EVA-AFT", "inner_open")["status"], "succeeded")
        transit("ACC-EVA-AFT", "forward")
        self.assertEqual(
            act("eva", "EVA-AFT", "inner_close")["status"], "succeeded")
        self.assertEqual(
            act("eva", "EVA-AFT", "checkout")["status"], "succeeded")
        self.assertEqual(
            act("eva", "EVA-AFT", "inner_open")["status"], "succeeded")
        transit("ACC-EVA-AFT", "reverse")
        self.assertEqual(
            act("eva", "EVA-AFT", "inner_close")["status"], "succeeded")

        self.assertEqual(
            act("generator_bay", room, "secure")["status"], "succeeded")
        self.assertEqual(
            act("hatch", hatch, "open")["status"], "succeeded")
        transit(hatch, "forward")
        self.assertEqual(
            act("hatch", hatch, "closed")["status"], "succeeded")
        self.assertEqual(self.tech.location.db.ox_space_id, room)
        self.assertEqual(
            act("generator_bay", room, "inspect")["status"], "succeeded")

        # Even with the old boolean explicitly false, the actual issued
        # suit and personal rated-room permit permit repair.
        self.assertFalse(bool(self.tech.db.ox_suit_verified))
        repair_id = ident()
        receipt = act("repair", "equipment:GEN-B", "start",
                      request_id=repair_id)
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(
            act("repair", "equipment:GEN-B", "start",
                request_id=repair_id), receipt)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:GEN-B"]["remaining_s"], 600)

        tick_continuous_physics(now_game_time=1060)
        self.assertEqual(_clock().details["repairs"]["jobs"][
            "equipment:GEN-B"]["remaining_s"], 540)
        self._tick(540, start=1060)
        self.assertEqual(state("equipment", "GEN-B").condition, "serviceable")
        self.assertFalse(state("equipment", "GEN-B").details["physics_online"])
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "open")
        self.assertFalse(
            state("equipment", "GEN-B").details["physics_commanded_on"])
        self.assertAlmostEqual(
            _clock().details["repairs"]["installed_kg"], 3.0)
        self.assertFalse(_clock().details["repairs"]["jobs"])
        self.assertEqual(
            _clock().details["generator_bays"]["rooms"][room]["entries"], 1)
        self.assertEqual(WorkReceipt.objects.filter(pk=repair_id).count(), 1)

        # Returning through the real hatch and releasing the exclusive
        # maintenance permit never silently rearms or reconnects GEN-B.
        self.assertEqual(
            act("hatch", hatch, "open")["status"], "succeeded")
        transit(hatch, "reverse")
        self.assertEqual(
            act("hatch", hatch, "closed")["status"], "succeeded")
        self.assertEqual(
            act("generator_bay", room, "release")["status"], "succeeded")
        self.assertIsNone(_clock().details[
            "generator_bays"]["rooms"][room]["permit"])
        self.assertFalse(state("equipment", "GEN-B").details["physics_online"])
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "open")

        # Repair proves only serviceability, not generation. An operator
        # now has to rearm GEN-B after the worker has left and released
        # the rated site. Isolate other sources so B cannot borrow proof.
        self.tech.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        set_isolator("ISO-GEN-M", "open", operator=True)
        set_isolator("ISO-GEN-A", "open", operator=True)
        before_stock_kg = state("inventory", "INV-GEN-CART").quantity * 1000.0
        before_meter = _clock().details["electrical"]["meter"]["generation_kwh"]
        rearm_id = ident()
        rearmed = act("generator_bay", room, "rearm", request_id=rearm_id)
        self.assertEqual(rearmed["status"], "succeeded")
        self.assertEqual(
            act("generator_bay", room, "rearm", request_id=rearm_id), rearmed)
        self.assertEqual(WorkReceipt.objects.filter(pk=rearm_id).count(), 1)
        self.assertFalse(state("equipment", "GEN-B").details["physics_online"])
        self.assertEqual(state("equipment", "GEN-B").details["physics_startup_s"], 30)
        self.assertEqual(state("isolator", "ISO-GEN-B").setting, "closed")
        self._line_up_original_power_path(
            "NODE-GEN-B", "NODE-HAB-06-ECLSS-A-LP")

        # An ON request is not a watt. The original 30-second startup
        # is physically advanced by the same authoritative ship clock.
        for now in (1610, 1620):
            dark = tick_continuous_physics(now_game_time=now)
            self.assertEqual(dark["electrical"]["last"]["sources"], [])
            self.assertEqual(
                dark["electrical"]["last"]["generator_delivered_mw"], 0)
            self.assertAlmostEqual(
                state("inventory", "INV-GEN-CART").quantity * 1000.0,
                before_stock_kg, places=6)
        live = tick_continuous_physics(now_game_time=1630)
        report = live["electrical"]
        self.assertEqual(report["last"]["sources"], ["GEN-B"])
        self.assertTrue(state("equipment", "GEN-B").details["physics_online"])
        self.assertEqual(state("equipment", "GEN-B").details["physics_startup_s"], 0)
        self.assertTrue(report["last"]["main_b"])
        self.assertTrue(report["last"]["live_consumer_circuit"])
        self.assertGreater(report["last"]["generator_delivered_mw"], 0)
        delta_kwh = report["meter"]["generation_kwh"] - before_meter
        self.assertGreater(delta_kwh, 0)
        self.assertGreater(report["meter"]["served_kwh"], 0)
        used_kg = before_stock_kg - state(
            "inventory", "INV-GEN-CART").quantity * 1000.0
        self.assertGreater(used_kg, 0)
        self.assertAlmostEqual(used_kg, delta_kwh * .002, delta=1e-5)
        self.assertAlmostEqual(
            state("inventory", "INV-GEN-CART").quantity * 1000.0
            + _clock().details["generator_spent_cartridge_kg"],
            _clock().details["generator_cartridge_baseline_kg"],
            delta=1e-4)

        # A subsequent real emergency trip removes B's contribution
        # without recreating consumed fuel or replaying a signed request.
        tripped = act("generator_bay", room, "trip")
        self.assertEqual(tripped["status"], "succeeded")
        stopped = tick_continuous_physics(now_game_time=1640)
        self.assertEqual(stopped["electrical"]["last"]["sources"], [])
        self.assertEqual(
            stopped["electrical"]["last"]["generator_delivered_mw"], 0)
        self.assertEqual(
            stopped["electrical"]["last"]["generator_cartridge_consumed_kg"], 0)
        final_stock = state("inventory", "INV-GEN-CART").quantity
        final_clock = _clock().details["last_game_time"]
        self.assertFalse(tick_continuous_physics(
            now_game_time=1640)["advanced"])
        self.assertEqual(state("inventory", "INV-GEN-CART").quantity,
                         final_stock)
        self.assertEqual(_clock().details["last_game_time"], final_clock)


if __name__ == "__main__":
    import unittest
    unittest.main()
