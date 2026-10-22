"""Live Evennia P4a boundary: person routes to GOAP or native Concordia.

This is an opt-in, separately provisioned real-world test. The one choice
follows Ari's addressed radio alarm and physical inspection. The real WorkStep
ledger submits and reconciles at most one isolation request. A deferred
choice intentionally leaves the cooling alarm unresolved.

The mock model is only a deterministic alternate-choice fixture; actual
LLM comparison remains a separate experiment. No production supervisor
switches are changed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from collections.abc import Callable

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.agents.goap_crew import pump_action_model
from ox_ai.agents.live_concordia import LiveCrewBrain
from ox_ai.planning.goap import GoapPlanner
from ox_ai.ports.base import ActionOutcome
from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.ports.evennia.durable import DurableEvenniaPort
from ox_ai.runtime.cognition_scheduler import DecisionScheduler
from ox_ai.runtime.personality_routing import (
    PersonalityRouter, CharacterRouteController, PersonalState,
)
from ox_ai.runtime.watch_service import atomic_json
from ox_ai.runtime.work_steps import WorkStepLedger, SimulatedWorkInterruption
from ox_ai.scenarios.p3b_goap import inspect
from ox_ai.scenarios.p3c_crew import IDS, URL, next_event, replayable_event


TRAITS = {
    "methodical": {
        "conscientiousness": 92, "risk_tolerance": 20,
        "authority_challenge": 15, "openness": 38, "neuroticism": 30,
    },
    "independent": {
        "conscientiousness": 50, "risk_tolerance": 88,
        "authority_challenge": 90, "openness": 70, "neuroticism": 35,
    },
}
STATE = PersonalState(stress=.4, uncertainty=.6, fatigue=.2)
CHOICES = (
    CommandOption("Follow training: isolate P-01 after local low pressure reading",
                  "isolate", "pump"),
    CommandOption("Defer isolation and request assistance", "defer"),
)


class DeferChoiceModel:
    """Deterministic smoke fixture; emphatically NOT emergent behaviour."""
    def sample_choice(self, prompt, responses, *, seed=None):
        if len(responses) != 2:
            raise ValueError("Boundary must offer two alternatives")
        return 1, responses[1], {}
    def sample_text(self, *args, **kwargs):
        raise AssertionError("Model has only bounded choice output")


def _model(name: str):
    if name=="scripted-defer":
        return DeferChoiceModel()
    if name=="decider-q4":
        from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
        path=os.environ.get("OX_DECIDER_GGUF_PATH","")
        return DeciderGGUFChoiceModel(path,[o.label for o in CHOICES])
    if name=="qwen-q4":
        from ox_ai.inference.compatible_chat import CompatibleChatModel
        return CompatibleChatModel(
            "qwen3.5-4b",api_key="local-no-secret",
            api_base="http://127.0.0.1:8080/v1",
        )
    raise ValueError("Unsupported cognition provider")


def _profile(persona: str):
    if persona not in TRAITS:
        raise ValueError("Only authored trial personalities allowed")
    return compose_blueprint(
        "live.pump." + persona, persona.title() + " Engineer",
        templates=("occupation.environmental_technician",),
        trait_overrides=TRAITS[persona],
    )


def _select_coverage_seed(profile, actor: str, boundary: str,
                          expected: str) -> str:
    """CI ONLY: exercise both branches, without changing policy probabilities.

    This is coverage-oriented seed selection and cannot be used to claim a
    naturally observed frequency or an optimal personality.
    """
    if expected not in ("goap", "llm"):
        raise ValueError("Only the two routing branches may be exercised")
    for i in range(256):
        seed="ox-p4a-boundary-seed-" + str(i)
        probe=PersonalityRouter(profile, actor, {}, seed=seed)
        p=probe.probability(STATE, "ambiguous")
        if ("llm" if probe._draw(boundary) < p else "goap")==expected:
            return seed
    raise RuntimeError("Failed to find deterministic coverage seed")


def _outcome(report, *, state: dict, brain: LiveCrewBrain, route,
             status: str, source_event_id: str | None = None):
    report.update({
        "status":status, "route":route.selected,
        "route_probability":route.probability_llm,
        "route_roll":route.roll,
        "source_event_id":source_event_id,
        "world_commands_sent":1 if state.get("work_steps",{}).get("isolate") else 0,
        "world_actor":brain.character_id,
        "model_calls":brain.inference_calls,
        "physical_work_steps":state.get("work_steps", {}),
    })
    return report


async def run(*, persona: str, expect_route: str,
              checkpoint: Path, verdict: Path,
              model_name: str = "scripted-defer",
              interrupt_at: str | None = None) -> dict:
    ids=json.loads(IDS.read_text(encoding="utf-8"))
    if set(ids)!={"lin","ari","iona"}:
        raise ValueError("P4a world fixture requires exactly three identities")
    profile=_profile(persona)
    actor=ids["ari"]
    model=_model(model_name)
    trial_name=f"p4a-personality.{persona}"
    if checkpoint.is_file():
        state=json.loads(checkpoint.read_text(encoding="utf-8"))
        if (state.get("version") != 1 or
                state.get("persona") != persona or
                state.get("model_name") != model_name or
                state.get("actor") != actor or
                state.get("experiment") != trial_name):
            raise PermissionError("Recovered routing world actor or trial changed")
        brain=LiveCrewBrain.from_checkpoint(
            "ari",actor,model,checkpoint.with_suffix(".brain.json"),
        )
        if brain.agent.blueprint != profile:
            raise PermissionError("Checkpoint psychology changed")
    else:
        state={"version":1, "experiment":trial_name, "persona":persona,
               "actor":actor, "model_name":model_name,
               "phase":"new", "route_ledger":{},
               "work_steps":{}}
        brain=LiveCrewBrain("ari",actor,model,blueprint=profile)

    def persist():
        brain.save_checkpoint(checkpoint.with_suffix(".brain.json"))
        atomic_json(checkpoint,state)

    password=os.environ["OX_PROBE_PASSWORD"]
    sessions={}
    for role,name in (("lin","OxBotLin"),("ari","OxBotAri")):
        sessions[role]=EvenniaWebSocketClient(
            URL,name,password,ids[role],timeout=15,
        )
    report={"experiment":trial_name,"persona":persona,
            "model":model_name,
            "goap_planner":"GoapPlanner/pump_action_model",
            "world_authority":"Evennia",
            "route_seed_provenance":"CI branch coverage; NOT empirical personality frequency",
            "restart":checkpoint.is_file()}
    try:
        for c in sessions.values():
            await c.open()
        ari=sessions["ari"]
        if state["phase"]=="new":
            lin=sessions["lin"]
            memory={"lin":[],"ari":[]}
            alarm=await replayable_event(lin,"coolant_alarm",memory["lin"])
            # Bridge actually transmits the alarm. The engineer can only
            # decide after receiving the addressed world-generated radio.
            await lin.send_line("oxradio")
            radio=await next_event(ari,"radio_alert",memory["ari"])
            if radio["sender_dbref"]!=ids["lin"] or radio["data"].get("alarm_id")!=alarm["data"].get("alarm_id"):
                raise PermissionError("Radio was not an authentic addressed alarm")
            brain.observe_event(radio)
            reading=await inspect(ari)
            brain.observe_local("Actual engineering P-01 inspection",reading)
            if "LOW PRESSURE" not in reading:
                raise RuntimeError("No verified fault to act on")
            boundary=f"incident.{radio['event_id']}.isolation"
            seed=_select_coverage_seed(profile,actor,boundary,expect_route)
            state["boundary"]=boundary
            state["seed"]=seed
            state["phase"]="observed"
            persist()
        if state["phase"] in ("observed","chosen"):
            router=PersonalityRouter(
                profile,actor,state["route_ledger"],seed=state["seed"],
            )
            boundary=state["boundary"]
            if state["phase"]=="observed":
                controller=CharacterRouteController(
                    router,DecisionScheduler(max_parallel=1,timeout_seconds=20),
                    role="ari",
                )
                result=await controller.decide(
                    agent=brain.agent,planner=GoapPlanner(pump_action_model()),
                    beliefs=frozenset({"at_engineering","status_known",
                                       "pump_low_pressure"}),
                    goals=frozenset({"pump_isolated"}),options=CHOICES,
                    boundary_id=boundary,kind="ambiguous",state=STATE,
                    persist=persist,
                )
                if result.route.selected!=expect_route:
                    raise AssertionError("Coverage seed did not produce requested route")
                state["chosen_verb"]=result.action.verb
                state["model_choice_details"]=getattr(model,"last",None)
                state["phase"]="chosen"
                state["model_calls_at_choice"]=result.model_calls
                if result.route.selected=="llm":
                    # This is an internal decision outcome, not success of
                    # a physical command. No work submitted for 'defer'.
                    brain.agent.record_outcome(ActionOutcome(
                        result.action.request_id,"succeeded",
                        "Locally selected a proposed action, not a world effect",
                    ))
                persist()
            route=router.select(
                boundary_id=boundary,kind="ambiguous",state=STATE,
                observation_revision=brain.agent.revision,
                cognition_revision=brain.agent.cognition_revision,
                persist=lambda: (_ for _ in ()).throw(AssertionError("Route rerolled")),
            )
            if state["chosen_verb"]=="defer":
                state["phase"]="deferred"
                persist()
                outcome=_outcome(report,state=state,brain=brain,route=route,status="deferred_no_isolation")
                verdict.parent.mkdir(parents=True,exist_ok=True)
                atomic_json(verdict,outcome)
                return outcome
            if state["chosen_verb"]!="isolate":
                raise PermissionError("Unrecognized selected command")
            state["phase"]="prepared_or_pending"
            persist()
        if state["phase"]=="prepared_or_pending":
            router=PersonalityRouter(
                profile,actor,state["route_ledger"],seed=state["seed"],
            )
            route=router.select(
                boundary_id=state["boundary"],kind="ambiguous",state=STATE,
                observation_revision=brain.agent.revision,
                cognition_revision=brain.agent.cognition_revision,
                persist=lambda: (_ for _ in ()).throw(AssertionError("Route rerolled")),
            )
            # This is the real world-owned WorkReceipt operation. On a
            # crashed process, the ORIGINAL durable ID must be reconciled.
            outcome=await WorkStepLedger(
                state,persist,character_ids={"ari":actor},
            ).run(
                "isolate","ari","isolate_pump","pump",
                DurableEvenniaPort(ari),interrupt_at=interrupt_at,
            )
            if not outcome.source_event_id:
                raise RuntimeError("Isolation lacked authoritative world receipt")
            reading=await inspect(ari)
            brain.observe_local("Post-isolation physical inspection",reading)
            if "ISOLATED" not in reading:
                raise RuntimeError("World disagreed with isolation receipt")
            state["phase"]="isolated"
            persist()
            finished=_outcome(
                report,state=state,brain=brain,route=route,
                status="isolated_verified",source_event_id=outcome.source_event_id,
            )
            verdict.parent.mkdir(parents=True,exist_ok=True)
            atomic_json(verdict,finished)
            return finished
        raise RuntimeError("Trial already terminated or has invalid phase")
    finally:
        for c in sessions.values():
            await c.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--persona",choices=tuple(TRAITS),required=True)
    p.add_argument("--model",choices=("scripted-defer","decider-q4","qwen-q4"),
                   default="scripted-defer")
    p.add_argument("--expect-route",choices=("goap","llm"),required=True)
    p.add_argument("--checkpoint",type=Path,required=True)
    p.add_argument("--verdict",type=Path,required=True)
    p.add_argument("--interrupt-at",choices=("isolate:prepared","isolate:committed"))
    args=p.parse_args()
    print(json.dumps(asyncio.run(run(
        persona=args.persona,expect_route=args.expect_route,
        checkpoint=args.checkpoint,verdict=args.verdict,
        model_name=args.model,interrupt_at=args.interrupt_at,
    )),sort_keys=True))


if __name__=="__main__":
    main()
