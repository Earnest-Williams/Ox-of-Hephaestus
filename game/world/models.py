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
