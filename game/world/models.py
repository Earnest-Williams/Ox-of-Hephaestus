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


class InvestigationCase(models.Model):
    """World-secret latent cause and authoritative individually sampled evidence."""
    case_id = models.CharField(max_length=32, primary_key=True)
    status = models.CharField(max_length=16)
    cause = models.CharField(max_length=32)
    signals = models.JSONField(default=dict)
    samples = models.JSONField(default=dict)
    reports = models.JSONField(default=dict)
    assessment = models.JSONField(default=dict)
    # Independent and optionally contradictory second-stage evidence.
    # Kept out of actor observations unless explicitly relayed by Evennia.
    probe_key = models.CharField(max_length=32, default="")
    challenges = models.JSONField(default=dict)
    questions = models.JSONField(default=dict)
    probes = models.JSONField(default=dict)
    reconsiderations = models.JSONField(default=dict)
    reassessment = models.JSONField(default=dict)
    created_game_time = models.FloatField()


class CaptainObligation(models.Model):
    """Persistent command responsibility for unresolved world-created problems.

    A captain's theory, assignment, or report cannot change physical state
    or close an obligation. Closure requires an authoritative world outcome.
    """
    ticket_id = models.CharField(max_length=32, primary_key=True)
    kind = models.CharField(max_length=32)
    source_ref = models.CharField(max_length=64)
    priority = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, default="open")
    captain_dbref = models.CharField(max_length=32)
    assignment = models.JSONField(default=dict)
    history = models.JSONField(default=list)
    due_game_time = models.FloatField()
    last_reminded_game_time = models.FloatField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["status", "due_game_time"],
                         name="ox_captain_due"),
        ]


class CharacterProfile(models.Model):
    """Authoritative, persistent person identity and formative baseline.

    The role, duty, agent checkpoint and person's self-assessment are not here.
    A checkpoint may describe a person, but it cannot authoritatively modify
    these scores or replace the character-to-person binding.
    """
    person_id = models.CharField(max_length=64, primary_key=True)
    character_dbref = models.CharField(max_length=32, unique=True)
    schema_version = models.PositiveSmallIntegerField(default=2)
    aptitudes = models.JSONField(default=dict)
    psychology = models.JSONField(default=dict)
    styles = models.JSONField(default=list)
    source = models.CharField(max_length=48, default="ox_initial_seed")


class CharacterSkill(models.Model):
    """One world-owned numerical competency per person and canonical skill ID.

    Progression and attempts have separate evidence records in a future slice.
    A mere blueprint skill estimate or AI claim never changes this row.
    """
    person = models.ForeignKey(
        CharacterProfile, on_delete=models.PROTECT, related_name="skill_records",
    )
    skill_id = models.CharField(max_length=64)
    proficiency = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=48, default="g3f_initial_estimate")
    first_recorded_game_time = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "skill_id"], name="ox_person_skill_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(proficiency__lte=100), name="ox_person_skill_range",
            ),
        ]
