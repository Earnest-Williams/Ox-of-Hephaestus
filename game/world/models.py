"""Indexed authoritative world records (not handler-side beliefs).

The large recipient-addressed event journal is a separate Django table,
not a serialized Attribute list attached to cooling pump P-01.
"""
from django.db import models


class CrewEvent(models.Model):
    """Immutable, globally ordered, recipient-private observation."""

    sequence = models.BigAutoField(primary_key=True)
    event_id = models.CharField(max_length=64, unique=True, null=True)
    recipient_dbref = models.CharField(max_length=32)
    sender_dbref = models.CharField(max_length=32, null=True)
    kind = models.CharField(max_length=64)
    details = models.JSONField(default=dict)
    text = models.TextField(default="")
    game_time = models.FloatField()

    class Meta:
        indexes = [
            models.Index(
                fields=["recipient_dbref", "sequence"],
                name="ox_event_recipient_seq",
            ),
        ]


class WorkReceipt(models.Model):
    """One authoritative outcome per globally unique requested work ID.

    All supported physical and social actions pass through the same world
    transaction. This table does not contain an AI intention or grant any
    additional privileges; source transitions still enforce world rules.
    """

    request_id = models.CharField(max_length=32, primary_key=True)
    actor_dbref = models.CharField(max_length=32)
    target = models.CharField(max_length=32)
    operation = models.CharField(max_length=48)
    arguments = models.JSONField(default=dict)
    outcome = models.JSONField(default=dict)
    game_time = models.FloatField()

    class Meta:
        indexes = [
            models.Index(
                fields=["actor_dbref", "game_time"],
                name="ox_work_actor_time",
            ),
        ]


class InventoryItem(models.Model):
    """One serialised physical consumable; exactly one place/carrier or used.

    Individual item rows make single-unit scarcity and transfer inspectable.
    No AI-authored claim can change this table. Consumed rows remain durable
    conservation evidence instead of disappearing from the count.
    """

    item_id = models.CharField(max_length=48, primary_key=True)
    kind = models.CharField(max_length=48)
    state = models.CharField(max_length=16, default="stored")
    location_dbref = models.CharField(max_length=32, null=True)
    carrier_dbref = models.CharField(max_length=32, null=True)
    reserved_order_id = models.CharField(max_length=32, null=True)
    consumed_by_dbref = models.CharField(max_length=32, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["kind", "state", "location_dbref"],
                         name="ox_inventory_location"),
            models.Index(fields=["carrier_dbref", "state"],
                         name="ox_inventory_carrier"),
        ]
        constraints = [
            models.CheckConstraint(
                name="ox_inventory_one_location",
                condition=(
                    models.Q(state="stored", location_dbref__isnull=False,
                             carrier_dbref__isnull=True)
                    | models.Q(state="carried", location_dbref__isnull=True,
                               carrier_dbref__isnull=False)
                    | models.Q(state="consumed", location_dbref__isnull=True,
                               carrier_dbref__isnull=True)
                ),
            ),
        ]


class SupplyOrder(models.Model):
    """World-owned interdepartment dependency, not agent-private agenda."""

    order_id = models.CharField(max_length=32, primary_key=True)
    item_kind = models.CharField(max_length=48)
    requester_dbref = models.CharField(max_length=32)
    assigned_dbref = models.CharField(max_length=32)
    delivery_room_dbref = models.CharField(max_length=32)
    status = models.CharField(max_length=20)
    item_id = models.CharField(max_length=48, null=True)
    created_game_time = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=["assigned_dbref", "status"],
                         name="ox_supply_assignee"),
            models.Index(fields=["requester_dbref", "status"],
                         name="ox_supply_requester"),
        ]
