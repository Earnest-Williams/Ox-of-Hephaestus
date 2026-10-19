"""G3f starting competencies; they are NOT permissions or experience gains.

World owns these coarse initial 0-4 attributes. Authority is always
validated separately at the command's real equipment/role boundary.
Progression by genuine world receipts is a later project stage.
"""
ROLE_SKILLS = {
    "captain": {"command": 4, "coordination": 4, "engineering": 1,
                "environment": 1, "cargo": 1, "diagnostics": 1},
    "bridge_officer": {"command": 2, "coordination": 3, "engineering": 1,
                       "environment": 1, "cargo": 1, "diagnostics": 2},
    "watch_engineer": {"command": 0, "coordination": 1, "engineering": 3,
                       "environment": 1, "cargo": 0, "diagnostics": 3},
    "chief_engineer": {"command": 1, "coordination": 2, "engineering": 4,
                       "environment": 2, "cargo": 0, "diagnostics": 4},
    "cargo_officer": {"command": 1, "coordination": 2, "engineering": 0,
                      "environment": 1, "cargo": 4, "diagnostics": 2},
    "environment_tech": {"command": 0, "coordination": 1, "engineering": 1,
                         "environment": 4, "cargo": 0, "diagnostics": 3},
}

def skills_for(role: str) -> dict[str, int]:
    if role not in ROLE_SKILLS:
        raise ValueError("Unrecognized shipboard role")
    return dict(ROLE_SKILLS[role])
