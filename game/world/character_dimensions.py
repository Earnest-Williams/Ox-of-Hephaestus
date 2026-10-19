"""Immutable identifiers and ranges for world-owned formative character state.

The AI-side blueprint is an authored seed. Evennia independently validates
actual records and never imports cognition services to determine world facts.
"""

APTITUDES = (
    "strength", "dexterity", "agility", "constitution", "reflexes",
    "perception", "spatial_sense", "attention", "reasoning", "memory",
    "nerve", "social_insight",
)
OCEAN = (
    "openness", "conscientiousness", "extraversion",
    "agreeableness", "neuroticism",
)
OPERATING_TENDENCIES = (
    "risk_tolerance", "authority_challenge", "collaboration",
    "uncertainty_tolerance", "stress_recovery",
    "persistence", "isolation_tolerance",
)
PSYCHOLOGY = OCEAN + OPERATING_TENDENCIES
PROFILE_VERSION = 2


def validate_profile(aptitudes: dict, psychology: dict) -> None:
    """Strict full-record validation. bool is not a valid numeric score."""
    if not isinstance(aptitudes, dict) or set(aptitudes) != set(APTITUDES):
        raise ValueError("Exactly twelve recognised aptitudes are required")
    if not isinstance(psychology, dict) or set(psychology) != set(PSYCHOLOGY):
        raise ValueError("Exactly twelve recognised psychological dimensions are required")
    for score in aptitudes.values():
        if type(score) is not int or not 1 <= score <= 10:
            raise ValueError("Aptitude scores must be integers from 1 through 10")
    for score in psychology.values():
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("Psychological scores must be integers from 0 through 100")


def neutral_profile() -> tuple[dict[str, int], dict[str, int]]:
    return ({key: 5 for key in APTITUDES},
            {key: 50 for key in PSYCHOLOGY})
