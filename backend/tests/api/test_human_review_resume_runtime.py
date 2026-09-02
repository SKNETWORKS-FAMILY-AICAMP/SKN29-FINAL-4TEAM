"""Backend rejected HumanReview resume scheduling and binding tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from django.test import override_settings

from apps.evidence.models import EvidenceLink
from apps.inquiries.models import (
    ConsultationCauseLedger,
    HumanReview,
    HumanReviewResumeDispatch,
    Inquiry,
)
from apps.inquiries.services.human_review_resume_dispatch_service import (
    HumanReviewResumeDispatchService,
)
from integrations.ai.human_review_resume import (
    HumanReviewResumeClient,
    HumanReviewResumeFailure,
    HumanReviewResumeReceipt,
    build_human_review_resume_payload,
)
from tests.api.test_ai_consultation_handoff_runtime import (
    configure_v2_run,
    create_fixture as create_handoff_fixture,
    create_rejected_review,
    create_verified_mapping,
)
from tests.api.test_human_review_runtime import (
    create_review,
    create_user,
    decide,
)
from tests.unit.evidence.test_evidence_link_model import link_values
from apps.accounts.models import User
from common.json_integrity import canonical_json_sha256


pytestmark = pytest.mark.django_db
TOKEN = "test-only-distinct-resume-token-32-bytes"


def _receipt(review: HumanReview) -> HumanReviewResumeReceipt:
    return HumanReviewResumeReceipt(
        backend_review_id=review.public_id,
        inquiry_id=review.inquiry.public_id,
        ai_request_id=review.source_ai_request_id,
        review_state_version=review.review_state_version,
        context_agent_calls=1,
        provider_calls=0,
        context_synthesis_status="FALLBACK",
        fallback_reason="CONFIGURATION",
        handoff_created=True,
        handoff_delivery_scheduled=False,
        idempotent_replay=False,
    )


def _mock_dispatch_payload(monkeypatch, review: HumanReview) -> None:
    key = f"human-review-resume:{review.public_id}:2"
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "build_human_review_resume_payload",
        lambda review_public_id: (
            {
                "backend_review_id": str(review_public_id),
                "decision": "REJECT",
            },
            key,
        ),
    )


def _set_jac104(review: HumanReview) -> None:
    product = review.inquiry.subscription.product_model
    product.model_code = "WPUJAC104DWH"
    product.save(update_fields=["model_code", "updated_at"])


@override_settings(
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
)
def test_official_reject_schedules_once_and_decision_replay_schedules_zero(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    consultant = create_user(1801, role=User.Role.CONSULTANT)
    _inquiry, _guidance, review = create_review(
        1801,
        assigned_consultant=consultant,
    )
    _set_jac104(review)
    calls = []

    def fake_resume(payload, *, idempotency_key):
        del idempotency_key
        review_public_id = payload["backend_review_id"]
        persisted = HumanReview.objects.get(public_id=review_public_id)
        calls.append(persisted.public_id)
        return _receipt(persisted)

    _mock_dispatch_payload(monkeypatch, review)
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        fake_resume,
    )
    body = {
        "decision": HumanReview.Decision.REJECT,
        "review_state_version": 1,
        "reason_code": "INSUFFICIENT_EVIDENCE",
    }
    key = "human-review-resume-once-1801"

    with django_capture_on_commit_callbacks(execute=True):
        first = decide(
            actor=consultant,
            review=review,
            body=body,
            key=key,
        )
    with django_capture_on_commit_callbacks(execute=True):
        replay = decide(
            actor=consultant,
            review=review,
            body=body,
            key=key,
        )

    assert first.status_code == replay.status_code == 200
    assert first.json()["data"]["idempotent_replay"] is False
    assert replay.json()["data"]["idempotent_replay"] is True
    assert calls == [review.public_id]
    dispatch = HumanReviewResumeDispatch.objects.get(human_review=review)
    assert dispatch.status == HumanReviewResumeDispatch.Status.SUCCEEDED
    assert dispatch.attempt_count == 1
    assert len(dispatch.payload_sha256) == 64


@override_settings(
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
)
def test_ai_failure_keeps_reject_and_inquiry_transition_durable(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    consultant = create_user(1802, role=User.Role.CONSULTANT)
    inquiry, _guidance, review = create_review(
        1802,
        assigned_consultant=consultant,
    )
    _set_jac104(review)
    sentinel = inquiry.raw_text

    def fail_resume(_payload, *, idempotency_key):
        del idempotency_key
        raise HumanReviewResumeFailure("AI_RESUME_TRANSPORT")

    _mock_dispatch_payload(monkeypatch, review)
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        fail_resume,
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = decide(
            actor=consultant,
            review=review,
            body={
                "decision": HumanReview.Decision.REJECT,
                "review_state_version": 1,
                "reason_code": "INSUFFICIENT_EVIDENCE",
            },
            key="human-review-resume-failure-1802",
        )

    assert response.status_code == 200
    review.refresh_from_db()
    inquiry.refresh_from_db()
    assert review.decision_code == HumanReview.Decision.REJECT
    assert review.status_code == HumanReview.Status.REJECTED
    assert review.resume_failure_code is None
    assert review.review_state_version == 2
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert sentinel not in str(response.json())
    dispatch = HumanReviewResumeDispatch.objects.get(human_review=review)
    assert dispatch.status == HumanReviewResumeDispatch.Status.OUTCOME_UNKNOWN
    assert dispatch.attempt_count == 1
    assert dispatch.failure_code == "AI_RESUME_TRANSPORT"


@override_settings(AI_HUMAN_REVIEW_RESUME_ENABLED=False)
def test_disabled_resume_never_schedules_ai_call(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    consultant = create_user(1803, role=User.Role.CONSULTANT)
    _inquiry, _guidance, review = create_review(
        1803,
        assigned_consultant=consultant,
    )
    calls = []
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        lambda payload, **kwargs: calls.append((payload, kwargs)),
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = decide(
            actor=consultant,
            review=review,
            body={
                "decision": HumanReview.Decision.REJECT,
                "review_state_version": 1,
                "reason_code": "INSUFFICIENT_EVIDENCE",
            },
            key="human-review-resume-disabled-1803",
        )

    assert response.status_code == 200
    assert callbacks == []
    assert calls == []
    assert not HumanReviewResumeDispatch.objects.filter(
        human_review=review
    ).exists()


@override_settings(
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
)
def test_non_jac104_reject_never_schedules_context_resume(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    consultant = create_user(1812, role=User.Role.CONSULTANT)
    _inquiry, _guidance, review = create_review(
        1812,
        assigned_consultant=consultant,
    )
    product = review.inquiry.subscription.product_model
    product.model_code = "WPUIAC425SNW"
    product.save(update_fields=["model_code", "updated_at"])
    calls = []
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        lambda payload, **kwargs: calls.append((payload, kwargs)),
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = decide(
            actor=consultant,
            review=review,
            body={
                "decision": HumanReview.Decision.REJECT,
                "review_state_version": 1,
                "reason_code": "INSUFFICIENT_EVIDENCE",
            },
            key="human-review-resume-iac425-blocked-1812",
        )

    assert response.status_code == 200
    assert callbacks == []
    assert calls == []
    assert not HumanReviewResumeDispatch.objects.filter(
        human_review=review
    ).exists()


def test_non_jac104_payload_is_blocked_before_provider_dispatch():
    _inquiry, _run, review, _mapping = _bound_rejected_review(1813)
    product = review.inquiry.subscription.product_model
    product.model_code = "WPUIAC606SNW"
    product.save(update_fields=["model_code", "updated_at"])

    with pytest.raises(HumanReviewResumeFailure) as captured:
        build_human_review_resume_payload(review.public_id)

    assert captured.value.failure_code == "RUNTIME_PRODUCT_NOT_APPROVED"


@override_settings(
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
)
def test_commit_callback_loss_leaves_pending_row_for_worker_recovery(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    consultant = create_user(1804, role=User.Role.CONSULTANT)
    _inquiry, _guidance, review = create_review(
        1804,
        assigned_consultant=consultant,
    )
    _set_jac104(review)
    calls = []
    _mock_dispatch_payload(monkeypatch, review)

    def fake_resume(payload, *, idempotency_key):
        del idempotency_key
        review_public_id = payload["backend_review_id"]
        persisted = HumanReview.objects.get(public_id=review_public_id)
        calls.append(persisted.public_id)
        return _receipt(persisted)

    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        fake_resume,
    )
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        response = decide(
            actor=consultant,
            review=review,
            body={
                "decision": HumanReview.Decision.REJECT,
                "review_state_version": 1,
                "reason_code": "INSUFFICIENT_EVIDENCE",
            },
            key="human-review-resume-pending-1804",
        )

    assert response.status_code == 200
    assert len(callbacks) == 1
    dispatch = HumanReviewResumeDispatch.objects.get(human_review=review)
    assert dispatch.status == HumanReviewResumeDispatch.Status.PENDING
    assert dispatch.attempt_count == 0
    assert calls == []

    result = HumanReviewResumeDispatchService.process_pending(max_rows=10)

    assert result == {
        "processed": 1,
        "succeeded": 1,
        "failed_pre_send": 0,
        "outcome_unknown": 0,
        "skipped": 0,
    }
    dispatch.refresh_from_db()
    assert dispatch.status == HumanReviewResumeDispatch.Status.SUCCEEDED
    assert calls == [review.public_id]


@override_settings(
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
)
def test_unknown_outcome_is_never_automatically_retried(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    consultant = create_user(1805, role=User.Role.CONSULTANT)
    _inquiry, _guidance, review = create_review(
        1805,
        assigned_consultant=consultant,
    )
    _set_jac104(review)
    calls = []
    _mock_dispatch_payload(monkeypatch, review)

    def fail_once(payload, *, idempotency_key):
        del idempotency_key
        calls.append(UUID(payload["backend_review_id"]))
        raise HumanReviewResumeFailure("AI_RESUME_TIMEOUT")

    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        fail_once,
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = decide(
            actor=consultant,
            review=review,
            body={
                "decision": HumanReview.Decision.REJECT,
                "review_state_version": 1,
                "reason_code": "INSUFFICIENT_EVIDENCE",
            },
            key="human-review-resume-unknown-1805",
        )

    assert response.status_code == 200
    assert calls == [review.public_id]
    result = HumanReviewResumeDispatchService.process_pending(max_rows=10)
    assert result["processed"] == 0
    assert calls == [review.public_id]
    dispatch = HumanReviewResumeDispatch.objects.get(human_review=review)
    assert dispatch.status == HumanReviewResumeDispatch.Status.OUTCOME_UNKNOWN


def _bound_rejected_review(sequence: int):
    inquiry, run, correlation_id, ai_request_id = create_handoff_fixture(
        sequence
    )
    product = inquiry.subscription.product_model
    product.model_code = "WPUJAC104DWH"
    product.save(update_fields=["model_code", "updated_at"])
    mapping = create_verified_mapping(inquiry, sequence=sequence)
    source_state_version = inquiry.state_version - 1
    configure_v2_run(
        run,
        {
            "inquiry_id": str(inquiry.public_id),
            "correlation_id": str(correlation_id),
            "ai_request_id": ai_request_id,
            "state_version": source_state_version,
            "model_code": product.model_code,
        },
        mapping=mapping,
    )
    _attach_cause_ledger(
        inquiry=inquiry,
        run=run,
        source_state_version=source_state_version,
    )
    review = create_rejected_review(
        inquiry=inquiry,
        ai_run=run,
        state_version=source_state_version,
        sequence=sequence,
    )
    EvidenceLink.objects.create(
        **link_values(
            sequence,
            inquiry=inquiry,
            chunk=mapping.chunk,
            target=review.guidance,
            ai_run=run,
            is_verified=True,
            verified_by=mapping.verified_by,
            verified_at=mapping.verified_at,
        )
    )
    return inquiry, run, review, mapping


def _attach_cause_ledger(*, inquiry, run, source_state_version: int):
    ledger_id = uuid4()
    causes = [
        {
            "cause_id": str(uuid4()),
            "cause_code": "FAIL_CLOSED_AI_RESULT",
            "origin": "AI_RUNTIME",
            "lock_class": "FAIL_CLOSED_LOCKED",
            "verification_code": "AI_OUTPUT_VERIFIED",
            "matched_safety_rule_ids": [],
            "required_fact_codes": [],
            "evidence_refs": [],
            "status": "ACTIVE",
            "supersedes_cause_id": None,
        }
    ]
    execution_identity = {
        "execution_commit_sha": "a" * 40,
        "runtime_name": "multi_agent",
        "model_provider": "waterbridge-test",
        "model_name": "resume-test",
        "prompt_version": "resume-v1",
        "prompt_sha256": "b" * 64,
    }
    payload = {
        "contract_version": "1.0.0",
        "ledger_id": str(ledger_id),
        "inquiry_id": str(inquiry.public_id),
        "correlation_id": str(run.correlation_id),
        "ai_request_id": run.idempotency_key,
        "state_version": source_state_version,
        "model_code": inquiry.subscription.product_model.model_code,
        "producer": "AI_HARNESS",
        "policy_version": "resume-test-v1",
        "execution_identity": execution_identity,
        "analysis_result_sha256": canonical_json_sha256(
            run.validated_output_payload
        ),
        "causes": causes,
    }
    ledger = ConsultationCauseLedger(
        ledger_id=ledger_id,
        inquiry=inquiry,
        ai_run=run,
        contract_version=payload["contract_version"],
        correlation_id=run.correlation_id,
        ai_request_id=run.idempotency_key,
        source_inquiry_state_version=source_state_version,
        model_code=payload["model_code"],
        producer=payload["producer"],
        policy_version=payload["policy_version"],
        execution_identity=execution_identity,
        analysis_result_sha256=payload["analysis_result_sha256"],
        causes=causes,
        ledger_sha256=canonical_json_sha256(payload),
    )
    ledger.full_clean()
    ledger.save()
    return ledger


@override_settings(
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
)
def test_pre_send_binding_failure_is_recorded_without_http_attempt(monkeypatch):
    inquiry, _run, review, _mapping = _bound_rejected_review(1806)
    dispatch = HumanReviewResumeDispatchService.enqueue(review)
    inquiry.state_version += 1
    inquiry.save(update_fields=["state_version", "updated_at"])
    calls = []
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    outcome = HumanReviewResumeDispatchService.process_dispatch(
        dispatch.public_id
    )

    assert outcome == "failed_pre_send"
    assert calls == []
    dispatch.refresh_from_db()
    assert dispatch.status == HumanReviewResumeDispatch.Status.FAILED_PRE_SEND
    assert dispatch.attempt_count == 0
    assert dispatch.payload_sha256 == ""
    assert dispatch.failure_code == "AI_RESUME_STALE_INQUIRY_VERSION"
    result = HumanReviewResumeDispatchService.process_pending(max_rows=10)
    assert result["processed"] == 0


@override_settings(AI_HUMAN_REVIEW_RESUME_ENABLED=False)
def test_kill_switch_keeps_existing_pending_dispatch_unsent(monkeypatch):
    _inquiry, _run, review, _mapping = _bound_rejected_review(1807)
    dispatch = HumanReviewResumeDispatchService.enqueue(review)
    calls = []
    monkeypatch.setattr(
        "apps.inquiries.services.human_review_resume_dispatch_service."
        "send_human_review_resume_payload",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    outcome = HumanReviewResumeDispatchService.process_dispatch(
        dispatch.public_id
    )
    pending_result = HumanReviewResumeDispatchService.process_pending(
        max_rows=10
    )

    assert outcome == "skipped"
    assert pending_result["processed"] == 0
    assert calls == []
    dispatch.refresh_from_db()
    assert dispatch.status == HumanReviewResumeDispatch.Status.PENDING
    assert dispatch.attempt_count == 0


def test_payload_is_rebuilt_from_bound_ledger_without_customer_original():
    inquiry, _run, review, mapping = _bound_rejected_review(1810)

    payload, idempotency_key = build_human_review_resume_payload(
        review.public_id
    )

    assert payload["backend_review_id"] == str(review.public_id)
    assert payload["current_inquiry_state_version"] == inquiry.state_version
    assert payload["analysis_result"]["evidence_references"][0][
        "chunk_id"
    ] == mapping.canonical_chunk_id
    assert idempotency_key.endswith(":2")
    serialized = str(payload)
    assert inquiry.raw_text not in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "system_prompt" not in serialized


def test_no_evidence_review_can_reconstruct_without_fabricated_evidence():
    inquiry, run, correlation_id, ai_request_id = create_handoff_fixture(1811)
    product = inquiry.subscription.product_model
    product.model_code = "WPUJAC104DWH"
    product.save(update_fields=["model_code", "updated_at"])
    source_state_version = inquiry.state_version - 1
    configure_v2_run(
        run,
        {
            "inquiry_id": str(inquiry.public_id),
            "correlation_id": str(correlation_id),
            "ai_request_id": ai_request_id,
            "state_version": source_state_version,
            "model_code": product.model_code,
        },
        fallback_reason_code="NO_EVIDENCE",
        failure_stage="RETRIEVING",
    )
    _attach_cause_ledger(
        inquiry=inquiry,
        run=run,
        source_state_version=source_state_version,
    )
    review = create_rejected_review(
        inquiry=inquiry,
        ai_run=run,
        state_version=source_state_version,
        sequence=1811,
    )

    payload, _idempotency_key = build_human_review_resume_payload(
        review.public_id
    )

    assert payload["analysis_result"]["status"] == "FALLBACK"
    assert payload["analysis_result"]["evidence_references"] == []


@pytest.mark.parametrize(
    "mutation,expected_code",
    [
        ("stale_version", "AI_RESUME_STALE_INQUIRY_VERSION"),
        ("advanced_version", "AI_RESUME_STALE_INQUIRY_VERSION"),
        ("team_evidence", "AI_RESUME_EVIDENCE_NOT_OFFICIAL"),
        ("mismatched_ai_request", "AI_RESUME_OUTPUT_ID_MISMATCH"),
        ("missing_cause_ledger", "AI_RESUME_CAUSE_LEDGER_MISSING"),
        ("tampered_cause_ledger", "AI_RESUME_CAUSE_LEDGER_INVALID"),
    ],
)
def test_payload_builder_fails_closed_on_stale_or_mismatched_ledger(
    mutation,
    expected_code,
):
    inquiry, run, review, _mapping = _bound_rejected_review(
        1820
        + {
            "stale_version": 1,
            "advanced_version": 2,
            "team_evidence": 3,
            "mismatched_ai_request": 4,
            "missing_cause_ledger": 5,
            "tampered_cause_ledger": 6,
        }[mutation]
    )
    if mutation == "stale_version":
        inquiry.state_version = review.source_inquiry_state_version
        inquiry.save(update_fields=["state_version", "updated_at"])
    elif mutation == "advanced_version":
        inquiry.state_version = review.source_inquiry_state_version + 2
        inquiry.save(update_fields=["state_version", "updated_at"])
    elif mutation in {"team_evidence", "mismatched_ai_request"}:
        output = dict(run.validated_output_payload)
        if mutation == "team_evidence":
            evidence = [dict(item) for item in output["evidence_references"]]
            evidence[0]["verification_status"] = "team_verified"
            output["evidence_references"] = evidence
        else:
            output["ai_request_id"] = "mismatched-ai-request"
        run.validated_output_payload = output
        run.save(update_fields=["validated_output_payload", "updated_at"])
    elif mutation == "missing_cause_ledger":
        ConsultationCauseLedger.objects.filter(ai_run=run).delete()
    else:
        ConsultationCauseLedger.objects.filter(ai_run=run).update(
            analysis_result_sha256="0" * 64
        )

    with pytest.raises(HumanReviewResumeFailure) as captured:
        build_human_review_resume_payload(review.public_id)

    assert captured.value.failure_code == expected_code


def test_resume_http_client_uses_exactly_one_request_on_failure():
    attempts = []

    def handler(request):
        attempts.append(request)
        return httpx.Response(503, json={"error": "sanitized"})

    client = HumanReviewResumeClient(
        base_url="http://ai.invalid",
        token=TOKEN,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    payload = {
        "decision_correlation_id": str(uuid4()),
    }

    with pytest.raises(HumanReviewResumeFailure) as captured:
        client.resume(payload, idempotency_key="resume-once")

    assert captured.value.failure_code == "AI_RESUME_REJECTED"
    assert len(attempts) == 1


def test_resume_http_client_validates_protected_success_receipt():
    backend_review_id = uuid4()
    inquiry_id = uuid4()
    decision_correlation_id = uuid4()
    payload = {
        "backend_review_id": str(backend_review_id),
        "review_state_version": 2,
        "source_inquiry_state_version": 4,
        "decision_correlation_id": str(decision_correlation_id),
        "analysis_result": {
            "inquiry_id": str(inquiry_id),
            "ai_request_id": "ai-resume-success-001",
        },
    }
    attempts = []

    def handler(request):
        attempts.append(request)
        assert request.headers["X-Backend-Resume-Token"] == TOKEN
        assert request.headers["Idempotency-Key"] == "resume-success"
        assert request.headers["X-Correlation-ID"] == str(
            decision_correlation_id
        )
        return httpx.Response(
            200,
            json={
                "contract_version": "1.0.0",
                "backend_review_id": str(backend_review_id),
                "inquiry_id": str(inquiry_id),
                "ai_request_id": "ai-resume-success-001",
                "source_inquiry_state_version": 4,
                "review_state_version": 2,
                "status": "RESUMED",
                "routing_reason": "FAIL_CLOSED_CONSULTATION",
                "escalation_reason": "HUMAN_REVIEW_REJECTED",
                "context_agent_calls": 1,
                "provider_calls": 0,
                "context_synthesis_status": "FALLBACK",
                "fallback_reason": "CONFIGURATION",
                "handoff_created": True,
                "handoff_delivery_scheduled": False,
                "idempotent_replay": False,
            },
        )

    client = HumanReviewResumeClient(
        base_url="http://ai.invalid",
        token=TOKEN,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    receipt = client.resume(payload, idempotency_key="resume-success")

    assert len(attempts) == 1
    assert receipt.backend_review_id == backend_review_id
    assert receipt.context_agent_calls == 1
    assert receipt.provider_calls == 0
    assert receipt.fallback_reason == "CONFIGURATION"
