"""G10 scale complement: forty independent personality route ledgers.

20,480 distinct boundaries, repeated and evaluated in reverse order after
JSON checkpoint recovery. There are no native model calls, no Evennia
connections, and no asserted world effects. This directly stress-tests the
determinism and actor ownership on which real Decider consultations rely.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.runtime.personality_routing import (
    PersonalState, PersonalityRouter,
)

ROLES=40
BOUNDARIES=512
KINDS=("routine","ambiguous","social","urgent")


def profile(i):
    if not 0 <= i < ROLES:
        raise ValueError("Not an experimental crew identity")
    procedural=i<20
    # Large group difference plus smaller authentic person-specific variations.
    return compose_blueprint(
        f"pop.person.{i:02d}",f"Population Crew {i:02d}",
        trait_overrides={
            "conscientiousness": 82+(i%5)*3 if procedural else 22+(i%5)*4,
            "risk_tolerance": 12+(i%7)*4 if procedural else 68+(i%7)*4,
            "authority_challenge": 16+(i%7)*4 if procedural else 70+(i%7)*4,
            "openness": 36+(i%5)*4 if procedural else 75+(i%5)*4,
            "neuroticism": 28+(i%5)*8 if procedural else 35+(i%5)*8,
        },
        history=(
            "Experienced procedural watchkeeping; verifies every handover"
            if procedural else
            "Habitually challenges routine instructions and improvises "
            "when ambiguous evidence arrives",
        ),
    )


def situation(kind):
    if kind not in KINDS:
        raise ValueError("Unknown decision kind")
    return PersonalState(
        stress=.62 if kind=="urgent" else .31,
        fatigue=.38, social_pressure=.74 if kind=="social" else .16,
        uncertainty=.82 if kind=="ambiguous" else .42,
    )


def actor_run(i):
    ident=f"#{4100+i}"
    seed=f"forty-crew-route-test-{i:02d}"
    person=profile(i)
    ledger={}
    router=PersonalityRouter(person,ident,ledger,seed=seed)
    routes={}
    saved_count=0
    recorded_prob=Counter()
    recorded_routes=Counter()
    conditions={}
    checkpoint_every=64
    snapshot_files=0

    for number in range(BOUNDARIES):
        kind=KINDS[number%len(KINDS)]
        state=situation(kind)
        boundary=f"pop.{i:02d}.{kind}.{number:04d}"
        def persist():
            nonlocal saved_count
            saved_count+=1
            assert boundary in ledger["boundaries"]
            assert ledger["character_id"]==ident
        decision=router.select(
            boundary_id=boundary,kind=kind,state=state,
            observation_revision=number//3,
            cognition_revision=number//2,
            persist=persist,
        )
        routes[boundary]=decision
        conditions[boundary]=(kind,state)
        recorded_routes[decision.selected]+=1
        recorded_prob[kind]+=decision.probability_llm
        if (number+1)%checkpoint_every==0:
            # Actual JSON round-trip is the explicit durability boundary.
            archived=json.loads(json.dumps(ledger))
            assert archived["character_id"]==ident
            assert len(archived["boundaries"])==number+1
            snapshot_files+=1

    if saved_count!=BOUNDARIES or len(routes)!=BOUNDARIES:
        raise AssertionError("Missing route-specific durable checkpoints")
    restored=json.loads(json.dumps(ledger))
    recovered=PersonalityRouter(person,ident,restored,seed=seed)
    replays=0
    for boundary in reversed(tuple(routes)):
        kind,_=conditions[boundary]
        observed=recovered.select(
            boundary_id=boundary,kind=kind,
            state=PersonalState(stress=1,fatigue=1,social_pressure=1,
                                uncertainty=1),
            observation_revision=900000,
            cognition_revision=900000,
            persist=lambda: (_ for _ in ()).throw(
                AssertionError("Persist called during exact recovery")),
        )
        if observed != routes[boundary]:
            raise AssertionError("Recovery rerolled a frozen route")
        replays+=1

    # Independent fresh ledger processes the same decision IDs in opposite
    # order. A global random stream or evaluation-order dependence fails here.
    reverse={}
    reversed_router=PersonalityRouter(person,ident,reverse,seed=seed)
    for boundary in reversed(tuple(routes)):
        kind,state=conditions[boundary]
        reproduced=reversed_router.select(
            boundary_id=boundary,kind=kind,state=state,
            observation_revision=routes[boundary].observation_revision,
            cognition_revision=routes[boundary].cognition_revision,
            persist=lambda: None,
        )
        if reproduced!=routes[boundary]:
            raise AssertionError("Route changed when independent actors interleaved")

    # The ledger must not be transferred to another body or trait vector.
    try:
        PersonalityRouter(person,"#999999",json.loads(json.dumps(ledger)),seed=seed)
    except PermissionError:
        pass
    else:
        raise AssertionError("Character authority boundary was bypassed")
    try:
        PersonalityRouter(profile((i+1)%ROLES),ident,
                          json.loads(json.dumps(ledger)),seed=seed)
    except PermissionError:
        pass
    else:
        raise AssertionError("Cross-character personality profile was rebound")
    try:
        PersonalityRouter(person,ident,json.loads(json.dumps(ledger)),
                          seed=seed+"-tampered")
    except PermissionError:
        pass
    else:
        raise AssertionError("Seed rollback switched personal history")

    return {
        "identity":ident,"person_id":person.person_id,
        "group":"procedural" if i<20 else "independent",
        "boundaries":len(routes),
        "persistent_writes":saved_count,
        "durable_serializations":snapshot_files,
        "recovered_boundaries":replays,
        "order_invariant_boundaries":len(reverse["boundaries"]),
        "goap_routes":recorded_routes["goap"],
        "decider_routes":recorded_routes["llm"],
        "average_p_llm_by_kind":{
            kind:recorded_prob[kind]/(BOUNDARIES//len(KINDS))
            for kind in KINDS
        },
        "world_commands_sent":0,"native_model_calls":0,
    }


def run():
    evidence=[actor_run(i) for i in range(ROLES)]
    if len({x["identity"] for x in evidence})!=ROLES:
        raise AssertionError("Character IDs collided")
    if len({x["person_id"] for x in evidence})!=ROLES:
        raise AssertionError("Blueprint IDs collided")
    procedural=[x for x in evidence if x["group"]=="procedural"]
    independent=[x for x in evidence if x["group"]=="independent"]
    if len(procedural)!=20 or len(independent)!=20:
        raise AssertionError("Missing persona coverage")
    p_proc=sum(x["decider_routes"] for x in procedural)/(20*BOUNDARIES)
    p_ind=sum(x["decider_routes"] for x in independent)/(20*BOUNDARIES)
    if not p_ind>p_proc+.25:
        raise AssertionError("Independent profiles did not change routing propensity")
    if (not all(x["recovered_boundaries"]==BOUNDARIES
                and x["order_invariant_boundaries"]==BOUNDARIES
                and x["durable_serializations"]==BOUNDARIES//64
                for x in evidence)):
        raise AssertionError("Checkpoint recovery or replay coverage incomplete")

    # One injected disk write failure cannot leave behind an accepted
    # uncheckpointed decision in its actor-private routing ledger.
    record={}
    one=PersonalityRouter(profile(0),"#4100",record,seed="write-fault-check")
    def faulty():
        raise OSError("Faked storage interruption")
    try:
        one.select(boundary_id="pop.injected.failure",kind="social",
                   state=situation("social"),observation_revision=0,
                   cognition_revision=0,persist=faulty)
    except OSError:
        pass
    else:
        raise AssertionError("Failed storage persist was ignored")
    if record["boundaries"]:
        raise AssertionError("Unpersisted route survived failed storage write")

    return {
        "schema":1,"status":"verified_40_actor_personality_route_recovery",
        "actors":ROLES,"unique_boundaries":ROLES*BOUNDARIES,
        "persist_callbacks":sum(x["persistent_writes"] for x in evidence),
        "durable_serializations":sum(x["durable_serializations"] for x in evidence),
        "replayed_boundaries":sum(x["recovered_boundaries"] for x in evidence),
        "reordered_boundaries":sum(x["order_invariant_boundaries"] for x in evidence),
        "goap_routes":sum(x["goap_routes"] for x in evidence),
        "decider_routes":sum(x["decider_routes"] for x in evidence),
        "procedural_decider_rate":p_proc,"independent_decider_rate":p_ind,
        "rejected_cross_character_ledger_rebinds":ROLES*3,
        "injected_storage_failures_rolled_back":1,
        "real_model_calls":0,"world_commands_sent":0,
        "limitations":[
            "These are forty synthetic persona routers, not forty Evennia-connected crewmates.",
            "Differences in route propensity follow configured traits, not observed human behavior.",
            "The verified route is not itself an accepted world action.",
            "Native Decider behavior was separately tested in G10 (216 choices) and G11 (real world replies).",
        ],
        "actor_evidence":evidence,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    report=run()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({k:v for k,v in report.items() if k not in (
        "actor_evidence","limitations"
    )},sort_keys=True))
    print("OX_FORTY_ACTOR_PERSONALITY_RECOVERY_PASS")


if __name__=="__main__":
    main()
