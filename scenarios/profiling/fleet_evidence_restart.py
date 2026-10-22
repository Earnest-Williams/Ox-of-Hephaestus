#!/usr/bin/env python3
"""P4f fleet restart profile using the actual actor-private SQLite archive.

This is NOT a live 40-account Evennia login or a native Concordia restore.
The measured work is filesystem reopen, full retained-event prefix and
obligation verification, and old-source retrieval for distinct actors.

In the running supervisor, archive reads are synchronous in one Python
process. Here, staggered and simultaneous *threads* model candidate startup
scheduling, not a claim that production currently launches 40 verifiers.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import sqlite3
import statistics
import tempfile
import time

from ox_ai.ports.evennia.journal import continue_digest, journal_seed
from ox_ai.runtime.evidence_index import ActorEvidenceIndex

GENERATION = "b" * 32
PAGE = 128
BUNDLE = 512
FIRST_ACTOR = 1000


def actor_specs(actors: int, events_per_actor: int) -> list[dict]:
    """25% lighter, 50% typical, 25% heavier, with global interleaving."""
    if type(actors) is not int or actors < 4 or actors % 4:
        raise ValueError("Actor count must be a multiple of four, >= 4")
    if type(events_per_actor) is not int or events_per_actor < 600:
        raise ValueError("At least 600 baseline events per actor are required")
    specs = []
    for i in range(actors):
        count = (
            events_per_actor // 2 if i < actors // 4
            else events_per_actor if i < actors * 3 // 4
            else events_per_actor * 3 // 2
        )
        specs.append({
            "ordinal": i,
            "actor_dbref": f"#{FIRST_ACTOR + i}",
            "event_count": count,
        })
    return specs


def event_for(actor: dict, local: int, actors: int, chars: int) -> dict:
    """Distinct journal IDs, shared interleaved sequence, isolated recipient."""
    sequence = (local - 1) * actors + actor["ordinal"] + 1
    anchor = (
        f"Ship notice {sequence}, actor {actor['actor_dbref']}: "
        "inspection, engineering observations and shift report; "
        f"checksum={hashlib.sha256(str(sequence).encode()).hexdigest()}; "
    )
    text = (anchor * (chars // len(anchor) + 1))[:chars]
    kind = "ship_notice"
    data = {"case_id": f"case-{local % 257:04d}", "observation": local}
    if local == 1:
        kind, data["hail_id"] = "crew_hail", "open-hail"
    elif local == 2:
        kind, data["ticket_id"] = "captain_problem_open", "open-ticket"
    elif local % 512 == 20:
        kind, data["hail_id"] = "crew_hail", f"hail-{local}"
    elif local % 512 == 21:
        kind, data["hail_id"] = "hail_answered", f"hail-{local - 1}"
    elif local % 512 == 22:
        kind, data["ticket_id"] = "captain_problem_open", f"ticket-{local}"
    elif local % 512 == 23:
        kind, data["ticket_id"] = "captain_world_resolved", f"ticket-{local - 1}"
    return {
        "event_id": f"oxevt-v2-{sequence:010d}",
        "sequence": sequence,
        "recipient_dbref": actor["actor_dbref"],
        "sender_dbref": "#19",
        "kind": kind,
        "data": data,
        "text": text,
        "game_time": float(sequence),
    }


def build_archives(root: Path, specs: list[dict], chars: int) -> dict:
    """Build production hot/cold files in increments, with real repack policy.

    Setup is explicitly outside every timed restart experiment.
    """
    started = time.perf_counter()
    actors = len(specs)
    for actor in specs:
        path = root / f"actor-{actor['ordinal']:02d}.sqlite3"
        index = ActorEvidenceIndex(path, actor["actor_dbref"])
        os.chmod(path, 0o600)
        digest = journal_seed(GENERATION, actor["actor_dbref"])
        pin_seq = 2 * actors + actor["ordinal"] + 1
        try:
            index.replace_pins({f"oxevt-v2-{pin_seq:010d}"})
            repacks = 0
            for first in range(1, actor["event_count"] + 1, BUNDLE):
                end = min(first + BUNDLE, actor["event_count"] + 1)
                with index.transaction():
                    for page_first in range(first, end, PAGE):
                        page = [
                            event_for(actor, local, actors, chars)
                            for local in range(page_first, min(page_first + PAGE, end))
                        ]
                        index.append_page(page)
                        for event in page:
                            digest = continue_digest(digest, event)
                    index.compact_hot()
                    index.seal_attestation(GENERATION, digest)
                repacks += bool(index.repack_if_worthwhile())
            newest = (actor["event_count"] - 1) * actors + actor["ordinal"] + 1
            if (
                index.cursor != newest
                or len(index.view()) != actor["event_count"]
                or index.stored_attestation() != (GENERATION, newest, digest)
            ):
                raise AssertionError("Archive build lost an addressed event or seal")
            if index.cold_count == 0:
                raise AssertionError("Fleet fixture did not exercise cold evidence")
            actor.update({
                "path": str(path),
                "expected_digest": digest,
                "cursor": newest,
                "hot_rows": index.hot_count,
                "cold_rows": index.cold_count,
                "repack_count": repacks,
                "file_bytes": path.stat().st_size,
            })
            print(
                f"OX_FLEET_BUILT actor={actor['actor_dbref']} "
                f"events={actor['event_count']} cold={actor['cold_rows']} "
                f"repacked={repacks}",
                flush=True,
            )
        finally:
            index.close()
    return {
        "build_wall_s": round(time.perf_counter() - started, 5),
        "archive_bytes": sum(a["file_bytes"] for a in specs),
        "total_events": sum(a["event_count"] for a in specs),
        "total_repack_operations": sum(a["repack_count"] for a in specs),
    }


def verify_actor(actor: dict, started: float, actors: int) -> dict:
    """Fresh connection per actor; no shared SQLite handle across threads."""
    began = time.perf_counter()
    cpu_began = time.thread_time()
    index = ActorEvidenceIndex(Path(actor["path"]), actor["actor_dbref"])
    try:
        opened = time.perf_counter()
        attested = index.stored_attestation()
        expected = (GENERATION, actor["cursor"], actor["expected_digest"])
        if attested != expected:
            raise RuntimeError("Fleet restart local attestation differs from fixture")
        actual = index.recompute_prefix(GENERATION)
        verified = time.perf_counter()
        if actual != actor["expected_digest"]:
            raise RuntimeError("Fleet restart reconstructed prefix differs from fixture")
        # These are old proof identities retained well beyond the hot window.
        first = actor["ordinal"] + 1
        third = 2 * actors + actor["ordinal"] + 1
        if (
            index.view().get(f"oxevt-v2-{first:010d}")["kind"] != "crew_hail"
            or index.view().get(f"oxevt-v2-{third:010d}")["sequence"] != third
            or len(list(index.view().pending("hail"))) != 1
            or len(list(index.view().pending("captain"))) != 1
        ):
            raise AssertionError("Fleet old source or unresolved obligation missing")
        finished = time.perf_counter()
        return {
            "actor_dbref": actor["actor_dbref"],
            "event_count": actor["event_count"],
            "start_offset_s": round(began - started, 5),
            "sqlite_open_s": round(opened - began, 5),
            "prefix_and_obligations_s": round(verified - opened, 5),
            "old_proof_queries_s": round(finished - verified, 5),
            "ready_offset_s": round(finished - started, 5),
            "thread_cpu_s": round(time.thread_time() - cpu_began, 5),
        }
    finally:
        index.close()


def percentile(values: list[float], share: float) -> float:
    if not values or not (0 < share <= 1):
        raise ValueError("Nonempty samples and percentile in (0, 1] required")
    return sorted(values)[math.ceil(share * len(values)) - 1]


def linux_io() -> dict | None:
    """Linux counters: physical read_bytes may be zero when files are cached."""
    try:
        pairs = (
            line.split(":", 1) for line in
            Path("/proc/self/io").read_text(encoding="utf-8").splitlines()
        )
        return {key.strip(): int(value) for key, value in pairs}
    except (OSError, ValueError):
        return None


def run_cohort(specs: list[dict], *, mode: str, width: int) -> dict:
    actors = len(specs)
    workers = actors if mode == "simultaneous" else width
    if mode not in ("staggered", "simultaneous") or not 1 <= workers <= actors:
        raise ValueError("Invalid fleet restart scheduling policy")
    before = resource.getrusage(resource.RUSAGE_SELF)
    io_before = linux_io()
    cpu_before = time.process_time()
    started = time.perf_counter()
    # All 40 are eligible immediately. In staggered mode only 'width'
    # workers run; later actors begin as earlier verifications finish.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(verify_actor, actor, started, actors)
            for actor in specs
        ]
        results = [future.result() for future in futures]
    finished = time.perf_counter()
    cpu = time.process_time() - cpu_before
    after = resource.getrusage(resource.RUSAGE_SELF)
    io_after = linux_io()
    return {
        "mode": mode,
        "parallel_workers": workers,
        "cohort_wall_s": round(finished - started, 5),
        "cohort_process_cpu_s": round(cpu, 5),
        "cohort_cpu_per_wall": round(cpu / (finished - started), 4),
        "first_actor_ready_s": round(min(x["ready_offset_s"] for x in results), 5),
        "median_actor_ready_s": round(statistics.median(
            x["ready_offset_s"] for x in results
        ), 5),
        "p95_actor_ready_s": round(percentile(
            [x["ready_offset_s"] for x in results], .95
        ), 5),
        "p95_prefix_verify_s": round(percentile(
            [x["prefix_and_obligations_s"] for x in results], .95
        ), 5),
        "sum_thread_cpu_s": round(sum(x["thread_cpu_s"] for x in results), 5),
        "max_rss_kb_linux": after.ru_maxrss,
        "major_faults": after.ru_majflt - before.ru_majflt,
        "input_blocks": after.ru_inblock - before.ru_inblock,
        "output_blocks": after.ru_oublock - before.ru_oublock,
        "physical_read_bytes_linux": (
            io_after["read_bytes"] - io_before["read_bytes"]
            if io_before is not None and io_after is not None else None
        ),
        "actors": results,
    }


def summarize_rounds(rounds: list[dict]) -> list[dict]:
    """Compare candidate worker widths, without changing the actor count."""
    answer = []
    for workers in sorted({round_["parallel_workers"] for round_ in rounds}):
        group = [r for r in rounds if r["parallel_workers"] == workers]
        answer.append({
            "parallel_workers": workers,
            "mode": group[0]["mode"],
            "rounds": len(group),
            "median_cohort_wall_s": round(statistics.median(
                r["cohort_wall_s"] for r in group
            ), 5),
            "median_first_actor_ready_s": round(statistics.median(
                r["first_actor_ready_s"] for r in group
            ), 5),
            "median_p95_actor_ready_s": round(statistics.median(
                r["p95_actor_ready_s"] for r in group
            ), 5),
            "median_p95_prefix_verify_s": round(statistics.median(
                r["p95_prefix_verify_s"] for r in group
            ), 5),
            "median_process_cpu_s": round(statistics.median(
                r["cohort_process_cpu_s"] for r in group
            ), 5),
            "median_cpu_per_wall": round(statistics.median(
                r["cohort_cpu_per_wall"] for r in group
            ), 4),
            "median_physical_read_bytes_linux": (
                round(statistics.median(
                    r["physical_read_bytes_linux"] for r in group
                )) if all(r["physical_read_bytes_linux"] is not None
                         for r in group) else None
            ),
        })
    return answer


def profile_fleet(
    *, actors: int, events_per_actor: int, chars: int,
    stagger_width: int, trials: int, widths: tuple[int, ...] | None = None,
) -> dict:
    if not 1 <= trials <= 4 or not 1 <= stagger_width < actors:
        raise ValueError("Invalid trial count or stagger width")
    if not 64 <= chars <= 16384:
        raise ValueError("Payload must be 64..16384 characters")
    if widths is None:
        # Retain the original two-policy profile for reproducibility.
        selected_widths = (stagger_width, actors)
    else:
        if (
            not widths or len(set(widths)) != len(widths)
            or any(type(width) is not int or not 1 <= width <= actors
                   for width in widths)
        ):
            raise ValueError("Widths must be distinct integers between 1 and actors")
        selected_widths = tuple(widths)
    specs = actor_specs(actors, events_per_actor)
    if sum(s["event_count"] for s in specs) > 3_000_000:
        raise ValueError("Fleet benchmark limited to three million events")
    with tempfile.TemporaryDirectory(prefix="ox-p4f-fleet-") as folder:
        root = Path(folder)
        build = build_archives(root, specs, chars)
        rounds = []
        # Reverse candidate order on alternating trials to reduce, not erase,
        # the confounding effect of warmed OS caches and variable CI load.
        for trial in range(trials):
            order = selected_widths if trial % 2 == 0 else selected_widths[::-1]
            for width in order:
                mode = "simultaneous" if width == actors else "staggered"
                record = run_cohort(specs, mode=mode, width=width)
                record["trial"] = trial + 1
                rounds.append(record)
                print(
                    f"OX_FLEET_VERIFIED trial={trial+1} mode={mode} "
                    f"actors={actors} workers={width} "
                    f"wall_s={record['cohort_wall_s']:.5f} "
                    f"cpu_s={record['cohort_process_cpu_s']:.5f} "
                    f"first_ready_s={record['first_actor_ready_s']:.5f} "
                    f"p95_ready_s={record['p95_actor_ready_s']:.5f}",
                    flush=True,
                )
        return {
            "experiment": "p4f_fleet_local_archive_restart",
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version,
                "cpu_count": os.cpu_count(),
            },
            "fixture": {
                "actors": actors,
                "baseline_events_per_actor": events_per_actor,
                "event_distribution": "25% half; 50% baseline; 25% one-and-a-half",
                "synthetic_text_chars": chars,
                "page": PAGE,
                "bundle": BUNDLE,
                "stagger_width": stagger_width,
                "worker_widths": list(selected_widths),
                "scheduling_order": "forward/reversed each alternating trial",
                "generation": "synthetic",
                "build": build,
                "actor_archives": [
                    {
                        "actor_dbref": actor["actor_dbref"],
                        "events": actor["event_count"],
                        "cursor": actor["cursor"],
                        "file_bytes": actor["file_bytes"],
                        "hot_rows": actor["hot_rows"],
                        "cold_rows": actor["cold_rows"],
                        "repack_count": actor["repack_count"],
                    }
                    for actor in specs
                ],
            },
            "rounds": rounds,
            "summary": summarize_rounds(rounds),
            "stage_coverage": {
                "production_sqlite_reopen": True,
                "complete_archive_and_obligation_verification": True,
                "old_world_source_lookup": True,
                "native_concordia_checkpoint_restore": False,
                "evennia_websocket_authentication": False,
                "nonce_bound_world_journal_certificate": False,
                "live_40_actor_supervisor": False,
            },
            "limitations": [
                "All candidate widths verify the SAME complete actor population.",
                "Synthetic 40-recipient interleaved history; not measured voyage telemetry.",
                "ThreadPoolExecutor tests candidate scheduling, not current supervisor concurrency.",
                "Build/setup time is excluded from every measured restart round.",
                "Verification remains O(each actor's complete addressed history).",
                "SQLite data may be in the OS page cache; Linux physical_read_bytes can be zero.",
                "Process CPU and thread CPU distinguish contention; do not infer real disk latency from cached reads.",
                "Process maxrss is a lifetime high-water mark, not cohort-specific peak memory.",
                "Real native brain restore, world authentication, and certificate round trips are not measured.",
                "No truncation, no reassignment of actor scope, and no weakening of local digest checks.",
                "Shared CI runner numbers are observations, never performance SLAs.",
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actors", type=int, default=40)
    parser.add_argument("--events-per-actor", type=int, default=40000)
    parser.add_argument("--payload-chars", type=int, default=1200)
    parser.add_argument("--stagger-width", type=int, default=4)
    parser.add_argument("--widths", help="Distinct concurrency widths, e.g. 1,2,4,8,16,40")
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    try:
        result = profile_fleet(
            actors=options.actors,
            events_per_actor=options.events_per_actor,
            chars=options.payload_chars,
            stagger_width=options.stagger_width,
            trials=options.trials,
            widths=(tuple(int(x) for x in options.widths.split(","))
                    if options.widths is not None else None),
        )
    except ValueError as exc:
        parser.error(str(exc))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(encoded, encoding="utf-8")
    print("OX_P4F_FLEET_SUMMARY_JSON=" + json.dumps({
        "fixture": result["fixture"]["build"],
        "summary": result["summary"],
        "stage_coverage": result["stage_coverage"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
