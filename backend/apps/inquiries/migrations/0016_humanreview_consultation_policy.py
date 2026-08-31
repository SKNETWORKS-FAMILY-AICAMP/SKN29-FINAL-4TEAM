from django.db import migrations, models
from django.db.models import F, Q


def populate_consultation_audit(apps, schema_editor):
    HumanReview = apps.get_model("inquiries", "HumanReview")
    reviews = HumanReview.objects.select_related(
        "guidance",
        "published_guidance",
    )
    for review in reviews.iterator():
        original = bool(review.guidance.requires_consultation)
        review.original_requires_consultation = original
        review.consultation_origin_code = (
            "UNKNOWN_LOCKED" if original else "NOT_REQUIRED"
        )
        review.consultation_origin_reason_code = (
            "LEGACY_UNCLASSIFIED" if original else "NOT_REQUIRED"
        )
        review.consultation_evidence_snapshot = []
        if review.status_code == "PENDING":
            review.effective_requires_consultation = original
            review.consultation_disposition_code = None
            review.consultation_reason_code = None
        elif review.decision_code == "REJECT":
            review.effective_requires_consultation = True
            review.consultation_disposition_code = "REQUIRE"
            review.consultation_reason_code = "HUMAN_REVIEW_REJECTED"
        else:
            effective = (
                bool(review.published_guidance.requires_consultation)
                if review.published_guidance_id
                else original
            )
            if effective == original:
                review.effective_requires_consultation = original
                review.consultation_disposition_code = "PRESERVE"
                review.consultation_reason_code = None
            elif not original and effective:
                review.effective_requires_consultation = True
                review.consultation_disposition_code = "REQUIRE"
                review.consultation_reason_code = (
                    "CONSULTANT_SAFETY_ESCALATION"
                )
            else:
                # A legacy true -> false row has no durable non-Safety origin
                # or verified resolution Evidence. Preserve true so migration
                # cannot silently grant downgrade authority. The old published
                # Guidance then fails the customer audit gate until re-reviewed.
                review.effective_requires_consultation = True
                review.consultation_disposition_code = "PRESERVE"
                review.consultation_reason_code = None
        review.save(
            update_fields=[
                "original_requires_consultation",
                "effective_requires_consultation",
                "consultation_origin_code",
                "consultation_origin_reason_code",
                "consultation_disposition_code",
                "consultation_reason_code",
                "consultation_evidence_snapshot",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0015_humanreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="humanreview",
            name="original_requires_consultation",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="humanreview",
            name="effective_requires_consultation",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="humanreview",
            name="consultation_origin_code",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="humanreview",
            name="consultation_origin_reason_code",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name="humanreview",
            name="consultation_disposition_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PRESERVE", "Preserve"),
                    ("REQUIRE", "Require"),
                    ("RESOLVE_NON_SAFETY", "Resolve non-safety"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="humanreview",
            name="consultation_reason_code",
            field=models.CharField(
                blank=True,
                choices=[
                    (
                        "CONSULTANT_SAFETY_ESCALATION",
                        "Consultant safety escalation",
                    ),
                    (
                        "PRODUCT_FUNCTION_UNCERTAIN",
                        "Product function uncertain",
                    ),
                    (
                        "CUSTOMER_CONTEXT_INCOMPLETE",
                        "Customer context incomplete",
                    ),
                    (
                        "PRODUCT_CAPABILITY_VERIFIED",
                        "Product capability verified",
                    ),
                    ("HARNESS_SCOPE_VERIFIED", "Harness scope verified"),
                    ("HUMAN_REVIEW_REJECTED", "Human review rejected"),
                ],
                max_length=80,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="humanreview",
            name="consultation_evidence_snapshot",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            populate_consultation_audit,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="humanreview",
            name="original_requires_consultation",
            field=models.BooleanField(),
        ),
        migrations.AlterField(
            model_name="humanreview",
            name="effective_requires_consultation",
            field=models.BooleanField(),
        ),
        migrations.AlterField(
            model_name="humanreview",
            name="consultation_origin_code",
            field=models.CharField(
                choices=[
                    ("NOT_REQUIRED", "Not required"),
                    ("SAFETY_LOCKED", "Safety locked"),
                    ("FAIL_CLOSED_LOCKED", "Fail-closed locked"),
                    ("NON_SAFETY_RESOLVABLE", "Non-safety resolvable"),
                    ("UNKNOWN_LOCKED", "Unknown locked"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="humanreview",
            name="consultation_origin_reason_code",
            field=models.CharField(
                choices=[
                    ("NOT_REQUIRED", "Not required"),
                    ("DANGER_ASSESSMENT", "Danger assessment"),
                    ("EXPLICIT_SAFETY_RULE", "Explicit safety rule"),
                    ("FAIL_CLOSED_AI_RESULT", "Fail-closed AI result"),
                    (
                        "HARNESS_UNSUPPORTED_FUNCTION",
                        "Harness unsupported function",
                    ),
                    ("HARNESS_SCOPE_EXCEEDED", "Harness scope exceeded"),
                    ("UNCLASSIFIED_AI_SIGNAL", "Unclassified AI signal"),
                    ("LEGACY_UNCLASSIFIED", "Legacy unclassified"),
                ],
                max_length=80,
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=Q(
                    consultation_origin_code__in=[
                        "NOT_REQUIRED",
                        "SAFETY_LOCKED",
                        "FAIL_CLOSED_LOCKED",
                        "NON_SAFETY_RESOLVABLE",
                        "UNKNOWN_LOCKED",
                    ]
                ),
                name="ck_hreview_consult_origin",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    Q(consultation_disposition_code__isnull=True)
                    | Q(
                        consultation_disposition_code__in=[
                            "PRESERVE",
                            "REQUIRE",
                            "RESOLVE_NON_SAFETY",
                        ]
                    )
                ),
                name="ck_hreview_consult_disposition",
            ),
        ),
        migrations.AddConstraint(
            model_name="humanreview",
            constraint=models.CheckConstraint(
                condition=(
                    Q(
                        status_code="PENDING",
                        consultation_disposition_code__isnull=True,
                        consultation_reason_code__isnull=True,
                        consultation_evidence_snapshot=[],
                        effective_requires_consultation=F(
                            "original_requires_consultation"
                        ),
                    )
                    | Q(
                        status_code__in=[
                            "APPROVED",
                            "MODIFIED",
                            "REJECTED",
                            "RESUME_FAILED",
                        ],
                        consultation_disposition_code__isnull=False,
                    )
                ),
                name="ck_hreview_consult_audit",
            ),
        ),
    ]
