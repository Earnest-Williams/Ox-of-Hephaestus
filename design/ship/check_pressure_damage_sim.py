#!/usr/bin/env python3
"""Adversarial real-topology reference trials for pressure/damage control.

No Evennia, AI decisions, hidden-condition truth or live world commands.
Run with: python design/ship/check_pressure_damage_sim.py
"""
from __future__ import annotations

from copy import deepcopy
import json
from math import isclose
from random import Random

from pressure_damage_sim_v05 import PressureDamageTrial, load_model


def insist(condition, message):
    if not condition:
        raise AssertionError(message)


TOPOLOGY, GAS, ENVIRONMENTAL = load_model()


def fresh_trial(basis="midpoint"):
    return PressureDamageTrial(TOPOLOGY, GAS, ENVIRONMENTAL, volume_basis=basis)


def ready_hab_bridge(trial):
    ids = ("PZ-HAB-03", "PZ-BR-03", "PZ-HAB-04")
    for id in ids:
        trial.sample_local(id, qualified_local_probe=True)
    for gate in ("ACC-BR-03-HAB-03", "ACC-BR-03-HAB-04"):
        insist(trial.open_gate(gate, local_authority=True),
               "healthy verified hab bridge cannot be opened")


def make_breach_trial(close_after=None, jam=False):
    trial = fresh_trial()
    ready_hab_bridge(trial)
    if jam:
        trial.fail_gate_open("ACC-BR-03-HAB-03")
    trial.breach("HULL-03", "PZ-HAB-03", 18.0)
    if close_after is None:
        trial.advance(90)
        return trial, None
    trial.advance(close_after)
    closed = trial.isolate_zone("PZ-HAB-03")
    trial.advance(90 - close_after)
    return trial, closed


def validate():
    report = {}
    cold = fresh_trial()
    insist(len(cold.cells) == 133 and len(cold.gates) == 339
           and len(cold.unknown_gate_ids) == 131,
           "designed ship topology not preserved")
    insist(all(g.state == "closed" for g in cold.gates.values()),
           "trial falsely assumes as-installed open hatch states")
    insist(all(isclose(c.pressure_kpa, 101.325, abs_tol=0.002)
               for c in cold.cells.values()),
           "cold isolated design-reference pressure not reproducible")
    insist(cold.mass_balance_error_kg() < 1e-6,
           "initial mass balance incorrect")
    report["loaded_ship"] = {"pressure_cells": len(cold.cells),
                             "independently_rated_boundaries": len(cold.gates),
                             "unclassified_environment_hatches":
                                 len(cold.unknown_gate_ids)}

    # Requested unsafe opening cannot use design default or an invented
    # sealed transfer; physically forced-open failure is a separate event.
    denied, reason = cold.can_open("ACC-BR-03-HAB-03", local_authority=True)
    insist(not denied and "sample" in reason,
           "unmeasured initially nominal air incorrectly permits hatch opening")
    for forbidden in ("ACC-DR-01-SEC-01", "ACC-EVA-FWD-EXT", "ACC-F1-BAY"):
        insist(not cold.open_gate(forbidden, local_authority=True),
               "unverified cargo/vacuum receiving hatch allowed to vent crew")
    cold.sample_local("PZ-HAB-03", qualified_local_probe=True)
    cold.sample_local("PZ-BR-03", qualified_local_probe=True)
    insist(cold.open_gate("ACC-BR-03-HAB-03", local_authority=True),
           "compatible measured bridge denied")
    insist("PZ-BR-03" in cold.traversable_zones("PZ-HAB-03"),
           "healthy proven-open bridge not traversable")
    cold.advance(11)
    insist("PZ-BR-03" not in cold.traversable_zones("PZ-HAB-03"),
           "stale local samples incorrectly grant unsuited crew passage")
    report["access"] = "proven healthy bridge permits passage; unknown, vacuum and stale evidence deny"

    # Rotary indexing and heavy freight are mechanically distinct from
    # equalized compartment air. Prove both independent interlock types.
    indexed = fresh_trial()
    for zone in ("PZ-DR-01-LOCK", "PZ-DR-01-SVC"):
        indexed.sample_local(zone, qualified_local_probe=True)
    insist(not indexed.open_gate("ACC-DR-01-LOCK-ROT", local_authority=True),
           "stationary pressure evidence bypassed drum indexer hard-lock")
    insist(indexed.open_gate("ACC-DR-01-LOCK-ROT", local_authority=True,
                            transfer_interlocks_proven=True),
           "verified indexed personnel transfer denied")
    freight = fresh_trial()
    for zone in ("PZ-DR-01-FREIGHT", "PZ-DR-01-SVC"):
        freight.sample_local(zone, qualified_local_probe=True)
    insist(not freight.open_gate("ACC-DR-01-FREIGHT-CAPTURE",
                                local_authority=True),
           "heavy capture permitted without interlock or cargo authority")
    insist(not freight.open_gate("ACC-DR-01-FREIGHT-CAPTURE",
                                local_authority=True,
                                transfer_interlocks_proven=True),
           "hard-locked freight collar permitted without cargo authority")
    insist(freight.open_gate("ACC-DR-01-FREIGHT-CAPTURE",
                            local_authority=True,
                            transfer_interlocks_proven=True,
                            freight_permit_proven=True),
           "verified freight transfer cannot open")
    report["mechanical_transfer_interlocks"] = "indexer witness and heavy-freight authority required"

    # Closed hull breach must not produce mass loss from adjacent zones.
    sealed = fresh_trial()
    sealed.set_crew("PZ-HAB-03", 6)
    sealed.breach("HULL-03", "PZ-HAB-03", 18)
    sealed.advance(90)
    insist(sealed.cells["PZ-HAB-03"].pressure_kpa < 80
           and sealed.cells["PZ-HAB-03"].crew_unsafe_seconds > 0,
           "hull breach does not create actual respiratory consequences")
    insist(isclose(sealed.cells["PZ-HAB-04"].pressure_kpa, 101.325, abs_tol=1e-6)
           and isclose(sealed.cells["PZ-BR-03"].pressure_kpa, 101.325,
                       abs_tol=1e-6),
           "closed rated bulkheads not isolating neighboring air mass")
    insist(sealed.lost_to_vacuum_kg > 0 and sealed.mass_balance_error_kg() < 1e-5,
           "vacuum leak does not debit physical gas mass")
    report["isolated_hull_breach"] = sealed.summary(
        ["PZ-HAB-03", "PZ-BR-03", "PZ-HAB-04"])

    early, early_result = make_breach_trial(close_after=3)
    late, late_result = make_breach_trial(close_after=50)
    unisolated, _ = make_breach_trial(close_after=None)
    insist(not early_result["failed"] and not late_result["failed"],
           "sound isolation door falsely jammed")
    p_early = early.cells["PZ-HAB-04"].pressure_kpa
    p_late = late.cells["PZ-HAB-04"].pressure_kpa
    p_none = unisolated.cells["PZ-HAB-04"].pressure_kpa
    insist(p_early > p_late + 0.2 and p_late > p_none + 0.2,
           "isolation time does not alter adjacent HAB-04 pressure loss")
    insist(all(c.pressure_kpa <= 101.326 for trial in (early, late, unisolated)
               for c in trial.cells.values()),
           "leak-only casualty created fictitious local overpressure")
    insist(all(c.pressure_kpa >= -1e-7 for trial in (early, late, unisolated)
               for c in trial.cells.values()),
           "gas equalization created negative compartment pressure")
    insist(early.lost_to_vacuum_kg > 0 and
           late.lost_to_vacuum_kg > early.lost_to_vacuum_kg,
           "delayed closure does not increase atmosphere lost")
    insist("PZ-HAB-04" not in late.traversable_zones("PZ-HAB-03"),
           "closed casualty partition leaves unrestricted crew shortcut")
    for trial in (early, late, unisolated):
        insist(trial.mass_balance_error_kg() < 1e-5,
               "leak + compartment equalization did not conserve gas mass")
    report["isolation_timing"] = {
        "early_3s_HAB04_kpa": round(p_early, 3),
        "late_50s_HAB04_kpa": round(p_late, 3),
        "unisolated_90s_HAB04_kpa": round(p_none, 3),
        "early_vacuum_loss_kg": round(early.lost_to_vacuum_kg, 3),
        "late_vacuum_loss_kg": round(late.lost_to_vacuum_kg, 3),
    }

    jammed, result = make_breach_trial(close_after=50, jam=True)
    insist("ACC-BR-03-HAB-03" in result["failed"] and
           jammed.gates["ACC-BR-03-HAB-03"].is_open(),
           "jammed-open pressure door incorrectly reports successful closure")
    insist(jammed.cells["PZ-HAB-04"].pressure_kpa < p_late,
           "jammed bridge does not continue to propagate hull loss")
    jammed.close_gate("ACC-BR-03-HAB-04")
    insist(jammed.gates["ACC-BR-03-HAB-04"].state == "closed",
           "secondary bridge boundary unavailable to local damage control")
    report["jammed_end_hatch"] = jammed.summary(["PZ-HAB-03", "PZ-HAB-04"])

    # Model individual sectional trunk pressure cells, not a monolithic
    # 950 m corridor and not a fabricated room/dungeon instance.
    trunk = fresh_trial()
    for id in ("PZ-TRUNK-A-BOW", "PZ-TRUNK-A-DR-01"):
        trunk.sample_local(id, qualified_local_probe=True)
    insist(trunk.open_gate("ACC-TRUNK-A-BOW-DR-01", local_authority=True),
           "existing sequential crew-trunk pressure door unavailable")
    trunk.breach("BOW-HIT", "PZ-TRUNK-A-BOW", 12)
    trunk.advance(20)
    insist(trunk.cells["PZ-TRUNK-A-DR-01"].pressure_kpa < 101.0,
           "open neighboring 950m trunk segment has no local gas consequence")
    trunk.isolate_zone("PZ-TRUNK-A-DR-01")
    guard = trunk.cells["PZ-TRUNK-A-DR-01"].pressure_kpa
    trunk.advance(20)
    insist(isclose(trunk.cells["PZ-TRUNK-A-DR-01"].pressure_kpa,
                   guard, abs_tol=1e-5),
           "trunk segmentation incorrectly remains linked after closure")

    # A real known-vacuum plant interface vents; an unclassified receiver
    # is NOT assigned vacuum conditions simply because its door is open.
    vacuum = fresh_trial()
    vacuum.fail_gate_open("ACC-F1-BAY")
    vacuum.advance(20)
    insist(vacuum.cells["PZ-TRUNK-A-F1"].pressure_kpa < 101
           and vacuum.lost_to_vacuum_kg > 0,
           "failed-open airlock to known F1 vacuum has no gas loss")
    unknown = fresh_trial()
    unknown.fail_gate_open("ACC-DR-01-SEC-01")
    unknown.advance(20)
    affected = unknown.cells["PZ-DR-01-SVC"]
    insist(affected.unknown_exposure and
           not unknown.may_enter_unsuited(affected.id)
           and isclose(unknown.lost_to_vacuum_kg, 0),
           "unclassified cargo falsely assigned breathable air or vacuum")
    insist(not unknown.close_gate("ACC-DR-01-SEC-01")
           and affected.unknown_exposure,
           "jammed hazardous cargo hatch spontaneously restored")
    report["unknown_cargo"] = {"receiver_is_quantitatively_unmodelled": True,
                                "crew_access_blocked": True}

    # Contaminants are a finite tracer fraction of existing carrier gas.
    # A failed-open hatch spreads it into a physically adjacent bridge.
    dirty = fresh_trial()
    dirty.mark_contaminated("PZ-HAB-03", 1.0)
    dirty.fail_gate_open("ACC-BR-03-HAB-03")
    dirty.advance(20)
    insist(dirty.cells["PZ-BR-03"].trace_kg > 0
           and dirty.cells["PZ-HAB-03"].trace_kg < 1.0,
           "opening contaminated atmosphere fails to mix material species")
    dirty.sample_local("PZ-BR-03", qualified_local_probe=True)
    insist(not dirty.may_enter_unsuited("PZ-BR-03")
           and dirty.mass_balance_error_kg() < 1e-5,
           "contaminated atmosphere admitted or tracer created from nothing")

    # Repeat leak propagation across different real gates with fixed
    # random seeds. The gas ledger is never allowed to create pressure
    # above its original maximum, even in tiny bridge cells.
    stress_cases = 0
    for seed in (7, 19, 619, 1009, 2026):
        random = Random(seed)
        varied = fresh_trial()
        known_pairs = [g.id for g in varied.gates.values()
                       if g.a in varied.cells and g.b in varied.cells]
        for gate_id in random.sample(known_pairs, 8):
            varied.fail_gate_open(gate_id)
        target = random.choice(sorted(varied.cells))
        varied.breach("SEED-HULL", target, random.uniform(5.0, 45.0))
        varied.advance(65)
        insist(varied.mass_balance_error_kg() < 1e-5
               and all(-1e-6 <= c.pressure_kpa <= 101.326
                       for c in varied.cells.values())
               and varied.lost_to_vacuum_kg > 0,
               "seeded multigate breach violates pressure or mass accounting")
        stress_cases += 1
    report["deterministic_multigate_stress_seeds"] = stress_cases

    # Delayed intervention changes the loss even without connected neighbors;
    # the smaller physical-volume bound loses pressure more rapidly.
    lower = fresh_trial("lower")
    upper = fresh_trial("upper")
    for trial in (lower, upper):
        trial.breach("M", "PZ-HAB-03", 18)
        trial.advance(45)
    insist(lower.cells["PZ-HAB-03"].pressure_kpa <
           upper.cells["PZ-HAB-03"].pressure_kpa,
           "bounded free-air uncertainty has no pressure-rate consequence")

    # Actual finite reserve stock and the nominal distribution valve remain
    # distinct from filled-compartment mass and protected refuge O2.
    recovery = fresh_trial()
    recovery.breach("PUNCTURE", "PZ-HAB-03", 18)
    recovery.advance(12)
    try:
        recovery.pump_replacement_air("INV-GAS-REFILL-A", "PZ-HAB-03", 3600,
                                      path_locally_proven=True,
                                      receiving_chemistry_verified=True)
    except ValueError:
        pass
    else:
        raise AssertionError("unrepaired leak was allowed to drain gas reserve")
    recovery.seal_breach("PUNCTURE", repair_verified=True)
    recovery.sample_local("PZ-HAB-03", qualified_local_probe=True)
    try:
        recovery.pump_replacement_air("INV-GAS-REFILL-A", "PZ-HAB-03", 3600,
                                      path_locally_proven=True,
                                      receiving_chemistry_verified=True)
    except ValueError:
        pass
    else:
        raise AssertionError("closed bank valve permitted transfer")
    # The target hull can be locally patched yet remain connected through
    # an open door to a different leaking cell. That is not safe refill.
    downstream = fresh_trial()
    for zone in ("PZ-HAB-03", "PZ-BR-03"):
        downstream.sample_local(zone, qualified_local_probe=True)
    insist(downstream.open_gate("ACC-BR-03-HAB-03",
                               local_authority=True),
           "adjacent bridge cannot be joined for connected-leak test")
    downstream.breach("BRIDGE-LEAK", "PZ-BR-03", 5)
    downstream.set_bank_outlet("INV-GAS-REFILL-A", True, local_authority=True)
    try:
        downstream.pump_replacement_air("INV-GAS-REFILL-A",
                                       "PZ-HAB-03", 3600,
                                       path_locally_proven=True,
                                       receiving_chemistry_verified=True)
    except ValueError:
        pass
    else:
        raise AssertionError("refill used physically open route into another active leak")
    insist(isclose(downstream.bank_kg["INV-GAS-REFILL-A"], 2750),
           "refused connected-casualty refill spent gas inventory")
    recovery.set_bank_outlet("INV-GAS-REFILL-A", True, local_authority=True)
    try:
        recovery.pump_replacement_air("INV-GAS-REFILL-A", "PZ-HAB-03", 3600,
                                      path_locally_proven=False,
                                      receiving_chemistry_verified=True)
    except ValueError:
        pass
    else:
        raise AssertionError("imaginary unchecked gas route permitted replenishment")
    refilled = recovery.pump_replacement_air("INV-GAS-REFILL-A", "PZ-HAB-03",
                                            3600, path_locally_proven=True,
                                            receiving_chemistry_verified=True)
    insist(0 < refilled <= 200
           and 2550 <= recovery.bank_kg["INV-GAS-REFILL-A"] < 2750
           and recovery.cells["PZ-HAB-03"].pressure_kpa <= 101.325 + 1e-4
           and recovery.mass_balance_error_kg() < 1e-5,
           "gas reserve, rate, pressure ceiling or mass conservation broken")
    report["verified_refill"] = {"transferred_kg": round(refilled, 3),
                                  "remaining_bank_A_kg": round(
                                      recovery.bank_kg["INV-GAS-REFILL-A"], 3),
                                  "recovered_reference_kpa": round(
                                      recovery.cells["PZ-HAB-03"].pressure_kpa, 3)}

    # Prove intentionally broken inputs fail rather than simply making
    # the nominal test data look impressive.
    negative = [
        lambda: PressureDamageTrial(TOPOLOGY, GAS, ENVIRONMENTAL, "fantasy"),
        lambda: fresh_trial().advance(-5),
        lambda: fresh_trial().advance(5, integration_step_s=4),
        lambda: fresh_trial().set_crew("PZ-HAB-03", 41),
        lambda: fresh_trial().breach("X", "PZ-MISSING", 5),
        lambda: fresh_trial().breach("X", "PZ-HAB-03", -5),
        lambda: fresh_trial().sample_local("PZ-HAB-03",
                                          qualified_local_probe=False),
        lambda: fresh_trial().set_bank_outlet("INV-GAS-REFILL-A", True,
                                              local_authority=False),
        lambda: fresh_trial().mark_contaminated("PZ-HAB-03", 5000),
    ]
    for number, fail in enumerate(negative, 1):
        try:
            fail()
        except (ValueError, KeyError):
            continue
        raise AssertionError("invalid casualty mutation accepted: " + str(number))
    bad_topology = deepcopy(TOPOLOGY)
    bad_topology["pressure_boundary_doors"].pop()
    try:
        PressureDamageTrial(bad_topology, GAS, ENVIRONMENTAL)
    except ValueError:
        pass
    else:
        raise AssertionError("missing rated boundary silently accepted")
    bad_gas = deepcopy(GAS)
    bad_gas["sized_and_unsized_pressure_cells"][0]["verified_as_installed_free_gas_m3"] = 1
    try:
        PressureDamageTrial(TOPOLOGY, bad_gas, ENVIRONMENTAL)
    except ValueError:
        pass
    else:
        raise AssertionError("falsely measured installed gas accepted")
    report["adversarial_invalid_inputs_rejected"] = len(negative) + 2
    return report


if __name__ == "__main__":
    results = validate()
    print(json.dumps(results, indent=2, sort_keys=True))
    print("OX_COUPLED_PRESSURE_DAMAGE_TIMING_AND_ELEVEN_NEGATIVE_TESTS_PASS")
