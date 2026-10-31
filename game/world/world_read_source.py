"""Evennia adapter: read one committed G19 snapshot for ``ox.world.read/1``.

SKETCH. Thin by design: every rule lives in ``world_read_projection``. This
module only reads world-owned rows and never writes, emits or repairs.

Consistency: the developer snapshot is read under the continuous-physics
clock row lock (``_clock(lock=True)``), which every physics tick also takes,
so cells, access settings, equipment and stocks come from one tick boundary.
No other lock is taken, so the P-01 → captain ticket → journal order is
untouched. Pages of that snapshot are cached by ``publication_seq`` so a
paging client sees one consistent world even while ticks continue.
"""

from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any, Final, Literal, cast

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from evennia.objects.models import ObjectDB
from evennia.utils import gametime
from ox_contracts.world_read_model import ActorWorldPage, DeveloperWorldPage

from world.full_ship_operations import MODEL, ShipOperationsError, load_candidate
from world.models import (
    CanonicalShipEvent,
    CanonicalShipState,
    CrewEvent,
    JournalEpoch,
)
from world.ship_world import ROOT_MARKER, WORLD_CATEGORY, find_world_entity
from world.world_read_projection import (
    ACTOR_EVENT_WINDOW,
    AccessRow,
    ActorSnapshot,
    AuditRow,
    CellRow,
    CursorBinding,
    EquipmentRow,
    ExitRow,
    InventoryRow,
    JournalRow,
    MotionBalances,
    OmissionReport,
    PanelReadingRow,
    SpaceRow,
    StaleCursor,
    WorldSnapshot,
    actor_series,
    decode_cursor,
    developer_series,
)

# Typed boundary over existing untyped world code: one cast, named once.
_load_candidate: Callable[[], dict[str, Any]] = cast(
    Callable[[], dict[str, Any]], load_candidate
)
_game_time: Callable[..., float] = cast(Callable[..., float], gametime.gametime)

AUDIT_WINDOW: Final[int] = 512
SERIES_CACHE: Final[int] = 4
PANEL_READING_KIND: Final[str] = "panel_reading"

_DeveloperSeries = tuple[tuple[DeveloperWorldPage, ...], OmissionReport]
_series_cache: OrderedDict[tuple[str, int], _DeveloperSeries] = OrderedDict()


def cursor_key() -> bytes:
    """Derived from the server secret; rotating SECRET_KEY voids all cursors."""
    secret: bytes = str(settings.SECRET_KEY).encode("utf-8")
    return hashlib.blake2b(secret, person=b"ox.world.read/1").digest()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShipOperationsError("Non-numeric " + label)
    number: float = float(value)
    if not math.isfinite(number):
        raise ShipOperationsError("Non-finite " + label)
    return number


@lru_cache(maxsize=1)
def _authored_zones() -> Mapping[str, str | None]:
    """Immutable v0.5 reference: room → authored pressure zone."""
    reference: dict[str, Any] = _load_candidate()
    return {
        str(space["id"]): space.get("pressure_zone") for space in reference["spaces"]
    }


def _world_identity() -> tuple[str, str, str]:
    root: Any = find_world_entity(ROOT_MARKER)
    if root is None or not root.db.ox_topology_complete:
        raise ShipOperationsError("Canonical topology not installed")
    epoch: JournalEpoch | None = JournalEpoch.objects.filter(id=1).first()
    if epoch is None:
        raise ShipOperationsError("World journal epoch not established")
    return "ox-" + str(epoch.generation), str(root.db.ox_model_version), MODEL


def _publication_seq() -> int:
    latest: object = CanonicalShipEvent.objects.aggregate(top=Max("sequence"))["top"]
    if type(latest) is not int or latest < 1:
        raise ShipOperationsError("No committed world publication yet")
    return latest


def _room_conditions() -> dict[str, str]:
    """Same allowlisted attribute read as ``ship_telemetry``."""
    rooms: Any = (
        ObjectDB.objects.filter(
            db_tags__db_category__iexact=WORLD_CATEGORY,
            db_tags__db_key__istartswith="space:",
        )
        .distinct()
        .prefetch_related("db_attributes")
    )
    conditions: dict[str, str] = {}
    for room in rooms:
        values: dict[str, object] = {
            a.db_key: a.value
            for a in room.db_attributes.all()
            if a.db_key in ("ox_space_id", "ox_current_condition")
        }
        space_id: object = values.get("ox_space_id")
        condition: object = values.get("ox_current_condition")
        if isinstance(space_id, str) and space_id:
            conditions[space_id] = (
                condition if isinstance(condition, str) and condition else "unknown"
            )
    return conditions


def read_world_snapshot() -> WorldSnapshot:
    from world.continuous_ship_physics import _clock as untyped_clock

    _clock: Callable[..., Any] = cast(Callable[..., Any], untyped_clock)
    zones: Mapping[str, str | None] = _authored_zones()
    with transaction.atomic():
        clock: Any = _clock(lock=True)
        world_id, topology, engineering = _world_identity()
        game_time: float = _finite(clock.details["last_game_time"], "physics time")
        motion: Mapping[str, object] = clock.details["motion"]
        rows: list[Any] = list(
            CanonicalShipState.objects.filter(
                category__in=("pressure", "access", "equipment", "inventory")
            ).order_by("key")
        )
        conditions: dict[str, str] = _room_conditions()
        audit: list[Any] = list(
            CanonicalShipEvent.objects.filter(game_time__lte=game_time).order_by(
                "-sequence"
            )[:AUDIT_WINDOW]
        )
        publication: int = _publication_seq()

    cells: list[CellRow] = []
    access: list[AccessRow] = []
    equipment: list[EquipmentRow] = []
    inventories: list[InventoryRow] = []
    for row in rows:
        if row.category == "pressure":
            cells.append(
                CellRow(
                    cell_id=row.source_id,
                    gas_mass_kg=_finite(row.quantity, "cell mass"),
                    oxygen_kg=_finite(row.details["physics_oxygen_kg"], "oxygen"),
                    temperature_k=_finite(row.details["temperature_k"], "temp"),
                    volume_m3=_finite(row.details["gas_volume_m3"], "volume"),
                )
            )
        elif row.category == "access":
            access.append(
                AccessRow(
                    link_id=row.source_id,
                    from_space_id=str(row.reference["from"]),
                    to_space_id=str(row.reference["to"]),
                    pressure_boundary=row.reference.get("pressure_boundary") is True,
                    setting=row.setting,
                    authored_policy=str(row.reference.get("normal_state", "")),
                    condition=row.condition,
                )
            )
        elif row.category == "equipment" and row.space_id:
            online: object = row.details.get("physics_online")
            equipment.append(
                EquipmentRow(
                    equipment_id=row.source_id,
                    space_id=row.space_id,
                    condition=row.condition,
                    online=online if type(online) is bool else None,
                    numeric_details={
                        k: float(v)
                        for k, v in row.details.items()
                        if type(v) in (int, float)
                    },
                )
            )
        elif row.category == "inventory":
            inventories.append(
                InventoryRow(row.source_id, _finite(row.quantity, "inventory"))
            )

    return WorldSnapshot(
        world_id=world_id,
        topology_version=topology,
        engineering_version=engineering,
        publication_seq=publication,
        game_time_s=game_time,
        spaces=tuple(
            SpaceRow(space_id, condition, zones.get(space_id))
            for space_id, condition in conditions.items()
        ),
        cells=tuple(cells),
        access=tuple(access),
        equipment=tuple(equipment),
        inventories=tuple(inventories),
        motion=MotionBalances(
            propellant_kg=_finite(motion["propellant_kg"], "propellant"),
            ftl_fuel_kg=_finite(motion["ftl_fuel_kg"], "FTL fuel"),
        ),
        audit=tuple(
            AuditRow(int(e.sequence), str(e.operation), float(e.game_time))
            for e in audit
        ),
    )


def developer_page(viewer: str, cursor: str | None) -> DeveloperWorldPage:
    """One page of a cached consistent series; stale cursors restart."""
    key: bytes = cursor_key()
    if cursor is None:
        snapshot: WorldSnapshot = read_world_snapshot()
        cache_key: tuple[str, int] = (viewer, snapshot.publication_seq)
        if cache_key not in _series_cache:
            _series_cache[cache_key] = developer_series(
                snapshot, viewer=viewer, key=key
            )
            while len(_series_cache) > SERIES_CACHE:
                _series_cache.popitem(last=False)
        return _series_cache[cache_key][0][0]
    for (cached_viewer, publication), (pages, _) in _series_cache.items():
        first: DeveloperWorldPage = pages[0]
        if cached_viewer != viewer:
            continue
        binding: CursorBinding = CursorBinding(
            scope="developer_actual",
            viewer=viewer,
            world_id=first.world_id,
            publication_seq=publication,
            topology_version=first.models.topology_version,
            engineering_version=first.models.engineering_version,
        )
        try:
            index: int = decode_cursor(cursor, binding, key=key)
        except StaleCursor:
            continue
        if index < len(pages):
            return pages[index]
    raise StaleCursor("Publication evicted; restart the read from page 1")


# --------------------------------------------------------------------------
# Actor scope
# --------------------------------------------------------------------------


def _panel_reading(record: Any) -> PanelReadingRow | None:
    details: Mapping[str, object] = record.details
    panel: object = details.get("panel")
    room: object = details.get("room")
    status: object = details.get("status")
    sampled: object = details.get("sampled_game_s")
    if not (isinstance(panel, str) and isinstance(room, str)):
        return None
    if not isinstance(status, str):
        return None
    return PanelReadingRow(
        event_id=str(record.event_id),
        panel_id=panel,
        room_id=room,
        status=status,
        read_game_s=float(record.game_time),
        sampled_game_s=(
            float(sampled)
            if isinstance(sampled, (int, float)) and not isinstance(sampled, bool)
            else None
        ),
        metrics={
            key[len("metric_") :]: float(value)
            for key, value in details.items()
            if key.startswith("metric_")
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        },
    )


def _exit_rows(actor: Any) -> tuple[ExitRow, ...]:
    """Exits in this room only, assessed by the real traversal gate."""
    from typeclasses.ship_world import CanonicalShipAccess
    from world.ship_crew_access import _clearance as untyped_clearance

    _clearance: Callable[..., Any] = cast(Callable[..., Any], untyped_clearance)

    rows: list[ExitRow] = []
    for obj in actor.location.contents:
        if not isinstance(obj, CanonicalShipAccess):
            continue
        link: object = obj.db.ox_access_link_id
        dest: Any = obj.destination
        if not isinstance(link, str) or link.startswith("runtime-"):
            continue
        assessment: Literal["advertised", "blocked", "unknown"] = "unknown"
        try:
            # _clearance raises on any gate and performs no writes; run it
            # inside a savepoint so its row locks end with this check.
            with transaction.atomic():
                _clearance(actor, obj, dest)
            assessment = "advertised"
        except (ShipOperationsError, PermissionError):
            assessment = "blocked"
        rows.append(
            ExitRow(
                link_id=link,
                to_space_id=(
                    str(dest.db.ox_space_id)
                    if assessment == "advertised" and dest is not None
                    else None
                ),
                assessment=assessment,
            )
        )
    return tuple(rows)


def read_actor_snapshot(actor: Any) -> ActorSnapshot:
    world_id, topology, engineering = _world_identity()
    location: object = getattr(getattr(actor.location, "db", None), "ox_space_id", None)
    records: list[Any] = list(
        CrewEvent.objects.filter(recipient_dbref=actor.dbref).order_by("-sequence")[
            :ACTOR_EVENT_WINDOW
        ]
    )
    readings: list[PanelReadingRow] = [
        reading
        for record in records
        if record.kind == PANEL_READING_KIND
        and (reading := _panel_reading(record)) is not None
    ]
    return ActorSnapshot(
        world_id=world_id,
        topology_version=topology,
        engineering_version=engineering,
        publication_seq=_publication_seq(),
        game_time_s=float(_game_time(absolute=True)),
        character_id=str(actor.dbref),
        location_id=location if isinstance(location, str) else None,
        panel_readings=tuple(readings),
        exits=_exit_rows(actor) if isinstance(location, str) else (),
        events=tuple(
            JournalRow(
                event_id=str(r.event_id),
                recipient_dbref=str(r.recipient_dbref),
                kind=str(r.kind),
                game_time_s=float(r.game_time),
                text=str(r.text),
                details=dict(r.details),
            )
            for r in records
        ),
    )


def actor_page(actor: Any, cursor: str | None) -> ActorWorldPage:
    """Actor pages are rebuilt per request; a cursor only selects the index."""
    key: bytes = cursor_key()
    pages, _ = actor_series(read_actor_snapshot(actor), key=key)
    if cursor is None:
        return pages[0]
    first: ActorWorldPage = pages[0]
    binding: CursorBinding = CursorBinding(
        scope="actor_observed",
        viewer=first.character_id,
        world_id=first.world_id,
        publication_seq=first.publication_seq,
        topology_version=first.models.topology_version,
        engineering_version=first.models.engineering_version,
    )
    index: int = decode_cursor(cursor, binding, key=key)
    if index >= len(pages):
        raise StaleCursor("Actor view changed; restart the read from page 1")
    return pages[index]
