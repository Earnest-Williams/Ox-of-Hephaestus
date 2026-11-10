"""Installed G19 lead-mind power network on persistent Evennia ship records.

Exercises real original generator/bus/feeder contacts and the same bounded
ten-second physics clock. No simulated voyage or independent fake grid.
"""
from __future__ import annotations

from evennia.utils.test_resources import EvenniaTestCase

from world.ship_world import ensure_canonical_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_isolator, set_component_condition, state, load_candidate,
)
from world.models import CanonicalShipState, CanonicalShipEvent
from world.ship_mind_power import load_design
from world.ship_mind_runtime import validate_mind_runtime
from world.ship_mind_support import load_support, validate_cooling_ledger
from world.ship_mind_support_world import installed_network_cohort
from world.ship_electrical_power import audit_topology
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    commission_g19_mind_power, survey_g19_mind_reserve,
    commission_g19_mind_support, survey_g19_mind_cooling,
    tick_continuous_physics, _clock,
)


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
        return tick_continuous_physics(now_game_time=time)

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
        self.assertEqual(first["created"],147)
        self.assertEqual(first["total"],147)
        support=load_support()
        rows=CanonicalShipState.objects.filter(source_model="ox.ship-support/1")
        self.assertEqual(rows.count(),147)
        self.assertEqual(rows.filter(category="equipment").count(),21)
        self.assertEqual(rows.filter(category="node").count(),64)
        self.assertEqual(rows.filter(category="edge").count(),62)
        self.assertFalse(commission_g19_mind_support(
            operator_approved=True)["commissioned"])
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
