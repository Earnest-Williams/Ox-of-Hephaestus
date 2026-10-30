"""Pure G19 casualty repressurisation: finite banks, rated metering, routes."""

from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path
from typing import Any

from world.ship_gas_refill import (
    MAX_HISTORY,
    NETWORK,
    RATED_KG_S,
    REGULATORS,
    GasRefillError,
    RefillLedger,
    RouteEdge,
    bank_remaining_kg,
    deliverable_kg,
    initial_refill,
    mass_at_pressure,
    reachable_cells,
    reconciles_with_inventory,
    record_delivery,
    start_refill,
    stop_refill,
    validate_refill,
)

CANDIDATE: Path = (
    Path(__file__).resolve().parents[3] / "design/ship/ox_full_ship_v0.5_candidate.json"
)
FULL_BANKS: dict[str, float] = {"A": 2750.0, "B": 2750.0}


def _started(bank: str = "A", cell: str = "PZ-HAB-03") -> RefillLedger:
    return start_refill(
        initial_refill(FULL_BANKS),
        bank=bank,
        cell=cell,
        setpoint_pa=101_325.0,
        actor="#7",
        request_id="a" * 32,
        now_s=1000.0,
    )


class LedgerContract(unittest.TestCase):
    def test_commissioning_requires_both_finite_banks(self) -> None:
        with self.assertRaises(GasRefillError):
            initial_refill({"A": 2750.0})
        with self.assertRaises(GasRefillError):
            initial_refill({"A": 2750.0, "B": 9000.0})
        with self.assertRaises(GasRefillError):
            initial_refill({"A": math.nan, "B": 0.0})
        ledger: RefillLedger = initial_refill(FULL_BANKS)
        self.assertEqual(bank_remaining_kg(ledger, "B"), 2750.0)

    def test_one_job_per_regulator_and_rated_setpoint(self) -> None:
        ledger: RefillLedger = _started()
        with self.assertRaises(GasRefillError):
            start_refill(
                ledger,
                bank="A",
                cell="PZ-HAB-04",
                setpoint_pa=101_325.0,
                actor="#7",
                request_id="b" * 32,
                now_s=1001.0,
            )
        for setpoint in (10_000.0, 200_000.0, math.inf):
            with self.assertRaises(GasRefillError):
                start_refill(
                    initial_refill(FULL_BANKS),
                    bank="B",
                    cell="PZ-HAB-04",
                    setpoint_pa=setpoint,
                    actor="#7",
                    request_id="c" * 32,
                    now_s=1.0,
                )
        both: RefillLedger = start_refill(
            ledger,
            bank="B",
            cell="PZ-HAB-03",
            setpoint_pa=101_325.0,
            actor="#8",
            request_id="d" * 32,
            now_s=1001.0,
        )
        self.assertEqual(set(both["jobs"]), {"A", "B"})

    def test_delivery_cannot_exceed_stock_and_is_audited(self) -> None:
        ledger: RefillLedger = start_refill(
            initial_refill({"A": 5.0, "B": 0.0}),
            bank="A",
            cell="PZ-HAB-03",
            setpoint_pa=101_325.0,
            actor="#7",
            request_id="e" * 32,
            now_s=0.0,
        )
        ledger = record_delivery(ledger, bank="A", kg=3.0)
        self.assertTrue(reconciles_with_inventory(ledger, "A", 2.0))
        self.assertFalse(reconciles_with_inventory(ledger, "A", 2.5))
        with self.assertRaises(GasRefillError):
            record_delivery(ledger, bank="A", kg=2.5)
        with self.assertRaises(GasRefillError):
            record_delivery(ledger, bank="B", kg=0.1)
        closed: RefillLedger = stop_refill(
            ledger, bank="A", reason="bank_exhausted", now_s=200.0
        )
        self.assertEqual(closed["jobs"], {})
        self.assertEqual(closed["history"][-1]["delivered_kg"], 3.0)
        self.assertEqual(closed["delivered_kg"]["A"], 3.0)

    def test_exhausted_bank_cannot_start(self) -> None:
        with self.assertRaises(GasRefillError):
            start_refill(
                initial_refill({"A": 0.0, "B": 2750.0}),
                bank="A",
                cell="PZ-HAB-03",
                setpoint_pa=101_325.0,
                actor="#7",
                request_id="f" * 32,
                now_s=0.0,
            )

    def test_tampered_ledgers_are_rejected_not_repaired(self) -> None:
        good: RefillLedger = _started()
        cases: list[dict[str, Any]] = []
        over: dict[str, Any] = copy.deepcopy(dict(good))
        over["delivered_kg"]["A"] = 3000.0
        cases.append(over)
        stray: dict[str, Any] = copy.deepcopy(dict(good))
        stray["jobs"]["C"] = stray["jobs"]["A"]
        cases.append(stray)
        unbound: dict[str, Any] = copy.deepcopy(dict(good))
        unbound["jobs"]["A"]["cell"] = "HAB-03"
        cases.append(unbound)
        extra: dict[str, Any] = copy.deepcopy(dict(good))
        extra["refund_kg"] = 1.0
        cases.append(extra)
        case: dict[str, Any]
        for case in cases:
            with self.assertRaises(GasRefillError):
                validate_refill(case)

    def test_history_is_bounded(self) -> None:
        ledger: RefillLedger = initial_refill(FULL_BANKS)
        index: int
        for index in range(MAX_HISTORY + 5):
            ledger = start_refill(
                ledger,
                bank="A",
                cell="PZ-HAB-03",
                setpoint_pa=101_325.0,
                actor="#7",
                request_id=f"{index:032x}",
                now_s=float(index),
            )
            ledger = stop_refill(
                ledger, bank="A", reason="operator_stop", now_s=float(index)
            )
        self.assertEqual(len(ledger["history"]), MAX_HISTORY)
        self.assertEqual(ledger["history"][-1]["request_id"], f"{MAX_HISTORY + 4:032x}")

    def test_json_round_trip(self) -> None:
        ledger: RefillLedger = record_delivery(_started(), bank="A", kg=1.25)
        restored: RefillLedger = validate_refill(json.loads(json.dumps(ledger)))
        self.assertEqual(restored, ledger)


class Metering(unittest.TestCase):
    volume_m3: float = 2500.0
    temperature_k: float = 293.15

    def _mass(self, pressure_pa: float) -> float:
        return mass_at_pressure(
            pressure_pa=pressure_pa,
            volume_m3=self.volume_m3,
            temperature_k=self.temperature_k,
        )

    def test_rate_limited_by_rated_regulator(self) -> None:
        kg: float = deliverable_kg(
            mass_kg=self._mass(60_000.0),
            volume_m3=self.volume_m3,
            temperature_k=self.temperature_k,
            setpoint_pa=101_325.0,
            bank_kg=2750.0,
            seconds=10.0,
        )
        self.assertAlmostEqual(kg, RATED_KG_S * 10.0, places=12)

    def test_stops_exactly_at_setpoint_and_never_overfills(self) -> None:
        near: float = self._mass(101_325.0) - 0.05
        kg: float = deliverable_kg(
            mass_kg=near,
            volume_m3=self.volume_m3,
            temperature_k=self.temperature_k,
            setpoint_pa=101_325.0,
            bank_kg=2750.0,
            seconds=10.0,
        )
        self.assertAlmostEqual(kg, 0.05, places=9)
        self.assertEqual(
            deliverable_kg(
                mass_kg=self._mass(102_000.0),
                volume_m3=self.volume_m3,
                temperature_k=self.temperature_k,
                setpoint_pa=101_325.0,
                bank_kg=2750.0,
                seconds=10.0,
            ),
            0.0,
        )

    def test_limited_by_remaining_stock(self) -> None:
        kg: float = deliverable_kg(
            mass_kg=0.0,
            volume_m3=self.volume_m3,
            temperature_k=self.temperature_k,
            setpoint_pa=101_325.0,
            bank_kg=0.1,
            seconds=10.0,
        )
        self.assertAlmostEqual(kg, 0.1, places=12)

    def test_full_arc_refill_takes_hours_not_seconds(self) -> None:
        missing_kg: float = 3100.0
        hours: float = missing_kg / (RATED_KG_S * 3600.0)
        self.assertGreater(hours, 30.0)


class AuthoredNetworkRoutes(unittest.TestCase):
    """Route physics over the real v0.5 repressurisation graph."""

    @classmethod
    def setUpClass(cls) -> None:
        data: dict[str, Any] = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        nodes: list[dict[str, Any]] = [
            n for n in data["service_nodes"] if n["network"] == NETWORK
        ]
        cls.edges = [e for e in data["service_edges"] if e["network"] == NETWORK]
        cls.isolators = {
            i["id"]: i for i in data["isolation_points"] if i["network"] == NETWORK
        }
        spaces: dict[str, dict[str, Any]] = {s["id"]: s for s in data["spaces"]}
        equipment: dict[str, dict[str, Any]] = {e["id"]: e for e in data["equipment"]}
        cls.node_owner = {
            n["id"]: n["owner_id"] for n in nodes if n["owner_type"] == "equipment"
        }
        cls.node_cells = {}
        node: dict[str, Any]
        for node in nodes:
            if node["kind"] == "pressure_cell_tap":
                cls.node_cells[node["id"]] = spaces[node["owner_id"]]["pressure_zone"]
            elif node["kind"] == "hab_makeup_manifold":
                attrs: dict[str, Any] = equipment[node["owner_id"]]["attributes"]
                cls.node_cells[node["id"]] = attrs["target_pressure_zone_id"]

    edges: list[dict[str, Any]]
    isolators: dict[str, dict[str, Any]]
    node_owner: dict[str, str]
    node_cells: dict[str, str]

    def _route(self, opened: set[str]) -> list[RouteEdge]:
        routes: list[RouteEdge] = []
        edge: dict[str, Any]
        for edge in self.edges:
            states: list[bool] = [
                iso_id in opened or self.isolators[iso_id]["current_state"] == "open"
                for iso_id in edge["isolator_ids"]
            ]
            routes.append(
                {"a": edge["from_node"], "b": edge["to_node"], "conducts": all(states)}
            )
        return routes

    def _blocked(self, failed: frozenset[str]) -> frozenset[str]:
        return frozenset(n for n, owner in self.node_owner.items() if owner in failed)

    def test_authored_network_serves_77_cells_including_all_hab_arcs(self) -> None:
        served: set[str] = set(self.node_cells.values())
        self.assertEqual(len(served), 77)
        self.assertTrue({f"PZ-HAB-{i:02d}" for i in range(1, 9)} <= served)

    def test_as_found_valves_deliver_nothing(self) -> None:
        bank: str
        for bank in REGULATORS:
            cells: frozenset[str] = reachable_cells(
                start_node=REGULATORS[bank]["bank_node"],
                edges=self._route(set()),
                blocked_nodes=frozenset(),
                node_cells=self.node_cells,
            )
            self.assertEqual(cells, frozenset())

    def test_every_valve_open_reaches_all_served_cells_from_either_bank(self) -> None:
        bank: str
        for bank in REGULATORS:
            cells: frozenset[str] = reachable_cells(
                start_node=REGULATORS[bank]["bank_node"],
                edges=self._route(set(self.isolators)),
                blocked_nodes=frozenset(),
                node_cells=self.node_cells,
            )
            self.assertEqual(cells, frozenset(self.node_cells.values()))

    def test_failed_regulator_or_bank_blocks_its_side(self) -> None:
        cells: frozenset[str] = reachable_cells(
            start_node=REGULATORS["A"]["bank_node"],
            edges=self._route(set(self.isolators)),
            blocked_nodes=self._blocked(frozenset({"GAS-REFILL-REG-A"})),
            node_cells=self.node_cells,
        )
        self.assertEqual(cells, frozenset())
        cells = reachable_cells(
            start_node=REGULATORS["B"]["bank_node"],
            edges=self._route(set(self.isolators)),
            blocked_nodes=self._blocked(frozenset({"GAS-REFILL-BANK-B"})),
            node_cells=self.node_cells,
        )
        self.assertEqual(cells, frozenset())

    def test_failed_hab_manifold_cuts_only_its_arc(self) -> None:
        cells: frozenset[str] = reachable_cells(
            start_node=REGULATORS["A"]["bank_node"],
            edges=self._route(set(self.isolators)),
            blocked_nodes=self._blocked(frozenset({"GAS-HAB-03-MAN"})),
            node_cells=self.node_cells,
        )
        self.assertNotIn("PZ-HAB-03", cells)
        self.assertIn("PZ-HAB-04", cells)


if __name__ == "__main__":
    unittest.main()
