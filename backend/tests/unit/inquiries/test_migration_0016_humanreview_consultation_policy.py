"""Forward migration proof for fail-closed HumanReview consultation audit."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
import pytest

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Guidance, Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


OLD_TARGET = [("inquiries", "0015_humanreview")]
NEW_TARGET = [("inquiries", "0016_humanreview_consultation_policy")]


def _guidance(
    inquiry: Inquiry,
    *,
    version: int,
    requires_consultation: bool,
) -> Guidance:
    return Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=version,
        review_status_code="APPROVED",
        title=f"Migration guidance {version}",
        summary_text=f"Migration guidance summary {version}",
        evidence_sufficiency_code="VERIFIED",
        requires_consultation=requires_consultation,
    )


@pytest.mark.django_db(transaction=True)
def test_0016_backfill_never_silently_accepts_legacy_true_to_false(request):
    request.addfinalizer(
        lambda: MigrationExecutor(connection).migrate(NEW_TARGET)
    )
    reviewer = User.objects.create_user(
        username="HREVIEW-0016-MIGRATION-REVIEWER",
        full_name="HumanReview migration reviewer",
        role_code=User.Role.CONSULTANT,
        employee_no="HREVIEW-0016",
        is_synthetic=True,
    )
    customer_user = User.objects.create_user(
        username="HREVIEW-0016-MIGRATION-CUSTOMER",
        full_name="HumanReview migration customer",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no="HREVIEW-0016-MIGRATION-CUSTOMER",
        customer_name="HumanReview migration customer",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code="HREVIEW-0016-MIGRATION-MODEL",
        model_name="HumanReview migration model",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="HREVIEW-0016-MIGRATION-CONTRACT",
        customer=customer,
        product_model=product,
        serial_no="HREVIEW-0016-MIGRATION-SERIAL",
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        inquiry_code="HREVIEW-0016-MIGRATION-INQUIRY",
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="HumanReview migration synthetic symptom",
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=4,
    )
    preserve_source = _guidance(
        inquiry,
        version=1,
        requires_consultation=False,
    )
    preserve_published = _guidance(
        inquiry,
        version=2,
        requires_consultation=False,
    )
    escalate_source = _guidance(
        inquiry,
        version=3,
        requires_consultation=False,
    )
    escalate_published = _guidance(
        inquiry,
        version=4,
        requires_consultation=True,
    )
    legacy_downgrade_source = _guidance(
        inquiry,
        version=5,
        requires_consultation=True,
    )
    legacy_downgrade_published = _guidance(
        inquiry,
        version=6,
        requires_consultation=False,
    )

    executor = MigrationExecutor(connection)
    executor.migrate(OLD_TARGET)
    old_apps = executor.loader.project_state(OLD_TARGET).apps
    OldHumanReview = old_apps.get_model("inquiries", "HumanReview")
    common = {
        "inquiry_id": inquiry.pk,
        "source_inquiry_state_version": 4,
        "status_code": "APPROVED",
        "decision_code": "APPROVE",
        "review_state_version": 2,
        "initial_reason_code": "CAUTION_PRE_SEND_REVIEW",
        "decision_reason_code": "APPROVED_AS_IS",
        "reviewer_id": reviewer.pk,
        "decided_at": timezone.now(),
        "decision_correlation_id": uuid4(),
        "modified_guidance_payload": {},
    }
    rows = []
    for sequence, source, published in (
        (1, preserve_source, preserve_published),
        (2, escalate_source, escalate_published),
        (3, legacy_downgrade_source, legacy_downgrade_published),
    ):
        rows.append(
            OldHumanReview.objects.create(
                **common,
                guidance_id=source.pk,
                published_guidance_id=published.pk,
                checkpoint_thread_id=f"migration-thread-{sequence}",
                source_ai_request_id=f"migration-ai-request-{sequence}",
                decision_idempotency_key=f"migration-idempotency-{sequence}",
            )
        )

    executor = MigrationExecutor(connection)
    executor.migrate(NEW_TARGET)
    new_apps = executor.loader.project_state(NEW_TARGET).apps
    NewHumanReview = new_apps.get_model("inquiries", "HumanReview")
    migrated = [NewHumanReview.objects.get(pk=row.pk) for row in rows]

    assert (
        migrated[0].original_requires_consultation,
        migrated[0].effective_requires_consultation,
        migrated[0].consultation_disposition_code,
    ) == (False, False, "PRESERVE")
    assert (
        migrated[1].original_requires_consultation,
        migrated[1].effective_requires_consultation,
        migrated[1].consultation_disposition_code,
        migrated[1].consultation_reason_code,
    ) == (False, True, "REQUIRE", "CONSULTANT_SAFETY_ESCALATION")
    assert (
        migrated[2].original_requires_consultation,
        migrated[2].effective_requires_consultation,
        migrated[2].consultation_origin_code,
        migrated[2].consultation_disposition_code,
        migrated[2].consultation_reason_code,
    ) == (True, True, "UNKNOWN_LOCKED", "PRESERVE", None)
