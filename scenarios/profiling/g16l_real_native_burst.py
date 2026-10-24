"""G16l: actual 25-second native G16c 6/20/40 actor burst acceptance.

Original G16f real Concordia actor/controller/catalog/replay path. Changes
ONLY arrival pattern and scheduler deadline to existing production defaults.
One physically measured native scoring lane; no Evennia, work, or dialogue.
Results include logged timeout, no proposals for timed-out characters, and
native forward counts. An expired model worker may continue until reaped.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import tempfile
import time

from ox_ai.agents.crew import CommandOption
from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import (
    CognitionBusy, CognitionTimedOut, DecisionScheduler,
)
from ox_ai.runtime.personality_routing import PersonalState
from ox_contracts import load_catalog
from g16f_personality_throughput import (
    COHORTS, MENU_KEY, MODEL_REVISIONS, FakeSystemOne,
    EngineMeter, make_actor,
)

GGUF_SHA256 = "c03deb433d539ef49579fca5a015d5090c739a331448493aded7a57ad9b4261b"
TIMEOUT_SECONDS = 25.0
MODEL_SLOTS = 1


def hash_file(path:Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as source:
        while block:=source.read(8*1024*1024):
            digest.update(block)
    return digest.hexdigest()


def validate_source(gguf:Path|None, manifest:Path|None, engine:str):
    if engine=="fixture":
        return FakeSystemOne(), {"synthetic_source_for_shape_only":True}
    if engine!="decider-q4" or gguf is None or manifest is None:
        raise ValueError("G16l must use exact native Decider Q4 or explicit fake fixture")
    if not gguf.is_file() or not manifest.is_file():
        raise FileNotFoundError("Full real GGUF and publisher manifest required")
    record=json.loads(manifest.read_text(encoding="utf-8"))
    if (record.get("model")!="decider-q4"
            or record.get("sha256")!=GGUF_SHA256
            or (record.get("hf_revision"),record.get("tokenizer_revision"))!=MODEL_REVISIONS
            or record.get("size")!=gguf.stat().st_size
            or hash_file(gguf)!=GGUF_SHA256):
        raise PermissionError("Source native model/hash/revision changed")
    real=DeciderGGUFChoiceModel(
        gguf,("accept_help","work_alone","reschedule"),n_threads=2,
    ).engine
    return real,record


def menu_and_goap():
    menu=load_catalog().menu(MENU_KEY)
    if len(menu.options)!=3 or menu.safety_critical:
        raise ValueError("G16l expected exact preauthored nonsafety three-action menu")
    options=tuple(CommandOption(
        "Act: "+o.semantic_key,o.verb,o.target,
    ) for o in menu.options)
    planner=GoapPlanner(tuple(GoapAction(
        o.semantic_key,requires=frozenset({"notes_active"}),
        adds=frozenset({"decision"}),verb=o.verb,target=o.target,
    ) for o in menu.options))
    return menu,options,planner


async def actual_burst(size:int, *, meter:EngineMeter) -> dict:
    if size not in COHORTS:
        raise ValueError("Unknown G16l actor cohort")
    if os.getenv("OX_PERSONALITY_CHOICE")!="1":
        raise PermissionError("G16l isolated experiment needs opt-in typed G16c path")
    menu,offered,planner=menu_and_goap()
    state=PersonalState(stress=.35,social_pressure=.65,fatigue=.2,uncertainty=.4)
    scheduler=DecisionScheduler(
        max_parallel=MODEL_SLOTS,
        per_actor_budget=3,
        total_budget=size*3,
        timeout_seconds=TIMEOUT_SECONDS,
    )
    with tempfile.TemporaryDirectory(prefix="ox-g16l-native-") as scratch:
        root=Path(scratch)
        actors=[make_actor(
            i,scheduler=scheduler,engine=meter,path=root,
            state=state,menu=menu,
        ) for i in range(size)]
        if len({a.brain.identity.character_id for a in actors})!=size:
            raise AssertionError("Actor identities duplicated")
        before=meter.calls
        started=time.perf_counter()
        async def one(actor):
            return await actor.controller.decide(
                agent=actor.brain,planner=planner,
                beliefs=frozenset({"notes_active"}),
                goals=frozenset({"decision"}),
                options=offered,boundary_id=actor.boundary,
                kind="social",state=state,
                menu_key=MENU_KEY,persist=actor.persist,
            )
        tasks=[asyncio.create_task(one(a),name=a.role) for a in actors]
        outcomes=await asyncio.gather(*tasks,return_exceptions=True)
        deadline_phase=time.perf_counter()-started
        ontime=[]
        timeouts=[]
        for a,outcome in zip(actors,outcomes):
            if isinstance(outcome,CognitionTimedOut):
                timeouts.append(a.role)
                if a.brain.pending_requests:
                    raise PermissionError("Timed-out actor silently adopted model proposal")
                if a.boundary in a.router.record.get("personality_choices",{}):
                    raise PermissionError("Timed-out actor had a committed choice ledger")
            elif isinstance(outcome,BaseException):
                raise RuntimeError(
                    "G16l unexpected actor/model failure, refusing false result"
                ) from outcome
            else:
                if (outcome.route.selected!="llm"
                        or outcome.model_calls!=3
                        or outcome.action.character_id!=a.brain.identity.character_id
                        or len(a.brain.pending_requests)!=1
                        or outcome.action not in a.brain.pending_requests
                        or a.boundary not in a.router.record.get("personality_choices",{})
                        or len(a.writes)!=2):
                    raise PermissionError("Native three-forward proposal not durably adopted")
                ontime.append(a.role)
            if (a.boundary not in a.router.record["boundaries"]
                    or not a.router_path.is_file()
                    or json.loads(a.router_path.read_text(encoding="utf-8"))
                       !=a.router.record):
                raise PermissionError("No durable original routing checkpoint")
        # A timed-out to_thread provider still executes; do NOT pretend it was
        # cancelled. Account and wait until every actual worker has exited.
        cleanup_started=time.perf_counter()
        while scheduler.metrics["inflight_roles"]:
            if time.perf_counter()-cleanup_started>150:
                raise TimeoutError("Native orphaned worker did not exit")
            await asyncio.sleep(.05)
        cleanup_seconds=time.perf_counter()-cleanup_started
        diagnostic=scheduler.metrics
        event=diagnostic["queue_observability"]
        native_calls=meter.calls-before
        if (len(ontime)+len(timeouts)!=size
                or native_calls!=3*event["inference_invocations_finished"]
                or event["inference_invocations_started"]
                   !=event["inference_invocations_finished"]
                or event["requests_accepted_for_scheduling"]!=size
                or event["proposals_adopted"]!=len(ontime)
                or event["timed_out_waiting_for_slot"]
                   +event["timed_out_with_provider_active"]!=len(timeouts)
                or event["maximum_simultaneous_inference_invocations"]!=1
                or diagnostic["started"]!=3*size
                or diagnostic["inflight_roles"]
                or event["provider_active_roles"]
                or event["waiting_for_inference_slot"]
                or meter.active
                or meter.peak_active!=1):
            raise PermissionError("Real native deadline/queue/three-forward audit inconsistent")
        return {
            "actors":size,"arrival_pattern":"same_event_loop_tick",
            "actual_provider":"fixture" if isinstance(meter.delegate,FakeSystemOne) else "decider-q4",
            "requested_g16_decisions":size,
            "adopted_valid_nonworld_proposals":len(ontime),
            "expired_no_world_proposals":len(timeouts),
            "native_forward_calls":native_calls,
            "deadline_phase_seconds":deadline_phase,
            "orphaned_native_cleanup_seconds":cleanup_seconds,
            "all_underlying_native_workers_reaped":True,
            "actual_maximum_concurrent_native_forwards":meter.peak_active,
            "scheduler_metrics":diagnostic,
            "physical_work_receipts_created":0,
            "evennia_commands_sent":0,
            "role_names_not_world_actors":True,
            "results_independent_of_hypothetical_queue_predications":True,
        }


async def evaluate(name:str,gguf:Path|None,manifest:Path|None) -> dict:
    source,origin=validate_source(gguf,manifest,name)
    meter=EngineMeter(source)
    output=[]
    for cohort in COHORTS:
        output.append(await actual_burst(cohort,meter=meter))
    return {
        "schema":1,
        "experiment":"g16l_genuine_native_burst_deadline",
        "model":name,
        "all_native_forwards_real":name=="decider-q4",
        "gguf_provenance":origin,
        "deadline_seconds":TIMEOUT_SECONDS,
        "max_native_workers":MODEL_SLOTS,
        "experiment_worker_threads":2,
        "population":[6,20,40],
        "measured_cohorts":output,
        "total_native_system_one_forwards":meter.calls,
        "max_actual_concurrent_native_system_one_forwards":meter.peak_active,
        "real_world_actions_submitted":0,
        "world_receipts_claimed":0,
        "production_policy_adopted":False,
        "limitations":"G16f synthetic-memory 6/20/40 agents, real G16c actor model and real System One native calls; isolated burst, no Evennia authorization, no evidence of a two-worker speedup or long-run duty arrival pattern.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--engine",required=True,choices=("fixture","decider-q4"))
    p.add_argument("--gguf-path",type=Path)
    p.add_argument("--model-manifest",type=Path)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=asyncio.run(evaluate(a.engine,a.gguf_path,a.model_manifest))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        "engine":result["model"],"native_calls":result["total_native_system_one_forwards"],
        "cohorts":[{k:v for k,v in x.items()
                    if k in ("actors","adopted_valid_nonworld_proposals",
                             "expired_no_world_proposals","native_forward_calls")}
                   for x in result["measured_cohorts"]],
    },sort_keys=True))
    print("OX_G16L_ACTUAL_BURST_DEADLINE_VS_NATIVE_FORWARDS_VERIFIED")


if __name__=="__main__":
    main()
