"""World-owned scarce cartridges, physical carriers and supply order transitions.

Each serialised cartridge has exactly one state: stored in a real room,
carried by an actual crew body, or irreversibly consumed. Supply order work
is called inside the global execute_work transaction, which serializes
same-ship requests under a world-owned PostgreSQL row lock. The handler
never reads this module, a Django model or a global inventory list.
"""
from __future__ import annotations

from django.db import transaction
from evennia.utils import gametime
import re
import uuid

from world.bootstrap import build_ship
from world.event_journal import emit
from world.models import InventoryItem, SupplyOrder

KIND = "a01_cartridge"
_ID = re.compile(r"[0-9a-f]{32}")


def available_at(room) -> int:
    """New physical, unconsumed cartridge units installed in this room."""
    return InventoryItem.objects.filter(
        kind=KIND, state="stored", location_dbref=room.dbref,
    ).count()


def total_local_spares(scrubber) -> int:
    """Legacy physical A-01 rack plus newly delivered serialised units."""
    old = int(scrubber.db.spare_cartridges or 0)
    if old < 0:
        raise ValueError("World cannot hold a negative legacy cartridge count")
    return old + available_at(scrubber.location)


def seed_disposable_cargo_cartridges(*, count: int = 1) -> tuple[str, ...]:
    """Operator fixture only, never exposed to game player/AI commands.

    Creates actual world objects as an initial scenario condition. Never
    called by idempotent build_ship(), never resets existing item quantities.
    """
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError("Disposable fixture supports 1-10 physical units")
    ship = build_ship()
    item_ids = []
    with transaction.atomic():
        for _ in range(count):
            item_id = "oxitem-" + uuid.uuid4().hex
            InventoryItem.objects.create(
                item_id=item_id, kind=KIND, state="stored",
                location_dbref=ship["cargo_hold"].dbref,
            )
            item_ids.append(item_id)
    return tuple(item_ids)


def _local_person(actor, expected_role: str, room) -> bool:
    return bool(
        actor is not None and actor.location == room
        and actor.db.crew_role == expected_role
    )


def execute_supply(actor, request_id: str, operation: str,
                   args: dict) -> tuple[bool, str | None]:
    """Apply one world transition; return success and actor's source event ID.

    Caller: execute_work, already holding the globally exclusive world lock
    and atomic WorkReceipt transaction. Negative outcomes persist as failed
    receipts by that caller, and cannot be retried with the same request ID.
    """
    if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
        raise ValueError("Invalid global supply work ID")
    ship = build_ship()
    pump = ship["pump"]
    if operation == "request_supply":
        if args:
            raise ValueError("Supply request takes no arbitrary parameters")
        scrubber = ship["scrubber"]
        if (not _local_person(actor, "environment_tech", ship["environmental"])
                or scrubber.state != "isolated"
                or total_local_spares(scrubber) > 0):
            return False, None
        # Explicit dependency is a *world object*, not an agent's claim.
        if SupplyOrder.objects.filter(pk=request_id).exists():
            raise PermissionError("Supply order ID already used")
        order = SupplyOrder.objects.create(
            order_id=request_id, requester_dbref=actor.dbref,
            assigned_dbref=ship["cargo"].dbref, item_kind=KIND,
            delivery_room_dbref=ship["environmental"].dbref,
            status="requested", created_game_time=float(
                gametime.gametime(absolute=True)
            ),
        )
        own = emit(
            pump, actor, "supply_requested", sender=actor,
            data={"order_id": order.order_id, "item_kind": KIND},
            text="World registered an environmental cartridge dependency.",
        )
        emit(
            pump, ship["cargo"], "supply_request", sender=actor,
            data={"order_id": order.order_id, "item_kind": KIND,
                  "delivery": "Environmental Plant"},
            text="Environmental technician requests one physical cartridge.",
        )
        return True, own["event_id"]

    order_id = args.get("order_id")
    if set(args) != {"order_id"} or not isinstance(order_id, str) or not _ID.fullmatch(order_id):
        raise ValueError("Supply handoff requires the exact order ID")
    order = SupplyOrder.objects.select_for_update().filter(pk=order_id).first()
    if (order is None or actor.dbref != order.assigned_dbref
            or actor.db.crew_role != "cargo_officer"):
        return False, None
    if operation == "accept_supply":
        if order.status != "requested":
            return False, None
        order.status = "accepted"
        order.save(update_fields=["status"])
        own = emit(
            pump, actor, "supply_accepted", sender=actor,
            data={"order_id": order_id}, text="Cargo accepted this supply job.",
        )
        emit(
            pump, ship["environment"], "supply_accepted", sender=actor,
            data={"order_id": order_id}, text="Cargo accepted the request; no item is delivered yet.",
        )
        return True, own["event_id"]

    if operation == "collect_supply":
        if (order.status != "accepted"
                or not _local_person(actor, "cargo_officer", ship["cargo_hold"])):
            return False, None
        item = (InventoryItem.objects.select_for_update().filter(
            kind=order.item_kind, state="stored",
            location_dbref=ship["cargo_hold"].dbref,
            reserved_order_id__isnull=True,
        ).order_by("item_id").first())
        if item is None:
            return False, None
        item.state = "carried"
        item.location_dbref = None
        item.carrier_dbref = actor.dbref
        item.reserved_order_id = order_id
        item.save(update_fields=[
            "state", "location_dbref", "carrier_dbref", "reserved_order_id",
        ])
        order.item_id = item.item_id
        order.status = "in_transit"
        order.save(update_fields=["item_id", "status"])
        own = emit(
            pump, actor, "supply_collected", sender=actor,
            data={"order_id": order_id, "item_id": item.item_id},
            text="Cargo collected and is physically carrying one cartridge.",
        )
        emit(
            pump, ship["environment"], "supply_in_transit", sender=actor,
            data={"order_id": order_id},
            text="Cargo reports one cartridge in transit; delivery is not confirmed.",
        )
        return True, own["event_id"]

    if operation == "deliver_supply":
        if (order.status != "in_transit"
                or actor.location is None
                or actor.location.dbref != order.delivery_room_dbref
                or not order.item_id):
            return False, None
        item = InventoryItem.objects.select_for_update().filter(
            pk=order.item_id, state="carried",
            carrier_dbref=actor.dbref, reserved_order_id=order_id,
        ).first()
        if item is None:
            return False, None
        item.state = "stored"
        item.location_dbref = order.delivery_room_dbref
        item.carrier_dbref = None
        item.reserved_order_id = None
        item.save(update_fields=[
            "state", "location_dbref", "carrier_dbref", "reserved_order_id",
        ])
        order.status = "delivered"
        order.save(update_fields=["status"])
        own = emit(
            pump, actor, "supply_delivered", sender=actor,
            data={"order_id": order_id, "item_id": item.item_id},
            text="World confirms the physical delivery was completed.",
        )
        from evennia.objects.models import ObjectDB
        requester = ObjectDB.objects.filter(
            id=int(order.requester_dbref.lstrip("#"))
        ).first()
        if requester is None:
            raise RuntimeError("Cannot complete delivery to a missing requester")
        emit(
            pump, requester, "supply_replenished", sender=actor,
            data={"order_id": order_id, "item_id": item.item_id,
                  "equipment": "A-01"},
            text="One physical cartridge arrived at Environmental Plant.",
        )
        return True, own["event_id"]

    raise ValueError("Unknown world supply operation")


def local_stock_for(actor, nonce: str) -> dict:
    """An ordinary world read: only local stock and own assigned orders."""
    if not isinstance(nonce, str) or not _ID.fullmatch(nonce):
        raise ValueError("Invalid stock observation nonce")
    if actor is None or not isinstance(getattr(actor, "dbref", None), str):
        raise PermissionError("Only actual characters may inspect inventory")
    ship = build_ship()
    at = actor.location
    total = None  # Outside stocked compartments, absence is UNKNOWN, not zero.
    if at == ship["cargo_hold"]:
        total = InventoryItem.objects.filter(
            kind=KIND, state="stored", location_dbref=at.dbref,
        ).count()
    elif at == ship["environmental"]:
        total = total_local_spares(ship["scrubber"])
    carried = list(InventoryItem.objects.filter(
        state="carried", carrier_dbref=actor.dbref,
    ).order_by("item_id").values_list("item_id", flat=True)[:16])
    # Order state is NOT a remote clairvoyant inventory listing: the
    # character learns about assigned jobs through their addressed journal.
    return {
        "version": 1, "nonce": nonce, "actor_dbref": actor.dbref,
        "room_dbref": at.dbref if at is not None else None,
        "game_time": float(gametime.gametime(absolute=True)),
        "local_cartridges": total, "carried": carried,
    }
