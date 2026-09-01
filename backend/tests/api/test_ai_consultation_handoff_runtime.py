"""Backend API and PostgreSQL evidence for AI consultation handoff storage."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.api.handoff_serializers import (
    ConsultationHandoffRequestSerializer,
)
from apps.consultations.models import Consultation, ConsultationHandoff
from apps.consultations.repositories import ConsultationHandoffRepository
from apps.consultations.services import ConsultationHandoffService
from apps.evidence.models import (
    AIChunkCrosswalk,
    AIChunkCrosswalkPage,
    DocumentChunk,
    DocumentModelScope,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)
from apps.inquiries.models import Guidance, HumanReview, Inquiry
from apps.inquiries.services.human_review_service import HumanReviewService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db
TOKEN = "test-protected-ai-handoff-token"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HANDOFF_EXAMPLE_ROOT = REPOSITORY_ROOT / "contracts" / "ai" / "examples" / "handoff"


def create_ai_run(
    inquiry,
    *,
    correlation_id=None,
    ai_request_id=None,
):
    correlation_id = correlation_id or uuid4()
    ai_request_id = ai_request_id or f"handoff-ai-{uuid4().hex}"
    completed_at = timezone.now()
    ai_run = AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.ANALYZE_SYMPTOM,
        request_schema_version="3.0.0",
        response_schema_version="3.0.0",
        model_config_version="v1",
        model_config={},
        input_payload={},
        input_sha256="0" * 64,
        idempotency_key=ai_request_id,
        model_provider="waterbridge-test",
        model_name="handoff-test",
        prompt_version="handoff-v1",
        validated_output_payload={},
        schema_validation_status_code=AIRun.SchemaValidationStatus.PASSED,
        status_code=AIRun.Status.NO_EVIDENCE,
        started_at=completed_at,
        completed_at=completed_at,
        correlation_id=correlation_id,
    )
    return ai_run, correlation_id, ai_request_id


def create_fixture(sequence: int = 1):
    customer_user = User.objects.create_user(
        username=f"HANDOFF-CUSTOMER-{sequence}",
        password=None,
        full_name="Synthetic handoff customer",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    profile = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"HANDOFF-CUS-{sequence}",
        customer_name="Synthetic handoff customer",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=f"HANDOFF-MODEL-{sequence}",
        model_name="Synthetic handoff product",
        is_active=True,
        is_supported_mvp=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"HANDOFF-CONTRACT-{sequence}",
        customer=profile,
        product_model=product,
        serial_no=f"HANDOFF-SERIAL-{sequence}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="합성 상담 인계 문의",
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
    )
    ai_run, correlation_id, ai_request_id = create_ai_run(inquiry)
    return inquiry, ai_run, correlation_id, ai_request_id


def handoff_payload(inquiry, correlation_id, ai_request_id):
    return {
        "inquiry_id": str(inquiry.public_id),
        "correlation_id": str(correlation_id),
        "ai_request_id": ai_request_id,
        "model_code": inquiry.subscription.product_model.model_code,
        "product_family": "WATER_PURIFIER",
        "customer_symptom_summary": "출수량 저하 증상이 확인됐습니다.",
        "questionnaire_answers": [],
        "self_help_actions": [],
        "evidence": [],
        "safety_level": "unknown",
        "safety_requires_consultation": False,
        "safety_notes": ["공식 근거 없음"],
        "escalation_reason": "NO_EVIDENCE",
        "consultant_priority_checks": ["출수 환경 확인"],
        "source_chunk_ids": [],
    }


def load_v2_payload(
    filename,
    *,
    inquiry,
    correlation_id,
    ai_request_id,
    mapping=None,
):
    payload = json.loads(
        (HANDOFF_EXAMPLE_ROOT / filename).read_text(encoding="utf-8")
    )
    payload.update(
        {
            "inquiry_id": str(inquiry.public_id),
            "correlation_id": str(correlation_id),
            "ai_request_id": ai_request_id,
            "state_version": inquiry.state_version,
            "model_code": inquiry.subscription.product_model.model_code,
        }
    )
    if mapping is None:
        payload["evidence"] = []
        payload["source_chunk_ids"] = []
        if isinstance(payload["context_synthesis"], dict):
            payload["context_synthesis"]["brief"][
                "evidence_based_findings"
            ] = []
    else:
        document = mapping.chunk.page.document
        payload["evidence"] = [
            {
                "chunk_id": mapping.canonical_chunk_id,
                "document_title": document.title,
                "page": mapping.chunk.page.page_no,
                "summary": "공식 문서에서 확인한 합성 근거입니다.",
            }
        ]
        payload["source_chunk_ids"] = [mapping.canonical_chunk_id]
        if isinstance(payload["context_synthesis"], dict):
            findings = payload["context_synthesis"]["brief"][
                "evidence_based_findings"
            ]
            if findings:
                findings[0]["source_chunk_ids"] = [mapping.canonical_chunk_id]
    return payload


def configure_v2_run(
    ai_run,
    payload,
    *,
    fallback_reason_code=None,
    failure_stage=None,
    danger=False,
    mapping=None,
    run_status=None,
):
    identity = {
        "inquiry_id": payload["inquiry_id"],
        "correlation_id": payload["correlation_id"],
        "ai_request_id": payload["ai_request_id"],
        "state_version": payload["state_version"],
        "model_code": payload["model_code"],
    }
    ai_run.input_payload = dict(identity)
    if run_status == AIRun.Status.TIMED_OUT:
        ai_run.validated_output_payload = None
        ai_run.error_code = "AI-TIMEOUT-01"
        ai_run.schema_validation_status_code = AIRun.SchemaValidationStatus.PASSED
    else:
        if danger:
            output = json.loads(
                (
                    REPOSITORY_ROOT
                    / "contracts"
                    / "ai"
                    / "examples"
                    / "symptom-analysis"
                    / "danger-detected.json"
                ).read_text(encoding="utf-8")
            )["response"]
            output.update(identity)
        else:
            output = {
                **identity,
                "status": "FALLBACK" if fallback_reason_code else "SUCCEEDED",
                "fallback_reason_code": fallback_reason_code,
                "failure_stage": failure_stage,
                "retry_count": 0,
                "structured_symptom": {
                    "symptom_type": "합성 상담 증상",
                    "occurrence_time": None,
                    "target_water_type": None,
                    "occurrence_condition": None,
                    "error_code": None,
                    "accompanying_symptoms": [],
                    "actions_taken": [],
                },
                "missing_fields": [],
                "followup_questions": [],
                "safety_assessment": {
                    "risk_level": "caution",
                    "priority": "consultation_recommended",
                    "requires_consultation": True,
                    "matched_safety_rule_ids": [],
                    "detected_risks": [],
                    "safety_reason": "상담사 확인이 필요합니다.",
                },
                "usage_guidance": {
                    "guidance_status": "PENDING_CONSULTATION",
                    "message": "전문 상담 연결이 필요합니다.",
                    "restricted_functions": [],
                    "next_actions": ["상담사 확인을 기다려 주세요."],
                },
                "evidence_references": [],
            }
        if mapping is not None:
            document = mapping.chunk.page.document
            output["evidence_references"] = [
                {
                    "document_title": document.title,
                    "document_version": document.revision_label,
                    "page": mapping.chunk.page.page_no,
                    "page_refs": [mapping.chunk.page.page_no],
                    "chunk_id": mapping.canonical_chunk_id,
                    "official_url": document.official_source_url,
                    "summary": "공식 문서에서 확인한 합성 근거입니다.",
                    "similarity_score": 0.9,
                    "verification_status": "official_verified",
                }
            ]
        ai_run.validated_output_payload = output
        ai_run.error_code = None
        ai_run.schema_validation_status_code = AIRun.SchemaValidationStatus.PASSED
    ai_run.status_code = run_status or (
        AIRun.Status.NO_EVIDENCE
        if fallback_reason_code == "NO_EVIDENCE"
        else AIRun.Status.SUCCEEDED
    )
    ai_run.completed_at = timezone.now()
    ai_run.save(
        update_fields=[
            "input_payload",
            "validated_output_payload",
            "schema_validation_status_code",
            "status_code",
            "error_code",
            "completed_at",
            "updated_at",
        ]
    )


def create_system_transition(*, inquiry, ai_run, event_code):
    latest_version = max(
        inquiry.transition_history.values_list("state_version", flat=True),
        default=0,
    )
    state_version = latest_version + 1
    return TransitionHistory.objects.create(
        target_type_code=TransitionHistory.TargetType.INQUIRY,
        inquiry=inquiry,
        actor=None,
        changed_by_type_code=TransitionHistory.ChangedByType.SYSTEM,
        event_code=event_code,
        from_state=None if state_version == 1 else inquiry.status_code,
        to_state=inquiry.status_code,
        state_version=state_version,
        correlation_id=ai_run.correlation_id,
        idempotency_key=ai_run.idempotency_key,
    )


def create_consultation(inquiry, sequence=1):
    return Consultation.objects.create(
        consultation_code=f"HANDOFF-CONSULTATION-{sequence}-{uuid4().hex[:8]}",
        inquiry=inquiry,
        sequence=sequence,
        status=Consultation.Status.WAITING,
        outcome=Consultation.Outcome.PENDING,
        state_version=1,
        idempotency_key=f"handoff-consultation-{sequence}-{uuid4().hex}",
        correlation_id=uuid4(),
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )


def create_verified_mapping(inquiry, sequence=1):
    operator = User.objects.create_user(
        username=f"HANDOFF-XWALK-OP-{sequence}",
        password=None,
        full_name=f"Handoff Crosswalk operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"HANDOFF-XWALK-{sequence}",
        is_synthetic=True,
    )
    batch = IngestionBatch.objects.create(
        batch_no=f"HANDOFF-XWALK-BATCH-{sequence}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"handoff-xwalk-batch-{sequence}",
        correlation_id=uuid4(),
        pipeline_version="handoff-v2-test",
        status_code=IngestionBatch.Status.SUCCEEDED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
        total_count=1,
        success_count=1,
    )
    source_hash = f"{sequence + 100:064x}"
    chunk_hash = f"{sequence + 200:064x}"
    document = SourceDocument.objects.create(
        ingestion_batch=batch,
        document_code=f"HANDOFF-XWALK-DOC-{sequence}",
        title=f"Handoff 공식 문서 {sequence}",
        source_org="Official test organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=f"https://example.test/handoff/{sequence}",
        usage_terms_url=f"https://example.test/handoff/terms/{sequence}",
        license_note="Synthetic test fixture.",
        original_file_uri=f"object://handoff/{sequence}.pdf",
        sha256_hash=source_hash,
        revision_label="REV-1",
        collected_by=operator,
        status_code="APPROVED",
    )
    page = DocumentPage.objects.create(
        document=document,
        page_no=40 + sequence,
        extracted_text="승인된 합성 페이지입니다.",
        text_sha256=f"{sequence + 300:064x}",
        parse_status_code="PARSED",
        review_status_code="APPROVED",
        is_rag_eligible=True,
        reviewer=operator,
        reviewed_at=timezone.now(),
    )
    chunk = DocumentChunk.objects.create(
        page=page,
        chunk_no=1,
        chunk_text="승인된 합성 Evidence Chunk입니다.",
        chunk_text_sha256=chunk_hash,
        metadata={"evidence_summary": "승인된 합성 근거"},
        chunking_version="handoff-v2-test",
    )
    scope = DocumentModelScope.objects.create(
        document=document,
        product_model=inquiry.subscription.product_model,
        is_verified=True,
        verified_by=operator,
        verified_at=timezone.now(),
    )
    mapping = AIChunkCrosswalk(
        canonical_chunk_id=f"RAG-HANDOFF-V2-{sequence}",
        chunk=chunk,
        model_scope=scope,
        manifest_schema_version="1.0.0",
        identity_manifest_sha256=f"{sequence + 400:064x}",
        canonical_verification_status="TEXT_AND_VISUAL_VERIFIED",
        source_file_sha256=source_hash,
        chunk_text_sha256=chunk_hash,
        embedding_model="BAAI/bge-m3",
        embedding_model_version=(
            "5617a9f61b028005a4858fdac845db406aefb181"
        ),
        index_version="1.0.0",
        chunk_set_sha256=f"{sequence + 500:064x}",
        is_verified=True,
        verified_by=operator,
        verified_at=timezone.now(),
        is_active=True,
    )
    mapping.full_clean()
    mapping.save()
    AIChunkCrosswalkPage.objects.create(
        crosswalk=mapping,
        page=page,
        display_order=1,
    )
    return mapping


def create_rejected_review(*, inquiry, ai_run, state_version, sequence=1):
    reviewer = User.objects.create_user(
        username=f"HANDOFF-REVIEWER-{sequence}",
        password=None,
        full_name=f"Handoff reviewer {sequence}",
        role_code=User.Role.CONSULTANT,
        employee_no=f"HANDOFF-REVIEWER-{sequence}",
        is_synthetic=True,
    )
    guidance = Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=sequence,
        review_status_code="PENDING",
        title="검토 대기 안내",
        summary_text="상담사 검토가 필요한 합성 안내입니다.",
        safety_notice="자동 안내 전 검토가 필요합니다.",
        evidence_sufficiency_code="CANDIDATE",
        requires_consultation=True,
        generated_by_ai_run=ai_run,
    )
    review = HumanReviewService.create_pending(
        guidance=guidance,
        ai_request_id=ai_run.idempotency_key,
        source_inquiry_state_version=state_version,
    )
    review.status_code = HumanReview.Status.REJECTED
    review.decision_code = HumanReview.Decision.REJECT
    review.review_state_version = 2
    review.decision_reason_code = "INSUFFICIENT_EVIDENCE"
    review.reviewer = reviewer
    review.decided_at = timezone.now()
    review.decision_idempotency_key = f"handoff-review-reject-{sequence}"
    review.decision_correlation_id = uuid4()
    review.effective_requires_consultation = True
    review.consultation_disposition_code = (
        HumanReview.ConsultationDisposition.REQUIRE
    )
    review.consultation_reason_code = (
        HumanReview.ConsultationChangeReason.HUMAN_REVIEW_REJECTED
    )
    review.full_clean()
    review.save()
    guidance.review_status_code = "REJECTED"
    guidance.save(update_fields=["review_status_code", "updated_at"])
    return review


def post_handoff(
    *,
    inquiry,
    correlation_id,
    ai_request_id,
    payload=None,
    token=TOKEN,
):
    return APIClient().post(
        (
            f"/api/v1/internal/ai/inquiries/{inquiry.public_id}/"
            "consultation-handoffs"
        ),
        payload or handoff_payload(inquiry, correlation_id, ai_request_id),
        format="json",
        HTTP_X_AI_HANDOFF_TOKEN=token,
        HTTP_IDEMPOTENCY_KEY=ai_request_id,
        HTTP_X_CORRELATION_ID=str(correlation_id),
    )


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_handoff_persists_before_consultation_without_changing_inquiry_state():
    inquiry, ai_run, correlation_id, ai_request_id = create_fixture()

    response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )

    assert response.status_code == 201
    handoff = ConsultationHandoff.objects.get()
    assert handoff.ai_run == ai_run
    assert handoff.consultation is None
    assert handoff.data_classification == "synthetic"
    assert "출수량 저하" in handoff.ai_draft_summary
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_unlinked_customer_handoff_uses_conservative_classification():
    """A nullable customer user must not crash or be assumed synthetic."""

    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    customer = inquiry.subscription.customer
    customer.user = None
    customer.save(update_fields=["user", "updated_at"])

    response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )

    assert response.status_code == 201
    assert (
        ConsultationHandoff.objects.get(inquiry=inquiry).data_classification
        == ConsultationHandoff.DataClassification.OPERATIONAL
    )


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_same_payload_replays_and_changed_payload_conflicts():
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    payload = handoff_payload(inquiry, correlation_id, ai_request_id)

    created = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=payload,
    )
    replayed = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=payload,
    )
    changed = dict(payload)
    changed["escalation_reason"] = "DANGER_PRIORITY"
    conflicted = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=changed,
    )

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.data["data"]["idempotent_replay"] is True
    assert created.data["data"]["handoff_id"] == replayed.data["data"]["handoff_id"]
    assert conflicted.status_code == 409
    assert conflicted.data["error"]["code"] == "DUPLICATE-EVENT-01"
    assert ConsultationHandoff.objects.count() == 1


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_internal_boundary_fails_closed_and_rejects_pii_or_prompt_fields():
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    payload = handoff_payload(inquiry, correlation_id, ai_request_id)

    no_token = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        token="",
    )
    with_prompt = dict(payload, system_prompt="do not persist")
    prompt_response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=with_prompt,
    )
    with_pii = dict(payload, customer_symptom_summary="연락처 010-1234-5678")
    pii_response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=with_pii,
    )

    assert no_token.status_code == 403
    assert prompt_response.status_code == 422
    assert pii_response.status_code == 422
    assert ConsultationHandoff.objects.count() == 0


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_wrong_model_or_ai_identity_stores_nothing():
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    wrong_model = handoff_payload(inquiry, correlation_id, ai_request_id)
    wrong_model["model_code"] = "OTHER-MODEL"

    model_response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=wrong_model,
    )
    wrong_correlation = uuid4()
    identity_payload = handoff_payload(
        inquiry,
        wrong_correlation,
        ai_request_id,
    )
    identity_response = post_handoff(
        inquiry=inquiry,
        correlation_id=wrong_correlation,
        ai_request_id=ai_request_id,
        payload=identity_payload,
    )

    assert model_response.status_code == 409
    assert identity_response.status_code == 409
    assert ConsultationHandoff.objects.count() == 0


def test_attach_failure_rolls_back_the_handoff(monkeypatch):
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    payload = handoff_payload(inquiry, correlation_id, ai_request_id)
    monkeypatch.setattr(
        ConsultationHandoffRepository,
        "attach_to_latest_consultation",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("forced rollback")),
    )

    with pytest.raises(RuntimeError, match="forced rollback"):
        ConsultationHandoffService.persist(
            inquiry_public_id=inquiry.public_id,
            validated_data=payload,
            idempotency_key=ai_request_id,
            correlation_id=correlation_id,
        )

    assert ConsultationHandoff.objects.count() == 0


def test_v1_contract_preserves_legacy_limits_and_rejects_mixed_v2_fields():
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    legacy = handoff_payload(inquiry, correlation_id, ai_request_id)
    legacy["schema_version"] = "1.0.0"
    legacy["safety_level"] = "legacy-custom-level"
    legacy["questionnaire_answers"] = [
        {"field_name": f"legacy-{index}", "answer": "기존 허용 답변"}
        for index in range(31)
    ]
    legacy["evidence"] = [
        {
            "chunk_id": "RAG-LEGACY-PAGE-OMITTED",
            "document_title": "기존 문서",
            "summary": "기존 page 생략 허용",
        }
    ]
    legacy["source_chunk_ids"] = ["RAG-LEGACY-PAGE-OMITTED"]

    explicit = ConsultationHandoffRequestSerializer(data=legacy)
    assert explicit.is_valid(), explicit.errors
    assert explicit.validated_data["schema_version"] == "1.0.0"
    assert explicit.validated_data["evidence"][0].get("page") is None

    page_null = json.loads(json.dumps(legacy))
    page_null["evidence"][0]["page"] = None
    assert ConsultationHandoffRequestSerializer(data=page_null).is_valid()

    mixed = handoff_payload(inquiry, correlation_id, ai_request_id)
    mixed["state_version"] = 3
    assert not ConsultationHandoffRequestSerializer(data=mixed).is_valid()


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_explicit_v1_runtime_remains_accepted():
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    payload = handoff_payload(inquiry, correlation_id, ai_request_id)
    payload["schema_version"] = "1.0.0"

    response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=payload,
    )

    assert response.status_code == 201
    assert ConsultationHandoff.objects.get().schema_version == "1.0.0"


def test_v2_contract_rejects_missing_limits_unknown_route_and_internal_metadata():
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    base = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    cases = []

    missing_array = json.loads(json.dumps(base))
    missing_array.pop("safety_notes")
    cases.append(missing_array)

    too_many = json.loads(json.dumps(base))
    too_many["questionnaire_answers"] = [
        {"field_name": f"field-{index}", "answer": "답변"}
        for index in range(31)
    ]
    cases.append(too_many)

    bad_safety = json.loads(json.dumps(base))
    bad_safety["safety_level"] = "legacy-custom-level"
    cases.append(bad_safety)

    missing_page = json.loads(json.dumps(base))
    missing_page["evidence"] = [
        {
            "chunk_id": "RAG-V2-PAGE-MISSING",
            "document_title": "공식 문서",
            "summary": "page 키가 없습니다.",
        }
    ]
    missing_page["source_chunk_ids"] = ["RAG-V2-PAGE-MISSING"]
    cases.append(missing_page)

    unknown = json.loads(json.dumps(base))
    unknown["provider_called"] = True
    cases.append(unknown)

    pre_send = json.loads(json.dumps(base))
    pre_send["routing_reason"] = "PRE_SEND_HUMAN_REVIEW"
    cases.append(pre_send)

    unsupported = json.loads(json.dumps(base))
    unsupported["schema_version"] = "3.0.0"
    cases.append(unsupported)

    danger = load_v2_payload(
        "v2-fallback-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    danger["context_synthesis"]["status"] = "SUCCEEDED"
    danger["context_synthesis"]["fallback_reason"] = None
    cases.append(danger)

    internal_context = load_v2_payload(
        "v2-fallback-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    internal_context["context_synthesis"]["provider_called"] = False
    cases.append(internal_context)

    outside_source = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    outside_source["context_synthesis"]["brief"]["evidence_based_findings"] = [
        {"text": "허용되지 않은 외부 근거", "source_chunk_ids": ["RAG-OUTSIDE"]}
    ]
    cases.append(outside_source)

    nested_pii = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    nested_pii["context_synthesis"]["brief"]["issue_summary"][
        "text"
    ] = "연락처 010-1234-5678"
    cases.append(nested_pii)

    for payload in cases:
        serializer = ConsultationHandoffRequestSerializer(data=payload)
        assert not serializer.is_valid(), payload

    page_null = json.loads(json.dumps(base))
    page_null["evidence"] = [
        {
            "chunk_id": "RAG-V2-PAGE-NULL",
            "document_title": "공식 문서",
            "page": None,
            "summary": "page null은 계약상 허용됩니다.",
        }
    ]
    page_null["source_chunk_ids"] = ["RAG-V2-PAGE-NULL"]
    assert ConsultationHandoffRequestSerializer(data=page_null).is_valid()


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_contract_examples_bind_to_backend_authority_and_persist():
    # HARNESS_ESCALATE: approved pair, verified Evidence, ledger only.
    harness_inquiry, harness_run, harness_correlation, harness_request = create_fixture(101)
    harness_mapping = create_verified_mapping(harness_inquiry, 101)
    harness_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=harness_inquiry,
        correlation_id=harness_correlation,
        ai_request_id=harness_request,
        mapping=harness_mapping,
    )
    configure_v2_run(
        harness_run,
        harness_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="VALIDATING",
        mapping=harness_mapping,
    )

    # DANGER_HANDOFF: strict danger output and matching Backend event.
    danger_inquiry, danger_run, danger_correlation, danger_request = create_fixture(102)
    danger_payload = load_v2_payload(
        "v2-fallback-request.json",
        inquiry=danger_inquiry,
        correlation_id=danger_correlation,
        ai_request_id=danger_request,
    )
    configure_v2_run(danger_run, danger_payload, danger=True)
    create_system_transition(
        inquiry=danger_inquiry,
        ai_run=danger_run,
        event_code="DANGER_DETECTED",
    )

    # FAIL_CLOSED no evidence: matching fallback and state event.
    empty_inquiry, empty_run, empty_correlation, empty_request = create_fixture(103)
    empty_payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=empty_inquiry,
        correlation_id=empty_correlation,
        ai_request_id=empty_request,
    )
    configure_v2_run(
        empty_run,
        empty_payload,
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    create_system_transition(
        inquiry=empty_inquiry,
        ai_run=empty_run,
        event_code="NO_EVIDENCE",
    )

    # FAIL_CLOSED HumanReview rejection: exact review identity bundle.
    review_inquiry, review_run, review_correlation, review_request = create_fixture(104)
    review_mapping = create_verified_mapping(review_inquiry, 104)
    review_payload = load_v2_payload(
        "v2-human-review-rejected-request.json",
        inquiry=review_inquiry,
        correlation_id=review_correlation,
        ai_request_id=review_request,
        mapping=review_mapping,
    )
    configure_v2_run(review_run, review_payload, mapping=review_mapping)
    create_rejected_review(
        inquiry=review_inquiry,
        ai_run=review_run,
        state_version=review_payload["state_version"],
        sequence=104,
    )

    outcomes = [
        post_handoff(
            inquiry=inquiry,
            correlation_id=correlation,
            ai_request_id=request_id,
            payload=payload,
        )
        for inquiry, correlation, request_id, payload in (
            (harness_inquiry, harness_correlation, harness_request, harness_payload),
            (danger_inquiry, danger_correlation, danger_request, danger_payload),
            (empty_inquiry, empty_correlation, empty_request, empty_payload),
            (review_inquiry, review_correlation, review_request, review_payload),
        )
    ]

    assert [response.status_code for response in outcomes] == [201, 201, 201, 201]
    assert ConsultationHandoff.objects.filter(schema_version="2.0.0").count() == 4
    assert ConsultationHandoff.objects.get(ai_run=harness_run).consultation is None
    assert ConsultationHandoff.objects.get(ai_run=review_run).consultation is None


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_not_ready_stale_and_harness_authority_errors_are_distinct():
    ready_inquiry, ready_run, ready_correlation, ready_request = create_fixture(201)
    ready_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=ready_inquiry,
        correlation_id=ready_correlation,
        ai_request_id=ready_request,
    )
    configure_v2_run(
        ready_run,
        ready_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="VALIDATING",
    )
    ready_run.status_code = AIRun.Status.RUNNING
    ready_run.completed_at = None
    ready_run.save(update_fields=["status_code", "completed_at", "updated_at"])
    not_ready = post_handoff(
        inquiry=ready_inquiry,
        correlation_id=ready_correlation,
        ai_request_id=ready_request,
        payload=ready_payload,
    )

    stale_inquiry, stale_run, stale_correlation, stale_request = create_fixture(202)
    stale_payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=stale_inquiry,
        correlation_id=stale_correlation,
        ai_request_id=stale_request,
    )
    configure_v2_run(
        stale_run,
        stale_payload,
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    stale_payload["state_version"] += 1
    stale = post_handoff(
        inquiry=stale_inquiry,
        correlation_id=stale_correlation,
        ai_request_id=stale_request,
        payload=stale_payload,
    )

    harness_inquiry, harness_run, harness_correlation, harness_request = create_fixture(203)
    harness_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=harness_inquiry,
        correlation_id=harness_correlation,
        ai_request_id=harness_request,
    )
    configure_v2_run(
        harness_run,
        harness_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="RETRIEVING",
    )
    invalid_harness = post_handoff(
        inquiry=harness_inquiry,
        correlation_id=harness_correlation,
        ai_request_id=harness_request,
        payload=harness_payload,
    )

    assert not_ready.status_code == 409
    assert not_ready.data["error"]["code"] == "AI_HANDOFF_NOT_READY"
    assert stale.status_code == 409
    assert stale.data["error"]["code"] == "AI_HANDOFF_STALE"
    assert invalid_harness.status_code == 409
    assert invalid_harness.data["error"]["code"] == "AI_HANDOFF_STALE"
    assert ConsultationHandoff.objects.count() == 0


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_human_review_binding_failure_stores_nothing():
    inquiry, ai_run, correlation_id, ai_request_id = create_fixture(301)
    payload = load_v2_payload(
        "v2-human-review-rejected-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    configure_v2_run(ai_run, payload)

    response = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=payload,
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "AI_HANDOFF_STALE"
    assert ConsultationHandoff.objects.count() == 0


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_product_rejection_and_timeout_require_matching_backend_events():
    product_inquiry, product_run, product_correlation, product_request = create_fixture(351)
    product_payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=product_inquiry,
        correlation_id=product_correlation,
        ai_request_id=product_request,
    )
    product_payload["escalation_reason"] = "RUNTIME_PRODUCT_NOT_APPROVED"
    configure_v2_run(
        product_run,
        product_payload,
        fallback_reason_code="RUNTIME_PRODUCT_NOT_APPROVED",
        failure_stage="STRUCTURING",
    )
    create_system_transition(
        inquiry=product_inquiry,
        ai_run=product_run,
        event_code="PRODUCT_VALIDATION_FAILED",
    )

    timeout_inquiry, timeout_run, timeout_correlation, timeout_request = create_fixture(352)
    timeout_payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=timeout_inquiry,
        correlation_id=timeout_correlation,
        ai_request_id=timeout_request,
    )
    timeout_payload["escalation_reason"] = "AI_PROCESSING_TIMEOUT"
    configure_v2_run(
        timeout_run,
        timeout_payload,
        run_status=AIRun.Status.TIMED_OUT,
    )
    timeout_run.validated_output_payload = {
        "success": False,
        "inquiry_id": timeout_payload["inquiry_id"],
        "correlation_id": timeout_payload["correlation_id"],
        "ai_request_id": timeout_payload["ai_request_id"],
        "state_version": timeout_payload["state_version"],
        "error": {
            "code": "AI-TIMEOUT-01",
            "message": "합성 시간 초과",
            "details": None,
            "retryable": True,
            "failure_stage": "CANCELLED",
            "retry_count": 0,
        },
    }
    timeout_run.save(update_fields=["validated_output_payload", "updated_at"])
    create_system_transition(
        inquiry=timeout_inquiry,
        ai_run=timeout_run,
        event_code="AI_PROCESSING_TIMEOUT",
    )

    product_response = post_handoff(
        inquiry=product_inquiry,
        correlation_id=product_correlation,
        ai_request_id=product_request,
        payload=product_payload,
    )
    timeout_response = post_handoff(
        inquiry=timeout_inquiry,
        correlation_id=timeout_correlation,
        ai_request_id=timeout_request,
        payload=timeout_payload,
    )

    assert product_response.status_code == 201
    assert timeout_response.status_code == 201
    assert ConsultationHandoff.objects.count() == 2


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_evidence_rejects_other_run_inactive_crosswalk_and_wrong_page():
    mismatch_inquiry, mismatch_run, mismatch_correlation, mismatch_request = create_fixture(401)
    mismatch_mapping = create_verified_mapping(mismatch_inquiry, 401)
    mismatch_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=mismatch_inquiry,
        correlation_id=mismatch_correlation,
        ai_request_id=mismatch_request,
        mapping=mismatch_mapping,
    )
    configure_v2_run(
        mismatch_run,
        mismatch_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="VALIDATING",
        mapping=mismatch_mapping,
    )
    mismatch_run.validated_output_payload["evidence_references"][0][
        "chunk_id"
    ] = "RAG-OTHER-RUN-401"
    mismatch_run.save(update_fields=["validated_output_payload", "updated_at"])
    other_run = post_handoff(
        inquiry=mismatch_inquiry,
        correlation_id=mismatch_correlation,
        ai_request_id=mismatch_request,
        payload=mismatch_payload,
    )

    inactive_inquiry, inactive_run, inactive_correlation, inactive_request = create_fixture(402)
    inactive_mapping = create_verified_mapping(inactive_inquiry, 402)
    inactive_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=inactive_inquiry,
        correlation_id=inactive_correlation,
        ai_request_id=inactive_request,
        mapping=inactive_mapping,
    )
    configure_v2_run(
        inactive_run,
        inactive_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="VALIDATING",
        mapping=inactive_mapping,
    )
    inactive_mapping.is_active = False
    inactive_mapping.save(update_fields=["is_active", "updated_at"])
    inactive = post_handoff(
        inquiry=inactive_inquiry,
        correlation_id=inactive_correlation,
        ai_request_id=inactive_request,
        payload=inactive_payload,
    )

    page_inquiry, page_run, page_correlation, page_request = create_fixture(403)
    page_mapping = create_verified_mapping(page_inquiry, 403)
    page_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=page_inquiry,
        correlation_id=page_correlation,
        ai_request_id=page_request,
        mapping=page_mapping,
    )
    configure_v2_run(
        page_run,
        page_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="VALIDATING",
        mapping=page_mapping,
    )
    page_payload["evidence"][0]["page"] += 1
    wrong_page = post_handoff(
        inquiry=page_inquiry,
        correlation_id=page_correlation,
        ai_request_id=page_request,
        payload=page_payload,
    )

    for response in (other_run, inactive, wrong_page):
        assert response.status_code == 422
        assert response.data["error"]["code"] == "AI_HANDOFF_EVIDENCE_REJECTED"
    assert ConsultationHandoff.objects.count() == 0


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_replay_is_read_only_and_v1_cannot_upgrade_in_place():
    inquiry, ai_run, correlation_id, ai_request_id = create_fixture(501)
    payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    configure_v2_run(
        ai_run,
        payload,
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    create_system_transition(inquiry=inquiry, ai_run=ai_run, event_code="NO_EVIDENCE")
    created = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=payload,
    )
    replayed = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=payload,
    )
    changed_payload = json.loads(json.dumps(payload))
    changed_payload["customer_symptom_summary"] = "변경된 재전송"
    changed = post_handoff(
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        payload=changed_payload,
    )

    legacy_inquiry, _legacy_run, legacy_correlation, legacy_request = create_fixture(502)
    legacy = post_handoff(
        inquiry=legacy_inquiry,
        correlation_id=legacy_correlation,
        ai_request_id=legacy_request,
    )
    upgrade = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=legacy_inquiry,
        correlation_id=legacy_correlation,
        ai_request_id=legacy_request,
    )
    upgraded = post_handoff(
        inquiry=legacy_inquiry,
        correlation_id=legacy_correlation,
        ai_request_id=legacy_request,
        payload=upgrade,
    )

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.data["data"]["idempotent_replay"] is True
    assert changed.status_code == 409
    assert changed.data["error"]["code"] == "DUPLICATE-EVENT-01"
    assert legacy.status_code == 201
    assert upgraded.status_code == 409
    assert upgraded.data["error"]["code"] == "DUPLICATE-EVENT-01"
    assert ConsultationHandoff.objects.count() == 2


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_v2_projection_is_summary_only_ledger_aware_and_non_degrading():
    harness_inquiry, harness_run, harness_correlation, harness_request = create_fixture(601)
    harness_consultation = create_consultation(harness_inquiry, 1)
    harness_payload = load_v2_payload(
        "v2-succeeded-request.json",
        inquiry=harness_inquiry,
        correlation_id=harness_correlation,
        ai_request_id=harness_request,
    )
    configure_v2_run(
        harness_run,
        harness_payload,
        fallback_reason_code="MCP_TOOL_FAILURE",
        failure_stage="VALIDATING",
    )
    harness_response = post_handoff(
        inquiry=harness_inquiry,
        correlation_id=harness_correlation,
        ai_request_id=harness_request,
        payload=harness_payload,
    )
    harness_consultation.refresh_from_db()
    harness_handoff = ConsultationHandoff.objects.get(ai_run=harness_run)

    inquiry, older_run, older_correlation, older_request = create_fixture(602)
    inquiry.state_version = 5
    inquiry.save(update_fields=["state_version", "updated_at"])
    consultation = create_consultation(inquiry, 1)
    older_payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=inquiry,
        correlation_id=older_correlation,
        ai_request_id=older_request,
    )
    older_payload["state_version"] = 4
    configure_v2_run(
        older_run,
        older_payload,
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    create_system_transition(inquiry=inquiry, ai_run=older_run, event_code="NO_EVIDENCE")

    newer_run, newer_correlation, newer_request = create_ai_run(inquiry)
    newer_payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=inquiry,
        correlation_id=newer_correlation,
        ai_request_id=newer_request,
    )
    newer_payload["state_version"] = 5
    newer_payload["customer_symptom_summary"] = "최신 상담 요약"
    newer_payload["safety_notes"] = ["가" * 1000 for _index in range(5)]
    configure_v2_run(
        newer_run,
        newer_payload,
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    create_system_transition(inquiry=inquiry, ai_run=newer_run, event_code="NO_EVIDENCE")

    newer_response = post_handoff(
        inquiry=inquiry,
        correlation_id=newer_correlation,
        ai_request_id=newer_request,
        payload=newer_payload,
    )
    consultation.refresh_from_db()
    newest_summary = consultation.ai_draft_summary
    older_response = post_handoff(
        inquiry=inquiry,
        correlation_id=older_correlation,
        ai_request_id=older_request,
        payload=older_payload,
    )
    consultation.refresh_from_db()
    older_handoff = ConsultationHandoff.objects.get(ai_run=older_run)

    assert harness_response.status_code == 201
    assert harness_handoff.consultation is None
    assert harness_consultation.ai_draft_summary in (None, "")
    assert newer_response.status_code == 201
    assert older_response.status_code == 201
    assert "최신 상담 요약" in newest_summary
    assert len(newest_summary) <= 4000
    assert "NO_EVIDENCE" not in newest_summary
    assert consultation.ai_draft_summary == newest_summary
    assert older_handoff.consultation is None


@pytest.mark.django_db(transaction=True)
@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_postgresql_concurrent_replay_creates_one_handoff():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock evidence")
    inquiry, _ai_run, correlation_id, ai_request_id = create_fixture()
    payload = handoff_payload(inquiry, correlation_id, ai_request_id)
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            response = post_handoff(
                inquiry=inquiry,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                payload=payload,
            )
            return response.status_code, response.data["data"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result(timeout=20) for future in [
            executor.submit(worker),
            executor.submit(worker),
        ]]

    assert sorted(status for status, _data in outcomes) == [200, 201]
    assert {data["handoff_id"] for _status, data in outcomes} == {
        str(ConsultationHandoff.objects.get().public_id)
    }
    assert ConsultationHandoff.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@override_settings(AI_HANDOFF_INTERNAL_TOKEN=TOKEN)
def test_postgresql_v2_concurrent_replay_creates_one_handoff():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL v2 row-lock evidence")
    inquiry, ai_run, correlation_id, ai_request_id = create_fixture(901)
    payload = load_v2_payload(
        "v2-null-context-request.json",
        inquiry=inquiry,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    configure_v2_run(
        ai_run,
        payload,
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    create_system_transition(inquiry=inquiry, ai_run=ai_run, event_code="NO_EVIDENCE")
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            response = post_handoff(
                inquiry=inquiry,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                payload=payload,
            )
            return response.status_code, response.data["data"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [
            future.result(timeout=20)
            for future in [executor.submit(worker), executor.submit(worker)]
        ]

    assert sorted(status for status, _data in outcomes) == [200, 201]
    assert {data["handoff_id"] for _status, data in outcomes} == {
        str(ConsultationHandoff.objects.get().public_id)
    }
    assert ConsultationHandoff.objects.count() == 1
