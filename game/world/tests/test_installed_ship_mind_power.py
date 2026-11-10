"""Installed G19 lead-mind power network on persistent Evennia ship records.

Exercises real original generator/bus/feeder contacts and the same bounded
ten-second physics clock. No simulated voyage or independent fake grid.
"""
from __future__ import annotations

from collections import defaultdict, deque

from django.db import transaction
from django.test import tag
from world.continuous_ship_physics import (
    PhysicsError,
    _clock,
    _load_cell,
    _topology,
    arm_continuous_physics,
    commission_g19_electrical,
    commission_g19_gateway_power,
    commission_g19_mind_heat_connections,
    commission_g19_mind_power,
    commission_g19_mind_support,
    survey_g19_data_path,
    survey_g19_gateway_power,
    survey_g19_heat_rejector,
    survey_g19_mind_cooling,
    survey_g19_mind_reserve,
    tick_continuous_physics,
    verify_g19_gateway_protocol,
)
from world.full_ship_operations import (
    initialize_nominal_atmosphere,
    install_candidate,
    install_pressure_cells,
    load_candidate,
    set_component_condition,
    set_isolator,
    state,
)
from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_control_gateway import PROFILE as GATEWAY_PROFILE
from world.ship_electrical_power import audit_topology
from world.ship_mind_power import load_design
from world.ship_mind_runtime import validate_mind_runtime
from world.ship_mind_support import (
    data_penetrations,
    load_support,
    validate_cooling_ledger,
)
from world.ship_mind_support_world import installed_network_cohort
from world.ship_world import ensure_canonical_ship

from evennia.utils.test_resources import EvenniaTestCase


class InstalledMindPowerTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        commission_g19_electrical(operator_approved=True)
        self.design = load_design()

    def close_authored_input(self, source):
        # The new fitter must NEVER silently close these original G19
        # contacts. A test operator brings the original feeder online.
        for island in self.design["islands"]:
            feed = next(x for x in island["inputs"] if x["source"] == source)
            for segment in feed["route_domains"]:
                if segment.startswith("ISO-"):
                    if state("isolator", segment).setting != "closed":
                        set_isolator(segment, "closed", operator=True)

    def online_generator(self, name):
        original = state("equipment", name, lock=True)
        details = dict(original.details)
        details["physics_online"] = True
        details["physics_commanded_on"] = True
        details["physics_startup_s"] = 0.0
        original.details = details
        original.save(update_fields=["details"])
        set_isolator("ISO-" + name, "closed", operator=True)

    def installed(self):
        return commission_g19_mind_power(operator_approved=True)

    def advance(self, time):
        """Catch up through bounded world ticks, preserving every elapsed second."""
        result = tick_continuous_physics(now_game_time=time)
        while result["advanced"] and _clock().details["last_game_time"] < time:
            result = tick_continuous_physics(now_game_time=time)
        return result

    def survey_network(self):
        """Commission each actual cable and the two moving optical joints."""
        ship = load_candidate()
        for row in CanonicalShipState.objects.filter(source_model="ox.ship-support/1"):
            if row.category == "edge" or row.source_id in {"NET-ROT-A", "NET-ROT-B"}:
                survey_g19_data_path(
                    operator_approved=True,
                    component_id=row.source_id,
                    evidence_id="installed-continuity-" + row.source_id,
                    penetration_ids=data_penetrations(row.reference, ship),
                    continuity_verified=True,
                    pressure_verified=True,
                    environment_verified=True,
                    emi_verified=True,
                    continuous_rpm=3.6 if row.category == "equipment" else None,
                )

    def survey_cold(self):
        """Measure the five existing finite thermal stores once."""
        for pod in load_support()["cooling_islands"]:
            survey_g19_mind_cooling(
                operator_approved=True,
                buffer_id=pod["independent_buffer_id"],
                capacity_kj=720,
                free_kj=720,
            )

    def power_original_panel(self, destination):
        """Close a real original generator-to-local-panel path."""
        graph = defaultdict(list)
        for edge in CanonicalShipState.objects.filter(category="edge"):
            ref = edge.reference
            if ref.get("network") == "power" and edge.setting == "available":
                graph[ref["from_node"]].append((ref["to_node"], edge))
                if ref["kind"] in {"cross_tie", "bridge_feeder"}:
                    graph[ref["to_node"]].append((ref["from_node"], edge))
        previous = {"NODE-GEN-M": None}
        queue = deque(previous)
        while queue:
            parent = queue.popleft()
            for node, edge in graph[parent]:
                if node not in previous:
                    previous[node] = (parent, edge)
                    queue.append(node)
        target = destination
        self.assertIn(target, previous)
        while previous[target] is not None:
            parent, edge = previous[target]
            for isolator_id in edge.reference["isolator_ids"]:
                set_isolator(isolator_id, "closed", operator=True)
            target = parent

    def power_lt_plant(self):
        """Energise the actual LT motor panel and open its existing fluid valves."""
        self.power_original_panel("NODE-LP-ROTARY-UTIL-A")
        for edge in CanonicalShipState.objects.filter(category="edge"):
            if edge.reference.get("network") == "lt_cooling":
                for isolator_id in edge.reference["isolator_ids"]:
                    set_isolator(isolator_id, "open", operator=True)

    def survey_lt_rejection(self):
        """Commission separate piping and attest every penetrated pressure seal."""
        result = commission_g19_mind_heat_connections(operator_approved=True)
        self.assertEqual(result["created"], 15)
        ship = load_candidate()
        for pod in load_support()["cooling_islands"]:
            feed = pod["lt_connection"]
            set_isolator(feed["isolator"], "open", operator=True)
            penetrations = set(data_penetrations(feed, ship))
            for path in pod["machine_coolant_routes"].values():
                penetrations.update(data_penetrations({"route_spaces": path}, ship))
            survey_g19_heat_rejector(
                operator_approved=True,
                rejector_id=pod["heat_rejector_id"],
                measured_kw=pod["peak_rejection_kw"],
                evidence_id="installed-LT-output",
                sink_kind="lt",
                penetration_ids=sorted(penetrations),
            )

    def test_explicit_world_fitting_idempotent_and_g19_graph_unchanged(self):
        with self.assertRaises(PermissionError):
            commission_g19_mind_power()
        result = self.installed()
        self.assertTrue(result["commissioned"])
        self.assertEqual(result["created"], 132)
        self.assertEqual(result["total"], 132)
        rows = list(CanonicalShipState.objects.filter(
            source_model="ox.lead-mind-power/1"))
        self.assertEqual(len(rows), 132)
        self.assertEqual(sum(x.category == "equipment" for x in rows), 28)
        self.assertEqual(sum(x.category == "edge" for x in rows), 38)
        self.assertEqual(sum(x.category == "isolator" for x in rows), 38)
        self.assertEqual(sum(x.category == "node" for x in rows), 28)
        before = {(x.key, x.setting, x.revision) for x in rows}
        repeat = self.installed()
        self.assertFalse(repeat["commissioned"])
        self.assertEqual(repeat["created"], 0)
        self.assertEqual(before, {(x.key, x.setting, x.revision)
                                  for x in CanonicalShipState.objects.filter(
                                      source_model="ox.lead-mind-power/1")})
        nodes = list(CanonicalShipState.objects.filter(category="node"))
        edges = list(CanonicalShipState.objects.filter(category="edge"))
        isolators = {x.source_id: x for x in
                     CanonicalShipState.objects.filter(category="isolator")}
        a, b, c = audit_topology(nodes, edges, isolators, strict=True)
        self.assertEqual((len(a), len(b), len(c)), (438, 450, 466))
        clock = _clock()
        self.assertTrue(validate_mind_runtime(
            self.design, clock.details["mind_power"]))
        self.assertEqual(clock.details["mind_power"]["meter"]["grid_served_kwh"], 0)
        self.assertEqual(clock.details["mind_power"]["meter"]["reserve_served_kwh"], 0)

    def test_real_source_power_draw_and_persistent_meter(self):
        self.installed()
        self.online_generator("GEN-M")
        self.close_authored_input("A")
        result = self.advance(1010)
        self.assertTrue(result["advanced"])
        clock = _clock()
        mind = clock.details["mind_power"]
        self.assertEqual(len(mind["last"]["powered"]), 9)
        self.assertAlmostEqual(mind["last"]["grid_served_mw"], .018)
        self.assertAlmostEqual(mind["meter"]["grid_served_kwh"], .05)
        # An A/B feeder that reports live compute but delivers no G19
        # energy is a counterfeit source, not a passing integration test.
        self.assertGreaterEqual(
            clock.details["electrical"]["meter"]["served_kwh"] + 1e-7,
            mind["meter"]["grid_served_kwh"])
        self.assertTrue(validate_mind_runtime(self.design, mind))
        before = mind["meter"]["grid_served_kwh"]
        self.assertFalse(self.advance(1010)["advanced"])
        self.assertEqual(_clock().details["mind_power"]["meter"]["grid_served_kwh"],
                         before)
        self.assertFalse(self.installed()["commissioned"])
        self.assertEqual(_clock().details["mind_power"]["meter"]["grid_served_kwh"],
                         before)
        self.advance(1020)
        self.assertAlmostEqual(_clock().details["mind_power"]["meter"][
            "grid_served_kwh"], .10)

    def test_actual_delayed_transfer_uses_metered_island_reserve(self):
        self.installed()
        self.online_generator("GEN-M")
        self.online_generator("GEN-B")
        self.close_authored_input("A")
        self.close_authored_input("B")
        bow = self.design["islands"][0]
        name = bow["local_reserve"]["id"]
        with self.assertRaises(PermissionError):
            survey_g19_mind_reserve(
                reserve_id=name, capacity_kwh=.5, charge_kwh=.2)
        survey_g19_mind_reserve(
            operator_approved=True, reserve_id=name,
            capacity_kwh=.5, charge_kwh=.2)
        with self.assertRaises(PhysicsError):
            survey_g19_mind_reserve(
                operator_approved=True, reserve_id=name,
                capacity_kwh=.5, charge_kwh=.5)
        # Trip only the A infeed at the original new island.
        a = bow["inputs"][0]
        b = bow["inputs"][1]
        set_isolator(a["breaker"], "open", operator=True)
        self.advance(1010)
        mind = _clock().details["mind_power"]
        self.assertEqual(len(mind["last"]["powered"]), 9)
        self.assertEqual(mind["pending"][bow["id"]]["to"], "B")
        self.assertEqual(state("edge", a["edge"]).setting, "available")
        self.advance(1020)
        self.assertEqual(state("edge", a["edge"]).setting, "standby")
        self.assertEqual(state("edge", b["edge"]).setting, "available")
        self.assertEqual(len(_clock().details["mind_power"]["last"]["powered"]), 9)
        self.advance(1030)
        mind = _clock().details["mind_power"]
        self.assertEqual(len(mind["last"]["powered"]), 9)
        self.assertAlmostEqual(mind["meter"]["reserve_served_kwh"],
                               .02 + .00222222222222222, places=6)
        transitions = CanonicalShipEvent.objects.filter(
            component_key__in=["edge:" + a["edge"], "edge:" + b["edge"]],
            operation__in=[
                "g19_mind_power_break_before_make_open",
                "g19_mind_power_transfer_complete",
            ])
        self.assertEqual(transitions.count(), 2)

    def test_backbone_and_cold_pods_install_separately_without_remote_authority(self):
        self.installed()
        with self.assertRaises(PermissionError):
            commission_g19_mind_support()
        first=commission_g19_mind_support(operator_approved=True)
        self.assertTrue(first["commissioned"])
        self.assertEqual(first["created"],153)
        self.assertEqual(first["total"],153)
        support=load_support()
        rows=CanonicalShipState.objects.filter(source_model="ox.ship-support/1")
        self.assertEqual(rows.count(),153)
        self.assertEqual(rows.filter(category="equipment").count(),23)
        self.assertEqual(rows.filter(category="node").count(),66)
        self.assertEqual(rows.filter(category="edge").count(),64)
        self.assertFalse(commission_g19_mind_support(
            operator_approved=True)["commissioned"])
        self.assertFalse(
            installed_network_cohort(
                CanonicalShipState,
                support,
                self.design,
                load_candidate(),
                machines={"MIND-%02d" % n for n in range(1, 10)},
            )
        )
        self.survey_network()
        self.assertEqual(len(installed_network_cohort(
            CanonicalShipState,support,self.design,
            load_candidate(),
            machines={"MIND-%02d"%n for n in range(1,10)})),9)
        self.assertTrue(validate_cooling_ledger(
            support,_clock().details["mind_cooling"]))
        self.assertTrue(all(not unit["surveyed"] for unit in
            _clock().details["mind_cooling"]["units"].values()))
        # Two actual independent rotary data couplers; a single cut does
        # not disconnect a region, but both cuts isolate the HAB pair.
        set_component_condition("equipment","NET-ROT-A","failed",operator=True)
        self.assertEqual(len(installed_network_cohort(
            CanonicalShipState,support,self.design,
            load_candidate(),
            machines={"MIND-%02d"%n for n in range(1,10)})),9)
        set_component_condition("equipment","NET-ROT-B","failed",operator=True)
        self.assertEqual(len(installed_network_cohort(
            CanonicalShipState,support,self.design,
            load_candidate(),
            machines={"MIND-%02d"%n for n in range(1,10)})),7)

    def test_surveyed_cold_ride_through_and_local_thermal_trip_are_clock_owned(self):
        self.installed()
        commission_g19_mind_support(operator_approved=True)
        self.survey_network()
        support=load_support()
        for pod in support["cooling_islands"]:
            survey_g19_mind_cooling(
                operator_approved=True,
                buffer_id=pod["independent_buffer_id"],
                capacity_kj=720,free_kj=720)
        self.online_generator("GEN-M")
        self.close_authored_input("A")
        self.advance(1010)
        details=_clock().details
        self.assertEqual(len(details["mind_support_last"]["compute_ready"]),9)
        self.assertEqual(details["mind_support_last"]["thermal_shutdown"],[])
        self.assertTrue(validate_cooling_ledger(
            support,details["mind_cooling"]))
        self.assertEqual(sum(unit["generated_kj"] for unit in
            details["mind_cooling"]["units"].values()),180.0)
        bow=support["cooling_islands"][0]
        self.assertEqual(details["mind_cooling"]["units"][
            bow["independent_buffer_id"]]["free_kj"],680.0)
        set_component_condition("equipment",bow["independent_buffer_id"],
                                "failed",operator=True)
        before_count=CanonicalShipEvent.objects.filter(
            operation="g19_mind_thermal_protection_trip").count()
        self.advance(1020)
        details=_clock().details
        self.assertEqual(details["mind_support_last"]["thermal_shutdown"],
                         ["MIND-01","MIND-02"])
        self.assertEqual(len(details["mind_support_last"]["compute_ready"]),7)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="g19_mind_thermal_protection_trip").count()
                         - before_count,2)
        self.assertEqual(state("equipment","MIND-01").condition,"faulted")
        self.assertEqual(state("equipment","MIND-02").condition,"faulted")
        self.advance(1030)
        self.assertEqual(len(_clock().details["mind_power"]["last"]["powered"]),7)
        self.assertFalse(commission_g19_mind_support(
            operator_approved=True)["commissioned"])

    def test_cable_survey_requires_real_seals_and_continuous_rotary_ratings(self):
        """Rejected measurements leave no partial certificates or repair effects."""
        self.installed()
        commission_g19_mind_support(operator_approved=True)
        name = "NET-SPAN-A-00"
        args = dict(
            component_id=name,
            evidence_id="continuity-test",
            continuity_verified=True,
            pressure_verified=True,
        )
        with self.assertRaises(PermissionError):
            survey_g19_data_path(**args)
        with self.assertRaises(PhysicsError):
            survey_g19_data_path(operator_approved=True, **args)
        self.assertNotIn("data_survey", state("edge", name).details)
        args["penetration_ids"] = ["ACC-TRUNK-A-BOW-DR-01"]
        survey_g19_data_path(operator_approved=True, **args)
        event = CanonicalShipEvent.objects.filter(
            component_key="edge:" + name, operation="g19_data_path_surveyed"
        ).get()
        self.assertEqual(
            event.after["measurement"]["pressure_penetrations"], args["penetration_ids"]
        )
        for rotary_args in (
            {"continuous_rpm": 3.45, "environment_verified": True, "emi_verified": True},
            {"continuous_rpm": 3.6},
        ):
            with self.assertRaises(PhysicsError):
                survey_g19_data_path(
                    operator_approved=True,
                    component_id="NET-ROT-A",
                    evidence_id="unqualified-rotary-test",
                    continuity_verified=True,
                    pressure_verified=True,
                    **rotary_args,
                )
        set_component_condition("edge", name, "failed", operator=True)
        with self.assertRaises(PhysicsError):
            survey_g19_data_path(operator_approved=True, **args)
        self.assertEqual(state("edge", name).condition, "failed")

    def test_real_air_heat_transfer_exceeds_buffer_autonomy_without_losing_heat(self):
        """Actual coupled ticks sustain all nine beyond the finite cold reserve."""
        self.installed()
        commission_g19_mind_support(operator_approved=True)
        self.survey_network()
        self.survey_cold()
        self.online_generator("GEN-M")
        self.close_authored_input("A")
        support = load_support()
        bow = support["cooling_islands"][0]
        zone = _topology()[0][bow["service_room"]]
        # Compare the same first tick, with all other machinery unchanged.
        # Buffered heat produces no room-air rise; the measured rejector
        # must add exactly its recorded rejected heat to the same cell.
        with transaction.atomic():
            self.advance(1010)
            baseline_energy = _load_cell(state("pressure", zone))["energy"]
            transaction.set_rollback(True)
        with self.assertRaises(PermissionError):
            survey_g19_heat_rejector(
                rejector_id=bow["heat_rejector_id"], measured_kw=5, evidence_id="thermal-test"
            )
        for pod in support["cooling_islands"]:
            survey_g19_heat_rejector(
                operator_approved=True,
                rejector_id=pod["heat_rejector_id"],
                measured_kw=pod["peak_rejection_kw"],
                evidence_id="physical-air-output",
            )
        self.advance(1010)
        receipts = _clock().details["mind_support_last"]["thermal_receipts"]
        self.assertAlmostEqual(
            _load_cell(state("pressure", zone))["energy"] - baseline_energy,
            receipts[bow["id"]]["rejected_kj"],
            places=5,
        )
        self.advance(1240)
        details = _clock().details
        self.assertEqual(len(details["mind_support_last"]["compute_ready"]), 9)
        for bank in details["mind_cooling"]["units"].values():
            self.assertEqual(bank["free_kj"], 720)
            self.assertEqual(bank["unabsorbed_kj"], 0)
            self.assertAlmostEqual(bank["generated_kj"], bank["rejected_kj"])
        set_component_condition("equipment", bow["heat_rejector_id"], "failed", operator=True)
        self.advance(1250)
        self.assertEqual(
            _clock().details["mind_cooling"]["units"][bow["independent_buffer_id"]]["free_kj"], 680
        )
        self.assertEqual(len(_clock().details["mind_support_last"]["compute_ready"]), 9)
        set_component_condition("equipment", bow["heat_rejector_id"], "serviceable", operator=True)
        self.advance(1260)
        self.assertEqual(
            _clock().details["mind_cooling"]["units"][bow["independent_buffer_id"]]["free_kj"], 640
        )
        survey_g19_heat_rejector(
            operator_approved=True,
            rejector_id=bow["heat_rejector_id"],
            measured_kw=5,
            evidence_id="verified-repaired-air-output",
        )
        self.advance(1270)
        bank = _clock().details["mind_cooling"]["units"][bow["independent_buffer_id"]]
        self.assertEqual(bank["free_kj"], 650)
        self.assertEqual(bank["recovered_kj"], 10)
        self.assertFalse(self.advance(1270)["advanced"])
        self.assertEqual(
            bank, _clock().details["mind_cooling"]["units"][bow["independent_buffer_id"]]
        )

    def test_steady_lt_rejection_and_common_plant_loss_preserve_finite_ride_through(self):
        """One real radiator budget supports steady operation and bounded outages."""
        self.installed()
        commission_g19_mind_support(operator_approved=True)
        self.survey_network()
        self.survey_cold()
        self.online_generator("GEN-M")
        self.close_authored_input("A")
        self.power_lt_plant()
        with self.assertRaises(PermissionError):
            commission_g19_mind_heat_connections()
        self.survey_lt_rejection()
        self.assertFalse(
            commission_g19_mind_heat_connections(operator_approved=True)["commissioned"]
        )
        # 240 s exceeds a paired island's 180 s entire nameplate buffer.
        # Every joule generated must actually leave through the original LT.
        self.advance(1240)
        details = _clock().details
        status = details["mind_support_last"]
        self.assertEqual(len(status["compute_ready"]), 9)
        self.assertAlmostEqual(status["lt_rejected_kw"], 18)
        self.assertLessEqual(status["lt_rejected_kw"], status["lt_reserved_kw"])
        for bank in details["mind_cooling"]["units"].values():
            self.assertEqual(bank["free_kj"], 720)
            self.assertAlmostEqual(bank["generated_kj"], bank["rejected_kj"])
        set_component_condition("equipment", "ROT-LT-COOLING-A", "failed", operator=True)
        set_component_condition("equipment", "ROT-LT-COOLING-B", "failed", operator=True)
        self.advance(1250)
        after_rotary_loss = _clock().details["mind_cooling"]["units"]
        self.assertEqual(after_rotary_loss["BUF-MIND-ISL-HAB"]["free_kj"], 680)
        self.assertEqual(after_rotary_loss["BUF-MIND-ISL-BOW"]["free_kj"], 720)
        set_component_condition("equipment", "LT-PLANT", "failed", operator=True)
        self.advance(1370)
        details = _clock().details
        self.assertEqual(len(details["mind_support_last"]["compute_ready"]), 9)
        self.assertEqual(details["mind_support_last"]["lt_rejected_kw"], 0)
        for pod in load_support()["cooling_islands"]:
            self.assertEqual(
                details["mind_cooling"]["units"][pod["independent_buffer_id"]]["free_kj"],
                after_rotary_loss[pod["independent_buffer_id"]]["free_kj"]
                - pod["heat_rate_kw"] * 120,
            )
        nodes = list(CanonicalShipState.objects.filter(category="node"))
        edges = list(CanonicalShipState.objects.filter(category="edge"))
        switches = {r.source_id: r for r in CanonicalShipState.objects.filter(category="isolator")}
        a, b, c = audit_topology(nodes, edges, switches, strict=True)
        self.assertEqual((len(a), len(b), len(c)), (438, 450, 466))

    def test_installed_upstream_and_final_board_single_fault_cohorts(self):
        """All fitted source-path parts and final boards retain seven for 120 s."""
        self.installed()
        commission_g19_mind_support(operator_approved=True)
        self.survey_network()
        self.survey_cold()
        self.online_generator("GEN-M")
        self.online_generator("GEN-B")
        self.close_authored_input("A")
        self.close_authored_input("B")
        for island in self.design["islands"]:
            survey_g19_mind_reserve(
                operator_approved=True,
                reserve_id=island["local_reserve"]["id"],
                capacity_kwh=0.5,
                charge_kwh=0.2,
            )
        domains = {
            token
            for island in self.design["islands"]
            for feed in island["inputs"]
            for token in feed["route_domains"]
        }
        keys = {"equipment:PROT-BUS"}
        for row in CanonicalShipState.objects.filter(source_id__in=domains):
            if row.category == "node":
                keys.add("equipment:" + row.reference["owner_id"])
            elif row.category in {"edge", "isolator", "equipment"}:
                keys.add(row.key)
        keys.update(
            "equipment:" + machine["final_board"]
            for island in self.design["islands"]
            for machine in island["machines"]
        )
        self.assertGreater(len(keys), 50)
        self.assertTrue({"equipment:MSB-A", "equipment:MSB-B", "equipment:PROT-BUS"} <= keys)
        for key in sorted(keys):
            with self.subTest(fitted_single_fault=key), transaction.atomic():
                category, identifier = key.split(":", 1)
                set_component_condition(category, identifier, "failed", operator=True)
                for observed_s in range(1010, 1121, 10):
                    self.advance(observed_s)
                    status = _clock().details["mind_support_last"]
                    self.assertGreaterEqual(len(status["compute_ready"]), 7)
                transaction.set_rollback(True)
        self.assertEqual(_clock().details["last_game_time"], 1000)

    @tag("g19_gateway")
    def test_gateway_live_power_verified_vocabulary_and_local_fallback(self):
        """Real local supply, actual controller samples and no remote operation."""
        self.installed()
        commission_g19_mind_support(operator_approved=True)
        self.survey_network()
        self.survey_cold()
        self.online_generator("GEN-M")
        self.close_authored_input("A")
        self.power_original_panel("NODE-LP-BE-05-SVC")
        with self.assertRaises(PermissionError):
            commission_g19_gateway_power()
        result = commission_g19_gateway_power(operator_approved=True)
        self.assertEqual(result["created"], 4)
        self.advance(1010)
        self.assertFalse(_clock().details["mind_gateway"]["last"]["powered"])
        survey_g19_gateway_power(
            operator_approved=True,
            measured_kw=0.05,
            evidence_id="actual-local-50W-circuit",
            thermal_path_verified=True,
        )
        sink_zone = _topology()[0]["TRUNK-B-DR-03"]
        with transaction.atomic():
            set_isolator("ISO-PWR-GW-LCS-DR-03", "open", operator=True)
            self.advance(1020)
            baseline_heat = _load_cell(state("pressure", sink_zone))["energy"]
            transaction.set_rollback(True)
        self.advance(1020)
        self.assertAlmostEqual(
            _load_cell(state("pressure", sink_zone))["energy"] - baseline_heat, 0.5
        )
        gateway = _clock().details["mind_gateway"]
        self.assertTrue(gateway["last"]["powered"])
        self.assertEqual(len(gateway["last"]["raw_samples"]), 3)
        self.assertEqual(gateway["last"]["readings"], {})
        confirmations = {}
        for key, sample in gateway["last"]["raw_samples"].items():
            valve = key.startswith("isolator:")
            confirmations[key] = {
                "value": (
                    {"O": "open", "C": "closed"}[sample["raw_value"]]
                    if valve
                    else bool(sample["raw_value"])
                ),
                "meaning": "valve_position" if valve else "running_feedback",
                "unit": "position" if valve else "state",
            }
        with self.assertRaises(PermissionError):
            verify_g19_gateway_protocol(
                profile=GATEWAY_PROFILE, confirmations=confirmations, evidence_id="protocol-test"
            )
        self.assertEqual(
            verify_g19_gateway_protocol(
                operator_approved=True,
                profile=GATEWAY_PROFILE,
                confirmations=confirmations,
                evidence_id="three-local-register-comparisons",
            )["mapping_revision"],
            1,
        )
        original_valve = state("isolator", "ISO-DR-03-LT-IF").setting
        self.advance(1030)
        gateway = _clock().details["mind_gateway"]
        self.assertEqual(len(gateway["last"]["readings"]), 3)
        for reading in gateway["last"]["readings"].values():
            self.assertEqual(reading["source_time"], 1030)
            self.assertEqual(reading["mapping_revision"], 1)
            self.assertIn("raw_value", reading)
        self.assertAlmostEqual(gateway["served_kwh"], 0.05 * 20 / 3600)
        self.assertFalse(gateway["last"]["remote_commands_enabled"])
        set_component_condition("edge", "NET-GW-DROP-A-DR-03", "severed", operator=True)
        self.advance(1040)
        self.assertTrue(_clock().details["mind_gateway"]["last"]["connected"])
        set_component_condition("edge", "NET-GW-DROP-B-DR-03", "severed", operator=True)
        self.advance(1050)
        gateway = _clock().details["mind_gateway"]
        self.assertTrue(gateway["last"]["powered"])
        self.assertFalse(gateway["last"]["readings"])
        self.assertEqual(len(_clock().details["mind_support_last"]["compute_ready"]), 9)
        self.assertEqual(state("isolator", "ISO-DR-03-LT-IF").setting, original_valve)
        consumed = gateway["served_kwh"]
        with transaction.atomic():
            set_component_condition("edge", "THERM-GW-LCS-DR-03", "failed", operator=True)
            self.advance(1060)
            self.assertFalse(_clock().details["mind_gateway"]["last"]["powered"])
            self.assertEqual(_clock().details["mind_gateway"]["served_kwh"], consumed)
            transaction.set_rollback(True)
        with transaction.atomic():
            source = state("equipment", "DR-03-CARGO-HX", lock=True)
            source.space_id = "BE-05-SVC"
            source.save(update_fields=["space_id"])
            with self.assertRaises(PhysicsError):
                self.advance(1060)
            self.assertEqual(_clock().details["last_game_time"],1050)
            transaction.set_rollback(True)
        set_isolator("ISO-PWR-GW-LCS-DR-03", "open", operator=True)
        self.advance(1060)
        self.assertFalse(_clock().details["mind_gateway"]["last"]["powered"])
        self.assertEqual(_clock().details["mind_gateway"]["served_kwh"], consumed)
        self.assertFalse(commission_g19_gateway_power(operator_approved=True)["commissioned"])
        self.assertEqual(_clock().details["mind_gateway"]["mapping_revision"], 1)

    def test_missing_new_machine_contact_or_tampered_identity_fails_closed(self):
        self.installed()
        unit = self.design["islands"][0]["machines"][0]
        state("isolator", unit["isolator"], lock=True)
        set_isolator(unit["isolator"], "open", operator=True)
        self.online_generator("GEN-M")
        self.close_authored_input("A")
        self.advance(1010)
        self.assertEqual(len(_clock().details["mind_power"]["last"]["powered"]), 8)
        row = state("node", unit["terminal_node"], lock=True)
        row.reference = dict(row.reference, owner_id="INVENTED-COMPUTER")
        row.save(update_fields=["reference"])
        with self.assertRaises(PhysicsError):
            self.advance(1020)
        # Transaction rollback preserves the previous clock epoch.
        self.assertEqual(_clock().details["last_game_time"], 1010)


if __name__ == "__main__":
    import unittest
    unittest.main()
