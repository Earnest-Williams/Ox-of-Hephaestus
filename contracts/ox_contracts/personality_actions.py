"""G16a authored action dispositions: shared schema, never world authority."""
from __future__ import annotations

import hashlib
import json
import math
from importlib import resources
from typing import Literal, Mapping, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


STRICT = ConfigDict(extra="forbid", frozen=True, strict=True)
KEY = r"^[a-z][a-z0-9_.-]{0,95}$"
DIMENSIONS = ("risk", "deference", "social", "autonomy", "procedure")


class DispositionTags(BaseModel):
    """Five finite [-1, 1] inclinations, not correctness or permission.

    Positive: risk-taking, deference to authority, social affinity/aid,
    autonomy, procedure-following. Negative: the respective opposites.
    """

    model_config = STRICT
    risk: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    deference: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    social: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    autonomy: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    procedure: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)

    @field_validator(*DIMENSIONS, mode="before")
    @classmethod
    def float_only(cls, value: object) -> float:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("Expected a finite JSON float, not a coerced number")
        return value

    def project(self, disposition: Mapping[str, float]) -> float:
        if set(disposition) != set(DIMENSIONS):
            raise ValueError("All five disposition dimensions required")
        if any(type(value) is not float or not math.isfinite(value)
               or not -1.0 <= value <= 1.0 for value in disposition.values()):
            raise ValueError("Dispositions must be bounded finite floats")
        return sum(getattr(self, k) * disposition[k] for k in DIMENSIONS)


class TaggedAction(BaseModel):
    """Stable semantic identity plus exact existing finite command signature."""

    model_config = STRICT
    semantic_key: str = Field(pattern=KEY)
    verb: str = Field(pattern=KEY)
    target: str | None = Field(default=None, max_length=160)
    arguments: tuple[tuple[str, str], ...] = ()
    tags: DispositionTags

    @model_validator(mode="after")
    def bounded_signature(self) -> Self:
        if self.target is not None and not self.target.strip():
            raise ValueError("Empty explicit target")
        if (len(self.arguments) > 16
                or any(not k or not v or len(k) > 80 or len(v) > 160
                       for k, v in self.arguments)
                or tuple(sorted(self.arguments)) != self.arguments
                or len({k for k, _ in self.arguments}) != len(self.arguments)):
            raise ValueError("Arguments must be finite, unique, sorted string pairs")
        return self

    @property
    def signature(self) -> tuple[str, str | None, tuple[tuple[str, str], ...]]:
        return (self.verb, self.target, self.arguments)


class TaggedMenu(BaseModel):
    model_config = STRICT
    menu_key: str = Field(pattern=KEY)
    scope: Literal["hypothetical", "live_trial", "offline_trial"]
    safety_critical: bool
    options: tuple[TaggedAction, ...] = Field(min_length=2, max_length=26)

    @model_validator(mode="after")
    def unique_actions(self) -> Self:
        if len({x.semantic_key for x in self.options}) != len(self.options):
            raise ValueError("Duplicate semantic keys")
        if len({x.signature for x in self.options}) != len(self.options):
            raise ValueError("Duplicate command signatures")
        return self

    def by_key(self, semantic_key: str) -> TaggedAction:
        for option in self.options:
            if option.semantic_key == semantic_key:
                return option
        raise KeyError("Unauthored semantic option")

    def by_command(self, verb: str, target: str | None,
                   arguments: Mapping[str, str] | None = None) -> TaggedAction:
        signature = (verb, target, tuple(sorted((arguments or {}).items())))
        for option in self.options:
            if option.signature == signature:
                return option
        raise KeyError("Unauthored command for menu")


class ActionTagCatalog(BaseModel):
    """One immutable typed manifest, to be installed by both systems in G16c/d."""

    model_config = STRICT
    schema_version: Literal[1]
    menus: tuple[TaggedMenu, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_menus(self) -> Self:
        if len({x.menu_key for x in self.menus}) != len(self.menus):
            raise ValueError("Duplicate menu IDs")
        return self

    def menu(self, menu_key: str) -> TaggedMenu:
        for menu in self.menus:
            if menu.menu_key == menu_key:
                return menu
        raise KeyError("Unauthored menu")

    def content_sha256(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


def load_catalog() -> ActionTagCatalog:
    """Fail closed on missing, invalid or unknown catalog versions."""
    source = resources.files("ox_contracts").joinpath(
        "data/personality_action_tags.v1.json"
    )
    return ActionTagCatalog.model_validate_json(source.read_text(encoding="utf-8"))
