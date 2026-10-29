"""G19 bounded whole-ship casualty/restart integration; not a crew voyage.

Real installed 421-space/808-equipment Evennia world, actual gas, ship
clock, original feeder and fitted cargo pressure boundary. Operator fault
injection is deliberately separated from crew operations. Every result
checks durable database state rather than an in-memory mock ship.
"""
from __future__ import annotations

import copy
from unittest.mock import patch

from evennia.scripts.models import ScriptDB
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    set_component_condition, set_isolator, state,
)
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt
from world.ship_world import build_canonical_ship, find_ship_space
from world.ship_unclassified_spaces import SECTORS
from world import continuous_ship_physics as physics
from world.continuous_ship_physics import (
    PhysicsError, SCRIPT_KEY, _clock, arm_continuous_physics,
    commission_g19_electrical, commission_g19_water,
    commission_g19_repairs, commission_g19_eva,
    commission_g19_unclassified_spaces, commission_g19_crew_physiology,
    commission_g19_instrumentation, configure_water_casualty,
    configure_scenario_casualty, survey_cargo_lot,
    survey_g19_cargo_sector, witness_g19_cargo_sector_leak,
    crew_physical_action, tick_continuous_physics,
    ensure_continuous_physics_clock,
)


class InstalledG19FinalCampaign(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        self.worker.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.worker.dbref])
        commission_g19_unclassified_spaces(operator_approved=True)
        commission_g19_instrumentation(operator_approved=True)
        self.time = 1000.0
        self.counter = 75000

    def action(self, action, target, value, *, request_id=None):
        if request_id is None:
            self.counter += 1
            request_id = f"{self.counter:032x}"
        return crew_physical_action(
            self.worker, request_id, action, target, value)

    def at(self, room):
        self.assertTrue(
            self.worker.move_to(find_ship_space(room), quiet=True), room)

    def advance(self, seconds):
        self.assertEqual(seconds % 10, 0)
        last = None
        for _ in range(int(seconds // 10)):
            self.time += 10
            last = tick_continuous_physics(now_game_time=self.time)
            self.assertTrue(last["advanced"])
        return last

    def survey_dr01(self):
        survey_cargo_lot(operator_approved=True, operation="verify",
                         drum="DR-01")
        for sector in SECTORS[:8]:
            survey_g19_cargo_sector(
                operator_approved=True, sector=sector,
                free_volume_m3=50, pressure_pa=101000,
                temperature_k=293.15, oxygen_mass_fraction=.232,
                co2_mass_fraction=.0004, smoke_mass_fraction=0,
                cargo_class="empty", lot_ids=[])

    def open_breached_sector(self, sector="DR-01-SEC-01", rate=.6):
        self.survey_dr01()
        self.at("DR-01-GALLERY")
        self.action("cargo_sector", sector, "secure")
        request = f"{self.counter + 1:032x}"
        first = self.action("hatch", "ACC-" + sector, "open",
                            request_id=request)
        self.counter += 1
        witness_g19_cargo_sector_leak(
            operator_approved=True, sector=sector, leak_kg_s=rate)
        return sector, request, first

    def test_sustained_cargo_fire_brownout_and_contaminated_water(self):
        """Four simultaneously real hazards persist without magical repair."""
        sector, _, _ = self.open_breached_sector(rate=.65)
        configure_scenario_casualty(
            "PZ-HAB-01", operator=True,
            fire_fuel_kg=12, fire_burn_kg_s=.03)
        available = _clock().details["water"]["working_kg"]
        self.assertGreater(available, 1)
        amount = min(20.0, available / 2)
        configure_water_casualty(operator=True, contaminated_kg=amount)
        set_component_condition(
            "edge", "EDGE-GEN-M", "severed", operator=True)
        first = self.advance(60)
        second = self.advance(120)
        self.assertFalse(first["power_assured"])
        self.assertFalse(second["power_assured"])
        d = _clock().details
        damaged = d["unclassified_spaces"]["sectors"][sector]
        self.assertGreater(damaged["lost_kg"], 0)
        self.assertGreater(damaged["gallery_net_kg"], 0)
        self.assertIn("ACC-" + sector, second["cargo_open_breached_hatches"])
        self.assertEqual(d["rotors"]["DR-01"]["target_rpm"], 0)
        self.assertTrue(d["water"]["potable_quarantined"])
        self.assertAlmostEqual(d["water"]["suspected_contamination_kg"],
                               amount)
        self.assertEqual(state("edge", "EDGE-GEN-M").condition, "severed")
        self.assertGreater(state(
            "pressure", "PZ-HAB-01").details["physics_smoke_kg"], 0)
        self.assertGreater(d["burned_fuel_kg"], 0)
        self.assertGreater(d["lost_to_space_kg"], 0)
        self.assertEqual(d["instrumentation"]["last_s"], self.time)
        # Opening/closing a rated boundary requires a real person there.
        self.action("hatch", "ACC-" + sector, "closed")
        net_before = damaged["gallery_net_kg"]
        lost_before = damaged["lost_kg"]
        self.advance(60)
        isolated = _clock().details["unclassified_spaces"]["sectors"][sector]
        self.assertAlmostEqual(isolated["gallery_net_kg"], net_before, places=5)
        self.assertGreater(isolated["lost_kg"], lost_before)
        self.assertEqual(state("edge", "EDGE-GEN-M").condition, "severed")
        self.assertTrue(_clock().details["water"]["potable_quarantined"])

    def test_rearm_rebuild_backlog_and_exactly_once_work_receipt(self):
        """Restart/recommission cannot reset losses, duplicate work or skip time."""
        sector, request, receipt = self.open_breached_sector(rate=.35)
        self.advance(60)
        before = copy.deepcopy(_clock().details)
        before_events = WorkReceipt.objects.filter(pk=request).count()
        self.assertEqual(before_events, 1)
        self.assertGreater(before["unclassified_spaces"]["sectors"][
            sector]["lost_kg"], 0)
        # This is a cold ORM/world-model re-entry, not a full live server
        # restart. The persistent script singleton is tested separately.
        build_canonical_ship()
        self.assertFalse(install_candidate(
            operator_approved=True)["installed"])
        rearmed = arm_continuous_physics(
            operator_approved=True, now_game_time=2500)
        self.assertFalse(rearmed["armed"])
        self.assertEqual(rearmed["last_game_time"], self.time)
        self.assertEqual(_clock().details, before)
        self.assertFalse(tick_continuous_physics(
            now_game_time=self.time)["advanced"])
        self.assertEqual(
            self.action("hatch", "ACC-" + sector, "open",
                        request_id=request), receipt)
        self.assertEqual(WorkReceipt.objects.filter(pk=request).count(),
                         before_events)
        self.assertEqual(_clock().details, before)
        # A 230-second offline interval is recovered in bounded chunks,
        # preserving exact elapsed game seconds and not replaying a tick.
        requested = self.time + 230
        iterations = 0
        losses = []
        while _clock().details["last_game_time"] < requested:
            old = _clock().details["last_game_time"]
            result = tick_continuous_physics(now_game_time=requested)
            self.assertTrue(result["advanced"])
            self.assertLessEqual(result["last_game_time"] - old, 60)
            self.assertGreater(result["last_game_time"], old)
            losses.append(_clock().details["unclassified_spaces"][
                "sectors"][sector]["lost_kg"])
            iterations += 1
        self.assertEqual(iterations, 4)
        self.assertEqual(_clock().details["last_game_time"], requested)
        self.assertEqual(losses, sorted(losses))
        self.assertGreater(losses[-1], losses[0])
        self.assertFalse(tick_continuous_physics(
            now_game_time=requested)["advanced"])
        self.assertEqual(_clock().details["unclassified_spaces"][
            "sectors"][sector]["lost_kg"], losses[-1])
        self.assertEqual(state("access", "ACC-" + sector).setting, "open")
        self.assertEqual(_clock().details["unclassified_spaces"][
            "sectors"][sector]["permit"]["holder"], self.worker.dbref)

    def test_late_substep_failure_rolls_back_every_world_ledger(self):
        """A failed 30-second substep must not partially commit preceding work."""
        sector, _, _ = self.open_breached_sector(rate=.4)
        before = copy.deepcopy(_clock().details)
        zone = state("pressure", "PZ-DR-01-SVC")
        gallery_before = zone.quantity
        fuel_before = state("inventory", "INV-GEN-CART").quantity
        events_before = CanonicalShipEvent.objects.count()
        original = physics._unclassified_advance
        calls = 0

        def fail_after_two_real_substeps(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise PhysicsError("injected late transactional failure")
            return original(*args, **kwargs)

        with patch.object(physics, "_unclassified_advance",
                          side_effect=fail_after_two_real_substeps):
            with self.assertRaisesRegex(
                    PhysicsError, "injected late transactional failure"):
                tick_continuous_physics(now_game_time=1060)
        self.assertEqual(calls, 3)
        self.assertEqual(_clock().details, before)
        self.assertEqual(state("pressure", "PZ-DR-01-SVC").quantity,
                         gallery_before)
        self.assertEqual(state("inventory", "INV-GEN-CART").quantity,
                         fuel_before)
        self.assertEqual(CanonicalShipEvent.objects.count(), events_before)
        self.assertEqual(_clock().details["last_game_time"], 1000)
        # Retry after the failed transaction: one completed minute, not
        # the minute plus the two rolled-back integration substeps.
        self.time = 1060
        once = tick_continuous_physics(now_game_time=self.time)
        self.assertTrue(once["advanced"])
        lost = _clock().details["unclassified_spaces"]["sectors"][
            sector]["lost_kg"]
        self.assertGreater(lost, 0)
        self.assertLessEqual(lost, .4 * 60 + 1e-6)
        self.assertFalse(tick_continuous_physics(
            now_game_time=self.time)["advanced"])
        self.assertEqual(_clock().details["unclassified_spaces"][
            "sectors"][sector]["lost_kg"], lost)

    def test_persistent_script_rebinds_once_without_rearming_gas(self):
        """Installed timer survives re-registration and never creates twins."""
        count = ScriptDB.objects.filter(db_key=SCRIPT_KEY).count()
        self.assertEqual(count, 0)
        self.assertTrue(ensure_continuous_physics_clock())
        self.assertTrue(ensure_continuous_physics_clock())
        self.assertEqual(ScriptDB.objects.filter(
            db_key=SCRIPT_KEY).count(), 1)
        before = copy.deepcopy(_clock().details)
        self.assertFalse(arm_continuous_physics(
            operator_approved=True, now_game_time=2000)["armed"])
        self.assertEqual(_clock().details, before)
        self.assertTrue(ScriptDB.objects.get(
            db_key=SCRIPT_KEY).db_persistent)
        self.assertFalse(tick_continuous_physics(
            now_game_time=1000)["advanced"])
