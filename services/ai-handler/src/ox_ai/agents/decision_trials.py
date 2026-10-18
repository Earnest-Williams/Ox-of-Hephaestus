"""Offline cognitive-choice probes. No world connection and no action submission.

The same situation and offered options are presented to independently
instantiated minds. The chosen *proposal*, never a physical result, is
recorded. MockModel should NOT be expected to exhibit personality variation.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ox_ai.agents.crew import CommandOption
from ox_ai.agents.crew_blueprints import CrewBlueprint, instantiate_crew
from ox_ai.ports.base import WorldObservation


@dataclass(frozen=True, slots=True)
class DecisionScenario:
    scenario_id: str
    situation: str
    options: tuple[CommandOption, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id or len(self.scenario_id) > 64:
            raise ValueError("Scenario identifier must be bounded")
        if not isinstance(self.situation, str) or not 1 <= len(self.situation) <= 1000:
            raise ValueError("Scenario observation must be bounded")
        if not isinstance(self.options, tuple) or not 2 <= len(self.options) <= 8:
            raise ValueError("Scenario must offer 2-8 actions")
        if any(not isinstance(x, CommandOption) for x in self.options):
            raise TypeError("Only typed command options may be offered")
        if len({x.label for x in self.options}) != len(self.options):
            raise ValueError("Scenario choices must have unique labels")
        signatures = {(x.verb, x.target, tuple(sorted(x.arguments.items())))
                      for x in self.options}
        if len(signatures) != len(self.options):
            raise ValueError("Scenario actions must be distinct")


SCENARIOS: tuple[DecisionScenario, ...] = (
    DecisionScenario(
        "uncertain_reading",
        "You see a mildly inconsistent environmental sensor reading. No active "
        "alarm exists and no critical procedure has been authorised. The chief "
        "engineer is reachable. Both permitted next steps are observational.",
        (
            CommandOption("Inspect another local instrument", "inspect", "second_gauge"),
            CommandOption("Ask a colleague to independently check", "request_review", "chief"),
            CommandOption("Record uncertainty and defer", "defer"),
        ),
    ),
    DecisionScenario(
        "routine_collaboration",
        "A routine inventory count has a small unexplained discrepancy. "
        "No deadline is imminent. A colleague has offered to help. "
        "The discrepancy is not yet a confirmed loss.",
        (
            CommandOption("Recount own assigned shelf", "inspect", "own_stock"),
            CommandOption("Compare notes with colleague", "request_review", "colleague"),
            CommandOption("Document discrepancy for later", "defer"),
        ),
    ),
)


def compare_profiles(
    profiles: Mapping[str, CrewBlueprint],
    *,
    model_factory: Callable[[], Any],
    repeats: int = 3,
    scenarios: tuple[DecisionScenario, ...] = SCENARIOS,
) -> dict[str, Any]:
    """Generate comparable *proposals* with no world client or shared memory.

    Creates a fresh model and mind for every trial, with the same observation,
    menu ordering and role brief. Model behaviour is evidence of a configured
    provider only; deterministic fixtures are integration checks, not psychology.
    """
    if not isinstance(profiles, Mapping) or not 2 <= len(profiles) <= 8:
        raise ValueError("Comparison requires 2-8 distinct personalities")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 16:
        raise ValueError("Repetitions must be 1-16")
    if not isinstance(scenarios, tuple) or not 1 <= len(scenarios) <= 8:
        raise ValueError("Expected 1-8 scenarios")
    ids = set()
    for label, profile in profiles.items():
        if not isinstance(label, str) or not label or len(label) > 64:
            raise ValueError("Invalid comparison cohort label")
        if not isinstance(profile, CrewBlueprint):
            raise TypeError("Profiles must be validated immutable blueprints")
        if profile.person_id in ids:
            raise ValueError("Comparison participants need unique identities")
        ids.add(profile.person_id)

    results: dict[str, dict[str, dict[str, int]]] = {}
    calls = 0
    for index, (label, profile) in enumerate(profiles.items()):
        for scenario in scenarios:
            counts: Counter[str] = Counter()
            for repetition in range(repeats):
                character_id = f"#{900000 + index * 1000 + repetition}"
                brain = instantiate_crew(
                    profile, character_id=character_id,
                    duty="Observe ship equipment and coordinate appropriately",
                    goal="Keep the ship safe using authorised observations",
                    model=model_factory(),
                )
                brain.observe(WorldObservation(
                    observation_id=f"trial-{scenario.scenario_id}-{repetition}",
                    character_id=character_id,
                    game_time=100.0,
                    text=scenario.situation,
                    kind="synthetic_observation",
                ))
                request = brain.decide(
                    scenario.options, expected_revision=brain.revision,
                )
                matched = [option.label for option in scenario.options
                           if (request.verb == option.verb
                               and request.target == option.target
                               and dict(request.arguments) == dict(option.arguments))]
                if len(matched) != 1 or request.character_id != character_id:
                    raise AssertionError("Choice did not match an offered scoped action")
                counts[matched[0]] += 1
                calls += brain.usage.total_calls
                # Deliberately do not send the proposal or turn it into a world receipt.
            results.setdefault(label, {})[scenario.scenario_id] = dict(sorted(counts.items()))
    return {
        "protocol": "ox-offline-profile-choice-v1",
        "type": "unexecuted_proposals",
        "world_actions_submitted": 0,
        "scenarios": [x.scenario_id for x in scenarios],
        "trials_per_profile_per_scenario": repeats,
        "profiles": results,
        "total_inference_calls": calls,
        "caution": "MockModel is deterministic; profile variance requires real "
                   "inference and repeated evaluation, not hardcoded outcomes.",
    }


def representative_profiles() -> dict[str, CrewBlueprint]:
    """Same initial job estimate; different authored tendencies."""
    from ox_ai.agents.crew_blueprints import compose_blueprint
    return {
        "methodical": compose_blueprint(
            "probe.methodical", "Methodical Candidate",
            templates=("occupation.environmental_technician", "ocean.methodical"),
        ),
        "collaborative": compose_blueprint(
            "probe.collaborative", "Collaborative Candidate",
            templates=("occupation.environmental_technician", "ocean.collaborative"),
        ),
    }


if __name__ == "__main__":
    import argparse
    import json
    from ox_ai.agents.live_concordia import make_model
    parser = argparse.ArgumentParser(description="Offline profile choice probes; no world effects")
    parser.add_argument("--provider", choices=("mock", "gemini"), default="mock")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(compare_profiles(
        representative_profiles(),
        model_factory=lambda: make_model(args.provider),
        repeats=args.repeats,
    ), indent=2, sort_keys=True))
