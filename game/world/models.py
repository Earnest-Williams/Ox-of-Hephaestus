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
    # Immutable recipient-prefix digest of this exact journal entry.
    # Populated by the one-time migration and every normal world writer.
    chain_hash = models.CharField(max_length=64, null=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["recipient_dbref", "sequence"],
                name="ox_event_recipient_seq",
            ),
        ]


class JournalEpoch(models.Model):
    """One durable world generation; rotated only by operator-only resets."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    generation = models.CharField(max_length=32)


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
            models.Index(fields=["kind", "state", "location_dbref"], name="ox_inventory_location"),
            models.Index(fields=["carrier_dbref", "state"], name="ox_inventory_carrier"),
        ]
        constraints = [
            models.CheckConstraint(
                name="ox_inventory_one_location",
                condition=(
                    models.Q(
                        state="stored", location_dbref__isnull=False, carrier_dbref__isnull=True
                    )
                    | models.Q(
                        state="carried", location_dbref__isnull=True, carrier_dbref__isnull=False
                    )
                    | models.Q(
                        state="consumed", location_dbref__isnull=True, carrier_dbref__isnull=True
                    )
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
            models.Index(fields=["assigned_dbref", "status"], name="ox_supply_assignee"),
            models.Index(fields=["requester_dbref", "status"], name="ox_supply_requester"),
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
            models.Index(fields=["status", "due_game_time"], name="ox_captain_due"),
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

    Progression has separate receipt-backed evidence records.
    A mere blueprint skill estimate or AI claim never changes this row.
    """

    person = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="skill_records",
    )
    skill_id = models.CharField(max_length=64)
    proficiency = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=48, default="g3f_initial_estimate")
    first_recorded_game_time = models.FloatField(default=0.0)
    practice_progress = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "skill_id"],
                name="ox_person_skill_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(proficiency__lte=100),
                name="ox_person_skill_range",
            ),
        ]


class CharacterKnowledge(models.Model):
    """A person's theoretical understanding, distinct from practical skill.

    Initial scores are authored calibration estimates, not a verified history
    of classroom attendance. Later updates require world-owned evidence.
    """

    person = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="knowledge_records",
    )
    foundation_id = models.CharField(max_length=64)
    mastery = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=48, default="g4e_initial_estimate")
    first_recorded_game_time = models.FloatField(default=0.0)
    study_progress = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "foundation_id"],
                name="ox_person_foundation_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(mastery__lte=100),
                name="ox_knowledge_mastery_range",
            ),
            models.CheckConstraint(
                condition=models.Q(study_progress__lte=999),
                name="ox_knowledge_study_range",
            ),
        ]


class CharacterTechnique(models.Model):
    """One person-specific procedure on a canonical equipment installation.

    The catalogue's technique ID binds a procedure to the exact equipment
    marker. Knowing a different model or task confers no automatic familiarity.
    """

    person = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="technique_records",
    )
    technique_id = models.CharField(max_length=96)
    familiarity = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=48, default="g4e_initial_estimate")
    first_recorded_game_time = models.FloatField(default=0.0)
    practice_progress = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "technique_id"],
                name="ox_person_technique_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(familiarity__lte=100),
                name="ox_technique_familiarity_range",
            ),
        ]


class CharacterLearningEvidence(models.Model):
    """Append-only provenance from exactly one verified world work receipt.

    Refused work and failed assessments cannot create learning credit. When evidence is
    applicable but repetition no longer teaches, credit_units may be zero so
    the underlying real attempt remains auditable.
    """

    person = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="learning_evidence",
    )
    receipt = models.ForeignKey(
        WorkReceipt,
        on_delete=models.PROTECT,
        related_name="learning_evidence",
    )
    event_key = models.CharField(max_length=128)
    task_id = models.CharField(max_length=96)
    component_kind = models.CharField(max_length=16)
    component_id = models.CharField(max_length=96)
    credit_units = models.PositiveSmallIntegerField(default=0)
    score_before = models.PositiveSmallIntegerField()
    score_after = models.PositiveSmallIntegerField()
    progress_before = models.PositiveSmallIntegerField(default=0)
    progress_after = models.PositiveSmallIntegerField(default=0)
    game_time = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "receipt", "component_kind", "component_id"],
                name="ox_learning_one_receipt_topic",
            ),
            models.UniqueConstraint(
                fields=["person", "event_key", "component_kind", "component_id"],
                name="ox_learning_one_event_topic",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_units__lte=1),
                name="ox_learning_credit_bounded",
            ),
            models.CheckConstraint(
                condition=models.Q(score_before__lte=100, score_after__lte=100),
                name="ox_learning_score_bounded",
            ),
            models.CheckConstraint(
                condition=models.Q(progress_before__lte=999, progress_after__lte=999),
                name="ox_learning_progress_bound",
            ),
        ]


class ConceptLesson(models.Model):
    """A supervised curriculum attempt, separate from beliefs and world faults.

    The exercise and its rubric belong to the world. Only a projection of the
    exercise is delivered to the learner; no current ship fault is an answer key.
    Lesson IDs are the offering instructor's global work request IDs.
    """

    lesson_id = models.CharField(max_length=32, primary_key=True)
    course_id = models.CharField(max_length=96)
    instructor = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="lessons_taught",
    )
    learner = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="lessons_taken",
    )
    room_dbref = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default="offered")
    offered_game_time = models.FloatField()
    started_game_time = models.FloatField(null=True)
    due_game_time = models.FloatField(null=True)
    expires_game_time = models.FloatField()
    completed_game_time = models.FloatField(null=True)
    qualification = models.JSONField(default=dict)
    exercise = models.JSONField(default=dict)
    answers = models.JSONField(default=dict)
    result_event_id = models.CharField(max_length=64, null=True)
    completion_receipt = models.OneToOneField(
        WorkReceipt,
        on_delete=models.PROTECT,
        null=True,
        related_name="concept_lesson",
    )

    class Meta:
        """Enforce distinct people and a finite, auditable lesson lifecycle."""

        constraints = [
            models.CheckConstraint(
                condition=~models.Q(instructor=models.F("learner")),
                name="ox_lesson_distinct_people",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["offered", "active", "passed", "failed", "interrupted"]
                ),
                name="ox_lesson_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["learner", "course_id", "completed_game_time"],
                name="ox_lesson_learner_course",
            ),
        ]


class InquiryLearningAttempt(models.Model):
    """One person's prediction and assessed reflection on their own real probe.

    This stores observed provenance and demonstrated investigative method,
    never the case's latent cause or a certificate of diagnostic correctness.
    """

    prediction_id = models.CharField(max_length=32, primary_key=True)
    person = models.ForeignKey(
        CharacterProfile,
        on_delete=models.PROTECT,
        related_name="inquiry_learning",
    )
    case = models.ForeignKey(
        InvestigationCase,
        on_delete=models.PROTECT,
        related_name="learning_attempts",
    )
    status = models.CharField(max_length=16, default="predicted")
    prediction = models.CharField(max_length=32)
    initial_report_event_id = models.CharField(max_length=64)
    inquiry_event_id = models.CharField(max_length=64)
    prediction_event_id = models.CharField(max_length=64)
    sample_event_id = models.CharField(max_length=64, null=True)
    report_event_id = models.CharField(max_length=64, null=True)
    result_event_id = models.CharField(max_length=64, null=True)
    reading = models.CharField(max_length=32, default="")
    tested_hypothesis = models.CharField(max_length=32, default="")
    created_game_time = models.FloatField()
    due_game_time = models.FloatField(null=True)
    expires_game_time = models.FloatField()
    completed_game_time = models.FloatField(null=True)
    exercise = models.JSONField(default=dict)
    answers = models.JSONField(default=dict)
    prediction_receipt = models.OneToOneField(
        WorkReceipt,
        on_delete=models.PROTECT,
        null=True,
        related_name="predicted_inquiry_learning",
    )
    report_receipt = models.ForeignKey(
        WorkReceipt,
        on_delete=models.PROTECT,
        null=True,
        related_name="reviewed_inquiry_learning",
    )
    completion_receipt = models.OneToOneField(
        WorkReceipt,
        on_delete=models.PROTECT,
        null=True,
        related_name="completed_inquiry_learning",
    )

    class Meta:
        """Keep one attempt per actual investigator/case and finite typed states."""

        constraints = [
            models.UniqueConstraint(fields=["person", "case"], name="ox_inquiry_person_case"),
            models.CheckConstraint(
                condition=models.Q(status__in=["predicted", "reviewing", "passed", "failed"]),
                name="ox_inquiry_learning_status",
            ),
            models.CheckConstraint(
                condition=models.Q(prediction__in=["supports", "does_not_support"]),
                name="ox_inquiry_prediction_valid",
            ),
        ]



class SocialAgreement(models.Model):
    """One world-owned bilateral, exactly-versioned agreement.

    Terms are public to the parties; private attraction, fear, and bargaining
    motivations never enter the authority table. Performance and consideration
    have *separate* receipt identities and do not follow from acceptance.
    """

    agreement_id = models.CharField(max_length=32, primary_key=True)
    pair_key = models.CharField(max_length=65)
    first_dbref = models.CharField(max_length=32)
    second_dbref = models.CharField(max_length=32)
    proposer_dbref = models.CharField(max_length=32)
    recipient_dbref = models.CharField(max_length=32)
    initiator_dbref = models.CharField(max_length=32)
    revision = models.PositiveSmallIntegerField(default=1)
    terms = models.JSONField(default=dict)
    state = models.CharField(max_length=16, default='pending')
    opened_at = models.FloatField()
    expires_at = models.FloatField()
    accepted_at = models.FloatField(null=True)
    consideration_id = models.CharField(max_length=32, null=True)
    performance_id = models.CharField(max_length=32, null=True)
    breached = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['first_dbref', 'state'], name='ox_social_first_state'),
            models.Index(fields=['second_dbref', 'state'], name='ox_social_second_state'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['pair_key'], condition=models.Q(state='pending'),
                name='ox_social_one_pending_pair',
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=[
                    'pending', 'accepted', 'declined', 'deferred', 'withdrawn', 'expired'
                ]), name='ox_social_state_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=1, revision__lte=100),
                name='ox_social_revision_range',
            ),
            models.CheckConstraint(
                condition=~models.Q(first_dbref=models.F('second_dbref')),
                name='ox_social_distinct_people',
            ),
        ]


class SocialAgreementEvent(models.Model):
    """Append-only public agreement history; all versions remain inspectable."""

    sequence = models.BigAutoField(primary_key=True)
    agreement = models.ForeignKey(
        SocialAgreement, on_delete=models.PROTECT, related_name='events',
    )
    request_id = models.CharField(max_length=32, unique=True)
    actor_dbref = models.CharField(max_length=32)
    kind = models.CharField(max_length=32)
    revision = models.PositiveSmallIntegerField()
    terms = models.JSONField(default=dict)
    state = models.CharField(max_length=16)
    game_time = models.FloatField()

    class Meta:
        indexes = [models.Index(
            fields=['agreement', 'sequence'], name='ox_social_events_order',
        )]


class SocialEvidence(models.Model):
    """A successful existing world receipt consumed at most once, for one side."""

    # Match the explicit BigAutoField already created by migration 0013.
    id = models.BigAutoField(primary_key=True)
    agreement = models.ForeignKey(
        SocialAgreement, on_delete=models.PROTECT, related_name='evidence',
    )
    side = models.CharField(max_length=16)
    receipt = models.OneToOneField(
        WorkReceipt, on_delete=models.PROTECT, related_name='social_fulfillment',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['agreement', 'side'], name='ox_social_one_evidence_side',
            ),
            models.CheckConstraint(
                condition=models.Q(side__in=['activity', 'consideration']),
                name='ox_social_evidence_side',
            ),
        ]