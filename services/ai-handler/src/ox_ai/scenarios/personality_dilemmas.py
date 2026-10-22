"""Decider-only behavioural probes: motives versus a real symbolic GOAP baseline.

These are ACTOR-SCOPED, AUTHOR-DEFINED situations, not authenticated Evennia
world observations. Every result is an ActionRequest PROPOSAL, never execution.
The paired arms hold persona, perceived facts, action menu and routing draw
constant and vary only a private, fallible recollection. Coverage seeds are
selected to exercise the LLM branch, NOT to estimate natural consultation rates.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path

from ox_ai.agents.crew import CommandOption, CrewAgent, CrewIdentity
from ox_ai.agents.crew_blueprints import compose_blueprint
from ox_ai.memory.seeds import SeededMemory
from ox_ai.planning.goap import GoapAction, GoapPlanner
from ox_ai.ports.base import WorldObservation
from ox_ai.runtime.cognition_scheduler import DecisionScheduler
from ox_ai.runtime.personality_routing import (
    CharacterRouteController, PersonalState, PersonalityRouter,
)


@dataclass(frozen=True, slots=True)
class Dilemma:
    key: str
    subject: str
    evidence: str
    kind: str
    state: PersonalState
    procedure: GoapAction
    choices: tuple[CommandOption, ...]


# Exact same observed facts for all characters and both memory arms. Nothing
# in these fixtures certifies actual ship condition, permissions, or outcomes.
DILEMMAS = (
    Dilemma(
        "pump_mara", "pump",
        "Training says isolate P-01 following the confirmed low-pressure "
        "reading. The shift log also shows a missed check by Mara. Mara asks "
        "you to delay filing the incident because she fears losing her berth.",
        "social", PersonalState(stress=.5, fatigue=.2,
                                 social_pressure=.8, uncertainty=.4),
        GoapAction("isolate_pump", frozenset({"observed"}),
                   frozenset({"handled"}), verb="isolate", target="pump"),
        (
            CommandOption("Isolate pump P-01 now as the procedure specifies",
                          "isolate", "pump"),
            CommandOption("Recheck pump P-01 privately before acting",
                          "recheck", "pump"),
            CommandOption("Ask the chief to decide about pump P-01 and Mara",
                          "escalate", "pump"),
            CommandOption("Delay pump P-01 isolation to protect Mara",
                          "defer", "pump"),
        ),
    ),
    Dilemma(
        "cargo_jon", "cargo",
        "The local cargo restraint gauge is red. Departure procedure says "
        "secure the affected pallet before handover. Jon, who signed its "
        "earlier inspection, asks you to leave it until the next watch because "
        "a reported defect may remove him from the preferred route.",
        "social", PersonalState(stress=.3, fatigue=.5,
                                 social_pressure=.7, uncertainty=.3),
        GoapAction("secure_cargo", frozenset({"observed"}),
                   frozenset({"handled"}), verb="secure", target="cargo"),
        (
            CommandOption("Secure the cargo restraint now and record the defect",
                          "secure", "cargo"),
            CommandOption("Inspect cargo once more before filing anything",
                          "recheck", "cargo"),
            CommandOption("Call a relief officer to review cargo with Jon",
                          "escalate", "cargo"),
            CommandOption("Leave the cargo restraint and protect Jon's record",
                          "defer", "cargo"),
        ),
    ),

    Dilemma(
        "routine_filter", "filter",
        "A scrubber filter passed the immediate air-quality test, but its "
        "nonurgent maintenance ticket is due before shift end. The spare is "
        "on hand and the old unit can safely stay online for one more watch. "
        "Rae, who signed an earlier service report, asks you to avoid a ticket "
        "that might expose her bookkeeping mistake.",
        "social", PersonalState(stress=.25, fatigue=.3,
                                 social_pressure=.85, uncertainty=.3),
        GoapAction("record_filter_ticket", frozenset({"observed"}),
                   frozenset({"handled"}), verb="record", target="filter"),
        (
            CommandOption("File the filter maintenance ticket in the shift log",
                          "record", "filter"),
            CommandOption("Inspect the filter a second time before filing",
                          "recheck", "filter"),
            CommandOption("Help Rae replace the filter first, then file the ticket",
                          "assist", "filter"),
            CommandOption("Privately postpone the filter report for Rae",
                          "defer", "filter"),
        ),
    ),
    Dilemma(
        "duty_swap", "watch",
        "You have been assigned a routine gauge watch. The gauge is currently "
        "normal and another qualified crewmember is available, but your posted "
        "roster has not been changed. Your friend Lio asks you to cover his "
        "navigation watch so he can visit an ill family member. The duty "
        "officer is available to authorize a roster swap.",
        "social", PersonalState(stress=.2, fatigue=.4,
                                 social_pressure=.9, uncertainty=.2),
        GoapAction("attend_gauge_watch", frozenset({"observed"}),
                   frozenset({"handled"}), verb="attend", target="watch"),
        (
            CommandOption("Attend your posted gauge watch as scheduled",
                          "attend", "watch"),
            CommandOption("Ask the duty officer to approve the watch swap",
                          "request", "watch"),
            CommandOption("Cover Lio's watch immediately, arranging relief informally",
                          "cover", "watch"),
            CommandOption("Offer to help Lio later but keep today's assignment",
                          "decline", "watch"),
        ),
    ),
)

PERSONAS = {
    "methodical": {
        "actor": "#811",
        "traits": {"conscientiousness": 95, "risk_tolerance": 16,
                   "authority_challenge": 12, "openness": 36,
                   "agreeableness": 50, "collaboration": 65},
        "background": "Has a reputation for written checklists and consistency.",
        "memories": {
            "pump_mara": "I once overlooked a low pump reading to save a colleague embarrassment; later I saw a ruptured line and was frightened by my own omission.",
            "cargo_jon": "A pallet slipped when I deferred a red restraint gauge years ago. I promised myself not to trust a verbal assurance over the local reading.",
            "routine_filter": "A forgotten routine filter ticket once caused a confusing week of duplicate maintenance. I rely on written logs to prevent that recurring mistake.",
            "duty_swap": "When colleagues improvised shifts without updating the roster, two people thought they were on relief. I remember the awkward scramble and now insist on a recorded switch.",
        },
    },
    "loyal": {
        "actor": "#812",
        "traits": {"conscientiousness": 48, "risk_tolerance": 73,
                   "authority_challenge": 52, "agreeableness": 95,
                   "collaboration": 92, "extraversion": 75},
        "background": "Finds personal obligations as compelling as formal duty.",
        "memories": {
            "pump_mara": "Mara stayed beside me through a frightening injury and risked her position to help me. I feel fiercely protective of her livelihood.",
            "cargo_jon": "Jon took responsibility for a mistake that I had made on our previous cargo run. I think I owe him the chance to avoid a formal charge.",
            "routine_filter": "Rae stayed up through two watches nursing me through illness. I believe she will personally put this filter problem right if I help rather than make her mistake public.",
            "duty_swap": "Lio once took an extra watch so I could be with a sick relative. I promised I would return that kindness if he ever needed me.",
        },
    },
    "defiant": {
        "actor": "#813",
        "traits": {"conscientiousness": 33, "risk_tolerance": 89,
                   "authority_challenge": 96, "openness": 82,
                   "agreeableness": 35, "uncertainty_tolerance": 85},
        "background": "Dislikes commands issued without explanation.",
        "memories": {
            "pump_mara": "The chief once ordered an unnecessary pump isolation, publicly blamed me for the downtime, and later refused to acknowledge the mistake.",
            "cargo_jon": "A supervisor once demanded a needless cargo hold and accused me of insubordination when my second inspection showed the gauge was defective.",
            "routine_filter": "A duty officer once used an inconsequential service ticket to punish my friend Rae. I resented the decision and thought he should have let us fix it ourselves.",
            "duty_swap": "A duty officer publicly forbade a reasonable shift swap, even with qualified relief. Since then I tend to distrust petty roster rules and solve problems among crewmates.",
        },
    },
}


class FixtureFirstChoice:
    """Only a no-download integration fixture. Not a behavioural model."""
    prompts: list[str] = []

    def sample_choice(self, prompt, responses, *, seed=None):
        self.prompts.append(prompt)
        return 0, responses[0], {}

    def sample_text(self, *args, **kwargs):
        raise AssertionError("Only a finite-action choice is permitted")


def profile_for(persona: str):
    data = PERSONAS[persona]
    return compose_blueprint(
        "dilemma." + persona, persona.title() + " Engineer",
        templates=("occupation.environmental_technician",),
        trait_overrides=data["traits"], history=(data["background"],),
    )


def coverage_seed(profile, actor: str, boundary: str, state: PersonalState,
                  kind: str) -> str:
    """Force LLM branch for coverage only; do not use for behavioural rates."""
    for n in range(2048):
        seed = "ox-dilemma-coverage-" + str(n)
        router = PersonalityRouter(profile, actor, {}, seed=seed)
        if router._draw(boundary) < router.probability(state, kind):
            return seed
    raise RuntimeError("Unable to cover LLM branch")


async def run_dossier(*, model_name: str = "fixture",
                      gguf_path: str | Path | None = None) -> dict:
    """Make counterbalanced paired proposals without world access."""
    if model_name not in ("fixture", "decider-q4"):
        raise ValueError("Only the selected Decider model or fixture is supported")
    shared_engine = None
    records = []
    # Position counterbalance: detect whether semantic choices survive a change
    # in list position. Order is NOT selected for a desirable answer.
    orders = ("canonical", "reversed")
    for case in DILEMMAS:
        planner = GoapPlanner((case.procedure,))
        first = planner.plan(frozenset({"observed"}),
                             frozenset({"handled"})).actions[0]
        if first.verb != case.choices[0].verb or first.target != case.choices[0].target:
            raise RuntimeError("Authored GOAP control is not an offered action")
        for persona, description in PERSONAS.items():
            actor = description["actor"]
            profile = profile_for(persona)
            boundary = "fixture." + case.key + ".procedure"
            seed = coverage_seed(profile, actor, boundary, case.state, case.kind)
            for order in orders:
              offered = (case.choices if order == "canonical"
                         else tuple(reversed(case.choices)))
              for arm in ("unseeded", "remembered"):
                if model_name == "fixture":
                    model = FixtureFirstChoice()
                else:
                    from ox_ai.inference.decider_gguf_choice import DeciderGGUFChoiceModel
                    model = DeciderGGUFChoiceModel(
                        gguf_path or os.environ.get("OX_DECIDER_GGUF_PATH", ""),
                        [option.label for option in offered],
                        engine=shared_engine,
                    )
                    if shared_engine is None:
                        shared_engine = model.engine
                seeds = ()
                if arm == "remembered":
                    seeds = (SeededMemory(
                        memory_id="dilemma." + persona + "." + case.key,
                        text=description["memories"][case.key],
                        about=case.subject,
                        confidence=80, salience=90,
                        occurred_turn=-30, learned_turn=0,
                    ),)
                agent = CrewAgent(
                    CrewIdentity(
                        "ox.person." + profile.person_id, actor, profile.name,
                        "Watch engineer", "Keep the ship serviceable",
                    ), model, blueprint=profile, initial_memories=seeds,
                )
                # A deliberately authored, recipient-scoped experiment
                # observation; never describe it as actual Evennia evidence.
                agent.observe(WorldObservation(
                    observation_id="fixture.observation." + case.key,
                    character_id=actor, game_time=10.0,
                    text=case.evidence, kind="authored_fixture",
                ))
                record = {}
                router = PersonalityRouter(profile, actor, record, seed=seed)
                controller = CharacterRouteController(
                    router,
                    DecisionScheduler(max_parallel=1, timeout_seconds=(
                        110 if model_name == "decider-q4" else 10)),
                    role="engineer." + persona,
                )
                checkpoints = []
                proposal = await controller.decide(
                    agent=agent, planner=planner,
                    beliefs=frozenset({"observed"}),
                    goals=frozenset({"handled"}),
                    options=offered, boundary_id=boundary,
                    kind=case.kind, state=case.state,
                    persist=lambda: checkpoints.append(
                        json.loads(json.dumps(record))),
                )
                if (proposal.route.selected != "llm" or
                        proposal.model_calls != 1 or len(checkpoints) != 1 or
                        len(agent.pending_requests) != 1 or
                        agent.pending_requests[0] != proposal.action):
                    raise RuntimeError("Dilemma violated bounded decision contract")
                matching = [
                    option for option in offered
                    if (option.verb, option.target,
                        dict(option.arguments)) ==
                       (proposal.action.verb, proposal.action.target,
                        dict(proposal.action.arguments))
                ]
                if len(matching) != 1:
                    raise RuntimeError("Unrecognized or ambiguous choice")
                records.append({
                    "case": case.key, "persona": persona, "arm": arm,
                    "order": order, "chosen_position": next(
                        i for i, option in enumerate(offered)
                        if option.verb == proposal.action.verb),
                    "actor": actor,
                    "baseline_goap_action": first.name,
                    "baseline_goap_verb": first.verb,
                    "choice": proposal.action.verb,
                    "choice_label": matching[0].label,
                    "different_from_goap": proposal.action.verb != first.verb,
                    "routing_probability": proposal.route.probability_llm,
                    "routing_roll": proposal.route.roll,
                    "route": proposal.route.selected,
                    "model_calls": proposal.model_calls,
                    "native_option_logits": getattr(model, "last", None),
                    "world_commands_sent": 0,
                })
    paired = []
    for case in DILEMMAS:
        for persona in PERSONAS:
            for order in orders:
                pair = [r for r in records
                        if r["case"] == case.key and r["persona"] == persona
                        and r["order"] == order]
                if len(pair) != 2:
                    raise RuntimeError("Incomplete paired decisions")
                base, recollection = pair
                if (base["arm"], recollection["arm"]) != ("unseeded", "remembered"):
                    raise RuntimeError("Paired arm order changed")
                paired.append({
                    "case": case.key, "persona": persona, "order": order,
                    "same_route_roll": base["routing_roll"] == recollection["routing_roll"],
                    "memory_changed_choice": base["choice"] != recollection["choice"],
                    "unseeded_choice": base["choice"],
                    "remembered_choice": recollection["choice"],
                })
    order_invariant = []
    for case in DILEMMAS:
        for persona in PERSONAS:
            for arm in ("unseeded", "remembered"):
                rowset = [r for r in records
                          if r["case"] == case.key and r["persona"] == persona
                          and r["arm"] == arm]
                if len(rowset) != 2:
                    raise RuntimeError("Incomplete order counterbalance")
                order_invariant.append({
                    "case": case.key, "persona": persona, "arm": arm,
                    "same_choice_across_order": rowset[0]["choice"] == rowset[1]["choice"],
                    "canonical_choice": rowset[0]["choice"],
                    "reversed_choice": rowset[1]["choice"],
                })
    return {
        "schema": 1, "model": model_name,
        "selected_engine": "Decider 4B Q4_K_M" if model_name == "decider-q4"
                           else "fixture, not real inference",
        "experiment": "within-persona remembered vs unseeded motivations",
        "routing_seed_provenance": "LLM-branch coverage, not natural routing frequency",
        "world_evidence": "authored simulation fixture, not Evennia",
        "world_commands_sent": 0,
        "model_generated_reasons": False,
        "interpretation": "Choice shifts are observations, not proof of motive or correctness",
        "rows": records, "paired": paired,
        "order_invariant": order_invariant,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("fixture", "decider-q4"),
                        default="decider-q4")
    parser.add_argument("--gguf-path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outcome = asyncio.run(run_dossier(
        model_name=args.model, gguf_path=args.gguf_path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True),
                           encoding="utf-8")
    print(json.dumps({
        "model": outcome["model"], "decisions": len(outcome["rows"]),
        "paired_memory_changes": sum(
            int(row["memory_changed_choice"]) for row in outcome["paired"]),
        "order_stable": sum(
            int(row["same_choice_across_order"]) for row in outcome["order_invariant"]),
        "different_from_goap": sum(
            int(row["different_from_goap"]) for row in outcome["rows"]),
        "report": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
