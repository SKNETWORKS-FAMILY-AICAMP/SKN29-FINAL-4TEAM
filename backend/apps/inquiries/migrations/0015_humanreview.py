import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.common_codes.db_expressions


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inquiries", "0014_allow_approved_partial_stop_danger"),
    ]

    operations = [
        migrations.CreateModel(
            name="HumanReview",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("checkpoint_thread_id", models.CharField(max_length=100, unique=True)),
                ("source_ai_request_id", models.CharField(max_length=100)),
                ("source_inquiry_state_version", models.PositiveIntegerField()),
                (
                    "status_code",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("MODIFIED", "Modified"),
                            ("REJECTED", "Rejected"),
                            ("RESUME_FAILED", "Resume failed"),
                        ],
                        default="PENDING",
                        max_length=40,
                    ),
                ),
                (
                    "decision_code",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("APPROVE", "Approve"),
                            ("MODIFY", "Modify"),
                            ("REJECT", "Reject"),
                        ],
                        max_length=40,
                        null=True,
                    ),
                ),
                ("review_state_version", models.PositiveIntegerField(default=1)),
                ("initial_reason_code", models.CharField(max_length=80)),
                (
                    "decision_reason_code",
                    models.CharField(blank=True, max_length=80, null=True),
                ),
                (
                    "decided_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "decision_idempotency_key",
                    models.CharField(blank=True, max_length=128, null=True),
                ),
                (
                    "decision_correlation_id",
                    models.UUIDField(blank=True, null=True),
                ),
                (
                    "modified_guidance_payload",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "resume_failure_code",
                    models.CharField(blank=True, max_length=80, null=True),
                ),
                (
                    "guidance",
                    models.OneToOneField(
                        db_column="guidance_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="human_review",
                        to="inquiries.guidance",
                    ),
                ),
                (
                    "inquiry",
                    models.ForeignKey(
                        db_column="inquiry_id",
                        db_index=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="human_reviews",
                        to="inquiries.inquiry",
                    ),
                ),
                (
                    "published_guidance",
                    models.ForeignKey(
                        blank=True,
                        db_column="published_guidance_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="published_by_human_reviews",
                        to="inquiries.guidance",
                    ),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        db_column="reviewer_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="human_review_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "support_human_review",
            },
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status_code__in=[
                        "PENDING",
                        "APPROVED",
                        "MODIFIED",
                        "REJECTED",
                        "RESUME_FAILED",
                    ]
                ),
                name="ck_hreview_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(decision_code__isnull=True)
                    | models.Q(decision_code__in=["APPROVE", "MODIFY", "REJECT"])
                ),
                name="ck_hreview_decision",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(review_state_version__gt=0)
                    & models.Q(source_inquiry_state_version__gt=0)
                ),
                name="ck_hreview_versions",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(reviewer__isnull=True, decided_at__isnull=True)
                    | models.Q(reviewer__isnull=False, decided_at__isnull=False)
                ),
                name="ck_hreview_actor_time",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=apps.common_codes.db_expressions.IsJSONObject(
                    "modified_guidance_payload"
                ),
                name="ck_hreview_modified_object",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status_code="PENDING",
                        decision_code__isnull=True,
                        decision_reason_code__isnull=True,
                        reviewer__isnull=True,
                        decided_at__isnull=True,
                        decision_idempotency_key__isnull=True,
                        decision_correlation_id__isnull=True,
                    )
                    | models.Q(
                        status_code__in=[
                            "APPROVED",
                            "MODIFIED",
                            "REJECTED",
                            "RESUME_FAILED",
                        ],
                        decision_code__isnull=False,
                        decision_reason_code__isnull=False,
                        reviewer__isnull=False,
                        decided_at__isnull=False,
                        decision_idempotency_key__isnull=False,
                        decision_correlation_id__isnull=False,
                    )
                ),
                name="ck_hreview_decision_audit",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status_code="PENDING",
                        published_guidance__isnull=True,
                        resume_failure_code__isnull=True,
                        modified_guidance_payload={},
                    )
                    | models.Q(
                        status_code="APPROVED",
                        decision_code="APPROVE",
                        published_guidance__isnull=False,
                        resume_failure_code__isnull=True,
                        modified_guidance_payload={},
                    )
                    | models.Q(
                        status_code="MODIFIED",
                        decision_code="MODIFY",
                        published_guidance__isnull=False,
                        resume_failure_code__isnull=True,
                    )
                    & ~models.Q(modified_guidance_payload={})
                    | models.Q(
                        status_code="REJECTED",
                        decision_code="REJECT",
                        published_guidance__isnull=True,
                        resume_failure_code__isnull=True,
                        modified_guidance_payload={},
                    )
                    | (
                        models.Q(
                            status_code="RESUME_FAILED",
                            resume_failure_code__isnull=False,
                        )
                        & (
                            models.Q(
                                decision_code="APPROVE",
                                published_guidance__isnull=False,
                                modified_guidance_payload={},
                            )
                            | models.Q(
                                decision_code="MODIFY",
                                published_guidance__isnull=False,
                            )
                            & ~models.Q(modified_guidance_payload={})
                            | models.Q(
                                decision_code="REJECT",
                                published_guidance__isnull=True,
                                modified_guidance_payload={},
                            )
                        )
                    )
                ),
                name="ck_hreview_state_fields",
            ),
        ),
        migrations.AddIndex(
            model_name="humanreview",
            index=models.Index(
                condition=models.Q(status_code="PENDING"),
                fields=["status_code", "created_at"],
                name="ix_hreview_pending_created",
            ),
        ),
        migrations.AddIndex(
            model_name="humanreview",
            index=models.Index(
                fields=["inquiry", "-created_at"],
                name="ix_hreview_inquiry_created",
            ),
        ),
    ]
