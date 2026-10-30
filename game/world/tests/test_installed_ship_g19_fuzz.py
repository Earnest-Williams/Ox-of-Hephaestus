"""Seeded fuzzing of the installed G19 world: chunking, crew actions, corruption.

F4 differential tick chunking, F5 stateful crew-action sequences with replays
and request-ID collisions, and F6 (opt-in, exploratory) single-field
corruption of persisted state. Each scenario runs inside database savepoints
so one commissioned ship serves many trials. Failures name seed and step.

Environment: OX_FUZZ_SCALE multiplies trial counts; OX_FUZZ_EXPLORE=1 enables
F6; OX_FUZZ_REPORT names the F6 JSON report path.
"""

from __future__ import annotations

import json
import math
import os
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final
from unittest import skipUnless

from django.db import IntegrityError, transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.continuous_ship_physics import (
    PhysicsError,
    _clock,
    _topology,
    arm_continuous_physics,
    commission_g19_crew_physiology,
    commission_g19_electrical,
    commission_g19_eva,
    commission_g19_hull,
    commission_g19_instrumentation,
    commission_g19_repairs,
    commission_g19_unclassified_spaces,
    commission_g19_water,
    configure_scenario_casualty,
    configure_water_casualty,
    crew_physical_action,
    tick_continuous_physics,
)
from world.full_ship_operations import (
    initialize_nominal_atmosphere,
    install_candidate,
    install_pressure_cells,
    set_component_condition,
    set_isolator,
    state,
)
from world.models import CanonicalShipState, WorkReceipt
from world.ship_gas_refill import REGULATORS
from world.ship_world import build_canonical_ship, find_ship_space

SCALE: Final[int] = max(1, int(os.environ.get("OX_FUZZ_SCALE", "1")))
EXPLORE: Final[bool] = os.environ.get("OX_FUZZ_EXPLORE") == "1"
# Crew physiology integrates a call's breathing after that call's physics
# substeps (operator splitting), so chunking moves ~1e-7 of a cell's mass.
# Before fix F4-1 the same scenario moved ~1e-2 and cooled occupied cells.
REL_TOL: Final[float] = 1e-6
# Trace species (CO2) show the same splitting as a few milligrams.
ABS_TOL: Final[float] = 1e-5
# Per-call bookkeeping that legitimately depends on how time is chunked: the
# tick counter, the per-call summary report, and instrument sampling.
CHUNK_DEPENDENT: Final[frozenset[str]] = frozenset(
    {"ticks", "summary", "instrumentation"}
)

TRUNK_LINEUP: Final[tuple[tuple[str, str], ...]] = (
    ("ISO-GAS-BANK-A", "WATER-FWD"),
    ("ISO-GAS-REG-A", "ENV-FWD"),
    ("ISO-GAS-HDR-TRUNK-A-BOW", "TRUNK-A-BOW"),
    ("ISO-GAS-TAP-TRUNK-A-BOW", "TRUNK-A-BOW"),
)
REFILL_VALVES: Final[tuple[tuple[str, str], ...]] = TRUNK_LINEUP + (
    ("ISO-GAS-ROT-FIX-A", "ROTARY-UTIL-A"),
    ("ISO-GAS-ROT-ROT-A", "ROTARY-UTIL-A"),
    ("ISO-GAS-HAB-FEED-A", "HAB-06-SERVICE-GALLERY"),
    ("ISO-GAS-BANK-B", "STORE-FLUID-AFT"),
    ("ISO-GAS-REG-B", "ENV-AFT"),
)


def _snapshot() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    row: Any
    for row in CanonicalShipState.objects.order_by("key"):
        rows[row.key] = {
            "quantity": row.quantity,
            "setting": row.setting,
            "condition": row.condition,
            "details": row.details,
        }
    return rows


def _diff(a: Any, b: Any, path: str, out: list[str], limit: int = 2000) -> None:
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        key: str
        for key in sorted(set(a) | set(b)):
            if key in CHUNK_DEPENDENT and path.endswith(
                "meta:continuous-physics.details"
            ):
                continue
            if key not in a or key not in b:
                out.append(f"{path}.{key}: present in only one run")
            else:
                _diff(a[key], b[key], f"{path}.{key}", out, limit)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} != {len(b)}")
            return
        index: int
        for index, (x, y) in enumerate(zip(a, b, strict=True)):
            _diff(x, y, f"{path}[{index}]", out, limit)
        return
    if (
        isinstance(a, int | float)
        and isinstance(b, int | float)
        and not isinstance(a, bool)
        and not isinstance(b, bool)
    ):
        if math.isnan(a) and math.isnan(b):
            return
        if not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            out.append(f"{path}: {a!r} != {b!r}")
        return
    if a != b:
        out.append(f"{path}: {a!r} != {b!r}")


def _leaves(node: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    if isinstance(node, dict):
        key: Any
        for key in node:
            yield from _leaves(node[key], path + (key,))
    elif isinstance(node, list):
        index: int
        for index in range(len(node)):
            yield from _leaves(node[index], path + (index,))
    else:
        yield path


def _get(node: Any, path: tuple[Any, ...]) -> Any:
    part: Any
    for part in path:
        node = node[part]
    return node


class _InstalledFuzzBase(EvenniaTestCase):  # type: ignore[misc]
    def setUp(self) -> None:
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        ship: dict[str, Any] = build_ship()
        self.worker: Any = ship["watch"]
        self.go("ENG-CONTROL")
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_electrical(operator_approved=True)
        commission_g19_water(operator_approved=True)
        commission_g19_repairs(operator_approved=True)
        commission_g19_hull(operator_approved=True)
        commission_g19_eva(operator_approved=True)
        commission_g19_crew_physiology(
            operator_approved=True, actor_dbrefs=[self.worker.dbref]
        )
        commission_g19_unclassified_spaces(operator_approved=True)
        commission_g19_instrumentation(operator_approved=True)
        self.now: float = 1000.0
        self.serial: int = 0x1900000

    def go(self, room: str) -> None:
        self.assertTrue(self.worker.move_to(find_ship_space(room), quiet=True), room)

    def next_id(self) -> str:
        self.serial += 1
        return f"{self.serial:032x}"

    def act(self, action: str, target: str, value: str) -> dict[str, Any]:
        result: dict[str, Any] = crew_physical_action(
            self.worker, self.next_id(), action, target, value
        )
        return result

    def advance(self, seconds: float) -> None:
        end: float = self.now + seconds
        while self.now < end:
            self.now = min(end, self.now + 60.0)
            tick_continuous_physics(now_game_time=self.now)

    def casualty_world(self, scenario: str = "full") -> None:
        """Fire, contaminated water, severed feeder and an active refill job.

        `scenario` selects parts for isolating a finding: "full", "quiet" (no
        casualties), "quietwarm" (quiet after a warm-up), "norefill"
        (casualties, no refill) or "refillonly".
        """
        if scenario in {"full", "norefill"}:
            configure_scenario_casualty(
                "PZ-HAB-01", operator=True, fire_fuel_kg=12, fire_burn_kg_s=0.03
            )
            working: float = _clock().details["water"]["working_kg"]
            configure_water_casualty(operator=True, contaminated_kg=0.3 * working)
            set_component_condition("edge", "EDGE-GEN-M", "severed", operator=True)
        if scenario in {"quiet", "quietwarm"}:
            if scenario == "quietwarm":
                parked: str | None = os.environ.get("OX_FUZZ_WORKER_ROOM")
                if parked:
                    self.go(parked)
                self.advance(float(os.environ.get("OX_FUZZ_WARMUP", "600")))
            return
        configure_scenario_casualty("PZ-TRUNK-A-BOW", operator=True, leak_kg_s=0.2)
        self.advance(300.0)
        configure_scenario_casualty("PZ-TRUNK-A-BOW", operator=True, leak_kg_s=0.0)
        if scenario == "norefill":
            return
        valve: str
        room: str
        for valve, room in TRUNK_LINEUP:
            self.go(room)
            self.act("switch", valve, "open")
        self.go("ENV-FWD")
        self.act("gas_refill", "PZ-TRUNK-A-BOW", "start:A")
        self.assertIn("A", _clock().details["gas_refill"]["jobs"])


class TickChunkingDifferentialFuzz(_InstalledFuzzBase):
    """F4: aligned tick splits of the same interval reach the same ship state."""

    def run_plan(self, start: float, chunks: list[float]) -> dict[str, Any]:
        now: float = start
        chunk: float
        for chunk in chunks:
            now += chunk
            tick_continuous_physics(now_game_time=now)
        return _snapshot()

    def test_random_aligned_chunkings_match_ten_second_baseline(self) -> None:
        self.casualty_world(os.environ.get("OX_FUZZ_F4_SCENARIO", "full"))
        start: float = self.now
        total: float = float(os.environ.get("OX_FUZZ_F4_TOTAL", "600"))
        fixed: str | None = os.environ.get("OX_FUZZ_F4_CHUNKS")
        sid: str = transaction.savepoint()
        baseline: dict[str, Any] = self.run_plan(start, [10.0] * int(total // 10))
        transaction.savepoint_rollback(sid)
        trial: int
        for trial in range(3 * SCALE):
            rng: random.Random = random.Random(0xC4A0 + trial)
            chunks: list[float] = []
            remaining: float = total
            if fixed:
                chunks = [float(x) for x in fixed.split(",")]
                remaining = 0.0
            while remaining > 0:
                size: float = float(min(remaining, 10 * rng.randint(1, 6)))
                chunks.append(size)
                remaining -= size
            sid = transaction.savepoint()
            got: dict[str, Any] = self.run_plan(start, chunks)
            transaction.savepoint_rollback(sid)
            diffs: list[str] = []
            _diff(baseline, got, "state", diffs)
            dump: str | None = os.environ.get("OX_FUZZ_DIFF_DUMP")
            if dump:
                Path(dump).write_text("\n".join(diffs))
            self.assertEqual(
                diffs, [], f"trial={trial} chunks={chunks} first differences: {diffs}"
            )


class CrewActionSequenceFuzz(_InstalledFuzzBase):
    """F5: random receipted crew actions keep replay, refusal and mass invariants."""

    def menu(self) -> list[tuple[str, str, str, str]]:
        """(room, action, target, value) candidates at their real stations."""
        options: list[tuple[str, str, str, str]] = []
        valve: str
        room: str
        for valve, room in REFILL_VALVES:
            options.append((room, "switch", valve, "open"))
            options.append((room, "switch", valve, "closed"))
        bank: str
        for bank, spec in REGULATORS.items():
            cell: str
            for cell in ("PZ-TRUNK-A-BOW", "PZ-HAB-03", "PZ-LOGI-BOW"):
                options.append((spec["station"], "gas_refill", cell, "start:" + bank))
                options.append((spec["station"], "gas_refill", cell, "stop:" + bank))
        gen_room: str = state("isolator", "ISO-GEN-M").space_id
        options.append((gen_room, "switch", "ISO-GEN-M", "open"))
        options.append((gen_room, "switch", "ISO-GEN-M", "closed"))
        options.append(("ENG-CONTROL", "plant", "GEN-M", "off"))
        options.append(("ENG-CONTROL", "plant", "GEN-M", "on"))
        # Unsuited crew may only stand in a real pressure cell: the clock
        # refuses to tick with a person in an unclassified room (finding F5-1).
        zones: dict[str, Any] = _topology()[0]
        cells: set[str] = {
            row.source_id
            for row in CanonicalShipState.objects.filter(category="pressure")
        }
        return [o for o in options if zones.get(o[0]) in cells]

    def bank_kg(self) -> dict[str, float]:
        return {
            b: float((state("inventory", s["inventory"]).quantity or 0.0) * 1000.0)
            for b, s in REGULATORS.items()
        }

    def test_random_action_sequences_hold_receipt_and_mass_invariants(self) -> None:
        configure_scenario_casualty("PZ-TRUNK-A-BOW", operator=True, leak_kg_s=0.2)
        self.advance(300.0)
        configure_scenario_casualty("PZ-TRUNK-A-BOW", operator=True, leak_kg_s=0.0)
        options: list[tuple[str, str, str, str]] = self.menu()
        seed: int
        for seed in (0x5EED, 0xACED):
            sid: str = transaction.savepoint()
            rng: random.Random = random.Random(seed)
            succeeded: dict[str, tuple[str, str, str, dict[str, Any]]] = {}
            lost: float = _clock().details["lost_to_space_kg"]
            banks: dict[str, float] = self.bank_kg()
            outcomes: dict[str, int] = {
                "ok": 0,
                "refused": 0,
                "replay": 0,
                "collision": 0,
                "tick": 0,
            }
            step: int
            for step in range(60 * SCALE):
                label: str = f"seed={seed:#x} step={step}"
                roll: float = rng.random()
                if roll < 0.2 and succeeded:
                    rid: str = rng.choice(sorted(succeeded))
                    action, target, value, receipt = succeeded[rid]
                    again: dict[str, Any] = crew_physical_action(
                        self.worker, rid, action, target, value
                    )
                    self.assertEqual(again, receipt, label + " replay differs")
                    outcomes["replay"] += 1
                elif roll < 0.25 and succeeded:
                    rid = rng.choice(sorted(succeeded))
                    action, target, value, _ = succeeded[rid]
                    before: dict[str, Any] = _snapshot()
                    with self.assertRaises(PermissionError, msg=label):
                        crew_physical_action(
                            self.worker, rid, action, target, value + "-x"
                        )
                    self.assertEqual(_snapshot(), before, label + " collision mutated")
                    outcomes["collision"] += 1
                elif roll < 0.45:
                    self.go("ENG-CONTROL")
                    seconds: float = float(10 * rng.randint(1, 12))
                    self.now += seconds
                    tick_continuous_physics(now_game_time=self.now)
                    outcomes["tick"] += 1
                else:
                    room, action, target, value = rng.choice(options)
                    self.go(room)
                    rid = self.next_id()
                    before = _snapshot()
                    try:
                        receipt = crew_physical_action(
                            self.worker, rid, action, target, value
                        )
                    except (PhysicsError, PermissionError, ValueError) as exc:
                        self.assertFalse(
                            WorkReceipt.objects.filter(pk=rid).exists(),
                            f"{label} refused {action} {target} {value} "
                            f"left a receipt: {exc}",
                        )
                        self.assertEqual(
                            _snapshot(),
                            before,
                            f"{label} refused {action} {target} {value} mutated: {exc}",
                        )
                        outcomes["refused"] += 1
                    else:
                        self.assertEqual(receipt["status"], "succeeded", label)
                        self.assertEqual(
                            WorkReceipt.objects.filter(pk=rid).count(), 1, label
                        )
                        succeeded[rid] = (action, target, value, receipt)
                        outcomes["ok"] += 1
                clock: dict[str, Any] = _clock().details
                self.assertGreaterEqual(clock["lost_to_space_kg"], lost - 1e-9, label)
                lost = clock["lost_to_space_kg"]
                now_banks: dict[str, float] = self.bank_kg()
                b: str
                for b in REGULATORS:
                    self.assertLessEqual(now_banks[b], banks[b] + 1e-9, label)
                    ledger: dict[str, Any] | None = clock.get("gas_refill")
                    if ledger is not None:
                        self.assertAlmostEqual(
                            ledger["commissioned_kg"][b] - ledger["delivered_kg"][b],
                            now_banks[b],
                            places=6,
                            msg=label,
                        )
                banks = now_banks
                cell: Any
                for cell in CanonicalShipState.objects.filter(category="pressure"):
                    self.assertTrue(
                        cell.quantity is not None
                        and math.isfinite(cell.quantity)
                        and cell.quantity >= 0,
                        f"{label} {cell.key}",
                    )
            self.assertGreater(outcomes["ok"], 0, f"seed={seed:#x} {outcomes}")
            print(f"F5 seed={seed:#x} outcomes={outcomes}")
            transaction.savepoint_rollback(sid)


class G19PersistedSafetyRegressions(_InstalledFuzzBase):
    """Safety failures must not freeze unrelated systems or falsify interlocks."""

    def test_unknown_envelope_is_nonbreathable_but_other_systems_keep_ticking(self):
        from world.models import CanonicalShipEvent
        self.go("STORE-FLUID-AFT")  # deliberate operator-like displacement
        before = _clock().details["last_game_time"]
        self.advance(60)
        d = _clock().details
        self.assertEqual(d["last_game_time"], before + 60)
        self.assertEqual(d["crew_unverified_envelopes"][self.worker.dbref],
                         "STORE-FLUID-AFT")
        self.assertEqual(d["summary"]["crew_o2_used_this_tick_kg"], 0)
        self.assertEqual(d["summary"]["crew_unverified_envelope_alarms"],
                         {self.worker.dbref: "STORE-FLUID-AFT"})
        health = CanonicalShipState.objects.get(
            pk="crew_health:" + self.worker.dbref)
        self.assertEqual(health.details["hypoxia_s"], 60)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="g19_crew_unverified_envelope_alarm",
            actor_dbref=self.worker.dbref).count(), 1)
        self.advance(60)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="g19_crew_unverified_envelope_alarm",
            actor_dbref=self.worker.dbref).count(), 1)
        self.go("ENG-CONTROL")
        self.advance(60)
        self.assertEqual(_clock().details["crew_unverified_envelopes"], {})
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="g19_crew_envelope_alarm_cleared",
            actor_dbref=self.worker.dbref).count(), 1)

    def test_corrupt_authoritative_stocks_motion_and_pressure_fail_closed(self):
        from copy import deepcopy
        mutations = [
            ("stock", "INV-WATER-NORMAL", "quantity", 1e30),
            ("stock", "INV-SPARES", "quantity", 1e30),
            ("stock", "INV-REACTION", "quantity", 1e30),
            ("stock", "INV-FTL-FUEL", "quantity", None),
            ("motion", None, "velocity_m_s", [1e30, 0.0, 0.0]),
            ("motion", None, "propellant_kg", 1e30),
            ("pressure", "PZ-BOW-CMD", "quantity", 1e30),
        ]
        for family, name, field, bad in mutations:
            with self.subTest(family=family, name=name, field=field):
                sid = transaction.savepoint()
                try:
                    if family == "motion":
                        row = _clock(lock=True)
                        d = deepcopy(row.details)
                        d["motion"][field] = bad
                        row.details = d
                        row.save(update_fields=["details"])
                    else:
                        row = state("inventory" if family == "stock"
                                    else "pressure", name, lock=True)
                        setattr(row, field, bad)
                        row.save(update_fields=[field])
                    before = _snapshot()
                    with self.assertRaises((PhysicsError, ValueError)):
                        tick_continuous_physics(now_game_time=self.now + 10)
                    self.assertEqual(_snapshot(), before)
                finally:
                    transaction.savepoint_rollback(sid)

    def test_water_and_electrical_schema_corruption_is_refused_transactionally(self):
        from copy import deepcopy
        for ledger in ("water", "electrical"):
            for kind in ("extra", "missing", "wrong_container"):
                with self.subTest(ledger=ledger, kind=kind):
                    sid = transaction.savepoint()
                    try:
                        clock = _clock(lock=True)
                        details = deepcopy(clock.details)
                        if kind == "extra":
                            details[ledger]["fuzz_extra_field"] = True
                        elif kind == "missing":
                            key = ("working_kg" if ledger == "water" else "meter")
                            del details[ledger][key]
                        else:
                            key = ("cumulative" if ledger == "water" else "meter")
                            details[ledger][key] = "corrupt"
                        clock.details = details
                        clock.save(update_fields=["details"])
                        before = _snapshot()
                        with self.assertRaises((PhysicsError, ValueError)):
                            tick_continuous_physics(now_game_time=self.now + 10)
                        self.assertEqual(_snapshot(), before)
                    finally:
                        transaction.savepoint_rollback(sid)

    def test_corrupt_rotary_interlocks_and_motion_conditions_fail_closed(self):
        from copy import deepcopy
        from world.ship_motion_machinery import initial_rotors
        mutations = [
            ("rotors", "DR-01", "hardlock", None),
            ("rotors", "DR-01", "brake", 0),
            ("rotors", "DR-01", "indexing", "false"),
            ("rotors", "DR-01", "freight_collar", None),
            ("rotors", "HAB", "passenger_indexer", 0),
            ("rotors", "WR-01", "rpm", 1e30),
            ("motion", None, "drive_condition", "nominal-ish"),
            ("motion", None, "rcs_condition", None),
        ]
        for family, machine, field, bad in mutations:
            with self.subTest(family=family, machine=machine, field=field):
                sid = transaction.savepoint()
                try:
                    clock = _clock(lock=True)
                    details = deepcopy(clock.details)
                    target = details[family][machine] if machine else details[family]
                    target[field] = bad
                    clock.details = details
                    clock.save(update_fields=["details"])
                    before = _snapshot()
                    with self.assertRaisesRegex(PhysicsError, "rotary|Rotor|drive|RCS|propulsion|interlock"):
                        tick_continuous_physics(now_game_time=self.now + 10)
                    self.assertEqual(_snapshot(), before)
                finally:
                    transaction.savepoint_rollback(sid)


class _Rollback(Exception):
    """Sentinel: discard one corruption trial."""


CORRUPTIONS: Final[tuple[str, ...]] = (
    "nan",
    "inf",
    "negative",
    "string",
    "none",
    "drop",
    "extra",
    "huge",
)


def _corrupt(container: Any, key: Any, kind: str) -> bool:
    """Apply one corruption in place; False if it does not apply to this leaf."""
    value: Any = container[key]
    if kind in {"nan", "inf", "negative", "huge"}:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return False
        container[key] = {
            "nan": math.nan,
            "inf": math.inf,
            "negative": -abs(value) - 1.0,
            "huge": 1e30,
        }[kind]
        return True
    if kind == "string":
        container[key] = "corrupt"
        return True
    if kind == "none":
        container[key] = None
        return True
    if kind == "drop":
        if not isinstance(container, dict):
            return False
        del container[key]
        return True
    if kind == "extra":
        if not isinstance(container, dict):
            return False
        container["fuzz_extra_field"] = 1
        return True
    return False


@skipUnless(EXPLORE, "Exploratory corruption campaign; set OX_FUZZ_EXPLORE=1")
class PersistedStateCorruptionFuzz(_InstalledFuzzBase):
    """F6: does a single corrupted persisted field make the next tick fail closed?"""

    def _trial(
        self,
        row: Any,
        row_kind: str,
        mutated: Any,
        path: tuple[Any, ...],
        kind: str,
    ) -> tuple[str, str]:
        """Write one corruption, tick once, classify. The caller rolls back."""
        if row_kind == "inventory":
            row.quantity = mutated["quantity"]
            row.save(update_fields=["quantity"])
        else:
            details: dict[str, Any] = dict(row.details)
            details.update(mutated if row_kind == "clock" else mutated["details"])
            row.details = details
            row.save(update_fields=["details"])
        try:
            with transaction.atomic():
                tick_continuous_physics(now_game_time=self.now + 10.0)
        except (PhysicsError, ValueError) as exc:
            return "rejected", f"{type(exc).__name__}: {exc}"[:160]
        except Exception as exc:  # noqa: BLE001 - classifying crashes is the point
            return "crashed", f"{type(exc).__name__}: {exc}"[:160]
        fresh: Any = CanonicalShipState.objects.get(pk=row.key)
        after_root: Any = (
            {"quantity": fresh.quantity}
            if row_kind == "inventory"
            else (
                {path[0]: fresh.details.get(path[0])}
                if row_kind == "clock"
                else {"details": fresh.details}
            )
        )
        try:
            still: Any = _get(after_root, path[:-1])
            present: bool = (
                (kind == "extra" and "fuzz_extra_field" in still)
                or (kind == "drop" and path[-1] not in still)
                or (
                    kind not in {"extra", "drop"}
                    and _same(still[path[-1]], _get(mutated, path))
                )
            )
        except (KeyError, IndexError, TypeError):
            present = False
        return ("accepted_persisted" if present else "accepted_overwritten"), ""

    def test_single_field_corruptions_of_live_state(self) -> None:
        self.casualty_world()
        self.advance(60.0)
        rng: random.Random = random.Random(0xF6)
        clock_details: dict[str, Any] = _clock().details
        subsystems: list[str] = sorted(
            k for k, v in clock_details.items() if isinstance(v, dict | list)
        )
        results: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        trial: int
        for trial in range(400 * SCALE):
            row_kind: str = rng.choice(("clock",) * 6 + ("pressure", "inventory"))
            if row_kind == "clock":
                row: Any = _clock(lock=True)
                top: str = rng.choice(subsystems)
                root: Any = {top: row.details[top]}
            elif row_kind == "pressure":
                row = rng.choice(
                    list(CanonicalShipState.objects.filter(category="pressure"))
                )
                root = {"details": row.details}
            else:
                row = rng.choice(
                    list(CanonicalShipState.objects.filter(category="inventory"))
                )
                root = {"quantity": row.quantity}
            paths: list[tuple[Any, ...]] = list(_leaves(root))
            if not paths:
                continue
            path: tuple[Any, ...] = rng.choice(paths)
            kind: str = rng.choice(CORRUPTIONS)
            if row_kind == "inventory" and kind in {"drop", "extra"}:
                continue
            mutated: Any = json.loads(json.dumps(root))
            parent: Any = _get(mutated, path[:-1])
            if not _corrupt(parent, path[-1], kind):
                continue
            outcome: str = "accepted_overwritten"
            error: str = ""
            try:
                with transaction.atomic():
                    outcome, error = self._trial(row, row_kind, mutated, path, kind)
                    raise _Rollback
            except _Rollback:
                pass
            except (IntegrityError, ValueError, TypeError) as exc:
                outcome = "storage_rejected"
                error = f"{type(exc).__name__}: {exc}"[:160]
            counts[outcome] = counts.get(outcome, 0) + 1
            results.append(
                {
                    "trial": trial,
                    "row": row.key,
                    "path": [str(p) for p in path],
                    "corruption": kind,
                    "outcome": outcome,
                    "error": error,
                }
            )
        report: Path = Path(
            os.environ.get("OX_FUZZ_REPORT", "/tmp/ox_g19_corruption_fuzz.json")
        )
        report.write_text(json.dumps({"counts": counts, "results": results}, indent=1))
        print(f"F6 corruption outcomes: {counts} -> {report}")
        self.assertGreater(sum(counts.values()), 0)


def _same(a: Any, b: Any) -> bool:
    if (
        isinstance(a, float)
        and isinstance(b, float)
        and math.isnan(a)
        and math.isnan(b)
    ):
        return True
    return bool(a == b)
