"""Who may read whose private cognition.

SKETCH. Bearer tokens are stored only as SHA-256 digests in a local grants
file (``orjson``), one grant per token:

    {"<sha256 hex>": {"kind": "developer"},
     "<sha256 hex>": {"kind": "character", "character_id": "#12"}}

A developer may inspect any character. A character grant reads only its own
character. Every refusal is indistinguishable from "no such character", so a
viewer cannot enumerate the crew or probe for private state.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import orjson

from ox_ai.inspection.projection import InspectionUnavailable


@dataclass(frozen=True, slots=True)
class Grant:
    kind: Literal["developer", "character"]
    character_id: str | None


def load_grants(path: Path) -> dict[str, Grant]:
    raw: object = orjson.loads(path.read_bytes())
    if not isinstance(raw, dict):
        raise ValueError("Grants file must be an object")
    grants: dict[str, Grant] = {}
    for digest, entry in raw.items():
        if not (isinstance(digest, str) and len(digest) == 64):
            raise ValueError("Grant keys are SHA-256 hex digests")
        if not isinstance(entry, dict):
            raise ValueError("Malformed grant")
        kind: object = entry.get("kind")
        if kind == "developer" and set(entry) == {"kind"}:
            grants[digest] = Grant("developer", None)
        elif kind == "character" and set(entry) == {"kind", "character_id"}:
            character: object = entry["character_id"]
            if not isinstance(character, str) or not character.startswith("#"):
                raise ValueError("Character grant needs a #dbref")
            grants[digest] = Grant("character", character)
        else:
            raise ValueError("Unknown grant kind")
    return grants


def resolve_token(token: str, grants: dict[str, Grant]) -> Grant | None:
    digest: str = hashlib.sha256(token.encode("utf-8")).hexdigest()
    for known, grant in grants.items():
        if hmac.compare_digest(known, digest):
            return grant
    return None


def authorize(grant: Grant | None, character_id: str) -> None:
    if grant is None:
        raise InspectionUnavailable(character_id)
    if grant.kind == "developer":
        return
    if grant.character_id != character_id:
        raise InspectionUnavailable(character_id)
