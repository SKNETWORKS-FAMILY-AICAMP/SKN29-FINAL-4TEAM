"""Backend API and PostgreSQL evidence for AI consultation handoff storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation, ConsultationHandoff
from apps.consultations.repositories import ConsultationHandoffRepository
from apps.consultations.services import ConsultationHandoffService
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db
TOKEN = "test-protected-ai-handoff-token"


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
    correlation_id = uuid4()
    ai_request_id = f"handoff-ai-{uuid4().hex}"
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
