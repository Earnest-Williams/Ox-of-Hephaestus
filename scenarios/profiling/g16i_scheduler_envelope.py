"""G16i: bounded scheduler-admission envelope from genuine G16f CPU data.

Read-only deterministic QUEUE MODEL, not actual native concurrent throughput,
not a world operation, not a live supervisor policy. Uses verified 40-actor
native median/p95 service times from the original 198-forward G16f artifact.
It compares the currently configured deadline with immutable hypothetical
arrival schedules under one MEASURED serial scoring lane, and two IDEALIZED
independent lanes (which are NOT supported native hardware evidence).

Does not fit unobserved latency distributions, model physiological realism,
or permit automatic fallthrough from an already-persisted Decider route.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
import statistics


NATIVE_RUN = 40048062817
NATIVE_MODEL_HASH = "c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b"
DEADLINE_SECONDS = 25.0
POPULATIONS = (6, 20, 40)
SEEDS = tuple(range(615, 627))
ARRIVAL_BURSTS = (0.0, 3.0, 10.0, 22.0)
DUTY_OPPORTUNITIES_HOURLY = (0.5, 1.0, 2.0, 4.0)
DELIBERATION_PROBABILITIES = (0.10, 0.38, 0.66, 1.00)


@dataclass(frozen=True, slots=True)
class Arrival:
    at: float
    actor: int
    ordinal: int


def validate_native_g16f(data: object) -> dict:
    if (not isinstance(data, dict)
            or data.get("schema") != 1
            or data.get("experiment") != "g16f_deliberate_personality_throughput"
            or data.get("backend") != "decider-q4"
            or data.get("native_gguf_forwards_measured") is not True
            or data.get("hypothetical_only") is not True
            or data.get("evennia_commands_sent") != 0
            or data.get("forward_calls") != 198
            or data.get("maximum_concurrent_native_forwards") != 1
            or data.get("default_production_timeout_seconds") != 25
            or data.get("engine_manifest", {}).get("sha256") != NATIVE_MODEL_HASH
            or data.get("engine_manifest", {}).get("model") != "decider-q4"):
        raise PermissionError("Actual pinned G16f native CPU reference is mandatory")
    cohorts = data.get("measured_cohorts")
    if (not isinstance(cohorts, list)
            or [x.get("actors") for x in cohorts] != [6, 20, 40]
            or [x.get("model_forwards_counted") for x in cohorts] != [18, 60, 120]
            or [x.get("decisions_completed") for x in cohorts] != [6, 20, 40]
            or any(x.get("arrival_pattern") != "sequential" for x in cohorts)):
        raise PermissionError("Native reference was not a full sequential 6/20/40 test")
    for x in cohorts:
        for k in ("median_end_to_end_seconds", "p95_end_to_end_seconds",
                  "measured_decisions_per_hour_at_this_backend"):
            v=x.get(k)
            if type(v) not in (float, int) or not math.isfinite(v) or v <= 0:
                raise ValueError("Native service reference is not finite")
        if x["p95_end_to_end_seconds"] < x["median_end_to_end_seconds"]:
            raise ValueError("Invalid native p95 reference")
    return data


def measured_service_seconds(data: dict, *, percentile: str) -> float:
    if percentile not in ("median", "p95"):
        raise ValueError("Only actually observed native quantiles are allowed")
    key = ("p95_end_to_end_seconds" if percentile == "p95"
           else "median_end_to_end_seconds")
    return float(data["measured_cohorts"][2][key])


def burst(population: int, separation: float) -> tuple[Arrival, ...]:
    if population not in POPULATIONS or separation not in ARRIVAL_BURSTS:
        raise ValueError("Unexpected cohort or burst separation")
    return tuple(Arrival(i*separation, i, 0) for i in range(population))


def stochastic_duty_arrivals(population: int, *, duty_rate: float,
                             route_probability: float,
                             seed: int) -> tuple[Arrival, ...]:
    """ONE simulated hour, explicit Poisson hypothesis, not measured duty use."""
    if (population not in POPULATIONS
            or duty_rate not in DUTY_OPPORTUNITIES_HOURLY
            or route_probability not in DELIBERATION_PROBABILITIES
            or seed not in SEEDS):
        raise ValueError("G16i demand grid is frozen")
    rng = random.Random(seed + 9731*population
                        + 103*int(duty_rate*100)
                        + 107*int(route_probability*100))
    rows=[]
    for actor in range(population):
        t = 0.0
        n = 0
        while True:
            t += rng.expovariate(duty_rate/3600.0)
            if t >= 3600.0:
                break
            if rng.random() < route_probability:
                rows.append(Arrival(t,actor,n))
            n += 1
    return tuple(sorted(rows,key=lambda a:(a.at,a.actor,a.ordinal)))


def simulate(arrivals: tuple[Arrival, ...], *, service_seconds: float,
             workers: int, mode: str, deadline: float=DEADLINE_SECONDS) -> dict:
    """Model irrevocable decision calls, no world action or model simulation.

    'queued': a task MAY start before expiry even when completion is too late:
              this models timeout/orphaned worker waste. Queued tasks that
              expire before worker availability cannot start native inference.
    'bounded': reject before starting any work whose modeled completion
               exceeds the submitted deadline. A refusal never sends a GOAP
               or world request.
    All inferences model single shared native CPU unless workers=2, which
    is explicitly only an idealized unmeasured independent-engine bound.
    """
    if (mode not in ("queued","bounded") or workers not in (1,2)
            or not math.isfinite(service_seconds) or service_seconds <= 0
            or deadline != 25.0):
        raise ValueError("Unsupported model or timer scenario")
    if tuple(sorted(arrivals,key=lambda a:(a.at,a.actor,a.ordinal))) != arrivals:
        raise ValueError("Arrival sequence must be deterministic and ordered")
    slots = [0.0]*workers
    actor_until: dict[int,float] = {}
    completions = []
    refused = expired_queued = expired_after_start = same_actor_blocked = 0
    native_started = 0
    elapsed_queue = []
    for row in arrivals:
        if (not isinstance(row,Arrival) or row.at < 0
                or not math.isfinite(row.at)
                or type(row.actor) is not int or row.actor < 0):
            raise ValueError("Malformed arrival")
        # Same actor's previous detached or pending work cannot be duplicated.
        if actor_until.get(row.actor,0.0) > row.at:
            same_actor_blocked += 1
            continue
        slot = min(range(workers), key=lambda i:(slots[i],i))
        start = max(row.at,slots[slot])
        end = start + service_seconds
        cutoff = row.at + deadline
        if mode == "bounded" and end > cutoff:
            refused += 1
            continue
        if start >= cutoff:
            expired_queued += 1
            continue
        native_started += 1
        slots[slot] = end
        actor_until[row.actor] = end
        elapsed_queue.append(start-row.at)
        if end > cutoff:
            expired_after_start += 1
        else:
            completions.append(end-row.at)
    return {
        "arrivals": len(arrivals), "mode": mode,
        "assumed_workers": workers,
        "measured_concurrent_engine": workers == 1,
        "accepted_native_starts": native_started,
        "completed_before_deadline": len(completions),
        "refused_unexecuted": refused,
        "expired_while_queued": expired_queued,
        "expired_after_native_started": expired_after_start,
        "same_actor_inflight_refusals": same_actor_blocked,
        "no_world_commands": True,
        "mean_wait_seconds_for_started": (
            statistics.mean(elapsed_queue) if elapsed_queue else 0.0),
        "max_latency_seconds_for_success": max(completions,default=0.0),
    }


def run(data:dict) -> dict:
    validate_native_g16f(data)
    tables=[]
    for population in POPULATIONS:
        for spacing in ARRIVAL_BURSTS:
            arrivals=burst(population,spacing)
            for p in ("median","p95"):
                seconds=measured_service_seconds(data,percentile=p)
                for workers in (1,2):
                    for policy in ("queued","bounded"):
                        result=simulate(arrivals,service_seconds=seconds,
                                        workers=workers,mode=policy)
                        tables.append({
                            "population":population,
                            "burst_spacing_seconds":spacing,
                            "service_source":p,
                            **result,
                        })
    demand=[]
    for pop in POPULATIONS:
        for duty in DUTY_OPPORTUNITIES_HOURLY:
            for probability in DELIBERATION_PROBABILITIES:
                for policy in ("queued","bounded"):
                    trials=[
                        simulate(stochastic_duty_arrivals(
                            pop,duty_rate=duty,
                            route_probability=probability,seed=seed),
                            service_seconds=measured_service_seconds(
                                data,percentile="p95"),
                            workers=1,mode=policy)
                        for seed in SEEDS
                    ]
                    demand.append({
                        "population":pop,
                        "hypothetical_duty_opportunities_per_actor_hour":duty,
                        "hypothetical_deliberation_probability":probability,
                        "policy":policy,
                        "service_source":"actual_g16f_40_actor_p95_constant",
                        "replicates":len(trials),
                        "mean_deliberate_arrivals_per_hour":statistics.mean(
                            t["arrivals"] for t in trials),
                        "mean_completed_before_deadline_per_hour":statistics.mean(
                            t["completed_before_deadline"] for t in trials),
                        "mean_refused_or_timed_out_per_hour":statistics.mean(
                            t["refused_unexecuted"]
                            + t["expired_while_queued"]
                            + t["expired_after_native_started"]
                            + t["same_actor_inflight_refusals"]
                            for t in trials),
                        "mean_wasted_native_starts_per_hour":statistics.mean(
                            t["expired_after_native_started"] for t in trials),
                    })
    if len(tables) != 3*4*2*2*2 or len(demand)!=3*4*4*2:
        raise AssertionError("G16i frozen model grid incomplete")
    return {
        "schema":1,"experiment":"g16i_hypothetical_admission_envelope",
        "source_native_run":NATIVE_RUN,
        "model_sha256":NATIVE_MODEL_HASH,
        "real_native_forwards_in_this_model":0,
        "actual_concurrent_native_capacity_measured":1,
        "two_workers_are_only_optimistic_unverified":True,
        "deadline_seconds":25,
        "reference_40_actor_sequential_median_seconds":measured_service_seconds(
            data,percentile="median"),
        "reference_40_actor_sequential_p95_seconds":measured_service_seconds(
            data,percentile="p95"),
        "burst_tables":tables,
        "hourly_hypothetical_demand_sweep":demand,
        "model_qualifications":(
            "Discrete-event replay of bounded, deterministic arrivals using "
            "observed sequential 40-actor median/p95 as CONSTANT hypothetical "
            "service times. Individual latency distribution, actual decision "
            "arrival process, native concurrency speedup and GOAP fallback are "
            "not measured. Refusal means no action is created; original "
            "actor-specific route and ledger semantics must be respected. "
            "Not an SLA or evidence for activation."
        ),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--native-g16f",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    x=json.loads(a.native_g16f.read_text(encoding="utf-8"))
    r=run(x)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",
                        encoding="utf-8")
    forty=lambda policy:[z for z in r["burst_tables"] if (
        z["population"]==40 and z["burst_spacing_seconds"]==0
        and z["service_source"]=="p95" and z["assumed_workers"]==1
        and z["mode"]==policy)][0]
    print(json.dumps({
        "real_forwards":r["real_native_forwards_in_this_model"],
        "40_simultaneous_native_completed_queued":forty("queued")[
            "completed_before_deadline"],
        "40_simultaneous_native_completed_bounded":forty("bounded")[
            "completed_before_deadline"],
        "40_simultaneous_bounded_refused":forty("bounded")[
            "refused_unexecuted"],
    },sort_keys=True))
    print("OX_G16I_HYPOTHETICAL_QUEUE_CAPACITY_NOT_NATIVE_CONCURRENCY")


if __name__=="__main__":
    main()
