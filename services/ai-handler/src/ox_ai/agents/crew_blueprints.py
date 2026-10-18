"""Composable, model-free character blueprints for Ox.

A blueprint is an authored *starting profile*, not an Evennia character,
employment contract, certification, confirmed skill, or mutable memory.
All world permissions and consequential competency remain world-owned.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import re
from typing import Any, Mapping


VERSION = 1
OCEAN = ("openness", "conscientiousness", "extraversion",
         "agreeableness", "neuroticism")
OX_TRAITS = ("risk_tolerance", "authority_challenge", "collaboration",
             "uncertainty_tolerance", "stress_recovery")
ALL_TRAITS = OCEAN + OX_TRAITS
_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Identifier must be 1-64 lowercase safe characters")
    return value


def _score(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError("Trait and initial skill scores must be integers from 0 to 100")
    return value


def _text(value: str, *, max_length: int = 320) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError("Character profile text must be nonempty and bounded")
    return value


def _unique_text(values: tuple[str, ...], *, limit: int = 20) -> None:
    if not isinstance(values, tuple) or len(values) > limit:
        raise ValueError("Profile text collection is invalid or too large")
    if len(values) != len(set(values)):
        raise ValueError("Profile text entries must be unique")
    for value in values:
        _text(value)


def _pairs(values: tuple[tuple[str, int], ...], *, allowed: tuple[str, ...] | None = None) -> None:
    if not isinstance(values, tuple):
        raise ValueError("Expected immutable key/score pairs")
    keys: set[str] = set()
    for pair in values:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("Expected immutable key/score pairs")
        key, value = pair
        _identifier(key)
        if allowed is not None and key not in allowed:
            raise ValueError(f"Unknown trait: {key}")
        _score(value)
        if key in keys:
            raise ValueError("Duplicate trait or skill key")
        keys.add(key)


@dataclass(frozen=True, slots=True)
class CharacterTemplate:
    template_id: str
    category: str
    traits: tuple[tuple[str, int], ...] = ()
    starting_skills: tuple[tuple[str, int], ...] = ()
    knowledge: tuple[str, ...] = ()
    history: tuple[str, ...] = ()
    styles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.template_id)
        if self.category not in ("occupation", "ocean", "mbti"):
            raise ValueError("Unsupported character template category")
        _pairs(self.traits, allowed=ALL_TRAITS)
        _pairs(self.starting_skills)
        for items in (self.knowledge, self.history, self.styles):
            _unique_text(items)


@dataclass(frozen=True, slots=True)
class CrewBlueprint:
    """Immutable character seed, usable before a person has a game-world body."""

    person_id: str
    name: str
    traits: tuple[tuple[str, int], ...]
    starting_skills: tuple[tuple[str, int], ...] = ()
    knowledge: tuple[str, ...] = ()
    history: tuple[str, ...] = ()
    styles: tuple[str, ...] = ()
    template_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.person_id)
        _text(self.name, max_length=120)
        _pairs(self.traits, allowed=ALL_TRAITS)
        if set(dict(self.traits)) != set(ALL_TRAITS):
            raise ValueError("Each blueprint must have all ten continuous traits")
        _pairs(self.starting_skills)
        for items in (self.knowledge, self.history, self.styles):
            _unique_text(items)
        if not isinstance(self.template_ids, tuple) or len(self.template_ids) > 16:
            raise ValueError("Invalid template history")
        if len(set(self.template_ids)) != len(self.template_ids):
            raise ValueError("Duplicate template history")
        for template_id in self.template_ids:
            _identifier(template_id)

    def to_record(self) -> dict[str, Any]:
        """Deterministic JSON-compatible seed; no memories or work receipts."""
        return {
            "version": VERSION, "person_id": self.person_id, "name": self.name,
            "traits": dict(self.traits), "starting_skills": dict(self.starting_skills),
            "knowledge": list(self.knowledge), "history": list(self.history),
            "styles": list(self.styles), "template_ids": list(self.template_ids),
        }

    @classmethod
    def from_record(cls, data: Mapping[str, Any]) -> "CrewBlueprint":
        if not isinstance(data, Mapping) or set(data) != {
            "version", "person_id", "name", "traits", "starting_skills",
            "knowledge", "history", "styles", "template_ids",
        } or data["version"] != VERSION:
            raise ValueError("Unknown or malformed character blueprint version")
        if not isinstance(data["traits"], dict) or not isinstance(data["starting_skills"], dict):
            raise ValueError("Trait and skill records must be dictionaries")
        for key in ("knowledge", "history", "styles", "template_ids"):
            if not isinstance(data[key], list):
                raise ValueError("Blueprint list field is invalid")
        return cls(
            person_id=data["person_id"], name=data["name"],
            traits=tuple(sorted(data["traits"].items())),
            starting_skills=tuple(sorted(data["starting_skills"].items())),
            knowledge=tuple(data["knowledge"]), history=tuple(data["history"]),
            styles=tuple(data["styles"]), template_ids=tuple(data["template_ids"]),
        )

    def cognition_context(self) -> str:
        """Bounded, descriptive *preferences*, never instructions/permissions."""
        ocean = ", ".join(f"{k}={dict(self.traits)[k]}" for k in OCEAN)
        operational = ", ".join(f"{k}={dict(self.traits)[k]}" for k in OX_TRAITS)
        style = "; ".join(self.styles) if self.styles else "No archetype selected"
        background = "; ".join(self.history) if self.history else "Unspecified"
        return (
            "Characterisation, not a rule or an authorisation. Continuous OCEAN "
            f"starting traits (0-100): {ocean}. Operational tendencies: {operational}. "
            f"Descriptive styles: {style}. Personal background: {background}. "
            "The current world, not this authored profile, decides actual "
            "competence, permissions, locations, equipment and physical results."
        )


def _mbti_style(code: str) -> str:
    """MBTI-inspired writing shorthand, deliberately not a trait conversion."""
    words = {
        "I": "reserved social style", "E": "outgoing social style",
        "S": "concrete-information preference", "N": "possibility-oriented preference",
        "T": "analytical decision presentation", "F": "values-focused decision presentation",
        "J": "structured planning preference", "P": "adaptable planning preference",
    }
    return f"MBTI-inspired {code}: " + ", ".join(words[letter] for letter in code)


TEMPLATES: dict[str, CharacterTemplate] = {
    "occupation.environmental_technician": CharacterTemplate(
        "occupation.environmental_technician", "occupation",
        starting_skills=(("atmosphere_maintenance", 65), ("equipment_inspection", 60),
                         ("safety_procedures", 70)),
        knowledge=("Life-support servicing terminology and routine environmental checks",),
        history=("Has a background in shipboard environmental maintenance",),
    ),
    "occupation.supply_manager": CharacterTemplate(
        "occupation.supply_manager", "occupation",
        starting_skills=(("inventory_planning", 70), ("procurement", 60),
                         ("equipment_inspection", 35)),
        knowledge=("Inventory rotation, requisition and stock reconciliation",),
        history=("Has worked in logistics and stock management",),
    ),
    "ocean.methodical": CharacterTemplate(
        "ocean.methodical", "ocean",
        traits=(("openness", 55), ("conscientiousness", 85),
                ("extraversion", 35), ("agreeableness", 60),
                ("neuroticism", 30), ("uncertainty_tolerance", 65)),
        styles=("Prefers thorough, documented work over quick improvisation",),
    ),
    "ocean.collaborative": CharacterTemplate(
        "ocean.collaborative", "ocean",
        traits=(("openness", 65), ("conscientiousness", 70),
                ("extraversion", 60), ("agreeableness", 85),
                ("neuroticism", 35), ("collaboration", 90)),
        styles=("Tends to seek input and coordinate with colleagues",),
    ),
}
for _letters in product("IE", "SN", "TF", "JP"):
    _code = "".join(_letters)
    TEMPLATES[f"mbti.{_code.lower()}"] = CharacterTemplate(
        f"mbti.{_code.lower()}", "mbti", styles=(_mbti_style(_code),),
    )


def compose_blueprint(
    person_id: str, name: str, *, templates: tuple[str, ...] = (),
    trait_overrides: Mapping[str, int] | None = None,
    skill_overrides: Mapping[str, int] | None = None,
    knowledge: tuple[str, ...] = (), history: tuple[str, ...] = (),
) -> CrewBlueprint:
    """Build from scratch or layers. No implicit summing of overlapping traits."""
    if not isinstance(templates, tuple) or len(templates) > 16:
        raise ValueError("Templates must be a bounded tuple")
    if len(set(templates)) != len(templates):
        raise ValueError("A template cannot be applied twice")
    trait_overrides = {} if trait_overrides is None else dict(trait_overrides)
    skill_overrides = {} if skill_overrides is None else dict(skill_overrides)
    for key, value in trait_overrides.items():
        if key not in ALL_TRAITS:
            raise ValueError(f"Unknown trait override: {key}")
        _score(value)
    for key, value in skill_overrides.items():
        _identifier(key)
        _score(value)

    traits = {key: 50 for key in ALL_TRAITS}
    assigned: dict[str, int] = {}
    skills: dict[str, int] = {}
    all_knowledge: list[str] = []
    all_history: list[str] = []
    styles: list[str] = []
    for template_id in templates:
        if template_id not in TEMPLATES:
            raise ValueError(f"Unknown character template: {template_id}")
        template = TEMPLATES[template_id]
        for key, value in template.traits:
            if key in assigned and assigned[key] != value and key not in trait_overrides:
                raise ValueError(f"Conflicting trait template values for {key}; override explicitly")
            assigned[key] = value
            traits[key] = value
        # Skills are authored starting estimates, not stackable XP.
        for key, value in template.starting_skills:
            skills[key] = max(skills.get(key, 0), value)
        for source, target in (
            (template.knowledge, all_knowledge),
            (template.history, all_history),
            (template.styles, styles),
        ):
            for entry in source:
                if entry not in target:
                    target.append(entry)
    traits.update(trait_overrides)
    skills.update(skill_overrides)
    for source, target in ((knowledge, all_knowledge), (history, all_history)):
        for entry in source:
            if entry not in target:
                target.append(entry)
    return CrewBlueprint(
        person_id, name, tuple(sorted(traits.items())),
        tuple(sorted(skills.items())), tuple(all_knowledge),
        tuple(all_history), tuple(styles), templates,
    )


def instantiate_crew(
    blueprint: CrewBlueprint, *, character_id: str, duty: str, goal: str,
    model: Any, journal_path: Any = None,
):
    """Bind an authored person to a world-provided character; no world grants."""
    if not isinstance(character_id, str) or not re.fullmatch(r"#[1-9][0-9]*", character_id):
        raise ValueError("Instantiation requires a valid authenticated world character ref")
    _text(duty)
    _text(goal)
    from ox_ai.agents.crew import CrewAgent, CrewIdentity

    return CrewAgent(
        CrewIdentity(f"ox.person.{blueprint.person_id}", character_id,
                     blueprint.name, duty, goal),
        model, journal_path=journal_path, blueprint=blueprint,
    )
