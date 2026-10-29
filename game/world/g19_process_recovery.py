"""Independent Python-process G19 persistence/recovery acceptance harness.

This is NOT a gameplay command, a simulated voyage, or an operator restart.
It refuses all databases except a specifically named, disposable SQLite
file under GitHub Actions' RUNNER_TEMP, with explicit CI opt-in.

Two distinct commands/processes share ONLY durable SQLite world objects and
a small expected-evidence JSON file. They never share module-level state.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _sandbox():
    if os.environ.get("OX_G19_RESTART_CI") != "1":
        raise RuntimeError("Independent process probe requires explicit CI approval")
    root_env = os.environ.get("RUNNER_TEMP")
    if not root_env:
        raise RuntimeError("Runner temporary directory is required")
    root = Path(root_env).resolve(strict=True)
    name = os.environ.get("OX_G19_RESTART_DB_PATH", "")
    if not name:
        raise RuntimeError("Missing explicitly selected isolated database")
    db = Path(name).resolve()
    if db.parent != root or db.name != "ox-g19-restart.sqlite3":
        raise RuntimeError("Refusing access to any existing ship database")
    evidence = root / "ox-g19-restart-proof.json"
    os.environ["DJANGO_SETTINGS_MODULE"] = "server.conf.settings"

    # Override the SQLite file BEFORE Django's first connection is made.
    # This avoids starting a server or modifying game/server/evennia.db3.
    from django.conf import settings
    databases = settings.DATABASES
    if "sqlite3" not in databases["default"]["ENGINE"]:
        raise RuntimeError("Disposable SQLite only; never a live Postgres connection")
    databases["default"]["NAME"] = str(db)
    import django
    django.setup()
    import evennia
    evennia._init()
    return db, evidence


def _assert(predicate, message):
    if not predicate:
        raise AssertionError(message)


def _prepare(db, proof):
    # Django/Evennia setup may create an empty SQLite file simply by
    # probing the game-time offset before migrations. The security boundary
    # is an EMPTY SCHEMA and absent proof, not the file's existence.
    from django.db import connection
    _assert(not proof.exists()
            and not connection.introspection.table_names(),
            "Process A refuses a previously migrated ship or old evidence")
    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)

    from world.bootstrap import build_ship
    from world.ship_world import build_canonical_ship, find_ship_space
    from world.full_ship_operations import (
        install_candidate, install_pressure_cells,
        initialize_nominal_atmosphere, set_isolator, state)
    from world.continuous_ship_physics import (
        _clock, arm_continuous_physics, commission_g19_electrical,
        commission_g19_water, commission_g19_repairs, commission_g19_eva,
        commission_g19_crew_physiology, commission_g19_unclassified_spaces,
        survey_cargo_lot, survey_g19_cargo_sector,
        witness_g19_cargo_sector_leak, configure_scenario_casualty,
        configure_water_casualty, crew_physical_action,
        tick_continuous_physics, ensure_continuous_physics_clock, SCRIPT_KEY)
    from world.ship_unclassified_spaces import SECTORS
    from world.models import CanonicalShipEvent, WorkReceipt
    from evennia.scripts.models import ScriptDB

    build_canonical_ship()
    _assert(install_candidate(operator_approved=True)["installed"],
            "New isolated ship was not installed")
    install_pressure_cells(operator_approved=True)
    initialize_nominal_atmosphere(operator_approved=True)
    arm_continuous_physics(operator_approved=True, now_game_time=1000)
    set_isolator("ISO-GEN-M", "closed", operator=True)
    commission_g19_electrical(operator_approved=True)
    commission_g19_water(operator_approved=True)
    commission_g19_repairs(operator_approved=True)
    commission_g19_eva(operator_approved=True)
    worker = build_ship()["watch"]
    worker.move_to(find_ship_space("ENG-CONTROL"), quiet=True)
    commission_g19_crew_physiology(
        operator_approved=True, actor_dbrefs=[worker.dbref])
    commission_g19_unclassified_spaces(operator_approved=True)
    survey_cargo_lot(operator_approved=True, operation="verify", drum="DR-01")
    for sector in SECTORS[:8]:
        survey_g19_cargo_sector(
            operator_approved=True, sector=sector,
            free_volume_m3=50, pressure_pa=101000,
            temperature_k=293.15, oxygen_mass_fraction=.232,
            co2_mass_fraction=.0004, smoke_mass_fraction=0,
            cargo_class="empty", lot_ids=[])
    worker.move_to(find_ship_space("DR-01-GALLERY"), quiet=True)
    sector = "DR-01-SEC-01"
    crew_physical_action(worker, "1" * 32, "cargo_sector", sector, "secure")
    request = "2" * 32
    receipt = crew_physical_action(
        worker, request, "hatch", "ACC-" + sector, "open")
    witness_g19_cargo_sector_leak(
        operator_approved=True, sector=sector, leak_kg_s=.30)
    configure_scenario_casualty(
        "PZ-HAB-01", operator=True, fire_fuel_kg=6, fire_burn_kg_s=.01)
    amount = min(10.0, _clock().details["water"]["working_kg"] / 2)
    _assert(amount > 0, "No surveyed finite water charge")
    configure_water_casualty(operator=True, contaminated_kg=amount)
    _assert(ensure_continuous_physics_clock(),
            "Persistent Evennia timer did not register")
    tick = tick_continuous_physics(now_game_time=1060)
    _assert(tick["advanced"], "Initial physical one-minute tick failed")
    clock = _clock()
    row = clock.details["unclassified_spaces"]["sectors"][sector]
    _assert(row["lost_kg"] > 0, "No actual cargo loss recorded")
    _assert(clock.details["burned_fuel_kg"] > 0, "Fire did not burn finite fuel")
    _assert(ScriptDB.objects.filter(db_key=SCRIPT_KEY).count() == 1,
            "Authoritative timer is duplicated")
    _assert(WorkReceipt.objects.filter(pk=request).count() == 1,
            "Crew work receipt not durable")
    result = {
        "world_model": "0.5-candidate",
        "crew_ref": worker.dbref, "sector": sector, "request": request,
        "receipt": receipt, "last_s": clock.details["last_game_time"],
        "loss_kg": row["lost_kg"],
        "burned_fuel_kg": clock.details["burned_fuel_kg"],
        "contamination_kg": amount,
        "gallery_gas_kg": state("pressure", "PZ-DR-01-SVC").quantity,
        "event_count": CanonicalShipEvent.objects.count(),
        "tick_count": clock.details["ticks"],
    }
    proof.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    print("PROCESS_A_COMPLETE " + json.dumps({
        "last_s": result["last_s"], "lost_kg": result["loss_kg"],
        "clock_ticks": result["tick_count"], "durable_receipts": 1},
        sort_keys=True))


def _resume(db, proof):
    _assert(db.is_file() and proof.is_file(),
            "Process B must reload existing durable physical records")
    expected = json.loads(proof.read_text(encoding="utf-8"))
    from evennia.objects.models import ObjectDB
    from evennia.scripts.models import ScriptDB
    from world.full_ship_operations import (
        ShipOperationsError, install_candidate, state,
        initialize_nominal_atmosphere)
    from world.continuous_ship_physics import (
        _clock, SCRIPT_KEY, arm_continuous_physics,
        crew_physical_action, tick_continuous_physics,
        ensure_continuous_physics_clock)
    from world.models import CanonicalShipEvent, WorkReceipt

    clock = _clock()
    sector = expected["sector"]
    site = clock.details["unclassified_spaces"]["sectors"][sector]
    _assert(clock.details["last_game_time"] == expected["last_s"],
            "Ship clock restarted at the wrong epoch")
    _assert(clock.details["ticks"] == expected["tick_count"],
            "Previously committed ticks were discarded")
    _assert(site["lost_kg"] == expected["loss_kg"],
            "Previously lost cargo gas reappeared")
    _assert(clock.details["burned_fuel_kg"] == expected["burned_fuel_kg"],
            "Burned fuel magically reappeared on process restart")
    _assert(state("pressure", "PZ-DR-01-SVC").quantity ==
            expected["gallery_gas_kg"],
            "Actual gallery gas changed between processes")
    _assert(clock.details["water"]["potable_quarantined"],
            "Water quarantine cleared on restart without proof")
    _assert(CanonicalShipEvent.objects.count() == expected["event_count"],
            "Event history was lost or replayed during process shutdown")
    _assert(ScriptDB.objects.filter(db_key=SCRIPT_KEY).count() == 1,
            "Persistent script was lost or duplicated by process handoff")

    _assert(not arm_continuous_physics(
        operator_approved=True, now_game_time=9000)["armed"],
        "Recommissioning incorrectly reset the original physical epoch")
    _assert(not install_candidate(operator_approved=True)["installed"],
            "World inventory recreated during restart")
    try:
        initialize_nominal_atmosphere(operator_approved=True)
    except ShipOperationsError as exc:
        _assert("already initialised" in str(exc),
                "Atmosphere reset failed for an unrelated reason")
    else:
        raise AssertionError("A restarted ship could refill original gas cells")

    worker = ObjectDB.objects.get(
        id=int(expected["crew_ref"].lstrip("#")))
    duplicate = crew_physical_action(
        worker, expected["request"], "hatch",
        "ACC-" + sector, "open")
    _assert(duplicate == expected["receipt"],
            "Work receipt was not idempotent across OS processes")
    _assert(WorkReceipt.objects.filter(pk=expected["request"]).count() == 1,
            "Work receipt duplicated during replay")
    _assert(CanonicalShipEvent.objects.count() == expected["event_count"],
            "Replay minted an additional canonical work event")
    _assert(ensure_continuous_physics_clock(),
            "Existing persistent script did not rebind")
    _assert(ScriptDB.objects.filter(db_key=SCRIPT_KEY).count() == 1,
            "Rebound clock created a second live script")
    _assert(not tick_continuous_physics(
        now_game_time=expected["last_s"])["advanced"],
        "Equal-time replay repeated finite resource flows")
    target = expected["last_s"] + 230
    positions = []
    losses = []
    while _clock().details["last_game_time"] < target:
        old = _clock().details["last_game_time"]
        out = tick_continuous_physics(now_game_time=target)
        _assert(out["advanced"], "Backlog iteration failed to run")
        _assert(0 < out["last_game_time"] - old <= 60,
                "Downtime processed in an unbounded jump")
        positions.append(out["last_game_time"])
        losses.append(_clock().details[
            "unclassified_spaces"]["sectors"][sector]["lost_kg"])
    _assert(len(positions) == 4 and positions[-1] == target,
            "Downtime was lost or replayed")
    _assert(losses == sorted(losses) and losses[-1] > expected["loss_kg"],
            "Continuing shell casualty was incorrectly cancelled")
    _assert(not tick_continuous_physics(
        now_game_time=target)["advanced"],
        "Second process replayed completed backlog")
    _assert(state("access", "ACC-" + sector).setting == "open",
            "Installed original pressure boundary was silently reset")
    _assert(_clock().details["water"]["potable_quarantined"],
            "New process erased unserviced water contamination")
    print("PROCESS_B_COMPLETE " + json.dumps({
        "first_s": expected["last_s"], "last_s": target,
        "recovery_ticks": len(positions), "lost_kg": losses[-1],
        "persistent_script_count": ScriptDB.objects.filter(
            db_key=SCRIPT_KEY).count(), "durable_receipts": 1},
        sort_keys=True))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "resume"}:
        raise SystemExit("Usage: python -m world.g19_process_recovery prepare|resume")
    db, proof = _sandbox()
    if sys.argv[1] == "prepare":
        _prepare(db, proof)
    else:
        _resume(db, proof)


if __name__ == "__main__":
    main()
