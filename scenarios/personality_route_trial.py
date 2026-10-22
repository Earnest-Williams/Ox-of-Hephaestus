"""P1 personality-weighted routing pilot: model-free planning or Concordia.

Synthetic actor-scoped, meaningful decision boundaries. No Evennia clients,
world commands, authoritative receipts or claim of emergent personality.
Native Concordia MockModel is an INTEGRATION FIXTURE, not a behavioural model.
Run with --decisions 48 for a small reproducible routing-frequency smoke test.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.runtime.cognition_scheduler import DecisionScheduler
from ox_ai.runtime.personality_routing import (
    PersonalityRouter, CharacterRouteController, PersonalState,
)


PROFILES = {
    "methodical": {
        "conscientiousness": 92, "risk_tolerance": 20,
        "authority_challenge": 15, "openness": 38,
        "neuroticism": 30,
    },
    "independent": {
        "conscientiousness": 50, "risk_tolerance": 88,
        "authority_challenge": 90, "openness": 70,
        "neuroticism": 35,
    },
    "social": {
        "conscientiousness": 42, "risk_tolerance": 60,
        "authority_challenge": 52, "openness": 77,
        "neuroticism": 65, "extraversion": 85,
    },
}


async def evaluate(*, decisions: int = 48) -> dict:
    if type(decisions) is not int or not 1 <= decisions <= 128:
        raise ValueError("Pilot decision count must be in 1..128")
    from concordia.testing.mock_model import MockModel

    planner = GoapPlanner((
        GoapAction("inspect_engineering_gauge",
                   requires=frozenset({"at_engineering"}),
                   adds=frozenset({"gauge_inspected"}),
                   verb="inspect",target="gauge"),
    ))
    options=(
        CommandOption("Inspect local gauge according to training",
                      "inspect","gauge"),
        CommandOption("Defer the inspection to the next watch","defer"),
    )
    report={}
    for index,(role,traits) in enumerate(PROFILES.items()):
        character_id=f"#{600+index}"
        profile=compose_blueprint(
            f"pilot.{role}",f"{role.capitalize()} Technician",
            templates=("occupation.environmental_technician",),
            trait_overrides=traits,
        )
        ledger={}
        router=PersonalityRouter(
            profile,character_id,ledger,seed="ox-personality-pilot-v1",
        )
        scheduler=DecisionScheduler(max_parallel=2,timeout_seconds=10)
        controller=CharacterRouteController(router,scheduler,role=role)
        counters=Counter()
        samples=[]
        for turn in range(decisions):
            # A fresh mind per synthetic decision avoids falsely interpreting
            # previous non-submitted proposals as world-resolved actions.
            agent=CrewAgent(
                CrewIdentity(f"ox.person.{profile.person_id}",character_id,
                             profile.name,"Inspect ship's instruments",
                             "Keep equipment serviceable"),
                MockModel(),blueprint=profile,
            )
            kind=("routine","ambiguous","social")[turn%3]
            state=PersonalState(
                stress=.1 if kind=="routine" else .45,
                uncertainty=.0 if kind=="routine" else .6,
                social_pressure=.75 if kind=="social" else 0.,
            )
            proposal=await controller.decide(
                agent=agent,planner=planner,
                beliefs=frozenset({"at_engineering"}),
                goals=frozenset({"gauge_inspected"}),
                options=options,
                boundary_id=f"fixture.{role}.{turn}",
                kind=kind,state=state,persist=lambda: None,
            )
            counters[proposal.route.selected]+=1
            counters["model_calls"]+=proposal.model_calls
            counters["proposed_commands"]+=1
            if (proposal.action.character_id != character_id
                    or proposal.action.verb not in ("inspect","defer")):
                raise AssertionError("Proposal escaped offered options or character")
            samples.append({
                "boundary":proposal.route.boundary_id,
                "route":proposal.route.selected,
                "probability_llm":proposal.route.probability_llm,
                "choice":proposal.action.verb,
                "model_calls":proposal.model_calls,
            })
        report[role]={
            "traits":dict(profile.traits),
            "route_counts":dict(counters),
            "samples":samples,
            "checkpoint_records":len(ledger["boundaries"]),
        }
    return {
        "protocol":"ox_personality_routed_choices_p1",
        "provider":"native_Concordia_MockModel_integration_fixture_NOT_intelligence",
        "decisions_per_character":decisions,
        "actors":report,
        "world_connections":0,
        "world_commands_sent":0,
        "authoritative_world_receipts":0,
        "status":"offline_integration_only",
        "warning":"MockModel's actions are scripted deterministic fixtures; routing "
                  "counts prove deterministic personality/circumstance gating, "
                  "not spontaneous mistakes or personality psychology.",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--decisions",type=int,default=48)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=asyncio.run(evaluate(decisions=args.decisions))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps({
        role:item["route_counts"] for role,item in result["actors"].items()
    },sort_keys=True))


if __name__=="__main__":
    main()
