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
