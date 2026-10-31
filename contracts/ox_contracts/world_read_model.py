"""P2/P5 preparatory world read contract; no endpoint or permission grant.

Evennia alone owns actual ship state. Actor projections must be assembled from
observations legitimately received by the authenticated character, never from
an omniscient snapshot with a few fields removed. Handler beliefs belong to a
separately authenticated service.
"""
from __future__ import annotations

import math
import re
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

SCHEMA = "ox.world.read/1"
STRICT = ConfigDict(extra="forbid", frozen=True, strict=True)
IDENTIFIER = r"^[A-Za-z0-9#][A-Za-z0-9#._:/-]{0,127}$"
VERSION = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
METRIC = r"^[a-z][a-z0-9_]{0,63}$"
DATUM_KEY = re.compile(r"datum_[a-z][a-z0-9_]{0,63}\\Z")
MAX_PAGE_ITEMS = 128
MAX_OBSERVATION_AGE_S = 60.0
LEGACY_FUEL_INVENTORIES = frozenset({"INV-REACTION", "INV-FTL-FUEL"})
OPERATIONAL_FUEL_ACCOUNTS = frozenset(
    {"motion.propellant_kg", "motion.ftl_fuel_kg"}
)

# Explicit physical display units rather than arbitrary human descriptions.
Unit = Literal[
    "Pa",
    "kPa",
    "K",
    "kg",
    "kg/s",
    "m3",
    "m/s",
    "kW",
    "MW",
    "kWh",
    "rpm",
    "rad",
    "s",
    "h",
    "%",
    "1",
]
FlatDatum = str | int | float | bool
METRIC_UNITS = {
    "pressure_kpa": "kPa",
    "oxygen_kpa": "kPa",
    "temperature_k": "K",
    "burn_kg_s": "kg/s",
    "leak_kg_s": "kg/s",
    "co2_fraction": "1",
    "smoke_fraction": "1",
    "cell_damage": "1",
    "power_kw": "kW",
    "water_working_kg": "kg",
    "nutrient_kg": "kg",
    "spoiled_food_kg": "kg",
}


class ReadRecord(BaseModel):
    model_config = STRICT


def _array_input(value: object) -> object:
    """Accept JSON arrays from a Python-decoded payload, freeze as tuples."""
    return tuple(value) if type(value) is list else value


def _finite(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("Physical measurements must be finite JSON numbers")
    return float(value)


def _unique_measurements(items: tuple[Measurement, ...]) -> None:
    if len({item.name for item in items}) != len(items):
        raise ValueError("Duplicate measurement names are ambiguous")


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
    unit: Unit
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def finite_value(cls, value: object) -> float:
        return _finite(value)

    @model_validator(mode="after")
    def canonical_unit(self) -> Self:
        known = METRIC_UNITS.get(self.name)
        if known is not None and self.unit != known:
            raise ValueError("Measurement unit disagrees with its physical name")
        return self


class SpaceActual(ReadRecord):
    space_id: str = Field(pattern=IDENTIFIER)
    condition: str = Field(min_length=1, max_length=100)
    # None means no verified commissioned gas envelope, never breathable air.
    pressure_cell_id: str | None = Field(default=None, pattern=IDENTIFIER)
    measurements: tuple[Measurement, ...] = Field(default=(), max_length=32)
    _measurements_input = field_validator("measurements", mode="before")(
        _array_input
    )

    @model_validator(mode="after")
    def no_duplicated_cell_readouts(self) -> Self:
        _unique_measurements(self.measurements)
        if any(m.name in METRIC_UNITS and METRIC_UNITS[m.name] in {"kPa", "K", "kg/s", "1"} for m in self.measurements):
            raise ValueError("Cell atmosphere must be projected by cell ID")
        return self


class PressureCellActual(ReadRecord):
    """One installed gas envelope can enclose several real ship spaces."""

    cell_id: str = Field(pattern=IDENTIFIER)
    space_ids: tuple[str, ...] = Field(min_length=1, max_length=421)
    pressure_kpa: float = Field(ge=0)
    oxygen_kpa: float = Field(ge=0)
    temperature_k: float = Field(gt=0)
    gas_mass_kg: float = Field(ge=0)
    volume_m3: float = Field(gt=0)
    _spaces_input = field_validator("space_ids", mode="before")(_array_input)

    @field_validator(
        "pressure_kpa",
        "oxygen_kpa",
        "temperature_k",
        "gas_mass_kg",
        "volume_m3",
        mode="before",
    )
    @classmethod
    def finite_measurements(cls, value: object) -> float:
        return _finite(value)

    @model_validator(mode="after")
    def valid_cell(self) -> Self:
        if len(set(self.space_ids)) != len(self.space_ids):
            raise ValueError("One room cannot be repeated inside a pressure cell")
        if self.oxygen_kpa > self.pressure_kpa + 1e-6:
            raise ValueError("Oxygen partial pressure exceeds total pressure")
        return self


class PressureBoundaryActual(ReadRecord):
    """G19 access link at a gas boundary, with actual setting and condition."""

    link_id: str = Field(pattern=IDENTIFIER)
    from_space_id: str = Field(pattern=IDENTIFIER)
    to_space_id: str = Field(pattern=IDENTIFIER)
    from_cell_id: str | None = Field(default=None, pattern=IDENTIFIER)
    to_cell_id: str | None = Field(default=None, pattern=IDENTIFIER)
    setting: Literal["open", "closed", "closed_or_auto"]
    condition: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def crosses_a_real_boundary(self) -> Self:
        if self.from_space_id == self.to_space_id:
            raise ValueError("Boundary cannot link a room to itself")
        if self.from_cell_id == self.to_cell_id:
            raise ValueError("Boundary must separate two different envelopes")
        return self


class EquipmentActual(ReadRecord):
    equipment_id: str = Field(pattern=IDENTIFIER)
    space_id: str = Field(pattern=IDENTIFIER)
    condition: str = Field(min_length=1, max_length=100)
    setting: str | None = Field(default=None, max_length=100)
    measurements: tuple[Measurement, ...] = Field(default=(), max_length=32)
    _measurements_input = field_validator("measurements", mode="before")(
        _array_input
    )

    @model_validator(mode="after")
    def no_ambiguous_measurements(self) -> Self:
        _unique_measurements(self.measurements)
        return self


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
    def has_legitimate_reading_shape(self) -> Self:
        _unique_measurements(self.readings)
        if (
            self.availability == "unavailable"
            and (self.reported_condition is not None or self.readings)
        ):
            raise ValueError("Unavailable instrument cannot supply a new reading")
        if (
            self.availability != "unavailable"
            and self.reported_condition is None
            and not self.readings
        ):
            raise ValueError("Available or stale evidence needs a reading")
        return self


class ExitObservation(ReadRecord):
    """Actor-local, world-advertised exit; no global topology oracle."""

    link_id: str = Field(pattern=IDENTIFIER)
    from_space_id: str = Field(pattern=IDENTIFIER)
    to_space_id: str | None = Field(default=None, pattern=IDENTIFIER)
    assessment: Literal["advertised", "blocked", "unknown"]
    evidence: Evidence

    @model_validator(mode="after")
    def advertised_means_located(self) -> Self:
        if self.assessment == "advertised" and self.to_space_id is None:
            raise ValueError("An advertised exit requires a destination")
        if self.to_space_id == self.from_space_id:
            raise ValueError("Exit cannot return to the same space")
        return self


class AddressedEvent(ReadRecord):
    """An actor's actual addressed OOB event, including message content."""

    event_id: str = Field(pattern=IDENTIFIER)
    recipient_character_id: str = Field(pattern=IDENTIFIER)
    kind: str = Field(pattern=METRIC)
    occurred_game_s: float = Field(ge=0)
    text: str = Field(min_length=1, max_length=4096)
    # Preserve the original OOB datum_* keys and only flat scalar values.
    datum_fields: dict[str, FlatDatum] = Field(default_factory=dict, max_length=32)
    source: Literal["delivered_world_event"]

    @field_validator("occurred_game_s", mode="before")
    @classmethod
    def finite_time(cls, value: object) -> float:
        return _finite(value)

    @field_validator("datum_fields", mode="before")
    @classmethod
    def check_flat_datums(cls, value: object) -> object:
        if not isinstance(value, dict):
            raise ValueError("Event datums must be a flat dictionary")
        for key, datum in value.items():
            if type(key) is not str or not DATUM_KEY.fullmatch(key):
                raise ValueError("Event datums need their original datum_* keys")
            if type(datum) not in (str, int, float, bool):
                raise ValueError("Event datums must be scalar and non-null")
            if type(datum) is float and not math.isfinite(datum):
                raise ValueError("Event datum cannot be nonfinite")
            if type(datum) is str and len(datum) > 512:
                raise ValueError("Event datum string is too long")
        return value


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
    """Explicitly authorized actual Evennia state; never handler beliefs."""

    scope: Literal["developer_actual"]
    spaces: tuple[SpaceActual, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    pressure_cells: tuple[PressureCellActual, ...] = Field(
        default=(), max_length=MAX_PAGE_ITEMS
    )
    pressure_boundaries: tuple[PressureBoundaryActual, ...] = Field(
        default=(), max_length=MAX_PAGE_ITEMS
    )
    equipment: tuple[EquipmentActual, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    stocks: tuple[StockActual, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    audit_events: tuple[AuditEvent, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)

    _page_arrays = field_validator(
        "spaces",
        "pressure_cells",
        "pressure_boundaries",
        "equipment",
        "stocks",
        "audit_events",
        mode="before",
    )(_array_input)

    @model_validator(mode="after")
    def validate_developer_page(self) -> Self:
        for keys in (
            [item.space_id for item in self.spaces],
            [item.cell_id for item in self.pressure_cells],
            [item.link_id for item in self.pressure_boundaries],
            [item.equipment_id for item in self.equipment],
            [item.account_id for item in self.stocks],
            [item.event_id for item in self.audit_events],
        ):
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate authoritative record IDs")
        if any(event.occurred_game_s > self.game_time_s for event in self.audit_events):
            raise ValueError("Event is later than the world snapshot")

        # Validate shared references where both entities appear on this page.
        # An entity absent due to pagination is not assumed nonexistent.
        room_cells = {room.space_id: room.pressure_cell_id for room in self.spaces}
        claimed_rooms: dict[str, str] = {}
        for cell in self.pressure_cells:
            for room_id in cell.space_ids:
                if room_id in claimed_rooms:
                    raise ValueError("Space claimed by multiple pressure cells")
                claimed_rooms[room_id] = cell.cell_id
                if room_id in room_cells and room_cells[room_id] != cell.cell_id:
                    raise ValueError("Room's gas envelope disagrees with cell")
        for boundary in self.pressure_boundaries:
            for room_id, cell_id in (
                (boundary.from_space_id, boundary.from_cell_id),
                (boundary.to_space_id, boundary.to_cell_id),
            ):
                if room_id in room_cells and room_cells[room_id] != cell_id:
                    raise ValueError("Boundary endpoint disagrees with room cell")
        return self


class ActorWorldPage(WorldPage):
    """Only world-origin evidence legitimately received by one actor."""

    scope: Literal["actor_observed"]
    character_id: str = Field(pattern=IDENTIFIER)
    location_id: str | None = Field(default=None, pattern=IDENTIFIER)
    equipment: tuple[EquipmentObservation, ...] = Field(
        default=(), max_length=MAX_PAGE_ITEMS
    )
    exits: tuple[ExitObservation, ...] = Field(default=(), max_length=MAX_PAGE_ITEMS)
    addressed_events: tuple[AddressedEvent, ...] = Field(
        default=(), max_length=MAX_PAGE_ITEMS
    )

    _page_arrays = field_validator(
        "equipment", "exits", "addressed_events", mode="before"
    )(_array_input)

    @model_validator(mode="after")
    def validate_actor_boundary(self) -> Self:
        if len({item.equipment_id for item in self.equipment}) != len(self.equipment):
            raise ValueError("Duplicate actor equipment observations")
        if len({item.link_id for item in self.exits}) != len(self.exits):
            raise ValueError("Duplicate actor exits")
        if len({event.event_id for event in self.addressed_events}) != len(
            self.addressed_events
        ):
            raise ValueError("Duplicate addressed event IDs")
        events = {event.event_id: event for event in self.addressed_events}
        if any(
            event.recipient_character_id != self.character_id
            or event.occurred_game_s > self.game_time_s
            for event in self.addressed_events
        ):
            raise ValueError("Foreign recipient or future event in actor view")
        for equipment in self.equipment:
            evidence = equipment.evidence
            if evidence.observed_game_s > self.game_time_s:
                raise ValueError("Observation cannot come from the future")
            age = self.game_time_s - evidence.observed_game_s
            if (equipment.availability == "stale") != (
                age > MAX_OBSERVATION_AGE_S
            ):
                raise ValueError("Observation freshness disagrees with sample age")
            self._verify_event_reference(evidence, events)
        for exit_view in self.exits:
            evidence = exit_view.evidence
            if evidence.observed_game_s > self.game_time_s:
                raise ValueError("Exit observation is from the future")
            if (
                self.location_id is None
                or exit_view.from_space_id != self.location_id
                or evidence.source != "local_capability"
            ):
                raise ValueError("Exit must be actor-local and world-advertised")
        return self

    @staticmethod
    def _verify_event_reference(
        evidence: Evidence, events: dict[str, AddressedEvent]
    ) -> None:
        if evidence.source == "addressed_event":
            event = events.get(evidence.event_id or "")
            if event is None:
                raise ValueError("Evidence references an event absent from page")
            if event.occurred_game_s > evidence.observed_game_s:
                raise ValueError("Evidence predates the cited world event")


WorldReadPage = Annotated[
    DeveloperWorldPage | ActorWorldPage, Field(discriminator="scope")
]
WORLD_READ_ADAPTER: TypeAdapter[DeveloperWorldPage | ActorWorldPage] = TypeAdapter(
    WorldReadPage
)


def parse_world_read_page(value: object) -> DeveloperWorldPage | ActorWorldPage:
    """Strictly reject unknown versions, scopes, fields and corrupted values."""
    return WORLD_READ_ADAPTER.validate_python(value)
