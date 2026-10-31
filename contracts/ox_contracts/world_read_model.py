"""P2/P5 preparatory world read contract; no server endpoint or authorization.

Evennia alone owns actual ship state. Actor projections must be assembled from
observations the authenticated character legitimately received, never from a
filtered omniscient world snapshot. Handler beliefs are a different API.
"""
from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

SCHEMA = "ox.world.read/1"
STRICT = ConfigDict(extra="forbid", frozen=True, strict=True)
IDENTIFIER = r"^[A-Za-z0-9#][A-Za-z0-9#._:/-]{0,127}$"
VERSION = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
METRIC = r"^[a-z][a-z0-9_]{0,63}$"
MAX_PAGE_ITEMS = 128
LEGACY_FUEL_INVENTORIES = frozenset({"INV-REACTION", "INV-FTL-FUEL"})
OPERATIONAL_FUEL_ACCOUNTS = frozenset({"motion.propellant_kg", "motion.ftl_fuel_kg"})


class ReadRecord(BaseModel):
    model_config = STRICT


def _array_input(value: object) -> object:
    """Accept JSON arrays from a Python-decoded payload, freeze as tuples."""
    return tuple(value) if type(value) is list else value


def _finite(value: object) -> object:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Physical measurements must be finite JSON numbers")
    return value


class ModelIdentity(ReadRecord):
    """Keep the v0.4 room graph distinct from the v0.5-candidate fit-out."""

    topology_version: str = Field(pattern=VERSION)
    engineering_version: str = Field(pattern=VERSION)

    def require_renderer(self, *, topology_version: str,
                         engineering_version: str) -> None:
        """A drawing may overlay only a matching, explicitly reviewed model."""
        if (topology_version != self.topology_version
                or engineering_version != self.engineering_version):
            raise ValueError("Drawing and installed model versions differ")


class Page(ReadRecord):
    """Opaque, viewer-bound pagination supplied by a future authorized API."""

    next_cursor: str | None = Field(default=None, min_length=1, max_length=1024)
    complete: bool

    @model_validator(mode="after")
    def continuation_consistency(self) -> Self:
        if self.complete == (self.next_cursor is not None):
            raise ValueError("Complete pages must end; partial pages need a cursor")
        return self


class Measurement(ReadRecord):
    name: str = Field(pattern=METRIC)
    unit: str = Field(min_length=1, max_length=24)
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def finite_value(cls, value: object) -> object:
        return _finite(value)


class SpaceActual(ReadRecord):
    space_id: str = Field(pattern=IDENTIFIER)
    condition: str = Field(min_length=1, max_length=100)
    # Omitted means not projected; it does not mean safe atmosphere.
    measurements: tuple[Measurement, ...] = Field(default=(), max_length=32)
    _measurements_input = field_validator("measurements", mode="before")(_array_input)


class EquipmentActual(ReadRecord):
    equipment_id: str = Field(pattern=IDENTIFIER)
    space_id: str = Field(pattern=IDENTIFIER)
    condition: str = Field(min_length=1, max_length=100)
    setting: str | None = Field(default=None, max_length=100)
    measurements: tuple[Measurement, ...] = Field(default=(), max_length=32)
    _measurements_input = field_validator("measurements", mode="before")(_array_input)


class StockActual(ReadRecord):
    """Explicit custody: legacy inventory fuel is not a spendable balance."""

    account_id: str = Field(pattern=IDENTIFIER)
    custodian: Literal["inventory", "motion_ledger"]
    accounting: Literal["fitted_stock", "legacy_reference", "operational_balance"]
    quantity_kg: float = Field(ge=0)

    @field_validator("quantity_kg", mode="before")
    @classmethod
    def finite_stock(cls, value: object) -> object:
        return _finite(value)

    @model_validator(mode="after")
    def no_false_fuel_equivalence(self) -> Self:
        if self.custodian == "motion_ledger":
            if (self.account_id not in OPERATIONAL_FUEL_ACCOUNTS
                    or self.accounting != "operational_balance"):
                raise ValueError("Unknown or nonoperational motion fuel account")
        elif self.account_id in LEGACY_FUEL_INVENTORIES:
            if self.accounting != "legacy_reference":
                raise ValueError("Legacy fuel inventory cannot report available fuel")
        elif (not self.account_id.startswith("INV-")
              or self.accounting != "fitted_stock"):
            raise ValueError("Unrecognised inventory account or custody")
        return self


class AuditEvent(ReadRecord):
    """World-only event; never silently promoted to an addressed crew alarm."""

    event_id: str = Field(pattern=IDENTIFIER)
    kind: str = Field(pattern=METRIC)
    occurred_game_s: float = Field(ge=0)
    visibility: Literal["developer_only"]

    @field_validator("occurred_game_s", mode="before")
    @classmethod
    def finite_time(cls, value: object) -> object:
        return _finite(value)


class Evidence(ReadRecord):
    """Proof of observation, not evidence that the underlying fact is true."""

    source: Literal["local_panel", "direct_inspection", "addressed_event", "local_capability"]
    source_id: str = Field(pattern=IDENTIFIER)
    observed_game_s: float = Field(ge=0)
    event_id: str | None = Field(default=None, pattern=IDENTIFIER)

    @field_validator("observed_game_s", mode="before")
    @classmethod
    def finite_time(cls, value: object) -> object:
        return _finite(value)

    @model_validator(mode="after")
    def require_event_proof(self) -> Self:
        if (self.source == "addressed_event") != (self.event_id is not None):
            raise ValueError("Addressed event evidence requires its event ID only")
        return self


class EquipmentObservation(ReadRecord):
    equipment_id: str = Field(pattern=IDENTIFIER)
    reported_space_id: str | None = Field(default=None, pattern=IDENTIFIER)
    availability: Literal["available", "stale", "unavailable"]
    reported_condition: str | None = Field(default=None, min_length=1, max_length=100)
    readings: tuple[Measurement, ...] = Field(default=(), max_length=32)
    _readings_input = field_validator("readings", mode="before")(_array_input)
    evidence: Evidence

    @model_validator(mode="after")
    def no_readout_from_unavailable_instrument(self) -> Self:
        if (self.availability == "unavailable"
                and (self.reported_condition is not None or self.readings)):
            raise ValueError("Unavailable instrument cannot supply a new reading")
        if (self.availability != "unavailable"
                and self.reported_condition is None and not self.readings):
            raise ValueError("Available or stale observation needs a reading")
        return self


class ExitObservation(ReadRecord):
    """Actor-local advertised exits, never a world-wide omniscient graph."""

    link_id: str = Field(pattern=IDENTIFIER)
    from_space_id: str = Field(pattern=IDENTIFIER)
    to_space_id: str | None = Field(default=None, pattern=IDENTIFIER)
    assessment: Literal["advertised", "blocked", "unknown"]
    evidence: Evidence


class AddressedEvent(ReadRecord):
    event_id: str = Field(pattern=IDENTIFIER)
    recipient_character_id: str = Field(pattern=IDENTIFIER)
    kind: str = Field(pattern=METRIC)
    occurred_game_s: float = Field(ge=0)
    source: Literal["delivered_world_event"]

    @field_validator("occurred_game_s", mode="before")
    @classmethod
    def finite_time(cls, value: object) -> object:
        return _finite(value)


class WorldPage(ReadRecord):
    schema_version: Literal["ox.world.read/1"]
    world_id: str = Field(pattern=IDENTIFIER)
    models: ModelIdentity
    publication_seq: int = Field(ge=1)
    game_time_s: float = Field(ge=0)
    page: Page

    @field_validator("game_time_s", mode="before")
    @classmethod
    def finite_time(cls, value: object) -> object:
        return _finite(value)


class DeveloperWorldPage(WorldPage):
    """Authorized developer truth: Evennia rows, never handler beliefs."""

    scope: Literal["developer_actual"]
    spaces: tuple[SpaceActual, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    equipment: tuple[EquipmentActual, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    stocks: tuple[StockActual, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    audit_events: tuple[AuditEvent, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)

    _page_arrays = field_validator(
        "spaces", "equipment", "stocks", "audit_events", mode="before"
    )(_array_input)

    @model_validator(mode="after")
    def no_duplicate_world_entries_or_future_events(self) -> Self:
        for items, name, key in (
            (self.spaces, "spaces", "space_id"),
            (self.equipment, "equipment", "equipment_id"),
            (self.stocks, "stocks", "account_id"),
            (self.audit_events, "audit_events", "event_id"),
        ):
            if len({getattr(entry, key) for entry in items}) != len(items):
                raise ValueError("Duplicate " + name)
        if any(event.occurred_game_s > self.game_time_s for event in self.audit_events):
            raise ValueError("Event is later than the world snapshot")
        return self


class ActorWorldPage(WorldPage):
    """Only firsthand/addressed world evidence for one authenticated actor."""

    scope: Literal["actor_observed"]
    character_id: str = Field(pattern=IDENTIFIER)
    location_id: str | None = Field(default=None, pattern=IDENTIFIER)
    equipment: tuple[EquipmentObservation, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    exits: tuple[ExitObservation, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    addressed_events: tuple[AddressedEvent, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)

    _page_arrays = field_validator(
        "equipment", "exits", "addressed_events", mode="before"
    )(_array_input)

    @model_validator(mode="after")
    def validate_actor_boundary(self) -> Self:
        for items, name, key in (
            (self.equipment, "equipment", "equipment_id"),
            (self.exits, "exits", "link_id"),
            (self.addressed_events, "events", "event_id"),
        ):
            if len({getattr(entry, key) for entry in items}) != len(items):
                raise ValueError("Duplicate actor " + name)
        if any(entry.evidence.observed_game_s > self.game_time_s
               for entry in (*self.equipment, *self.exits)):
            raise ValueError("Observation cannot come from the future")
        if any(entry.recipient_character_id != self.character_id
               or entry.occurred_game_s > self.game_time_s
               for entry in self.addressed_events):
            raise ValueError("Foreign recipient or future event in actor view")
        if any(self.location_id is None or entry.from_space_id != self.location_id
               or entry.evidence.source != "local_capability"
               for entry in self.exits):
            raise ValueError("Exit discovery must be actor-local and world-advertised")
        return self


WorldReadPage = Annotated[
    DeveloperWorldPage | ActorWorldPage, Field(discriminator="scope")
]
WORLD_READ_ADAPTER = TypeAdapter(WorldReadPage)


def parse_world_read_page(value: object) -> DeveloperWorldPage | ActorWorldPage:
    """Strictly reject unknown versions, scopes, fields and corrupted values."""
    return WORLD_READ_ADAPTER.validate_python(value)
