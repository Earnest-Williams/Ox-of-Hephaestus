"""Reproducible stateful fuzzing of G17's *real* Evennia/DB ship operations.

Not a mock world or a random smoke test. Deterministic seeds and failing
step labels make every counterexample replayable. No handler/character gets
access to the operator-only methods exercised here.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from django.db import transaction
from evennia.utils.test_resources import EvenniaTestCase

from world.full_ship_operations import (
    ShipOperationsError, access_clearance, consume_stock, equalize_cells,
    initialize_nominal_atmosphere, install_candidate, install_pressure_cells,
    load_candidate, pressure_reading, service_reachable,
    set_component_condition, set_isolator, state, vent_pressure_cell,
)
from world.models import CanonicalShipEvent, CanonicalShipState
from world.ship_world import ensure_canonical_ship


# Report any failure with its exact seed and step; no wall-clock randomness.
SEEDS = (0x1710, 0x250C, 0xBAD5EED)
STEPS_PER_SEED = 112
TOL = 2e-7


class FullShipCandidateMutationFuzz(unittest.TestCase):
    """Mutation fuzzes the real, full-sized 0.5 candidate before installation."""

    def test_rejects_mutated_physical_source(self):
        rng = random.Random(0xCA5CADE)
        source = load_candidate()
        # Mutation operators must introduce a single *known* inconsistency.
        variants = [
            "duplicate_equipment",
            "unknown_equipment_room",
            "unknown_access_endpoint",
            "duplicate_isolator",
            "missing_service_node",
            "missing_service_isolator",
            "negative_mass",
            "nan_mass",
            "cross_domain_edge",
            "broken_isolator_room",
            "unrated_pressure_boundary",
            "invalid_isolator_state",
            "invalid_maintenance_equipment",
            "bad_service_route",
        ]
        accepted_corruptions = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt_candidate.json"
            for index, mutation in enumerate(variants):
                payload = deepcopy(source)
                if mutation == "duplicate_equipment":
                    payload["equipment"][1]["id"] = payload["equipment"][0]["id"]
                elif mutation == "unknown_equipment_room":
                    payload["equipment"][rng.randrange(808)]["space_id"] = "NO-SUCH-ROOM"
                elif mutation == "unknown_access_endpoint":
                    payload["access_links"][rng.randrange(517)]["to"] = "NO-SUCH-ROOM"
                elif mutation == "duplicate_isolator":
                    payload["isolation_points"][1]["id"] = payload["isolation_points"][0]["id"]
                elif mutation == "missing_service_node":
                    payload["service_edges"][rng.randrange(1181)]["from_node"] = "NO-SUCH-NODE"
                elif mutation == "missing_service_isolator":
                    payload["service_edges"][rng.randrange(1181)]["isolator_ids"] = ["NO-SUCH-ISOLATOR"]
                elif mutation == "negative_mass":
                    payload["inventories"][0]["nominal_mass_t"] = -1.0
                elif mutation == "nan_mass":
                    payload["inventories"][0]["nominal_mass_t"] = float("nan")
                elif mutation == "cross_domain_edge":
                    edge = rng.choice(payload["service_edges"])
                    edge["network"] = "NOT-ITS-NETWORK"
                elif mutation == "broken_isolator_room":
                    payload["isolation_points"][rng.randrange(1256)]["space_id"] = "NO-SUCH-ROOM"
                elif mutation == "unrated_pressure_boundary":
                    edge = next(e for e in payload["access_links"] if e["pressure_boundary"])
                    edge["pressure_boundary"] = False
                elif mutation == "invalid_isolator_state":
                    payload["isolation_points"][rng.randrange(1256)]["current_state"] = "teleported"
                elif mutation == "invalid_maintenance_equipment":
                    payload["maintenance_tasks"][0]["equipment_ids"].append("NO-SUCH-EQUIPMENT")
                elif mutation == "bad_service_route":
                    edge = next(e for e in payload["service_edges"] if e["route_spaces"])
                    edge["route_spaces"].append("NO-SUCH-ROOM")
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(seed="0xCA5CADE", case=index, mutation=mutation):
                    try:
                        load_candidate(path)
                    except ShipOperationsError:
                        pass
                    else:
                        accepted_corruptions.append((index, mutation))
        self.assertFalse(accepted_corruptions,
                         f"Unsafe candidate mutations admitted: {accepted_corruptions}")
        print(f"OX_G17_MUTATION_FUZZ_PASS seed=0xCA5CADE cases={len(variants)} rejected={len(variants)}")


class FullShipStatefulFuzz(EvenniaTestCase):
    """Adversarial sequences against actual persisted world and event ledger."""

    def setUp(self):
        super().setUp()
        ensure_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)

    def test_bounded_random_casualties_and_controls(self):
        candidate = load_candidate()
        cell_ids = sorted(CanonicalShipState.objects.filter(
            category="pressure").values_list("source_id", flat=True))
        inventory_ids = ("INV-WATER-NORMAL", "INV-SPARES", "INV-FOOD-LONG-LEG",
                         "INV-GAS-REFILL-A", "INV-GAS-REFILL-B")
        switches = ("ISO-GEN-M", "ISO-GEN-A", "ISO-GEN-B", "ISO-SHORE-PWR")
        edges = ("EDGE-GEN-M", "EDGE-GEN-A", "EDGE-GEN-B", "EDGE-SHORE-PWR")
        equipment = ("F1-FW-01", "F1-FW-02", "F1-FW-03")
        original_stock = {key: state("inventory", key).quantity for key in inventory_ids}
        original_mass = sum(CanonicalShipState.objects.filter(
            category="pressure").values_list("quantity", flat=True))
        lost_mass = 0.0
        spent_stock = {key: 0.0 for key in inventory_ids}
        categories = {"vent": 0, "equalize": 0, "stock": 0, "isolate": 0,
                      "fault": 0, "rollback": 0, "deny": 0, "reach": 0}
        cells = {x["id"]: x for x in candidate["spaces"]}
        boundary_pairs = sorted({
            tuple(sorted((cells[e["from"]]["pressure_zone"],
                          cells[e["to"]]["pressure_zone"])))
            for e in candidate["access_links"] if e["pressure_boundary"]
            and isinstance(cells[e["from"]]["pressure_zone"], str)
            and isinstance(cells[e["to"]]["pressure_zone"], str)
            and cells[e["from"]]["pressure_zone"] in cell_ids
            and cells[e["to"]]["pressure_zone"] in cell_ids
            and cells[e["from"]]["pressure_zone"] != cells[e["to"]]["pressure_zone"]
        })
        self.assertGreater(len(boundary_pairs), 50)

        # Do not mutate a canonical spec to make the tests easier. The event
        # runner chooses only existing real equipment and named gas cells.
        for seed in SEEDS:
            rng = random.Random(seed)
            for step in range(STEPS_PER_SEED):
                label = f"seed=0x{seed:x} step={step}"
                operation = rng.choices(
                    list(categories),
                    weights=[25, 14, 14, 15, 13, 7, 8, 4], k=1,
                )[0]
                categories[operation] += 1
                try:
                    if operation == "vent":
                        cid = rng.choice(cell_ids)
                        existing = state("pressure", cid).quantity
                        if existing <= 0:
                            continue
                        requested = rng.choice((1e-6, 0.001, 0.1, 2.0, 20.0, existing * 3))
                        result = vent_pressure_cell(cid, requested, operator=True)
                        self.assertAlmostEqual(result["lost_kg"], min(existing, requested), delta=TOL)
                        self.assertGreaterEqual(state("pressure", cid).quantity, 0)
                        lost_mass += result["lost_kg"]
                    elif operation == "equalize":
                        a, b = rng.choice(boundary_pairs)
                        before = state("pressure", a).quantity + state("pressure", b).quantity
                        equalize_cells(a, b, operator=True)
                        after = state("pressure", a).quantity + state("pressure", b).quantity
                        self.assertAlmostEqual(before, after, delta=TOL)
                        self.assertTrue(math.isclose(
                            pressure_reading(a)["pressure_pa"],
                            pressure_reading(b)["pressure_pa"],
                            rel_tol=1e-10, abs_tol=1e-6))
                    elif operation == "stock":
                        item = rng.choice(inventory_ids)
                        current = state("inventory", item).quantity
                        requested = rng.choice((1e-8, 0.0001, 0.02, 0.2, current * 2 + 0.01))
                        if requested > current:
                            with self.assertRaises(ShipOperationsError):
                                consume_stock(item, requested, operator=True)
                        else:
                            consume_stock(item, requested, operator=True)
                            spent_stock[item] += requested
                        self.assertAlmostEqual(
                            state("inventory", item).quantity,
                            original_stock[item] - spent_stock[item], delta=TOL)
                    elif operation == "isolate":
                        name = rng.choice(switches)
                        before = state("isolator", name)
                        target = rng.choice(("open", "closed"))
                        if before.condition in {"failed", "faulted", "jammed", "severed"}:
                            with self.assertRaises(ShipOperationsError):
                                set_isolator(name, target, operator=True)
                        else:
                            set_isolator(name, target, operator=True)
                            self.assertEqual(state("isolator", name).setting, target)
                    elif operation == "fault":
                        category, name = rng.choice((
                            ("equipment", rng.choice(equipment)),
                            ("edge", rng.choice(edges)),
                            ("isolator", rng.choice(switches)),
                        ))
                        target = rng.choice(("serviceable", "faulted", "failed", "severed"))
                        set_component_condition(category, name, target, operator=True)
                        self.assertEqual(state(category, name).condition, target)
                    elif operation == "rollback":
                        name = rng.choice(inventory_ids)
                        before = state("inventory", name).quantity
                        events = CanonicalShipEvent.objects.count()
                        with self.assertRaises(RuntimeError):
                            with transaction.atomic():
                                if before > 0:
                                    consume_stock(name, min(before, 0.001), operator=True)
                                raise RuntimeError("deliberate transaction rollback")
                        self.assertEqual(state("inventory", name).quantity, before)
                        self.assertEqual(CanonicalShipEvent.objects.count(), events)
                    elif operation == "deny":
                        before = CanonicalShipEvent.objects.count()
                        with self.assertRaises(PermissionError):
                            consume_stock(rng.choice(inventory_ids), 0.001)
                        with self.assertRaises(PermissionError):
                            vent_pressure_cell(rng.choice(cell_ids), 0.1)
                        with self.assertRaises(PermissionError):
                            set_component_condition("equipment", rng.choice(equipment), "failed")
                        with self.assertRaises(PermissionError):
                            set_isolator(rng.choice(switches), "open")
                        with self.assertRaises(PermissionError):
                            equalize_cells(*rng.choice(boundary_pairs))
                        self.assertEqual(CanonicalShipEvent.objects.count(), before)
                    elif operation == "reach":
                        # A newly severed feeder cannot make more nodes reachable.
                        identifier = rng.choice(edges)
                        previous = service_reachable("power", "NODE-GEN-M")
                        set_component_condition("edge", identifier, "severed", operator=True)
                        remaining = service_reachable("power", "NODE-GEN-M")
                        self.assertTrue(remaining <= previous,
                                        f"Breaking {identifier} added reachable nodes")
                except Exception as exc:
                    raise AssertionError(f"OX_G17_STATEFUL_FUZZ_FAILURE {label} op={operation}") from exc

        final_mass = sum(CanonicalShipState.objects.filter(
            category="pressure").values_list("quantity", flat=True))
        self.assertAlmostEqual(original_mass - lost_mass, final_mass, delta=2e-6)
        for name in inventory_ids:
            self.assertAlmostEqual(
                original_stock[name] - spent_stock[name],
                state("inventory", name).quantity, delta=TOL)
        for cid in cell_ids:
            reading = pressure_reading(cid)
            self.assertTrue(math.isfinite(reading["pressure_pa"]))
            self.assertGreaterEqual(reading["pressure_pa"], 0)
        for name in inventory_ids:
            self.assertGreaterEqual(state("inventory", name).quantity, 0)
        self.assertFalse(install_candidate(operator_approved=True)["installed"])
        self.assertFalse(install_pressure_cells(operator_approved=True)["installed"])
        with self.assertRaises(ShipOperationsError):
            initialize_nominal_atmosphere(operator_approved=True)
        print("OX_G17_STATEFUL_FUZZ_PASS "
              f"seeds={','.join(hex(x) for x in SEEDS)} "
              f"steps={len(SEEDS) * STEPS_PER_SEED} "
              f"ops={categories} vented_kg={lost_mass:.6f}")

    def test_adversarial_boundaries_and_no_phantom_stock(self):
        # All malformed inputs must fail without state or event effects.
        bad = (0, -1, True, False, float("inf"), float("-inf"), float("nan"),
               "1.0", None, [], {})
        for i, amount in enumerate(bad):
            with self.subTest(case=i, payload=repr(amount)):
                count = CanonicalShipEvent.objects.count()
                with self.assertRaises(ShipOperationsError):
                    consume_stock("INV-WATER-NORMAL", amount, operator=True)
                with self.assertRaises(ShipOperationsError):
                    vent_pressure_cell("PZ-HAB-03", amount, operator=True)
                self.assertEqual(CanonicalShipEvent.objects.count(), count)

        # Edge-case stock withdrawal must not invent mass from rounding slack.
        zero = state("inventory", "INV-WASTE-RESIDUE")
        self.assertEqual(zero.quantity, 0)
        with self.assertRaises(ShipOperationsError):
            consume_stock("INV-WASTE-RESIDUE", 5e-10, operator=True)
        self.assertEqual(state("inventory", "INV-WASTE-RESIDUE").quantity, 0)

        # Even a deliberately forced-open boundary cannot bypass pressure,
        # while ordinary Developer traversal stays separately locked.
        hatch = state("access", "ACC-BR-03-HAB-03")
        hatch.setting = "open"  # direct test mutation; NEVER a public command
        hatch.save(update_fields=["setting"])
        self.assertEqual(access_clearance("ACC-BR-03-HAB-03"),
                         (False, "equalization_not_verified"))
        set_component_condition("access", "ACC-BR-03-HAB-03", "jammed", operator=True)
        self.assertEqual(access_clearance("ACC-BR-03-HAB-03"),
                         (False, "access_not_open"))

        # Repeat vent after full vacuum: no physical transition, no new event.
        room = "PZ-BR-03"
        mass = state("pressure", room).quantity
        vent_pressure_cell(room, mass + 1.0, operator=True)
        before = CanonicalShipEvent.objects.count()
        rev = state("pressure", room).revision
        again = vent_pressure_cell(room, 1.0, operator=True)
        self.assertEqual(again["lost_kg"], 0)
        self.assertEqual(CanonicalShipEvent.objects.count(), before)
        self.assertEqual(state("pressure", room).revision, rev)
        print("OX_G17_BOUNDARY_FUZZ_PASS malformed=11 small_stock=1 forced_hatch=1 empty_gas=1")
