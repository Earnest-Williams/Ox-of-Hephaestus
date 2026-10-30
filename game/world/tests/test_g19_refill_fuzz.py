"""Seeded, replayable fuzzing of the G19 casualty-refill kernel.

Model-based ledger fuzzing, metering bounds and differential route checks over
the real v0.5 repressurisation graph. Every failure message carries the seed
and step so the counterexample replays exactly. Scale with OX_FUZZ_SCALE.
"""

from __future__ import annotations

import json
import math
import os
import random
import unittest
from collections import deque
from pathlib import Path
from typing import Any, Final

from world.ship_gas_refill import (
    EPS_KG,
    MAX_BANK_KG,
    MAX_HISTORY,
    MAX_SETPOINT_PA,
    MIN_SETPOINT_PA,
    NETWORK,
    RATED_KG_S,
    REGULATORS,
    STOP_REASONS,
    GasRefillError,
    RefillLedger,
    RouteEdge,
    bank_remaining_kg,
    deliverable_kg,
    initial_refill,
    mass_at_pressure,
    reachable_cells,
    record_delivery,
    start_refill,
    stop_refill,
    validate_refill,
)

SCALE: Final[int] = max(1, int(os.environ.get("OX_FUZZ_SCALE", "1")))
SEEDS: Final[tuple[int, ...]] = (0x19A0, 0x6A5, 0xBA4C, 0x7E57)
CANDIDATE: Final[Path] = (
    Path(__file__).resolve().parents[3] / "design/ship/ox_full_ship_v0.5_candidate.json"
)
BANKS: Final[tuple[str, ...]] = tuple(REGULATORS)
CELLS: Final[tuple[str, ...]] = ("PZ-HAB-03", "PZ-TRUNK-A-BOW", "PZ-LOGI-DR-02")


def _awkward_number(rng: random.Random) -> float:
    choice: int = rng.randrange(8)
    if choice == 0:
        return math.nan
    if choice == 1:
        return math.inf
    if choice == 2:
        return -rng.uniform(0.0, 10.0)
    if choice == 3:
        return 0.0
    return rng.uniform(0.0, 40.0)


class RefillLedgerModelFuzz(unittest.TestCase):
    """The ledger must behave exactly like a simple shadow model."""

    def test_random_operation_sequences_match_shadow_model(self) -> None:
        seed: int
        for seed in SEEDS:
            rng: random.Random = random.Random(seed)
            stock: dict[str, float] = {b: rng.uniform(0.0, MAX_BANK_KG) for b in BANKS}
            if rng.random() < 0.3:
                stock[rng.choice(BANKS)] = 0.0
            ledger: RefillLedger = initial_refill(stock)
            delivered: dict[str, float] = {b: 0.0 for b in BANKS}
            jobs: dict[str, float] = {}
            history: int = 0
            step: int
            for step in range(400 * SCALE):
                label: str = f"seed={seed:#x} step={step}"
                bank: str = rng.choice(BANKS)
                op: int = rng.randrange(3)
                remaining: float = max(0.0, stock[bank] - delivered[bank])
                if op == 0:
                    setpoint: float = rng.choice(
                        (
                            rng.uniform(MIN_SETPOINT_PA, MAX_SETPOINT_PA),
                            rng.uniform(0.0, 2 * MAX_SETPOINT_PA),
                        )
                    )
                    should_work: bool = (
                        bank not in jobs
                        and MIN_SETPOINT_PA <= setpoint <= MAX_SETPOINT_PA
                        and remaining > EPS_KG
                    )
                    try:
                        ledger = start_refill(
                            ledger,
                            bank=bank,
                            cell=rng.choice(CELLS),
                            setpoint_pa=setpoint,
                            actor="#9",
                            request_id=f"{step:032x}",
                            now_s=float(step),
                        )
                        self.assertTrue(should_work, label + " accepted bad start")
                        jobs[bank] = 0.0
                    except GasRefillError:
                        self.assertFalse(should_work, label + " refused good start")
                elif op == 1:
                    kg: float = (
                        rng.uniform(0.0, remaining)
                        if rng.random() < 0.7
                        else _awkward_number(rng) + remaining * rng.random() * 2
                    )
                    should_work = (
                        bank in jobs
                        and math.isfinite(kg)
                        and 0.0 <= kg
                        and kg <= remaining + EPS_KG
                    )
                    try:
                        ledger = record_delivery(ledger, bank=bank, kg=kg)
                        self.assertTrue(should_work, label + f" accepted kg={kg!r}")
                        delivered[bank] += kg
                        jobs[bank] += kg
                    except GasRefillError:
                        self.assertFalse(should_work, label + f" refused kg={kg!r}")
                else:
                    reason: str = rng.choice(sorted(STOP_REASONS) + ["refund", ""])
                    should_work = bank in jobs and reason in STOP_REASONS
                    try:
                        ledger = stop_refill(
                            ledger, bank=bank, reason=reason, now_s=float(step)
                        )
                        self.assertTrue(should_work, label + " accepted bad stop")
                        jobs.pop(bank)
                        history += 1
                    except GasRefillError:
                        self.assertFalse(should_work, label + " refused good stop")
                validate_refill(ledger)
                restored: RefillLedger = validate_refill(json.loads(json.dumps(ledger)))
                self.assertEqual(restored, ledger, label)
                b: str
                for b in BANKS:
                    self.assertAlmostEqual(
                        ledger["delivered_kg"][b], delivered[b], places=6, msg=label
                    )
                    self.assertLessEqual(
                        ledger["delivered_kg"][b], stock[b] + EPS_KG, label
                    )
                    self.assertAlmostEqual(
                        bank_remaining_kg(ledger, b),
                        max(0.0, stock[b] - delivered[b]),
                        places=6,
                        msg=label,
                    )
                self.assertEqual(set(ledger["jobs"]), set(jobs), label)
                self.assertEqual(
                    len(ledger["history"]), min(history, MAX_HISTORY), label
                )


class MeteringFuzz(unittest.TestCase):
    def test_metering_never_exceeds_rate_stock_or_setpoint(self) -> None:
        seed: int
        for seed in SEEDS:
            rng: random.Random = random.Random(seed ^ 0xF00D)
            step: int
            for step in range(2000 * SCALE):
                label: str = f"seed={seed:#x} step={step}"
                volume: float = rng.uniform(1.0, 9000.0)
                temperature: float = rng.uniform(240.0, 330.0)
                setpoint: float = rng.uniform(MIN_SETPOINT_PA, MAX_SETPOINT_PA)
                target_kg: float = mass_at_pressure(
                    pressure_pa=setpoint, volume_m3=volume, temperature_k=temperature
                )
                # Half the cases start within two metering steps of setpoint:
                # the only region where an overshoot bug can show itself.
                mass: float = (
                    max(0.0, target_kg - rng.uniform(0.0, 2.0 * RATED_KG_S * 10.0))
                    if rng.random() < 0.5
                    else mass_at_pressure(
                        pressure_pa=rng.uniform(0.0, 1.1 * setpoint),
                        volume_m3=volume,
                        temperature_k=temperature,
                    )
                )
                stock: float = rng.choice(
                    (0.0, rng.uniform(0.0, 5.0), rng.uniform(0.0, MAX_BANK_KG))
                )
                seconds: float = rng.uniform(0.0, 10.0)
                kg: float = deliverable_kg(
                    mass_kg=mass,
                    volume_m3=volume,
                    temperature_k=temperature,
                    setpoint_pa=setpoint,
                    bank_kg=stock,
                    seconds=seconds,
                )
                target: float = mass_at_pressure(
                    pressure_pa=setpoint, volume_m3=volume, temperature_k=temperature
                )
                self.assertGreaterEqual(kg, 0.0, label)
                self.assertLessEqual(kg, RATED_KG_S * seconds + 1e-12, label)
                self.assertLessEqual(kg, stock + 1e-12, label)
                self.assertLessEqual(mass + kg, max(mass, target) + 1e-9, label)

    def test_nonphysical_inputs_are_rejected(self) -> None:
        rng: random.Random = random.Random(0xBAD)
        bad: tuple[float, ...] = (math.nan, math.inf, -1.0)
        step: int
        for step in range(200 * SCALE):
            args: dict[str, float] = {
                "mass_kg": 1.0,
                "volume_m3": 100.0,
                "temperature_k": 293.0,
                "setpoint_pa": 101_325.0,
                "bank_kg": 10.0,
                "seconds": 10.0,
            }
            key: str = rng.choice(sorted(args))
            args[key] = rng.choice(bad)
            with self.assertRaises(GasRefillError, msg=f"step={step} {key}"):
                deliverable_kg(**args)


def _oracle_cells(
    nodes: set[str],
    edges: list[dict[str, Any]],
    open_valves: set[str],
    failed_nodes: set[str],
    start: str,
    node_cells: dict[str, str],
) -> frozenset[str]:
    """Independent reference: union-find over conducting edges."""
    parent: dict[str, str] = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edge: dict[str, Any]
    for edge in edges:
        a: str = edge["from_node"]
        b: str = edge["to_node"]
        if a in failed_nodes or b in failed_nodes:
            continue
        if all(v in open_valves for v in edge["isolator_ids"]):
            parent[find(a)] = find(b)
    if start in failed_nodes:
        return frozenset()
    root: str = find(start)
    return frozenset(c for n, c in node_cells.items() if find(n) == root)


class RouteDifferentialFuzz(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data: dict[str, Any] = json.loads(CANDIDATE.read_text(encoding="utf-8"))
        node_rows: list[dict[str, Any]] = [
            n for n in data["service_nodes"] if n["network"] == NETWORK
        ]
        cls.nodes = {n["id"] for n in node_rows}
        cls.edges = [e for e in data["service_edges"] if e["network"] == NETWORK]
        cls.valves = sorted(
            i["id"] for i in data["isolation_points"] if i["network"] == NETWORK
        )
        cls.as_found_open = {
            i["id"]
            for i in data["isolation_points"]
            if i["network"] == NETWORK and i["current_state"] == "open"
        }
        spaces: dict[str, dict[str, Any]] = {s["id"]: s for s in data["spaces"]}
        equipment: dict[str, dict[str, Any]] = {e["id"]: e for e in data["equipment"]}
        cls.owner_nodes = {}
        cls.node_cells = {}
        node: dict[str, Any]
        for node in node_rows:
            if node["owner_type"] == "equipment":
                cls.owner_nodes.setdefault(node["owner_id"], set()).add(node["id"])
            if node["kind"] == "pressure_cell_tap":
                cls.node_cells[node["id"]] = spaces[node["owner_id"]]["pressure_zone"]
            elif node["kind"] == "hab_makeup_manifold":
                attrs: dict[str, Any] = equipment[node["owner_id"]]["attributes"]
                cls.node_cells[node["id"]] = attrs["target_pressure_zone_id"]

    nodes: set[str]
    edges: list[dict[str, Any]]
    valves: list[str]
    as_found_open: set[str]
    owner_nodes: dict[str, set[str]]
    node_cells: dict[str, str]

    def _cells(self, opened: set[str], failed: set[str], bank: str) -> frozenset[str]:
        blocked: frozenset[str] = frozenset(
            n for owner in failed for n in self.owner_nodes.get(owner, ())
        )
        edges: list[RouteEdge] = [
            {
                "a": e["from_node"],
                "b": e["to_node"],
                "conducts": all(v in opened for v in e["isolator_ids"]),
            }
            for e in self.edges
        ]
        return reachable_cells(
            start_node=REGULATORS[bank]["bank_node"],
            edges=edges,
            blocked_nodes=blocked,
            node_cells=self.node_cells,
        )

    def test_random_lineups_match_oracle_and_are_monotone(self) -> None:
        owners: list[str] = sorted(self.owner_nodes)
        served: frozenset[str] = frozenset(self.node_cells.values())
        seed: int
        for seed in SEEDS:
            rng: random.Random = random.Random(seed ^ 0xC0DE)
            step: int
            for step in range(150 * SCALE):
                label: str = f"seed={seed:#x} step={step}"
                p_open: float = rng.choice((0.3, 0.7, 0.9, 0.97, 1.0))
                opened: set[str] = {
                    v
                    for v in self.valves
                    if v in self.as_found_open or rng.random() < p_open
                }
                failed: set[str] = {o for o in owners if rng.random() < 0.05}
                bank: str = rng.choice(BANKS)
                got: frozenset[str] = self._cells(opened, failed, bank)
                blocked: set[str] = {
                    n for o in failed for n in self.owner_nodes.get(o, ())
                }
                want: frozenset[str] = _oracle_cells(
                    self.nodes,
                    self.edges,
                    opened,
                    blocked,
                    REGULATORS[bank]["bank_node"],
                    self.node_cells,
                )
                self.assertEqual(got, want, label)
                self.assertTrue(got <= served, label)
                closed: list[str] = sorted(set(self.valves) - opened)
                if closed:
                    more: frozenset[str] = self._cells(
                        opened | {rng.choice(closed)}, failed, bank
                    )
                    self.assertTrue(got <= more, label + " opening removed cells")
                if opened:
                    fewer: frozenset[str] = self._cells(
                        opened - {rng.choice(sorted(opened))}, failed, bank
                    )
                    self.assertTrue(fewer <= got, label + " closing added cells")
                worse: frozenset[str] = self._cells(
                    opened, failed | {rng.choice(owners)}, bank
                )
                self.assertTrue(worse <= got, label + " a failure added cells")

    def test_bfs_and_oracle_agree_on_every_single_valve_lineup(self) -> None:
        """Opening everything except one valve: exact agreement for all 143."""
        everything: set[str] = set(self.valves)
        valve: str
        for valve in self.valves:
            opened: set[str] = everything - {valve}
            bank: str
            for bank in BANKS:
                want: frozenset[str] = _oracle_cells(
                    self.nodes,
                    self.edges,
                    opened,
                    set(),
                    REGULATORS[bank]["bank_node"],
                    self.node_cells,
                )
                self.assertEqual(self._cells(opened, set(), bank), want, valve)


if __name__ == "__main__":
    unittest.main()
