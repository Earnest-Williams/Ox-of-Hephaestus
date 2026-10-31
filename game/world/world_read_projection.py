"""Pure projection of installed Evennia ship state into ``ox.world.read/1``.

SKETCH. No Django or ORM import: ``world_read_source`` reads one committed
snapshot under the physics clock lock and hands frozen rows to this module,
so the projection is unit-testable and ``mypy --strict`` clean.

Rules carried from ``contracts/WORLD_READ_MODEL.md``:

- pressure is cell-owned; rooms carry only their cell ID;
- a boundary's ``setting`` is the gas state the physics actually uses;
- inventory tonnes become kilograms exactly once, motion-ledger kilograms never;
- freshness is derived from sample age, never accepted from a caller;
- cursors are opaque, signed and bound to viewer, scope, world and revision.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypeVar

import orjson
from pydantic import ValidationError

from ox_contracts.world_read_model import (
    AIR_R_J_KG_K,
    LEGACY_FUEL_INVENTORIES,
    MAX_OBSERVATION_AGE_S,
    MAX_PAGE_ITEMS,
    ActorWorldPage,
    AddressedEvent,
    AuditEvent,
    DeveloperWorldPage,
    EquipmentActual,
    EquipmentObservation,
    Evidence,
    ExitObservation,
    Measurement,
    ModelIdentity,
    Page,
    PressureBoundaryActual,
    PressureCellActual,
    SpaceActual,
    StockActual,
    canonical_unit_for,
)

Scope = Literal["developer_actual", "actor_observed"]
T = TypeVar("T")

CURSOR_VERSION: Final[int] = 1
CURSOR_MAC_BYTES: Final[int] = 32
OXYGEN_KG_MOL: Final[float] = 0.032
AIR_KG_MOL: Final[float] = 0.029
# Equipment detail keys with a physical unit. Anything else stays out of the
# wire: unitless flags and trip reasons are not measurements.
EQUIPMENT_MEASUREMENTS: Final[Mapping[str, tuple[str, str]]] = {
    "physics_startup_s": ("startup_s", "s"),
}
ACTOR_EVENT_WINDOW: Final[int] = 512


class ProjectionError(ValueError):
    """Installed state cannot be published under ``ox.world.read/1``."""


class StaleCursor(PermissionError):
    """A cursor is foreign, forged or bound to an evicted publication."""


# --------------------------------------------------------------------------
# Frozen rows read by the Evennia adapter. Plain values only.
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpaceRow:
    space_id: str
    condition: str
    authored_zone: str | None


@dataclass(frozen=True, slots=True)
class CellRow:
    cell_id: str
    gas_mass_kg: float
    oxygen_kg: float
    temperature_k: float
    volume_m3: float


@dataclass(frozen=True, slots=True)
class AccessRow:
    link_id: str
    from_space_id: str
    to_space_id: str
    pressure_boundary: bool
    setting: str
    authored_policy: str
    condition: str


@dataclass(frozen=True, slots=True)
class EquipmentRow:
    equipment_id: str
    space_id: str
    condition: str
    online: bool | None
    numeric_details: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class InventoryRow:
    inventory_id: str
    quantity_t: float


@dataclass(frozen=True, slots=True)
class MotionBalances:
    propellant_kg: float
    ftl_fuel_kg: float


@dataclass(frozen=True, slots=True)
class AuditRow:
    sequence: int
    operation: str
    game_time_s: float


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    world_id: str
    topology_version: str
    engineering_version: str
    publication_seq: int
    game_time_s: float
    spaces: tuple[SpaceRow, ...]
    cells: tuple[CellRow, ...]
    access: tuple[AccessRow, ...]
    equipment: tuple[EquipmentRow, ...]
    inventories: tuple[InventoryRow, ...]
    motion: MotionBalances
    audit: tuple[AuditRow, ...]


@dataclass(frozen=True, slots=True)
class PanelReadingRow:
    """One journaled ``panel_reading`` event addressed to the actor."""

    event_id: str
    panel_id: str
    room_id: str
    status: str
    read_game_s: float
    sampled_game_s: float | None
    metrics: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class ExitRow:
    link_id: str
    to_space_id: str | None
    assessment: Literal["advertised", "blocked", "unknown"]


@dataclass(frozen=True, slots=True)
class JournalRow:
    event_id: str
    recipient_dbref: str
    kind: str
    game_time_s: float
    text: str
    details: Mapping[str, str | int | float | bool | None]


@dataclass(frozen=True, slots=True)
class ActorSnapshot:
    world_id: str
    topology_version: str
    engineering_version: str
    publication_seq: int
    game_time_s: float
    character_id: str
    location_id: str | None
    panel_readings: tuple[PanelReadingRow, ...]
    exits: tuple[ExitRow, ...]
    events: tuple[JournalRow, ...]


@dataclass(frozen=True, slots=True)
class OmissionReport:
    """What the projection refused to publish, for the operator log only."""

    reasons: tuple[str, ...]


# --------------------------------------------------------------------------
# Signed cursors
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CursorBinding:
    scope: Scope
    viewer: str
    world_id: str
    publication_seq: int
    topology_version: str
    engineering_version: str


def _binding_blob(binding: CursorBinding, page_index: int) -> bytes:
    return orjson.dumps(
        {
            "v": CURSOR_VERSION,
            "scope": binding.scope,
            "viewer": binding.viewer,
            "world": binding.world_id,
            "pub": binding.publication_seq,
            "topo": binding.topology_version,
            "eng": binding.engineering_version,
            "page": page_index,
        },
        option=orjson.OPT_SORT_KEYS,
    )


def encode_cursor(binding: CursorBinding, page_index: int, *, key: bytes) -> str:
    blob: bytes = _binding_blob(binding, page_index)
    mac: bytes = hmac.digest(key, blob, hashlib.blake2b)[:CURSOR_MAC_BYTES]
    body: str = base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")
    return body + "." + mac.hex()


def decode_cursor(token: str, binding: CursorBinding, *, key: bytes) -> int:
    """Return the page index, or reject any cursor not minted for this binding."""
    body, separator, mac_hex = token.partition(".")
    if not separator or len(token) > 1024:
        raise StaleCursor("Malformed world-read cursor")
    padding: str = "=" * (-len(body) % 4)
    try:
        blob: bytes = base64.urlsafe_b64decode(body + padding)
        claimed: bytes = bytes.fromhex(mac_hex)
        fields: object = orjson.loads(blob)
    except (ValueError, orjson.JSONDecodeError) as exc:
        raise StaleCursor("Malformed world-read cursor") from exc
    expected: bytes = hmac.digest(key, blob, hashlib.blake2b)[:CURSOR_MAC_BYTES]
    if not hmac.compare_digest(expected, claimed):
        raise StaleCursor("Forged or foreign world-read cursor")
    if not isinstance(fields, dict):
        raise StaleCursor("Malformed world-read cursor")
    page: object = fields.get("page")
    if type(page) is not int or page < 1:
        raise StaleCursor("Malformed world-read cursor")
    if blob != _binding_blob(binding, page):
        raise StaleCursor("Cursor bound to another viewer, scope or revision")
    return page


# --------------------------------------------------------------------------
# Physics helpers (identical arithmetic to the world, never re-simulated)
# --------------------------------------------------------------------------


def cell_pressure_kpa(cell: CellRow) -> float:
    """P = m·R·T/V, as ``continuous_ship_physics._cell_pressure``."""
    if cell.gas_mass_kg <= 0.0:
        return 0.0
    return (
        cell.gas_mass_kg * AIR_R_J_KG_K * cell.temperature_k / cell.volume_m3
    ) / 1000.0


def cell_oxygen_kpa(cell: CellRow, pressure_kpa: float) -> float:
    """Mole-fraction partial pressure, as the G19 panel ``_zone_metrics``."""
    if cell.gas_mass_kg <= 0.0:
        return 0.0
    oxygen_mol: float = cell.oxygen_kg / OXYGEN_KG_MOL
    other_mol: float = max(0.0, cell.gas_mass_kg - cell.oxygen_kg) / AIR_KG_MOL
    total_mol: float = oxygen_mol + other_mol
    return pressure_kpa * oxygen_mol / total_mol if total_mol > 0.0 else 0.0


def boundary_gas_setting(setting: str) -> Literal["open", "closed"]:
    """Physics exchanges gas only through ``setting == "open"``.

    ``continuous_ship_physics`` (open-hatch scan before gas exchange) skips
    every other setting, so a persisted ``closed_or_auto`` is gas-closed now.
    """
    if setting == "open":
        return "open"
    if setting in ("closed", "closed_or_auto"):
        return "closed"
    raise ProjectionError("Unrecognised persisted access setting: " + setting)


def _policy(value: str) -> Literal["open", "closed", "closed_or_auto"] | None:
    if value == "open":
        return "open"
    if value == "closed":
        return "closed"
    if value == "closed_or_auto":
        return "closed_or_auto"
    return None


def _event_kind(operation: str) -> str:
    return operation.strip().lower().replace("-", "_").replace(".", "_")[:64]


# --------------------------------------------------------------------------
# Developer scope
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeveloperRecords:
    spaces: tuple[SpaceActual, ...]
    cells: tuple[PressureCellActual, ...]
    boundaries: tuple[PressureBoundaryActual, ...]
    equipment: tuple[EquipmentActual, ...]
    stocks: tuple[StockActual, ...]
    audit: tuple[AuditEvent, ...]
    omissions: OmissionReport


def developer_records(snapshot: WorldSnapshot) -> DeveloperRecords:
    """Validate every record once; the pages only slice these tuples."""
    omitted: list[str] = []
    installed_cells: frozenset[str] = frozenset(c.cell_id for c in snapshot.cells)

    def cell_of(zone: str | None) -> str | None:
        return zone if zone is not None and zone in installed_cells else None

    zone_by_space: dict[str, str | None] = {
        row.space_id: row.authored_zone for row in snapshot.spaces
    }
    members: dict[str, list[str]] = {cell_id: [] for cell_id in installed_cells}
    spaces: list[SpaceActual] = []
    for row in sorted(snapshot.spaces, key=lambda r: r.space_id):
        cell_id: str | None = cell_of(row.authored_zone)
        if cell_id is not None:
            members[cell_id].append(row.space_id)
        spaces.append(
            SpaceActual(
                space_id=row.space_id,
                condition=row.condition[:100] or "unknown",
                pressure_cell_id=cell_id,
            )
        )

    cells: list[PressureCellActual] = []
    for cell in sorted(snapshot.cells, key=lambda c: c.cell_id):
        if not members[cell.cell_id]:
            omitted.append("cell without a materialised room: " + cell.cell_id)
            continue
        pressure: float = cell_pressure_kpa(cell)
        cells.append(
            PressureCellActual(
                cell_id=cell.cell_id,
                space_ids=tuple(sorted(members[cell.cell_id])),
                pressure_kpa=pressure,
                oxygen_kpa=cell_oxygen_kpa(cell, pressure),
                temperature_k=cell.temperature_k,
                gas_mass_kg=cell.gas_mass_kg,
                volume_m3=cell.volume_m3,
            )
        )

    boundaries: list[PressureBoundaryActual] = []
    for link in sorted(snapshot.access, key=lambda a: a.link_id):
        if not link.pressure_boundary:
            continue
        from_cell: str | None = cell_of(zone_by_space.get(link.from_space_id))
        to_cell: str | None = cell_of(zone_by_space.get(link.to_space_id))
        if from_cell == to_cell:
            # Same envelope (or two uncommissioned ones): not a gas boundary
            # the contract can express. Never invent a second cell.
            omitted.append("boundary inside one envelope: " + link.link_id)
            continue
        boundaries.append(
            PressureBoundaryActual(
                link_id=link.link_id,
                from_space_id=link.from_space_id,
                to_space_id=link.to_space_id,
                from_cell_id=from_cell,
                to_cell_id=to_cell,
                setting=boundary_gas_setting(link.setting),
                authored_policy=_policy(link.authored_policy),
                condition=link.condition[:100],
            )
        )

    equipment: list[EquipmentActual] = []
    for unit in sorted(snapshot.equipment, key=lambda e: e.equipment_id):
        readings: list[Measurement] = []
        for detail, (metric, unit_name) in EQUIPMENT_MEASUREMENTS.items():
            value: float | None = unit.numeric_details.get(detail)
            if value is not None and math.isfinite(value):
                readings.append(
                    Measurement.model_validate(
                        {"name": metric, "unit": unit_name, "value": value}
                    )
                )
        setting: str | None = None
        if unit.online is not None:
            setting = "online" if unit.online else "offline"
        equipment.append(
            EquipmentActual(
                equipment_id=unit.equipment_id,
                space_id=unit.space_id,
                condition=unit.condition[:100],
                setting=setting,
                measurements=tuple(readings),
            )
        )

    stocks: list[StockActual] = []
    for inventory in sorted(snapshot.inventories, key=lambda i: i.inventory_id):
        legacy: bool = inventory.inventory_id in LEGACY_FUEL_INVENTORIES
        stocks.append(
            StockActual(
                account_id=inventory.inventory_id,
                custodian="inventory",
                accounting="legacy_reference" if legacy else "fitted_stock",
                # Evennia inventories are tonnes; the wire is kilograms.
                quantity_kg=inventory.quantity_t * 1000.0,
            )
        )
    for account, quantity_kg in (
        ("motion.propellant_kg", snapshot.motion.propellant_kg),
        ("motion.ftl_fuel_kg", snapshot.motion.ftl_fuel_kg),
    ):
        # Already kilograms: never multiplied twice.
        stocks.append(
            StockActual(
                account_id=account,
                custodian="motion_ledger",
                accounting="operational_balance",
                quantity_kg=quantity_kg,
            )
        )

    audit: list[AuditEvent] = []
    for event in sorted(snapshot.audit, key=lambda e: e.sequence):
        if event.game_time_s > snapshot.game_time_s:
            continue  # after the physics snapshot; next publication shows it
        try:
            audit.append(
                AuditEvent(
                    event_id="cse-" + str(event.sequence),
                    kind=_event_kind(event.operation),
                    occurred_game_s=event.game_time_s,
                    visibility="developer_only",
                )
            )
        except ValidationError:
            omitted.append("audit operation outside kind grammar: " + event.operation)

    return DeveloperRecords(
        spaces=tuple(spaces),
        cells=tuple(cells),
        boundaries=tuple(boundaries),
        equipment=tuple(equipment),
        stocks=tuple(stocks),
        audit=tuple(audit),
        omissions=OmissionReport(tuple(omitted)),
    )


def _page_count(collections: Iterable[Sequence[object]]) -> int:
    longest: int = max((len(items) for items in collections), default=0)
    return max(1, math.ceil(longest / MAX_PAGE_ITEMS))


def _slice(items: tuple[T, ...], index: int) -> tuple[T, ...]:
    start: int = index * MAX_PAGE_ITEMS
    return items[start : start + MAX_PAGE_ITEMS]


def _page_meta(binding: CursorBinding, index: int, count: int, *, key: bytes) -> Page:
    if index == count - 1:
        return Page(complete=True)
    return Page(complete=False, next_cursor=encode_cursor(binding, index + 1, key=key))


def developer_series(
    snapshot: WorldSnapshot, *, viewer: str, key: bytes
) -> tuple[tuple[DeveloperWorldPage, ...], OmissionReport]:
    """Every page of one consistent snapshot, sliced in parallel by ID order."""
    records: DeveloperRecords = developer_records(snapshot)
    binding: CursorBinding = CursorBinding(
        scope="developer_actual",
        viewer=viewer,
        world_id=snapshot.world_id,
        publication_seq=snapshot.publication_seq,
        topology_version=snapshot.topology_version,
        engineering_version=snapshot.engineering_version,
    )
    models: ModelIdentity = ModelIdentity(
        topology_version=snapshot.topology_version,
        engineering_version=snapshot.engineering_version,
    )
    count: int = _page_count(
        (
            records.spaces,
            records.cells,
            records.boundaries,
            records.equipment,
            records.stocks,
            records.audit,
        )
    )
    pages: list[DeveloperWorldPage] = [
        DeveloperWorldPage(
            schema_version="ox.world.read/1",
            scope="developer_actual",
            world_id=snapshot.world_id,
            models=models,
            publication_seq=snapshot.publication_seq,
            game_time_s=snapshot.game_time_s,
            page=_page_meta(binding, index, count, key=key),
            spaces=_slice(records.spaces, index),
            pressure_cells=_slice(records.cells, index),
            pressure_boundaries=_slice(records.boundaries, index),
            equipment=_slice(records.equipment, index),
            stocks=_slice(records.stocks, index),
            audit_events=_slice(records.audit, index),
        )
        for index in range(count)
    ]
    return tuple(pages), records.omissions


# --------------------------------------------------------------------------
# Actor scope: only what this character legitimately received
# --------------------------------------------------------------------------


def panel_observation(
    reading: PanelReadingRow, *, now_s: float
) -> EquipmentObservation:
    """Freshness from the panel's own sample time, never the read time."""
    # An online panel outside any gas cell samples no metrics but still
    # reports its own status; dark, damaged or degraded panels report nothing.
    if reading.status != "online" or reading.sampled_game_s is None:
        # Failed sample: the evidence time is when failure was confirmed.
        return EquipmentObservation(
            equipment_id=reading.panel_id,
            reported_space_id=reading.room_id,
            availability="unavailable",
            evidence=Evidence(
                source="local_panel",
                source_id=reading.panel_id,
                observed_game_s=reading.read_game_s,
            ),
        )
    sampled: float = reading.sampled_game_s
    readings: tuple[Measurement, ...] = tuple(
        Measurement.model_validate({"name": name, "unit": unit, "value": value})
        for name, value in sorted(reading.metrics.items())
        if (unit := canonical_unit_for(name)) is not None and math.isfinite(value)
    )
    age: float = now_s - sampled
    return EquipmentObservation(
        equipment_id=reading.panel_id,
        reported_space_id=reading.room_id,
        availability="available" if age <= MAX_OBSERVATION_AGE_S else "stale",
        reported_condition="online",
        readings=readings,
        evidence=Evidence(
            source="local_panel",
            source_id=reading.panel_id,
            observed_game_s=sampled,
        ),
    )


def addressed_event(row: JournalRow) -> AddressedEvent | None:
    """Wire form of one journal row, or None if the contract cannot carry it.

    Two journal/contract mismatches are reported, not papered over:
    ``emit()`` defaults ``text`` to "" (contract needs >= 1 char) and allows
    ``None`` details (contract datums are non-null).
    """
    if not row.text:
        return None
    datums: dict[str, str | int | float | bool] = {
        "datum_" + key: value
        for key, value in row.details.items()
        if value is not None and key.islower()
    }
    try:
        return AddressedEvent(
            event_id=row.event_id,
            recipient_character_id=row.recipient_dbref,
            kind=_event_kind(row.kind),
            occurred_game_s=row.game_time_s,
            text=row.text[:4096],
            datum_fields=datums,
            source="delivered_world_event",
        )
    except ValidationError:
        return None


def actor_series(
    snapshot: ActorSnapshot, *, key: bytes
) -> tuple[tuple[ActorWorldPage, ...], OmissionReport]:
    omitted: list[str] = []
    latest: dict[str, PanelReadingRow] = {}
    for reading in sorted(snapshot.panel_readings, key=lambda r: r.read_game_s):
        latest[reading.panel_id] = reading
    observations: tuple[EquipmentObservation, ...] = tuple(
        panel_observation(latest[panel_id], now_s=snapshot.game_time_s)
        for panel_id in sorted(latest)
    )
    exits: tuple[ExitObservation, ...] = ()
    if snapshot.location_id is not None:
        exits = tuple(
            ExitObservation(
                link_id=row.link_id,
                from_space_id=snapshot.location_id,
                to_space_id=row.to_space_id,
                assessment=row.assessment,
                evidence=Evidence(
                    source="local_capability",
                    source_id=row.link_id,
                    observed_game_s=snapshot.game_time_s,
                ),
            )
            for row in sorted(snapshot.exits, key=lambda e: e.link_id)
        )
    events: list[AddressedEvent] = []
    window: list[JournalRow] = sorted(snapshot.events, key=lambda e: e.game_time_s)[
        -ACTOR_EVENT_WINDOW:
    ]
    for row in window:
        if row.recipient_dbref != snapshot.character_id:
            raise ProjectionError("Foreign journal row offered to actor scope")
        wire: AddressedEvent | None = addressed_event(row)
        if wire is None:
            omitted.append("journal row not expressible: " + row.event_id)
        elif wire.occurred_game_s <= snapshot.game_time_s:
            events.append(wire)
    binding: CursorBinding = CursorBinding(
        scope="actor_observed",
        viewer=snapshot.character_id,
        world_id=snapshot.world_id,
        publication_seq=snapshot.publication_seq,
        topology_version=snapshot.topology_version,
        engineering_version=snapshot.engineering_version,
    )
    models: ModelIdentity = ModelIdentity(
        topology_version=snapshot.topology_version,
        engineering_version=snapshot.engineering_version,
    )
    wire_events: tuple[AddressedEvent, ...] = tuple(events)
    count: int = _page_count((observations, exits, wire_events))
    pages: list[ActorWorldPage] = [
        ActorWorldPage(
            schema_version="ox.world.read/1",
            scope="actor_observed",
            world_id=snapshot.world_id,
            models=models,
            publication_seq=snapshot.publication_seq,
            game_time_s=snapshot.game_time_s,
            page=_page_meta(binding, index, count, key=key),
            character_id=snapshot.character_id,
            location_id=snapshot.location_id,
            equipment=_slice(observations, index),
            exits=_slice(exits, index),
            addressed_events=_slice(wire_events, index),
        )
        for index in range(count)
    ]
    return tuple(pages), OmissionReport(tuple(omitted))
