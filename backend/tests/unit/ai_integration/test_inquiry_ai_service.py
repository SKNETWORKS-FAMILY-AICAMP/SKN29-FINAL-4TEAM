"""Persistence and workflow tests for the Backend-to-AI vertical slice."""

from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import httpx
import pytest
from django.db import IntegrityError

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.inquiries.models import (
    FollowUpAnswer,
    Guidance,
    Inquiry,
    InquiryQA,
    SymptomAssessment,
)
from apps.inquiries.services.inquiry_ai_service import InquiryAIService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory
from integrations.ai.client import AIClient
from integrations.ai.exceptions import AIIdempotencyConflictError
from integrations.ai.schema_validator import DEFAULT_CONTRACT_ROOT


pytestmark = pytest.mark.django_db


def create_inquiry(sequence: int) -> Inquiry:
    user = User.objects.create_user(
        username=f"AI-SERVICE-{sequence:03d}",
        password=None,
        full_name=f"AI service customer {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    profile = CustomerProfile.objects.create(
        user=user,
        customer_no=f"AI-SERVICE-CUS-{sequence:03d}",
        customer_name=f"AI service customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"AI-SERVICE-MODEL-{sequence:03d}",
        model_name=f"AI service model {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"AI-SERVICE-SUB-{sequence:03d}",
        customer=profile,
        product_model=product,
        serial_no=f"AI-SERVICE-SERIAL-{sequence:03d}",
        started_on=date(2026, 8, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="The water flow has become noticeably weak.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=2,
    )


def success_payload(request_payload: dict) -> dict:
    example_path = (
        DEFAULT_CONTRACT_ROOT
        / "examples"
        / "symptom-analysis"
        / "general-guidance.json"
    )
    response = json.loads(example_path.read_text(encoding="utf-8"))[
        "response"
    ]
    for field in (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ):
        response[field] = request_payload[field]
    return response


def error_payload(request_payload: dict) -> dict:
    return {
        "success": False,
        "inquiry_id": request_payload["inquiry_id"],
        "correlation_id": request_payload["correlation_id"],
        "ai_request_id": request_payload["ai_request_id"],
        "state_version": request_payload["state_version"],
        "error": {
            "code": "AI-FAILED-01",
            "message": "The AI service could not complete the request.",
            "details": None,
            "retryable": False,
            "failure_stage": "RETRIEVING",
            "retry_count": 0,
        },
    }


def make_client(*, transform=None, status_code: int = 200):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        request_payload = json.loads(request.content.decode("utf-8"))
        response_payload = success_payload(request_payload)
        if transform is not None:
            response_payload = transform(
                response_payload,
                request_payload,
            )
        return httpx.Response(status_code, json=response_payload)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return (
        AIClient(
            base_url="http://ai.test",
            mode="local",
            http_client=http_client,
        ),
        http_client,
        calls,
    )


def analyze(inquiry: Inquiry, client: AIClient, **kwargs):
    return InquiryAIService.analyze_inquiry(
        inquiry_public_id=inquiry.public_id,
        correlation_id=kwargs.pop("correlation_id", uuid4()),
        ai_request_id=kwargs.pop("ai_request_id", uuid4()),
        client=client,
        **kwargs,
    )


def test_safe_result_is_persisted_but_held_without_verified_evidence():
    inquiry = create_inquiry(1)
    client, http_client, calls = make_client()

    outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.SUCCEEDED
    assert outcome.event_candidate == "SAFE_GUIDANCE_READY"
    assert outcome.event_applied is None
    assert outcome.pending_reason == "CANONICAL_EVIDENCE_VERIFICATION_REQUIRED"
    assert outcome.saved_assessment is True
    assert outcome.saved_guidance is True
    assert len(calls) == 1
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    guidance = Guidance.objects.get(inquiry=inquiry)
    assert guidance.items.count() == 2

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 2
    assert inquiry.risk_level_code == Inquiry.RiskLevel.GENERAL
    assert inquiry.evidence_ids == []
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    http_client.close()


def test_verified_evidence_allows_safe_guidance_system_transition():
    inquiry = create_inquiry(2)
    client, http_client, _calls = make_client()

    outcome = analyze(
        inquiry,
        client,
        evidence_verifier=lambda references, _inquiry: [
            references[0]["chunk_id"]
        ],
    )

    assert outcome.event_applied == "SAFE_GUIDANCE_READY"
    assert outcome.pending_reason is None
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 3
    assert inquiry.evidence_mode == Inquiry.EvidenceMode.EXACT_MODEL
    assert len(inquiry.evidence_ids) == 1
    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert history.event_code == "SAFE_GUIDANCE_READY"
    assert history.actor is None
    assert history.changed_by_type_code == TransitionHistory.ChangedByType.SYSTEM
    assert history.state_version == 3
    http_client.close()


def test_no_evidence_result_routes_to_consultation_required():
    inquiry = create_inquiry(3)

    def no_evidence(response: dict, _request: dict) -> dict:
        response.update(
            {
                "status": "FALLBACK",
                "failure_stage": "RETRIEVING",
                "evidence_references": [],
            }
        )
        response["safety_assessment"]["requires_consultation"] = True
        response["usage_guidance"].update(
            {
                "guidance_status": "PENDING_CONSULTATION",
                "message": "No verified evidence is available; consultation is required.",
                "next_actions": ["Request a customer consultation."],
            }
        )
        return response

    client, http_client, _calls = make_client(transform=no_evidence)
    outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.NO_EVIDENCE
    assert outcome.event_applied == "NO_EVIDENCE"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.evidence_mode == Inquiry.EvidenceMode.NO_EVIDENCE
    assert inquiry.requires_fallback is True
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == "NO_EVIDENCE"
    http_client.close()


def test_followup_questions_are_saved_without_advancing_state():
    inquiry = create_inquiry(4)

    def needs_followup(response: dict, _request: dict) -> dict:
        response["missing_fields"] = [
            {
                "field_name": "occurrence_time",
                "reason": "The occurrence time was not provided.",
                "importance": "medium",
            }
        ]
        response["followup_questions"] = [
            {
                "question_id": "Q_OCCURRENCE_TIME",
                "question_text": "When did the symptom begin?",
                "target_field": "occurrence_time",
                "options": ["TODAY", "EARLIER"],
            }
        ]
        return response

    client, http_client, _calls = make_client(transform=needs_followup)
    outcome = analyze(inquiry, client)

    assert outcome.event_candidate is None
    assert outcome.event_applied is None
    assert outcome.pending_reason == "NO_STATE_EVENT_CANDIDATE"
    assert outcome.saved_questions == 1
    question = InquiryQA.objects.get(inquiry=inquiry)
    assert question.question_code == "Q_OCCURRENCE_TIME"
    assert question.answer_type_code == "SINGLE_CHOICE"
    assert question.question_options == ["TODAY", "EARLIER"]
    assert question.target_field == "occurrence_time"
    assert question.asked_by_type_code == "AI"
    assert question.source_ai_run.task_type_code == AIRun.TaskType.ANALYZE_SYMPTOM
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2
    http_client.close()


def test_danger_result_is_held_until_matched_safety_rule_ids_exist():
    inquiry = create_inquiry(10)

    def danger(response: dict, request: dict) -> dict:
        example_path = (
            DEFAULT_CONTRACT_ROOT
            / "examples"
            / "symptom-analysis"
            / "danger-detected.json"
        )
        danger_response = json.loads(
            example_path.read_text(encoding="utf-8")
        )["response"]
        for field in (
            "inquiry_id",
            "correlation_id",
            "ai_request_id",
            "state_version",
        ):
            danger_response[field] = request[field]
        return danger_response

    client, http_client, _calls = make_client(transform=danger)
    outcome = analyze(inquiry, client)

    assert outcome.event_candidate == "DANGER_DETECTED"
    assert outcome.event_applied is None
    assert outcome.pending_reason == "MATCHED_SAFETY_RULE_IDS_REQUIRED"
    assessment = SymptomAssessment.objects.get(inquiry=inquiry)
    assert assessment.risk_level_code == SymptomAssessment.RiskLevel.DANGER
    assert assessment.requires_consultation is True
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 2
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    http_client.close()


def test_selected_answer_is_forwarded_and_same_question_is_not_recreated():
    inquiry = create_inquiry(12)
    question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="Q_LEAK_LOCATION",
        question_text="Where is the leak located?",
        answer_type_code="SINGLE_CHOICE",
        answer_payload={
            "question_options": ["FILTER_HOUSING", "FLOOR"],
            "target_field": "occurrence_condition",
        },
        asked_by_type_code="RULE",
    )
    FollowUpAnswer.objects.create(
        question=question,
        answer_payload={"selected_option": "FILTER_HOUSING"},
        answered_by=inquiry.initiated_by,
    )
    text_question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=2,
        question_code="Q_OBSERVED_TIME",
        question_text="When was the symptom first observed?",
        answer_payload={"target_field": "occurrence_time"},
        asked_by_type_code="RULE",
    )
    FollowUpAnswer.objects.create(
        question=text_question,
        answer_text="This morning",
        answered_by=inquiry.initiated_by,
    )
    received_previous_answers = []

    def followup(response: dict, request: dict) -> dict:
        received_previous_answers.extend(request["previous_answers"])
        response["missing_fields"] = [
            {
                "field_name": "occurrence_condition",
                "reason": "One more condition is required.",
                "importance": "medium",
            }
        ]
        response["followup_questions"] = [
            {
                "question_id": "Q_LEAK_LOCATION",
                "question_text": "Where is the leak located?",
                "target_field": "occurrence_condition",
                "options": [],
            },
            {
                "question_id": "Q_WHEN_VISIBLE",
                "question_text": "When is the symptom visible?",
                "target_field": "occurrence_condition",
                "options": [],
            },
        ]
        return response

    client, http_client, _calls = make_client(transform=followup)
    outcome = analyze(inquiry, client)

    assert received_previous_answers == [
        {
            "question_id": "Q_LEAK_LOCATION",
            "answer_text": "FILTER_HOUSING",
        },
        {
            "question_id": "Q_OBSERVED_TIME",
            "answer_text": "This morning",
        },
    ]
    assert outcome.saved_questions == 1
    assert InquiryQA.objects.filter(inquiry=inquiry).count() == 3
    assert (
        InquiryQA.objects.filter(
            inquiry=inquiry,
            question_code="Q_LEAK_LOCATION",
        ).count()
        == 1
    )
    http_client.close()


def test_duplicate_request_replays_without_second_http_call_or_rows():
    inquiry = create_inquiry(5)
    client, http_client, calls = make_client()
    correlation_id = uuid4()
    ai_request_id = uuid4()

    first = analyze(
        inquiry,
        client,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    replay = analyze(
        inquiry,
        client,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )

    assert first.idempotent_replay is False
    assert replay.idempotent_replay is True
    assert replay.ai_run_id == first.ai_run_id
    assert replay.pending_reason == "REPLAYED_EXISTING_RESULT"
    assert len(calls) == 1
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert Guidance.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_same_request_id_with_changed_payload_is_rejected():
    inquiry = create_inquiry(6)
    client, http_client, calls = make_client()
    correlation_id = uuid4()
    ai_request_id = uuid4()
    analyze(
        inquiry,
        client,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    inquiry.raw_text = "A materially different symptom payload."
    inquiry.save(update_fields=["raw_text", "updated_at"])

    with pytest.raises(AIIdempotencyConflictError):
        analyze(
            inquiry,
            client,
            correlation_id=correlation_id,
            ai_request_id=ai_request_id,
        )

    assert len(calls) == 1
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_concurrent_unique_key_winner_is_replayed_without_http_call(
    monkeypatch,
):
    inquiry = create_inquiry(11)
    client, http_client, calls = make_client()
    original_create_run = InquiryAIService._create_run

    def create_winner_then_raise(**kwargs):
        original_create_run(**kwargs)
        raise IntegrityError("simulated concurrent unique-key winner")

    monkeypatch.setattr(
        InquiryAIService,
        "_create_run",
        staticmethod(create_winner_then_raise),
    )
    outcome = analyze(inquiry, client)

    assert outcome.idempotent_replay is True
    assert outcome.status == AIRun.Status.QUEUED
    assert outcome.pending_reason == "RUN_ALREADY_IN_PROGRESS"
    assert len(calls) == 0
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_stale_response_is_audited_without_overwriting_domain_results():
    inquiry = create_inquiry(7)

    def make_stale(response: dict, _request: dict) -> dict:
        Inquiry.objects.filter(pk=inquiry.pk).update(state_version=3)
        return response

    client, http_client, _calls = make_client(transform=make_stale)
    outcome = analyze(inquiry, client)

    assert outcome.stale is True
    assert outcome.pending_reason == "STALE_STATE_VERSION"
    run = AIRun.objects.get(inquiry=inquiry)
    assert run.status_code == AIRun.Status.SUCCEEDED
    assert run.validated_output_payload is not None
    assert not SymptomAssessment.objects.filter(inquiry=inquiry).exists()
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    assert not InquiryQA.objects.filter(inquiry=inquiry).exists()
    http_client.close()


def test_error_contract_and_timeout_are_audited_without_backend_retry():
    failed_inquiry = create_inquiry(8)

    def service_error(_response: dict, request: dict) -> dict:
        return error_payload(request)

    failed_client, failed_http_client, failed_calls = make_client(
        transform=service_error,
        status_code=503,
    )
    failed = analyze(failed_inquiry, failed_client)
    failed_run = AIRun.objects.get(inquiry=failed_inquiry)

    assert failed.status == AIRun.Status.FAILED
    assert failed.pending_reason == "AI-FAILED-01"
    assert failed_run.schema_validation_status_code == AIRun.SchemaValidationStatus.PASSED
    assert failed_run.retry_count == 0
    assert len(failed_calls) == 1
    failed_http_client.close()

    timeout_inquiry = create_inquiry(9)
    timeout_calls = []

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        timeout_calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    timeout_http_client = httpx.Client(
        transport=httpx.MockTransport(timeout_handler)
    )
    timeout_client = AIClient(
        base_url="http://ai.test",
        http_client=timeout_http_client,
    )
    timed_out = analyze(timeout_inquiry, timeout_client)
    timeout_run = AIRun.objects.get(inquiry=timeout_inquiry)

    assert timed_out.status == AIRun.Status.TIMED_OUT
    assert timed_out.pending_reason == "AI-TIMEOUT-01"
    assert timeout_run.retry_count == 0
    assert len(timeout_calls) == 1
    timeout_http_client.close()
