"""Append-only inquiry transition history."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from common.models.base import TimestampedModel


def generate_status_history_code() -> str:
    """Generate a business-safe history code independent of the DB key."""

    return f"HST-{uuid.uuid4().hex.upper()}"


class TransitionHistory(TimestampedModel):
    """Auditable state transition produced by the workflow runtime."""

    class TargetType(models.TextChoices):
        QUESTIONNAIRE = "QUESTIONNAIRE", "Questionnaire"
        INQUIRY = "INQUIRY", "Inquiry"
        CONSULTATION = "CONSULTATION", "Consultation"
        VISIT = "VISIT", "Visit"

    class ChangedByType(models.TextChoices):
        USER = "USER", "User"
        SYSTEM = "SYSTEM", "System"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    status_history_code = models.CharField(
        max_length=60,
        unique=True,
        default=generate_status_history_code,
        editable=False,
    )
    target_type_code = models.CharField(
        max_length=40,
        choices=TargetType.choices,
        default=TargetType.INQUIRY,
    )
    questionnaire_session = models.ForeignKey(
        "questionnaires.QuestionnaireSession",
        on_delete=models.PROTECT,
        related_name="transition_history",
        db_column="questionnaire_session_id",
        null=True,
        blank=True,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="transition_history",
        db_column="inquiry_id",
        null=True,
        blank=True,
    )
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.PROTECT,
        related_name="transition_history",
        db_column="consultation_id",
        null=True,
        blank=True,
    )
    visit = models.ForeignKey(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="transition_history",
        db_column="visit_id",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflow_transitions",
        db_column="changed_by_id",
        null=True,
        blank=True,
    )
    changed_by_type_code = models.CharField(
        max_length=40,
        choices=ChangedByType.choices,
        default=ChangedByType.USER,
    )
    event_code = models.CharField(max_length=60)
    from_state = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_column="from_status_code",
    )
    to_state = models.CharField(
        max_length=40,
        db_column="to_status_code",
    )
    state_version = models.PositiveIntegerField()
    correlation_id = models.UUIDField()
    idempotency_key = models.CharField(max_length=128)
    change_reason = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "support_inquiry_status_history"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "state_version"],
                condition=Q(target_type_code="INQUIRY"),
                name="uq_status_history_inquiry_version",
            ),
            models.UniqueConstraint(
                fields=["consultation", "state_version"],
                condition=Q(target_type_code="CONSULTATION"),
                name="uq_status_history_consultation_version",
            ),
            models.UniqueConstraint(
                fields=["visit", "state_version"],
                condition=Q(target_type_code="VISIT"),
                name="uq_status_history_visit_version",
            ),
            models.UniqueConstraint(
                fields=[
                    "questionnaire_session",
                    "state_version",
                ],
                condition=Q(target_type_code="QUESTIONNAIRE"),
                name="uq_status_history_questionnaire_version",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_status_history_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        target_type_code="QUESTIONNAIRE",
                        questionnaire_session__isnull=False,
                        inquiry__isnull=True,
                        consultation__isnull=True,
                        visit__isnull=True,
                    )
                    | Q(
                        target_type_code="INQUIRY",
                        questionnaire_session__isnull=True,
                        inquiry__isnull=False,
                        consultation__isnull=True,
                        visit__isnull=True,
                    )
                    | Q(
                        target_type_code="CONSULTATION",
                        questionnaire_session__isnull=True,
                        inquiry__isnull=True,
                        consultation__isnull=False,
                        visit__isnull=True,
                    )
                    | Q(
                        target_type_code="VISIT",
                        questionnaire_session__isnull=True,
                        inquiry__isnull=True,
                        consultation__isnull=True,
                        visit__isnull=False,
                    )
                ),
                name="ck_status_history_target_type_matches_fk",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        questionnaire_session__isnull=False,
                        inquiry__isnull=True,
                        consultation__isnull=True,
                        visit__isnull=True,
                    )
                    | Q(
                        questionnaire_session__isnull=True,
                        inquiry__isnull=False,
                        consultation__isnull=True,
                        visit__isnull=True,
                    )
                    | Q(
                        questionnaire_session__isnull=True,
                        inquiry__isnull=True,
                        consultation__isnull=False,
                        visit__isnull=True,
                    )
                    | Q(
                        questionnaire_session__isnull=True,
                        inquiry__isnull=True,
                        consultation__isnull=True,
                        visit__isnull=False,
                    )
                ),
                name="ck_status_history_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        changed_by_type_code="USER",
                        actor__isnull=False,
                    )
                    | Q(
                        changed_by_type_code="SYSTEM",
                        actor__isnull=True,
                    )
                ),
                name="ck_status_history_changed_by",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state_version=1, from_state__isnull=True)
                    | Q(state_version__gt=1, from_state__isnull=False)
                ),
                name="ck_status_history_version_origin",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "target_type_code",
                    "event_code",
                    "-changed_at",
                ],
                name="ix_status_hist_target_event",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_status_hist_correlation",
            ),
            models.Index(
                fields=[
                    "questionnaire_session",
                    "event_code",
                    "idempotency_key",
                ],
                condition=Q(target_type_code="QUESTIONNAIRE"),
                name="ix_status_q_event_idem",
            ),
            models.Index(
                fields=["inquiry", "event_code", "idempotency_key"],
                condition=Q(target_type_code="INQUIRY"),
                name="ix_status_inq_event_idem",
            ),
            models.Index(
                fields=["consultation", "event_code", "idempotency_key"],
                condition=Q(target_type_code="CONSULTATION"),
                name="ix_status_cons_event_idem",
            ),
            models.Index(
                fields=["visit", "event_code", "idempotency_key"],
                condition=Q(target_type_code="VISIT"),
                name="ix_status_visit_event_idem",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.status_history_code} ({self.target_type_code})"
