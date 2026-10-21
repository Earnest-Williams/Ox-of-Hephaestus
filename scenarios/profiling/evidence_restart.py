"""P4f reproducible *local* restart-integrity microprofile.

This script exercises the production ActorEvidenceIndex hot/cold implementation
and complete O(history) attestation on one actor. It does NOT use a live
Evennia server, replay socket packets, native Concordia, or model inference.
It never assumes historical events can be deleted or unverified on restart.

Examples:
  python scenarios/profiling/evidence_restart.py --sizes 1000,10000
  python scenarios/profiling/evidence_restart.py --sizes 1000,10000,40000 \
      --payloads 160,1200 --output .ox-state/profiles/evidence.json
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
from pathlib import Path
import platform
import pstats
import resource
import sqlite3
import statistics
import tempfile
import time

from ox_ai.ports.evennia.journal import continue_digest, journal_seed
from ox_ai.runtime.evidence_index import ActorEvidenceIndex

ACTOR = "#42"
GENERATION = "b" * 32
PAGE = 128


def make_event(n: int, payload_chars: int) -> dict:
    # Repeatable but not perfectly compressible: prose interspersed with a
    # per-event digest. These are invented synthetic ship records, not real
    # crew dialogue or representative frequencies of every ship subsystem.
    basis = (
        f"Ship engineering log {n}: inspected equipment; correlated pressure, "
        f"temperature and shift report. digest="
        + hashlib.sha256(f"ox-bench:{n}".encode()).hexdigest()
        + "; no autonomous work authorization implied. "
    )
    text = (basis * (payload_chars // len(basis) + 1))[:payload_chars]
    data = {"case_id": f"case-{n % 257:04d}", "observation": n}
    kind = "ship_notice"
    if n == 1:
        kind, data["hail_id"] = "crew_hail", "long-open-hail"
    elif n == 2:
        kind, data["ticket_id"] = "captain_problem_open", "long-open-ticket"
    elif n % 512 == 20:
        kind, data["hail_id"] = "crew_hail", f"hail-{n}"
    elif n % 512 == 21:
        kind, data["hail_id"] = "hail_answered", f"hail-{n - 1}"
    elif n % 512 == 22:
        kind, data["ticket_id"] = "captain_problem_open", f"ticket-{n}"
    elif n % 512 == 23:
        kind, data["ticket_id"] = "captain_world_resolved", f"ticket-{n - 1}"
    return {
        "event_id": f"oxevt-v2-{n:08d}", "sequence": n,
        "recipient_dbref": ACTOR, "sender_dbref": "#19",
        "kind": kind, "data": data, "text": text, "game_time": float(n),
    }


def snap(index: ActorEvidenceIndex, path: Path) -> dict:
    db = index._db  # Read-only diagnostic PRAGMAs; no semantic bypass.
    return {
        "file_bytes": path.stat().st_size,
        "sqlite_page_size": db.execute("PRAGMA page_size").fetchone()[0],
        "sqlite_page_count": db.execute("PRAGMA page_count").fetchone()[0],
        "sqlite_freelist_pages": db.execute("PRAGMA freelist_count").fetchone()[0],
        "hot_rows": index.hot_count,
        "cold_rows": index.cold_count,
        "cold_body_bytes": int(db.execute(
            "SELECT COALESCE(SUM(LENGTH(body)),0) FROM cold_events"
        ).fetchone()[0]),
        "uncompressed_hot_bytes": int(db.execute(
            "SELECT COALESCE(SUM(LENGTH(payload)),0) FROM events"
        ).fetchone()[0]),
        "indexes_bytes": "included in SQLite file_bytes, not estimated independently",
    }


def samples_ms(index: ActorEvidenceIndex, n: int) -> dict:
    # Each event-id query decompresses and validates the *complete* original.
    # Use varied sequence positions, including the oldest cold records.
    positions = sorted(set(
        1 + (n - 1) * i // 199 for i in range(200)
    ))
    durations = []
    for serial in positions:
        started = time.perf_counter_ns()
        proof = index.view().get(f"oxevt-v2-{serial:08d}")
        durations.append((time.perf_counter_ns() - started) / 1e6)
        assert proof is not None and proof["sequence"] == serial
    started = time.perf_counter_ns()
    selected = list(index.view().select(
        kind="ship_notice", data={"case_id": "case-0005"},
    ))
    selector_ms = (time.perf_counter_ns() - started) / 1e6
    assert all(e["kind"] == "ship_notice"
               and e["data"]["case_id"] == "case-0005"
               for e in selected)
    pending = index.view().pending("hail")
    assert [e["data"]["hail_id"] for e in pending] == ["long-open-hail"]
    return {
        "exact_lookup_samples": len(durations),
        "exact_lookup_median_ms": round(statistics.median(durations), 5),
        "exact_lookup_p95_ms": round(
            sorted(durations)[int(.95 * (len(durations) - 1))], 5,
        ),
        "case_selector_total_ms": round(selector_ms, 4),
        "case_selector_matches": len(selected),
    }


def profile_case(
    n: int, payload_chars: int, *, trials: int, profile_hotspot: bool,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="ox-history-profile-") as folder:
        path = Path(folder) / "actor.sqlite3"
        index = ActorEvidenceIndex(path, ACTOR)
        digest = journal_seed(GENERATION, ACTOR)
        build_cpu_start = time.process_time()
        build_start = time.perf_counter()
        with index.transaction():
            for start in range(1, n + 1, PAGE):
                page = [
                    make_event(i, payload_chars)
                    for i in range(start, min(start + PAGE, n + 1))
                ]
                index.append_page(page)
                for event in page:
                    digest = continue_digest(digest, event)
            index.replace_pins({"oxevt-v2-00000003"})
            index.compact_hot()
            index.seal_attestation(GENERATION, digest)
        build_s = time.perf_counter() - build_start
        build_cpu_s = time.process_time() - build_cpu_start
        pre_close = snap(index, path)
        assert index.cursor == n and index.hot_count <= 260
        index.close()

        # This is the actual persisted-cache path, including fresh DB open
        # and rebuilt TEMP obligation projection. No synthetic bypasses.
        open_start = time.perf_counter()
        index = ActorEvidenceIndex(path, ACTOR)
        reopen_s = time.perf_counter() - open_start
        generation, cursor, expected = index.stored_attestation()
        assert generation == GENERATION and cursor == n and expected == digest
        verified = []
        cpu = []
        for trial in range(trials):
            start_cpu = time.process_time()
            start = time.perf_counter()
            actual = index.recompute_prefix(generation)
            verified.append(time.perf_counter() - start)
            cpu.append(time.process_time() - start_cpu)
            assert actual == expected
        lookups = samples_ms(index, n)
        profile_excerpt = None
        if profile_hotspot:
            profiler = cProfile.Profile()
            profiler.enable()
            actual = index.recompute_prefix(generation)
            profiler.disable()
            assert actual == expected
            output = io.StringIO()
            pstats.Stats(profiler, stream=output).sort_stats(
                "cumtime"
            ).print_stats(18)
            profile_excerpt = output.getvalue()
        # Benchmark the small incremental extension separately. An ordinary
        # warm delta hashes only new world events, not the entire prefix.
        extension = [
            make_event(i, payload_chars) for i in range(n + 1, n + PAGE + 1)
        ]
        start = time.perf_counter()
        with index.transaction():
            index.append_page(extension)
            for event in extension:
                digest = continue_digest(digest, event)
            index.compact_hot()
            index.seal_attestation(GENERATION, digest)
        delta_s = time.perf_counter() - start
        assert index.cursor == n + PAGE
        assert index.stored_attestation() == (GENERATION, n + PAGE, digest)
        index.close()
        return {
            "actor_events": n,
            "synthetic_text_chars": payload_chars,
            "initial_synthetic_generate_insert_hash_compact_s": round(build_s, 5),
            "initial_cpu_seconds": round(build_cpu_s, 5),
            "sqlite_reopen_seconds": round(reopen_s, 5),
            "restart_verify_first_s": round(verified[0], 5),
            "restart_verify_median_s": round(statistics.median(verified), 5),
            "restart_verify_cpu_median_s": round(statistics.median(cpu), 5),
            "restart_verify_trials": trials,
            "append_128_new_events_s": round(delta_s, 5),
            "before_delta_storage": pre_close,
            "lookup": lookups,
            "hotspot_cprofile": profile_excerpt,
        }


def run(*, sizes: tuple[int, ...], payloads: tuple[int, ...],
        trials: int, profile_hotspot: bool) -> dict:
    cases = []
    for payload in payloads:
        for n in sizes:
            case = profile_case(
                n, payload, trials=trials,
                profile_hotspot=profile_hotspot and
                                payload == max(payloads) and n == max(sizes),
            )
            cases.append(case)
            print(
                f"OX_EVIDENCE_PROFILE_PASS count={n} text_chars={payload} "
                f"verify_first_s={case['restart_verify_first_s']:.5f} "
                f"local_build_s={case['initial_synthetic_generate_insert_hash_compact_s']:.5f} "
                f"db_bytes={case['before_delta_storage']['file_bytes']}",
                flush=True,
            )
    return {
        "experiment": "p4f_attested_evidence_local_restart_profile",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version,
            "peak_process_maxrss_kb_linux": resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss,
        },
        "parameters": {"actor_dbref": ACTOR, "hot_target": 256,
                       "page_size": PAGE, "generation": "synthetic"},
        "cases": cases,
        "limitations": [
            "Single-actor deterministic synthetic events, not natural voyage telemetry.",
            "Build stage includes Python synthetic-event generation and local SQLite; no network costs.",
            "Verify stage reads local hot/cold SQLite and validates original prefix and obligations.",
            "Repeated verification trials may benefit from warmed operating-system page cache.",
            "No actual Evennia socket, 40 simultaneous processes, hosted cognition, or GPU use.",
            "Numbers from shared CI runners are observations, never performance SLAs.",
            "All original world events and referenced proofs remain required and retained.",
        ],
    }


def positive_csv(value: str, *, minimum: int, maximum: int) -> tuple[int, ...]:
    result = tuple(int(part) for part in value.split(","))
    if (not result or len(set(result)) != len(result)
            or any(n < minimum or n > maximum for n in result)):
        raise ValueError(f"Expected distinct values in [{minimum}, {maximum}]")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1000,10000,40000")
    parser.add_argument("--payloads", default="160,1200")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--hotspot", action="store_true")
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    sizes = positive_csv(options.sizes, minimum=300, maximum=250_000)
    payloads = positive_csv(options.payloads, minimum=32, maximum=16_384)
    if not 1 <= options.trials <= 5:
        parser.error("--trials must be 1..5")
    result = run(
        sizes=sizes, payloads=payloads,
        trials=options.trials, profile_hotspot=options.hotspot,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(encoded, encoding="utf-8")
    # Concise, comparable output plus optional CPU profiler excerpt.
    for case in result["cases"]:
        if case["hotspot_cprofile"]:
            print(case["hotspot_cprofile"], flush=True)
    print("OX_P4F_LOCAL_EVIDENCE_PROFILE_JSON=" + json.dumps({
        "cases": [{
            key: value for key, value in case.items() if key != "hotspot_cprofile"
        } for case in result["cases"]],
        "environment": result["environment"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
