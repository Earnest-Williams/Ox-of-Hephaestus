"""G16c/d opt-in CharacterRouteController proposal path.

Every decision originates in the router's already-durable actor boundary.
Only the event-loop owner writes the additional immutable choice ledger; the
detached native scorer cannot commit an action to the live agent or world.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
import os
from typing import Any

from ox_ai.agents.crew import CommandOption, CrewAgent, StaleAgentRevision
from ox_ai.inference.disposition_choice import (
    PersonalityAdjustedDeciderChoiceModel, ReplayedPersonalityChoiceModel,
)
from ox_ai.planning.goap import GoapPlanner, PlanUnavailable
from ox_ai.ports.base import ActionRequest
from ox_ai.runtime.disposition_goap import personality_goap_costs
from ox_ai.runtime.personality_choice_ledger import (
    PersonalityChoiceLedger, deterministic_proposal_id,
)
from ox_ai.runtime.personality_routing import (
    PersonalState, RoutedProposal,
)


async def decide_g16(
    controller: Any, *, agent: CrewAgent, planner: GoapPlanner,
    beliefs: frozenset[str], goals: frozenset[str],
    offered: Sequence[CommandOption], boundary_id: str,
    kind: str, state: PersonalState,
    persist: Callable[[], None], menu_key: str,
) -> RoutedProposal:
    """No world connection. Produce a checkpoint-backed pending proposal only."""
    from ox_contracts import load_catalog

    catalog = load_catalog()
    menu = catalog.menu(menu_key)
    catalog_sha = catalog.content_sha256()
    offered = tuple(offered)
    signatures = {
        (x.verb, x.target, tuple(sorted(x.arguments.items()))) for x in offered
    }
    if (len(signatures) != len(offered)
            or signatures != {x.signature for x in menu.options}):
        raise ValueError("Offered commands differ from the authored G16a tag catalog")

    # The original route is checkpointed before any planner or model call.
    route = controller.router.select(
        boundary_id=boundary_id, kind=kind, state=state,
        observation_revision=agent.revision,
        cognition_revision=agent.cognition_revision,
        persist=persist,
    )
    ledger = PersonalityChoiceLedger(controller.router)
    previous = ledger.saved(route=route, menu=menu, catalog_sha256=catalog_sha)
    request_id = deterministic_proposal_id(controller.router, boundary_id)

    if previous is not None:
        if (agent.revision != route.observation_revision
                or agent.cognition_revision != route.cognition_revision):
            raise StaleAgentRevision("Replayed personality choice has stale actor evidence")
        old_requests = [req for req in agent.pending_requests
                        if req.request_id == request_id]
        if old_requests:
            if route.selected != "llm" or len(old_requests) != 1:
                raise PermissionError("Saved action request belongs to another route")
            pending = old_requests[0]
            tagged = menu.by_key(previous["selected_semantic_key"])
            if (pending.character_id != agent.identity.character_id
                    or (pending.verb, pending.target,
                        tuple(sorted(pending.arguments.items()))) != tagged.signature
                    or pending.agent_revision != route.observation_revision):
                raise PermissionError("Saved pending proposal was rebound")
            return RoutedProposal(route, pending, 0, None)

    if route.selected == "goap":
        if previous is None:
            prices = personality_goap_costs(
                planner, menu, agent.blueprint, offered=offered,
            )
            plan = planner.plan(
                beliefs, goals, cost_overrides=prices,
            )
            if not plan.actions:
                raise PlanUnavailable("GOAP has already reached the goal")
            chosen_operator = plan.actions[0]
            tagged = menu.by_command(
                chosen_operator.verb, chosen_operator.target,
                dict(chosen_operator.arguments),
            )
            choice = {
                "planner_costs": prices,
                "draw": route.roll,
                "operator_name": chosen_operator.name,
            }
            ledger.commit(
                route=route, menu=menu, catalog_sha256=catalog_sha,
                selected_semantic_key=tagged.semantic_key,
                choice=choice, persist=persist,
            )
        else:
            tagged = menu.by_key(previous["selected_semantic_key"])
            chosen_operator = next(
                (a for a in planner.actions if
                 a.name == previous["choice"]["operator_name"]),
                None,
            )
            if chosen_operator is None or (chosen_operator.verb,
                    chosen_operator.target, chosen_operator.arguments) != tagged.signature:
                raise PermissionError("Original persisted GOAP operator is unavailable")
        request = ActionRequest(
            request_id=request_id,
            character_id=agent.identity.character_id,
            verb=tagged.verb, target=tagged.target,
            arguments=dict(tagged.arguments),
            agent_revision=route.observation_revision,
        )
        return RoutedProposal(route, request, 0, chosen_operator.name)

    if route.selected != "llm":
        raise PermissionError("Unknown checkpoint route")
    if len(offered) != 3:
        raise ValueError("G16c position-balanced Decider needs exactly three offered actions")

    # Concordia can include the caller's offered-order sequence in the
    # surrounding native prompt. Canonicalize that whole outer choice list,
    # not merely G15's three internal criteria rotations, or a display-order
    # perturbation can change the native actor's prompt.
    canonical_offered = tuple(sorted(
        offered,
        key=lambda o: menu.by_command(
            o.verb, o.target, o.arguments,
        ).semantic_key,
    ))
    options = tuple(
        (menu.by_command(
            o.verb, o.target, o.arguments,
        ).semantic_key, o.label)
        for o in canonical_offered
    )
    if previous is None:
        gguf_path = os.environ.get("OX_DECIDER_GGUF_PATH", "")
        if controller.decider_engine is None and not gguf_path:
            raise RuntimeError("Opt-in G16c requires a configured native Decider GGUF")
        model = PersonalityAdjustedDeciderChoiceModel(
            gguf_path, options, menu=menu, profile=agent.blueprint,
            seed=controller.router.record["seed"],
            actor=controller.router.character_id,
            boundary=boundary_id, kind=kind,
            engine=controller.decider_engine,
        )
    else:
        model = ReplayedPersonalityChoiceModel(previous["choice"], options)

    description = (
        "Character-local self-assessment; not world evidence, permission, "
        "or an order about other people. "
        f"Situation={kind}. Stress={state.stress:.2f}, "
        f"fatigue={state.fatigue:.2f}, social pressure={state.social_pressure:.2f}, "
        f"uncertainty={state.uncertainty:.2f}. "
        "Choose from the exact bounded world offer. No physical result "
        "or consent is established by this proposal."
    )

    def record_before_live_adoption(shadow: CrewAgent, draft: ActionRequest) -> None:
        result = model.last
        if not isinstance(result, dict) or draft.request_id != request_id:
            raise PermissionError("Native scorer has no verified bound selection")
        chosen = menu.by_command(draft.verb, draft.target, draft.arguments)
        if result.get("selected_semantic_key") != chosen.semantic_key:
            raise PermissionError("Native semantic action differs from proposed command")
        ledger.commit(
            route=route, menu=menu, catalog_sha256=catalog_sha,
            selected_semantic_key=chosen.semantic_key,
            choice=result, persist=persist,
        )

    # Three underlying native forwards are budgeted as three, while the
    # shadow Concordia model still sees one ordinary finite-choice request.
    # A prompt-validated ledger replay consumes zero native forwards.
    result = await controller.scheduler.decide(
        controller.role, agent, canonical_offered,
        decision_context=description,
        inference_model=model,
        prepared_request_id=request_id,
        before_adopt=record_before_live_adoption,
        cost_units=3 if previous is None else 1,
    )
    return RoutedProposal(route, result, 3 if previous is None else 0, None)
