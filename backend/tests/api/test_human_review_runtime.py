"""Backend HumanReview ledger, permission, version, and replay tests."""

from __future__ import annotations

import hashlib
from datetime import date
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.evidence.models import EvidenceLink
from apps.inquiries.models import Guidance, GuidanceItem, HumanReview, Inquiry
from apps.inquiries.repositories.human_review_repository import (
    HumanReviewRepository,
)
from apps.inquiries.services.human_review_service import HumanReviewService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord
from tests.unit.evidence.test_document_chunk_model import create_chunk
from tests.unit.evidence.test_evidence_link_model import link_values


pytestmark = pytest.mark.django_db
LIST_PATH = "/api/v1/inquiries/human-reviews"


def create_user(sequence: int, *, role: str, synthetic: bool = True) -> User:
    user = User.objects.create_user(
        username=f"HREVIEW-{role}-{sequence:03d}",
        password=None,
        full_name=f"Human Review {role} {sequence}",
        role_code=role,
        employee_no=(
            None if role == User.Role.CUSTOMER else f"HR-EMP-{sequence:03d}"
        ),
        is_active=True,
        is_synthetic=synthetic,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"HR-CUSTOMER-{sequence:03d}",
            customer_name=f"비노출 고객 {sequence}",
            phone=f"010-8000-{sequence:04d}",
            address_line1="HumanReview 응답에 노출하면 안 되는 주소",
            is_synthetic=True,
        )
    return user


def create_review(
    sequence: int,
    *,
    assigned_consultant: User | None = None,
    owner_synthetic: bool = True,
    requires_consultation: bool = False,
    matched_safety_rule_ids: list[str] | None = None,
    evidence_verified: bool = True,
) -> tuple[Inquiry, Guidance, HumanReview]:
    owner = create_user(
        sequence,
        role=User.Role.CUSTOMER,
        synthetic=owner_synthetic,
    )
    product = ProductModel.objects.create(
        model_code=f"HREVIEW-MODEL-{sequence:03d}",
        model_name=f"HumanReview 제품 {sequence}",
        features={"private_feature": "must-not-leak"},
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"HREVIEW-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"HREVIEW-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
        installation_address="HumanReview 비노출 설치 주소",
    )
    inquiry = Inquiry.objects.create(
        inquiry_code=f"HREVIEW-INQ-{sequence:03d}",
        subscription=subscription,
        initiated_by=owner,
        assigned_user=assigned_consultant,
        assigned_role_code=(
            Inquiry.AssignedRole.CONSULTANT
            if assigned_consultant
            else Inquiry.AssignedRole.NONE
        ),
        channel_code=Inquiry.Channel.MOBILE,
        raw_text=f"고객 원문 비노출 secret-{sequence}",
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=4,
    )
    now = timezone.now()
    payload = {
        "safety_assessment": {
            "risk_level": "caution",
            "requires_consultation": requires_consultation,
            "matched_safety_rule_ids": matched_safety_rule_ids or [],
        },
        "usage_guidance": {
            "guidance_status": "PARTIAL_STOP",
            "message": "안전한 합성 안내 초안",
            "restricted_functions": ["검토 대상 기능"],
            "next_actions": ["제품 상태를 안전하게 확인해 주세요."],
        },
        "evidence_references": [],
    }
    run = AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.ANALYZE_SYMPTOM,
        request_schema_version="3.0.0",
        response_schema_version="3.0.0",
        model_provider="local",
        model_name="human-review-test",
        model_config_version="3.0.0",
        model_config={"mode": "local"},
        prompt_version="human-review-test-v1",
        input_payload={"inquiry_id": str(inquiry.public_id)},
        input_sha256=hashlib.sha256(
            f"{inquiry.public_id}:{sequence}".encode("utf-8")
        ).hexdigest(),
        idempotency_key=f"human-review-ai-{sequence:03d}",
        correlation_id=uuid4(),
        validated_output_payload=payload,
        schema_validation_status_code=(
            AIRun.SchemaValidationStatus.PASSED
        ),
        schema_validation_errors=[],
        status_code=AIRun.Status.SUCCEEDED,
        started_at=now,
        completed_at=now,
    )
    guidance = Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=1,
        review_status_code="PENDING",
        title="검토 대기 안내",
        summary_text="안전한 합성 안내 초안",
        safety_notice="상담사 확인이 필요합니다.",
        evidence_sufficiency_code="VERIFIED",
        requires_consultation=requires_consultation,
        generated_by_ai_run=run,
    )
    GuidanceItem.objects.create(
        guidance=guidance,
        step_no=1,
        action_type_code="NEXT_ACTION",
        instruction_text="제품 상태를 안전하게 확인해 주세요.",
        requires_confirmation=True,
    )
    verifier = assigned_consultant or create_user(
        sequence + 1000,
        role=User.Role.OPERATOR,
    )
    chunk = create_chunk(sequence + 2000)
    EvidenceLink.objects.create(
        **link_values(
            sequence,
            inquiry=inquiry,
            chunk=chunk,
            target=guidance,
            ai_run=run,
            is_verified=evidence_verified,
            verified_by=verifier if evidence_verified else None,
            verified_at=now if evidence_verified else None,
        )
    )
    review = HumanReviewService.create_pending(
        guidance=guidance,
        ai_request_id=f"hr-ai-request-{sequence:03d}",
        source_inquiry_state_version=inquiry.state_version,
    )
    return inquiry, guidance, review


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def decide(
    *,
    actor: User,
    review: HumanReview,
    body: dict | None = None,
    key: str = "human-review-decision-key",
):
    return client_for(actor).post(
        f"{LIST_PATH}/{review.public_id}/decision",
        body
        or {
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )


def test_list_and_detail_apply_visibility_and_minimal_projection():
    consultant = create_user(1, role=User.Role.CONSULTANT)
    other = create_user(2, role=User.Role.CONSULTANT)
    visible_inquiry, _guidance, visible = create_review(10)
    create_review(11, assigned_consultant=other)
    create_review(12, owner_synthetic=False)

    listed = client_for(consultant).get(LIST_PATH)
    detailed = client_for(consultant).get(
        f"{LIST_PATH}/{visible.public_id}"
    )

    assert listed.status_code == detailed.status_code == 200
    assert [item["review_id"] for item in listed.json()["data"]["items"]] == [
        str(visible.public_id)
    ]
    data = detailed.json()["data"]
    assert data["status"] == HumanReview.Status.PENDING
    assert data["allowed_actions"] == ["DECIDE_HUMAN_REVIEW"]
    serialized = str(data)
    for private_value in (
        visible_inquiry.raw_text,
        visible_inquiry.subscription.contract_no,
        visible_inquiry.subscription.serial_no,
        visible_inquiry.subscription.installation_address,
        visible_inquiry.initiated_by.customer_profile.phone,
        "private_feature",
    ):
        assert private_value not in serialized


def test_approve_is_atomic_replayable_and_publishes_ai_guidance():
    consultant = create_user(20, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        20,
        assigned_consultant=consultant,
    )
    key = "human-review-approve-020"

    created = decide(actor=consultant, review=review, key=key)
    replayed = decide(actor=consultant, review=review, key=key)
    conflicted = decide(
        actor=consultant,
        review=review,
        key=key,
        body={
            "decision": HumanReview.Decision.REJECT,
            "review_state_version": 1,
            "reason_code": "INSUFFICIENT_EVIDENCE",
        },
    )

    assert created.status_code == replayed.status_code == 200
    assert created.json()["data"]["idempotent_replay"] is False
    assert replayed.json()["data"]["idempotent_replay"] is True
    assert conflicted.status_code == 409
    assert conflicted.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    review.refresh_from_db()
    guidance.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.status_code == HumanReview.Status.APPROVED
    assert review.review_state_version == 2
    assert review.published_guidance == guidance
    assert guidance.review_status_code == "APPROVED"
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 5
    assert review.original_requires_consultation is False
    assert review.effective_requires_consultation is False
    assert review.consultation_disposition_code == (
        HumanReview.ConsultationDisposition.PRESERVE
    )
    assert IdempotencyRecord.objects.filter(
        operation_id="decideHumanReview",
        idempotency_key=key,
    ).count() == 1


def test_modify_creates_a_new_public_guidance_and_preserves_the_ai_draft():
    consultant = create_user(30, role=User.Role.CONSULTANT)
    inquiry, original, review = create_review(
        30,
        assigned_consultant=consultant,
    )
    response = decide(
        actor=consultant,
        review=review,
        key="human-review-modify-030",
        body={
            "decision": HumanReview.Decision.MODIFY,
            "review_state_version": 1,
            "reason_code": "SAFETY_TEXT_CORRECTED",
            "modified_guidance": {
                "title": "상담사가 확인한 안내",
                "summary_text": "온수 기능 사용을 중단하고 상담을 기다려 주세요.",
                "safety_notice": "제품을 직접 분해하지 마세요.",
                "items": [
                    {
                        "instruction_text": "온수 버튼을 사용하지 마세요.",
                        "requires_confirmation": True,
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    review.refresh_from_db()
    original.refresh_from_db()
    assert review.status_code == HumanReview.Status.MODIFIED
    assert original.review_status_code == "REJECTED"
    assert review.published_guidance.guidance_version == 2
    assert review.published_guidance.review_status_code == "APPROVED"
    assert review.published_guidance.items.get().instruction_text == (
        "온수 버튼을 사용하지 마세요."
    )
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 5
    assert review.published_guidance.evidence_links.count() == 1
    assert Guidance.objects.filter(inquiry=review.inquiry).count() == 2


def test_approved_guidance_with_original_consultation_true_creates_queue():
    consultant = create_user(34, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        34,
        assigned_consultant=consultant,
        requires_consultation=True,
    )

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-preserve-consultation-034",
    )

    assert response.status_code == 200
    review.refresh_from_db()
    guidance.refresh_from_db()
    inquiry.refresh_from_db()
    assert guidance.review_status_code == "APPROVED"
    assert review.published_guidance == guidance
    assert review.effective_requires_consultation is True
    assert review.consultation_disposition_code == (
        HumanReview.ConsultationDisposition.PRESERVE
    )
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 5
    assert Consultation.objects.filter(
        inquiry=inquiry,
        status=Consultation.Status.WAITING,
    ).count() == 1


def test_consultant_can_raise_false_to_true_with_bounded_reason():
    consultant = create_user(35, role=User.Role.CONSULTANT)
    inquiry, original, review = create_review(
        35,
        assigned_consultant=consultant,
    )

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-require-consultation-035",
        body={
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.REQUIRE
            ),
            "consultation_reason_code": (
                HumanReview.ConsultationChangeReason.PRODUCT_FUNCTION_UNCERTAIN
            ),
        },
    )

    assert response.status_code == 200
    review.refresh_from_db()
    original.refresh_from_db()
    inquiry.refresh_from_db()
    assert original.requires_consultation is False
    assert original.review_status_code == "REJECTED"
    assert review.published_guidance.requires_consultation is True
    assert review.published_guidance.evidence_links.count() == 1
    assert review.original_requires_consultation is False
    assert review.effective_requires_consultation is True
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1


def test_persisted_non_safety_true_can_be_resolved_with_evidence_and_reason():
    consultant = create_user(36, role=User.Role.CONSULTANT)
    inquiry, original, review = create_review(
        36,
        assigned_consultant=consultant,
        requires_consultation=True,
    )
    # Simulate a future Backend-owned durable Harness classification ledger.
    # create_pending deliberately cannot accept a caller-supplied reason.
    HumanReview.objects.filter(pk=review.pk).update(
        consultation_origin_code=(
            HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
        ),
        consultation_origin_reason_code=(
            HumanReview.ConsultationOriginReason.HARNESS_UNSUPPORTED_FUNCTION
        ),
    )
    review.refresh_from_db()
    evidence_id = original.evidence_links.get().public_id

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-resolve-consultation-036",
        body={
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
            ),
            "consultation_reason_code": (
                HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED
            ),
            "consultation_evidence_ids": [str(evidence_id)],
        },
    )

    assert response.status_code == 200
    review.refresh_from_db()
    original.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.consultation_origin_code == (
        HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
    )
    assert original.requires_consultation is True
    assert original.review_status_code == "REJECTED"
    assert review.published_guidance.requires_consultation is False
    assert review.effective_requires_consultation is False
    assert review.consultation_evidence_snapshot == [
        {
            "evidence_link_id": str(evidence_id),
            "chunk_id": str(original.evidence_links.get().chunk.public_id),
            "document_sha256": (
                original.evidence_links.get().document_sha256_snapshot
            ),
        }
    ]
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert not Consultation.objects.filter(inquiry=inquiry).exists()


def test_safety_locked_true_cannot_be_resolved_by_consultant():
    consultant = create_user(37, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        37,
        assigned_consultant=consultant,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-LEAK-001"],
    )
    evidence_id = guidance.evidence_links.get().public_id

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-locked-consultation-037",
        body={
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
            ),
            "consultation_reason_code": (
                HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED
            ),
            "consultation_evidence_ids": [str(evidence_id)],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "HUMAN_REVIEW_CONSULTATION_LOCKED"
    )
    review.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.status_code == HumanReview.Status.PENDING
    assert review.consultation_origin_code == (
        HumanReview.ConsultationOrigin.SAFETY_LOCKED
    )
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert not IdempotencyRecord.objects.filter(
        idempotency_key="human-review-locked-consultation-037"
    ).exists()


def test_unclassified_true_is_locked_without_durable_backend_origin():
    consultant = create_user(136, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        136,
        assigned_consultant=consultant,
        requires_consultation=True,
    )
    evidence_id = guidance.evidence_links.get().public_id

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-unclassified-consultation-136",
        body={
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
            ),
            "consultation_reason_code": (
                HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED
            ),
            "consultation_evidence_ids": [str(evidence_id)],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "HUMAN_REVIEW_CONSULTATION_LOCKED"
    )
    review.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.consultation_origin_code == (
        HumanReview.ConsultationOrigin.UNKNOWN_LOCKED
    )
    assert review.status_code == HumanReview.Status.PENDING
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS


def test_fail_closed_ai_result_cannot_be_resolved_by_consultant():
    consultant = create_user(141, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        141,
        assigned_consultant=consultant,
        requires_consultation=True,
        evidence_verified=False,
    )
    evidence_id = guidance.evidence_links.get().public_id

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-fail-closed-consultation-141",
        body={
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
            ),
            "consultation_reason_code": (
                HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED
            ),
            "consultation_evidence_ids": [str(evidence_id)],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "HUMAN_REVIEW_CONSULTATION_LOCKED"
    )
    review.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.consultation_origin_code == (
        HumanReview.ConsultationOrigin.FAIL_CLOSED_LOCKED
    )
    assert review.status_code == HumanReview.Status.PENDING
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS


def test_human_review_rejects_unverified_evidence_without_writes():
    consultant = create_user(137, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        137,
        assigned_consultant=consultant,
    )
    guidance.evidence_links.update(
        is_verified=False,
        verified_by=None,
        verified_at=None,
    )

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-unverified-evidence-137",
    )

    assert response.status_code == 409
    review.refresh_from_db()
    guidance.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.status_code == HumanReview.Status.PENDING
    assert guidance.review_status_code == "PENDING"
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert not IdempotencyRecord.objects.filter(
        idempotency_key="human-review-unverified-evidence-137"
    ).exists()


def test_non_safety_resolution_rejects_foreign_evidence_without_writes():
    consultant = create_user(138, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        138,
        assigned_consultant=consultant,
        requires_consultation=True,
    )
    _other_inquiry, other_guidance, _other_review = create_review(139)
    foreign_evidence_id = other_guidance.evidence_links.get().public_id
    HumanReview.objects.filter(pk=review.pk).update(
        consultation_origin_code=(
            HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
        ),
        consultation_origin_reason_code=(
            HumanReview.ConsultationOriginReason.HARNESS_SCOPE_EXCEEDED
        ),
    )
    review.refresh_from_db()

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-foreign-evidence-138",
        body={
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
            ),
            "consultation_reason_code": (
                HumanReview.ConsultationChangeReason.HARNESS_SCOPE_VERIFIED
            ),
            "consultation_evidence_ids": [str(foreign_evidence_id)],
        },
    )

    assert response.status_code == 422
    review.refresh_from_db()
    guidance.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.status_code == HumanReview.Status.PENDING
    assert guidance.review_status_code == "PENDING"
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS


def test_consultation_creation_failure_rolls_back_review_and_guidance(monkeypatch):
    consultant = create_user(140, role=User.Role.CONSULTANT)
    inquiry, guidance, review = create_review(
        140,
        assigned_consultant=consultant,
        requires_consultation=True,
    )

    def fail_consultation_request(*args, **kwargs):
        raise RuntimeError("synthetic consultation persistence failure")

    monkeypatch.setattr(
        "apps.inquiries.services.human_review_service."
        "ConsultationRepository.request",
        fail_consultation_request,
    )

    with pytest.raises(RuntimeError, match="synthetic consultation"):
        HumanReviewService.decide(
            actor=consultant,
            review_public_id=review.public_id,
            validated_data={
                "decision": HumanReview.Decision.APPROVE,
                "review_state_version": 1,
                "consultation_disposition": (
                    HumanReview.ConsultationDisposition.PRESERVE
                ),
            },
            idempotency_key="human-review-rollback-140",
            correlation_id=uuid4(),
        )

    review.refresh_from_db()
    guidance.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.status_code == HumanReview.Status.PENDING
    assert review.published_guidance is None
    assert guidance.review_status_code == "PENDING"
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 4
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert not IdempotencyRecord.objects.filter(
        idempotency_key="human-review-rollback-140"
    ).exists()


@pytest.mark.parametrize(
    ("sequence", "summary_text", "instruction_text"),
    (
        (31, "가" * 3001, "안전한 확인 조치"),
        (32, "안전한 합성 안내", "나" * 1001),
    ),
)
def test_modify_rejects_text_beyond_customer_guidance_contract_without_writes(
    sequence,
    summary_text,
    instruction_text,
):
    consultant = create_user(sequence, role=User.Role.CONSULTANT)
    _inquiry, original, review = create_review(
        sequence,
        assigned_consultant=consultant,
    )
    key = f"human-review-public-limit-{sequence:03d}"

    response = decide(
        actor=consultant,
        review=review,
        key=key,
        body={
            "decision": HumanReview.Decision.MODIFY,
            "review_state_version": 1,
            "reason_code": "SAFETY_TEXT_CORRECTED",
            "modified_guidance": {
                "title": "상담사가 확인한 안내",
                "summary_text": summary_text,
                "safety_notice": "제품을 직접 분해하지 마세요.",
                "items": [
                    {
                        "instruction_text": instruction_text,
                        "requires_confirmation": True,
                    }
                ],
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    review.refresh_from_db()
    original.refresh_from_db()
    assert review.status_code == HumanReview.Status.PENDING
    assert review.review_state_version == 1
    assert review.published_guidance is None
    assert original.review_status_code == "PENDING"
    assert Guidance.objects.filter(inquiry=review.inquiry).count() == 1
    assert not IdempotencyRecord.objects.filter(idempotency_key=key).exists()


def test_modify_accepts_exact_customer_guidance_contract_limits():
    consultant = create_user(33, role=User.Role.CONSULTANT)
    _inquiry, _original, review = create_review(
        33,
        assigned_consultant=consultant,
    )

    response = decide(
        actor=consultant,
        review=review,
        key="human-review-public-limit-033",
        body={
            "decision": HumanReview.Decision.MODIFY,
            "review_state_version": 1,
            "reason_code": "SAFETY_TEXT_CORRECTED",
            "modified_guidance": {
                "title": "상담사가 확인한 안내",
                "summary_text": "가" * 3000,
                "safety_notice": "제품을 직접 분해하지 마세요.",
                "items": [
                    {
                        "instruction_text": "나" * 1000,
                        "requires_confirmation": True,
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    review.refresh_from_db()
    assert review.status_code == HumanReview.Status.MODIFIED
    assert len(review.published_guidance.summary_text) == 3000
    assert len(review.published_guidance.items.get().instruction_text) == 1000


def test_reject_hides_guidance_and_stale_version_writes_nothing():
    consultant = create_user(40, role=User.Role.CONSULTANT)
    inquiry, guidance, stale_review = create_review(
        40,
        assigned_consultant=consultant,
    )
    stale = decide(
        actor=consultant,
        review=stale_review,
        key="human-review-stale-040",
        body={
            "decision": HumanReview.Decision.REJECT,
            "review_state_version": 2,
            "reason_code": "INSUFFICIENT_EVIDENCE",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["details"] == {
        "current_status": HumanReview.Status.PENDING,
        "current_review_state_version": 1,
        "allowed_actions": ["DECIDE_HUMAN_REVIEW"],
    }
    assert not IdempotencyRecord.objects.filter(
        idempotency_key="human-review-stale-040"
    ).exists()

    rejected = decide(
        actor=consultant,
        review=stale_review,
        key="human-review-reject-040",
        body={
            "decision": HumanReview.Decision.REJECT,
            "review_state_version": 1,
            "reason_code": "INSUFFICIENT_EVIDENCE",
        },
    )
    assert rejected.status_code == 200
    stale_review.refresh_from_db()
    guidance.refresh_from_db()
    assert stale_review.status_code == HumanReview.Status.REJECTED
    assert stale_review.published_guidance is None
    assert guidance.review_status_code == "REJECTED"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 5
    assert stale_review.effective_requires_consultation is True
    assert stale_review.consultation_reason_code == (
        HumanReview.ConsultationChangeReason.HUMAN_REVIEW_REJECTED
    )
    assert Consultation.objects.filter(
        inquiry=inquiry,
        status=Consultation.Status.WAITING,
    ).count() == 1


def test_two_consultants_on_unassigned_review_produce_one_decision():
    first = create_user(50, role=User.Role.CONSULTANT)
    second = create_user(51, role=User.Role.CONSULTANT)
    _inquiry, guidance, review = create_review(50)

    winner = decide(
        actor=first,
        review=review,
        key="human-review-winner-050",
    )
    loser = decide(
        actor=second,
        review=review,
        key="human-review-loser-050",
    )

    assert winner.status_code == 200
    assert loser.status_code == 409
    assert loser.json()["error"]["code"] == "STATE-CONFLICT-01"
    review.refresh_from_db()
    guidance.refresh_from_db()
    assert review.reviewer == first
    assert review.review_state_version == 2
    assert guidance.review_status_code == "APPROVED"
    assert IdempotencyRecord.objects.filter(
        operation_id="decideHumanReview"
    ).count() == 1


def test_decision_lock_targets_only_the_human_review_ledger_row():
    consultant = create_user(55, role=User.Role.CONSULTANT)

    queryset = HumanReviewRepository._lock_visible_queryset(consultant)

    assert queryset.query.select_for_update is True
    assert queryset.query.select_for_update_of == ("self",)


def test_role_headers_payload_and_assigned_other_are_fail_closed():
    consultant = create_user(60, role=User.Role.CONSULTANT)
    other = create_user(61, role=User.Role.CONSULTANT)
    customer = create_user(62, role=User.Role.CUSTOMER)
    _inquiry, _guidance, review = create_review(
        60,
        assigned_consultant=other,
    )
    path = f"{LIST_PATH}/{review.public_id}/decision"

    assert APIClient().get(LIST_PATH).status_code == 401
    assert client_for(customer).get(LIST_PATH).status_code == 403
    assert client_for(consultant).get(
        f"{LIST_PATH}/{review.public_id}"
    ).status_code == 404
    missing_headers = client_for(other).post(
        path,
        {
            "decision": HumanReview.Decision.APPROVE,
            "review_state_version": 1,
        },
        format="json",
    )
    assert missing_headers.status_code == 422
    invalid_modify = decide(
        actor=other,
        review=review,
        key="human-review-invalid-060",
        body={
            "decision": HumanReview.Decision.MODIFY,
            "review_state_version": 1,
        },
    )
    assert invalid_modify.status_code == 422
    assert review.status_code == HumanReview.Status.PENDING


def test_resume_failure_stores_only_bounded_code():
    consultant = create_user(70, role=User.Role.CONSULTANT)
    _inquiry, _guidance, review = create_review(
        70,
        assigned_consultant=consultant,
    )
    assert decide(
        actor=consultant,
        review=review,
        key="human-review-resume-070",
    ).status_code == 200

    HumanReviewService.mark_resume_failed(
        review_public_id=review.public_id,
        failure_code="AI_RESUME_TIMEOUT",
    )

    review.refresh_from_db()
    assert review.status_code == HumanReview.Status.RESUME_FAILED
    assert review.resume_failure_code == "AI_RESUME_TIMEOUT"
    assert review.review_state_version == 3
    detail = client_for(consultant).get(f"{LIST_PATH}/{review.public_id}")
    assert detail.status_code == 200
    assert "AI_RESUME_TIMEOUT" not in detail.content.decode()


def test_database_constraint_rejects_status_without_decision_audit():
    _inquiry, _guidance, review = create_review(80)

    with pytest.raises(IntegrityError), transaction.atomic():
        HumanReview.objects.filter(pk=review.pk).update(
            status_code=HumanReview.Status.APPROVED,
        )

    review.refresh_from_db()
    assert review.status_code == HumanReview.Status.PENDING
