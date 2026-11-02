"""G19 installed casualty repressurisation from the fitted refill banks.

The real sequence: a breached HAB arc is patched and permanently restored,
then an engineer lines up the authored valves, meters bank air from the
regulator station and the arc returns to its commissioned pressure. Every
kilogram delivered is debited from the bank; nothing is refunded on a halt.
"""

from __future__ import annotations

from typing import Any

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError,
    _clock,
    _topology,
    arm_continuous_physics,
    commission_g19_hull,
    commission_g19_repairs,
    commission_g19_water,
    configure_scenario_casualty,
    crew_physical_action,
    local_physics_readout,
    register_g19_hull_breach,
    survey_g19_water_material,
    tick_continuous_physics,
)
from world.full_ship_operations import (
    R_SPECIFIC_AIR,
    initialize_nominal_atmosphere,
    install_candidate,
    install_pressure_cells,
    set_isolator,
    state,
)
from world.models import CanonicalShipEvent, WorkReceipt
from world.ship_gas_refill import RATED_KG_S
from world.ship_world import ensure_canonical_ship, find_ship_space

# (valve, room the engineer operates it from). ISO-GAS-BANK-A sits in the
# non-breathable WATER-SHIELD-FWD tank bay; it is worked remotely from the
# fitted WATER-FWD panel, as the switch action already allows.
TRUNK_LINEUP: tuple[tuple[str, str], ...] = (
    ("ISO-GAS-BANK-A", "WATER-FWD"),
    ("ISO-GAS-REG-A", "ENV-FWD"),
    ("ISO-GAS-HDR-TRUNK-A-BOW", "TRUNK-A-BOW"),
    ("ISO-GAS-TAP-TRUNK-A-BOW", "TRUNK-A-BOW"),
)
HAB03_LINEUP: tuple[tuple[str, str], ...] = (
    ("ISO-GAS-BANK-A", "WATER-FWD"),
    ("ISO-GAS-REG-A", "ENV-FWD"),
    ("ISO-GAS-HDR-TRUNK-A-BOW", "TRUNK-A-BOW"),
    ("ISO-GAS-ROT-FIX-A", "ROTARY-UTIL-A"),
    ("ISO-GAS-ROT-ROT-A", "ROTARY-UTIL-A"),
    ("ISO-GAS-HAB-FEED-A", "HAB-06-SERVICE-GALLERY"),
    ("ISO-GAS-BR-05-TO", "HAB-06-SERVICE-GALLERY"),
    ("ISO-GAS-BR-05-FROM", "HAB-05-SERVICE-GALLERY"),
    ("ISO-GAS-BR-04-TO", "HAB-05-SERVICE-GALLERY"),
    ("ISO-GAS-BR-04-FROM", "HAB-04-SERVICE-GALLERY"),
    ("ISO-GAS-BR-03-TO", "HAB-04-SERVICE-GALLERY"),
    ("ISO-GAS-BR-03-FROM", "HAB-03-SERVICE-GALLERY"),
)


class InstalledGasRefill(EvenniaTestCase):  # type: ignore[misc]
    def setUp(self) -> None:
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_hull(operator_approved=True)
        set_isolator("ISO-GEN-M", "closed", operator=True)
        self.tech: Any = build_ship()["watch"]
        self.now: float = 1000.0
        self.serial: int = 0

    # -- helpers -------------------------------------------------------------

    def action(self, action: str, target: str, value: str) -> dict[str, Any]:
        self.serial += 1
        request_id: str = f"{self.serial:032x}"
        result: dict[str, Any] = crew_physical_action(
            self.tech, request_id, action, target, value
        )
        return result

    def go(self, room: str) -> None:
        self.assertTrue(self.tech.move_to(find_ship_space(room), quiet=True))

    def tick(self, seconds: float) -> None:
        end: float = self.now + seconds
        while self.now < end:
            self.now = min(end, self.now + 60.0)
            tick_continuous_physics(now_game_time=self.now)

    def line_up(self, lineup: tuple[tuple[str, str], ...]) -> None:
        valve: str
        room: str
        for valve, room in lineup:
            self.go(room)
            self.action("switch", valve, "open")

    def pressure_pa(self, zone: str) -> float:
        cell: Any = state("pressure", zone)
        volume: float = cell.details["gas_volume_m3"]
        temperature: float = cell.details["temperature_k"]
        return float(cell.quantity * R_SPECIFIC_AIR * temperature / volume)

    def bank_kg(self, inventory: str) -> float:
        return float(state("inventory", inventory).quantity * 1000.0)

    def run_until_stopped(self, bank: str, limit_s: float) -> None:
        waited: float = 0.0
        while bank in _clock().details["gas_refill"]["jobs"] and waited < limit_s:
            self.tick(60.0)
            waited += 60.0

    def restore_hab03_breach(self) -> tuple[str, float]:
        zone: str = "PZ-HAB-03"
        link: Any = state("access", "ACC-BR-03-HAB-03")
        zones: dict[str, Any] = _topology()[0]
        site: str = next(
            room
            for room in (link.reference["from"], link.reference["to"])
            if zones.get(room) == zone
        )
        self.go("TOOL-CRIB")
        self.action("repair", "TOOL-CRIB", "pickup_toolkit")
        survey_g19_water_material(
            operator_approved=True,
            source="INV-SPARES",
            room_id="STORE-CRIT-SPARES",
            verified_kg=6,
        )
        self.go("STORE-CRIT-SPARES")
        self.action("repair", "INV-SPARES", "pickup:6")
        nominal_kg: float = float(state("pressure", zone).quantity)
        register_g19_hull_breach(
            operator_approved=True, zone_id=zone, site_room_id=site, leak_kg_s=0.05
        )
        self.tick(1200.0)
        self.go(site)
        self.action("hull", zone, "patch")
        self.tick(600.0)
        self.action("hull", zone, "restore")
        self.tick(900.0)
        self.assertEqual(state("pressure", zone).details["physics_leak_kg_s"], 0)
        self.assertEqual(
            _clock().details["hull"]["breaches"][zone]["phase"], "restored"
        )
        return zone, nominal_kg

    # -- acceptance ----------------------------------------------------------

    def test_restored_arc_refills_to_setpoint_with_exact_finite_debit(self) -> None:
        zone, nominal_kg = self.restore_hab03_breach()
        setpoint: float = state("pressure", zone).details[
            "scenario_initial_pressure_pa"
        ]
        deficit_kg: float = nominal_kg - float(state("pressure", zone).quantity)
        self.assertGreater(deficit_kg, 50.0)
        bank_a_before: float = self.bank_kg("INV-GAS-REFILL-A")
        bank_b_before: float = self.bank_kg("INV-GAS-REFILL-B")

        # As-found valves give no route; the refusal issues no receipt.
        self.go("ENV-FWD")
        self.serial += 1
        refused_id: str = f"{self.serial:032x}"
        with self.assertRaises(PhysicsError):
            crew_physical_action(self.tech, refused_id, "gas_refill", zone, "start:A")
        self.assertFalse(WorkReceipt.objects.filter(pk=refused_id).exists())

        # Starting is only possible at the regulator station.
        self.line_up(HAB03_LINEUP)
        self.go("CMD-PRIMARY")
        with self.assertRaises(PermissionError):
            self.action("gas_refill", zone, "start:A")
        self.go("ENV-FWD")
        self.serial += 1
        start_id: str = f"{self.serial:032x}"
        receipt: dict[str, Any] = crew_physical_action(
            self.tech, start_id, "gas_refill", zone, "start:A"
        )
        self.assertEqual(receipt["status"], "succeeded")
        replay: dict[str, Any] = crew_physical_action(
            self.tech, start_id, "gas_refill", zone, "start:A"
        )
        self.assertEqual(replay, receipt)
        self.assertEqual(WorkReceipt.objects.filter(pk=start_id).count(), 1)
        gauges: dict[str, Any] = local_physics_readout(self.tech, "gas_refill")
        self.assertEqual(gauges["job"]["cell"], zone)
        self.assertEqual(gauges["bank"], "A")

        started_s: float = self.now
        self.run_until_stopped("A", 6 * 3600.0)
        ledger: dict[str, Any] = _clock().details["gas_refill"]
        self.assertNotIn("A", ledger["jobs"])
        record: dict[str, Any] = ledger["history"][-1]
        self.assertEqual(record["reason"], "setpoint_reached")
        delivered: float = record["delivered_kg"]

        # Exact finite custody: bank A debited by exactly what was metered,
        # bank B untouched, and delivery no faster than the rated regulator.
        self.assertAlmostEqual(
            bank_a_before - self.bank_kg("INV-GAS-REFILL-A"), delivered, places=6
        )
        self.assertAlmostEqual(ledger["delivered_kg"]["A"], delivered, places=9)
        self.assertEqual(self.bank_kg("INV-GAS-REFILL-B"), bank_b_before)
        self.assertGreater(delivered, 0.8 * deficit_kg)
        self.assertGreaterEqual(
            self.now - started_s + 60.0, delivered / RATED_KG_S
        )
        self.assertLess(abs(self.pressure_pa(zone) - setpoint), 50.0)
        oxygen_fraction: float = (
            state("pressure", zone).details["physics_oxygen_kg"]
            / state("pressure", zone).quantity
        )
        self.assertGreater(oxygen_fraction, 0.20)
        self.assertLess(oxygen_fraction, 0.24)
        self.assertTrue(
            CanonicalShipEvent.objects.filter(
                operation="g19_gas_refill_stopped", actor_dbref=self.tech.dbref
            ).exists()
        )

        # An equal-time tick and a replayed request change nothing.
        after_kg: float = self.bank_kg("INV-GAS-REFILL-A")
        self.assertFalse(
            tick_continuous_physics(now_game_time=self.now)["advanced"]
        )
        crew_physical_action(self.tech, start_id, "gas_refill", zone, "start:A")
        self.tick(600.0)
        self.assertEqual(self.bank_kg("INV-GAS-REFILL-A"), after_kg)

        # At setpoint there is nothing to meter, so a new job is refused.
        with self.assertRaises(PhysicsError):
            self.action("gas_refill", zone, "start:A")

    def test_unrestored_breach_is_refused(self) -> None:
        zone: str = "PZ-HAB-03"
        link: Any = state("access", "ACC-BR-03-HAB-03")
        zones: dict[str, Any] = _topology()[0]
        site: str = next(
            room
            for room in (link.reference["from"], link.reference["to"])
            if zones.get(room) == zone
        )
        register_g19_hull_breach(
            operator_approved=True, zone_id=zone, site_room_id=site, leak_kg_s=0.01
        )
        self.tick(600.0)
        self.line_up(HAB03_LINEUP)
        self.go("ENV-FWD")
        with self.assertRaises(PhysicsError):
            self.action("gas_refill", zone, "start:A")
        self.assertNotIn("gas_refill", _clock().details)

    def test_closed_valve_and_new_leak_halt_without_refund(self) -> None:
        zone: str = "PZ-TRUNK-A-BOW"
        configure_scenario_casualty(zone, operator=True, leak_kg_s=0.2)
        self.tick(900.0)
        configure_scenario_casualty(zone, operator=True, leak_kg_s=0.0)
        self.line_up(TRUNK_LINEUP)
        self.go("ENV-FWD")
        self.action("gas_refill", zone, "start:A")
        self.tick(600.0)
        ledger: dict[str, Any] = _clock().details["gas_refill"]
        first_kg: float = ledger["jobs"]["A"]["delivered_kg"]
        self.assertGreater(first_kg, 0.0)

        # Closing the trunk entry valve at its station cuts the route.
        self.go("TRUNK-A-BOW")
        self.action("switch", "ISO-GAS-HDR-TRUNK-A-BOW", "closed")
        bank_before_halt: float = self.bank_kg("INV-GAS-REFILL-A")
        self.tick(60.0)
        ledger = _clock().details["gas_refill"]
        self.assertNotIn("A", ledger["jobs"])
        self.assertEqual(ledger["history"][-1]["reason"], "route_lost")
        self.assertEqual(self.bank_kg("INV-GAS-REFILL-A"), bank_before_halt)
        self.go("ENV-FWD")
        with self.assertRaises(PhysicsError):
            self.action("gas_refill", zone, "start:A")

        # Reopen and resume, then a fresh leak halts metering at once.
        self.go("TRUNK-A-BOW")
        self.action("switch", "ISO-GAS-HDR-TRUNK-A-BOW", "open")
        self.go("ENV-FWD")
        self.action("gas_refill", zone, "start:A")
        self.tick(120.0)
        configure_scenario_casualty(zone, operator=True, leak_kg_s=0.05)
        self.tick(60.0)
        ledger = _clock().details["gas_refill"]
        self.assertNotIn("A", ledger["jobs"])
        self.assertEqual(ledger["history"][-1]["reason"], "downstream_leak")
        total: float = ledger["delivered_kg"]["A"]
        self.assertAlmostEqual(
            ledger["commissioned_kg"]["A"] - self.bank_kg("INV-GAS-REFILL-A"),
            total,
            places=6,
        )
        with self.assertRaises(PhysicsError):
            self.action("gas_refill", zone, "start:A")

    def test_operator_stop_keeps_delivered_gas_and_bank_debit(self) -> None:
        zone: str = "PZ-TRUNK-A-BOW"
        configure_scenario_casualty(zone, operator=True, leak_kg_s=0.2)
        self.tick(900.0)
        configure_scenario_casualty(zone, operator=True, leak_kg_s=0.0)
        self.line_up(TRUNK_LINEUP)
        self.go("ENV-FWD")
        self.action("gas_refill", zone, "start:A")
        self.tick(300.0)
        with self.assertRaises(PhysicsError):
            self.action("gas_refill", "PZ-HAB-03", "stop:A")
        self.action("gas_refill", zone, "stop:A")
        ledger: dict[str, Any] = _clock().details["gas_refill"]
        self.assertEqual(ledger["history"][-1]["reason"], "operator_stop")
        kept: float = ledger["delivered_kg"]["A"]
        self.assertGreater(kept, 0.0)
        # After the stop the bank is no longer drawn on. The cell itself may
        # still gain gas from open neighbouring trunk sections; that is
        # equalisation within the ship, not bank delivery.
        bank_after_stop: float = self.bank_kg("INV-GAS-REFILL-A")
        self.tick(300.0)
        self.assertEqual(self.bank_kg("INV-GAS-REFILL-A"), bank_after_stop)
        self.assertNotIn("A", _clock().details["gas_refill"]["jobs"])
        self.assertAlmostEqual(
            ledger["commissioned_kg"]["A"] - self.bank_kg("INV-GAS-REFILL-A"),
            kept,
            places=6,
        )
