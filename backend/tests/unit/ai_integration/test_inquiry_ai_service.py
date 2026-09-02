"""Persistence and workflow tests for the Backend-to-AI vertical slice."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from django.test import override_settings
from django.db import IntegrityError

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.evidence.models import EvidenceLink
from apps.inquiries.models import (
    ConsultationCauseLedger,
    FollowUpAnswer,
    Guidance,
    HumanReview,
    Inquiry,
    InquiryQA,
    SymptomAssessment,
)
from apps.inquiries.services.inquiry_ai_service import InquiryAIService
from apps.inquiries.services.inquiry_service import InquiryService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from apps.workflow.models import TransitionHistory
from integrations.ai.client import AIClient
from integrations.ai.exceptions import AIIdempotencyConflictError
from integrations.ai.schema_validator import (
    DEFAULT_CONTRACT_ROOT,
    AIContractValidator,
)
from common.json_integrity import canonical_json_sha256


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
    if "model_code" in response:
        response["model_code"] = request_payload["model_code"]
    return response


def internal_envelope_payload(request_payload: dict) -> dict:
    example_path = (
        DEFAULT_CONTRACT_ROOT
        / "examples"
        / "internal"
        / "analysis-consultation-envelope-refrigerant.json"
    )
    envelope = json.loads(example_path.read_text(encoding="utf-8"))[
        "response"
    ]
    analysis = envelope["analysis_result"]
    ledger = envelope["consultation_cause_ledger"]
    for field in (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
        "model_code",
    ):
        analysis[field] = request_payload[field]
        ledger[field] = request_payload[field]
    ledger["analysis_result_sha256"] = canonical_json_sha256(analysis)
    ledger["ledger_sha256"] = canonical_json_sha256(
        {key: value for key, value in ledger.items() if key != "ledger_sha256"}
    )
    return envelope


class ContractV4CompatValidator:
    """Validate owner-proposed 4.0 fields over the current 3.0 baseline."""

    allowed_fallback_reasons = {
        "RUNTIME_PRODUCT_NOT_APPROVED",
        "NO_EVIDENCE",
        "MCP_TOOL_FAILURE",
        "OUTPUT_SCHEMA_INVALID",
        "UNSPECIFIED_FALLBACK",
    }

    def __init__(self) -> None:
        self._current = AIContractValidator()

    def validate_request(self, payload: dict) -> None:
        self._current.validate_request(payload)

    def validate_success_response(self, payload: dict) -> None:
        assert isinstance(payload.get("model_code"), str)
        reason = payload.get("fallback_reason_code")
        if payload["status"] == "FALLBACK":
            assert reason in self.allowed_fallback_reasons
        else:
            assert reason is None
        if self._current.contract_version("success") == "4.0.0":
            self._current.validate_success_response(payload)
            return
        legacy = deepcopy(payload)
        legacy.pop("model_code")
        legacy.pop("fallback_reason_code")
        self._current.validate_success_response(legacy)

    def validate_error_response(self, payload: dict) -> None:
        self._current.validate_error_response(payload)

    @staticmethod
    def contract_version(_kind: str = "request") -> str:
        return "4.0.0"


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


def make_client(*, transform=None, status_code: int = 200, validator=None):
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
            validator=validator,
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


def cancel_inquiry(inquiry: Inquiry, *, key: str) -> None:
    InquiryService.cancel(
        actor=inquiry.initiated_by,
        inquiry_public_id=inquiry.public_id,
        validated_data={
            "state_version": inquiry.state_version,
            "reason_code": Inquiry.CancellationReason.CUSTOMER_REQUEST,
            "reason_detail": None,
        },
        idempotency_key=key,
        correlation_id=uuid4(),
    )


def test_safe_result_without_verified_evidence_routes_to_consultation():
    inquiry = create_inquiry(1)
    client, http_client, calls = make_client()

    outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.SUCCEEDED
    assert outcome.event_candidate == "SAFE_GUIDANCE_READY"
    assert outcome.event_applied == "NO_EVIDENCE"
    assert outcome.pending_reason is None
    assert outcome.saved_assessment is True
    assert outcome.saved_guidance is False
    assert len(calls) == 1
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    assert not HumanReview.objects.filter(inquiry=inquiry).exists()

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.risk_level_code == Inquiry.RiskLevel.GENERAL
    assert (
        inquiry.usage_guidance_status
        == Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
    )
    assert inquiry.evidence_ids == []
    assert inquiry.evidence_mode == Inquiry.EvidenceMode.PARTIAL_EVIDENCE
    assert inquiry.requires_fallback is True
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == "NO_EVIDENCE"
    actions = AllowedActionResolver.resolve(
        context=AllowedActionContext.from_models(
            inquiry=inquiry,
            actor=inquiry.initiated_by,
            consultation=None,
            visit=None,
            open_followup_questions=False,
        )
    )
    assert [action["code"] for action in actions] == [
        "REQUEST_CONSULTATION",
        "CANCEL_INQUIRY",
    ]
    http_client.close()


def test_internal_envelope_persists_analysis_and_cause_ledger_atomically():
    inquiry = create_inquiry(201)

    def envelope(_response: dict, request: dict) -> dict:
        return internal_envelope_payload(request)

    client, http_client, calls = make_client(transform=envelope)

    outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.SUCCEEDED
    assert outcome.saved_assessment is True
    assert outcome.saved_cause_ledger is True
    assert outcome.event_candidate == "DANGER_DETECTED"
    assert outcome.event_applied == "DANGER_DETECTED"
    assert len(calls) == 1

    run = AIRun.objects.get(inquiry=inquiry)
    ledger = ConsultationCauseLedger.objects.get(inquiry=inquiry, ai_run=run)
    assessment = SymptomAssessment.objects.get(inquiry=inquiry, ai_run=run)
    assert "analysis_result" not in run.validated_output_payload
    assert run.validated_output_payload["safety_assessment"][
        "matched_safety_rule_ids"
    ] == ["SAFETY-REFRIGERANT-001"]
    assert ledger.contract_version == "1.0.0"
    assert ledger.ai_request_id == run.idempotency_key
    assert ledger.analysis_result_sha256 == canonical_json_sha256(
        run.validated_output_payload
    )
    assert ledger.causes[0]["lock_class"] == "SAFETY_LOCKED"
    assert assessment.risk_level_code == SymptomAssessment.RiskLevel.DANGER
    assert not HumanReview.objects.filter(inquiry=inquiry).exists()

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_invalid_internal_envelope_is_redacted_and_stores_no_domain_rows():
    inquiry = create_inquiry(202)

    def invalid_envelope(_response: dict, request: dict) -> dict:
        envelope = internal_envelope_payload(request)
        envelope["consultation_cause_ledger"][
            "analysis_result_sha256"
        ] = "f" * 64
        return envelope

    client, http_client, _calls = make_client(transform=invalid_envelope)

    outcome = analyze(inquiry, client)

    run = AIRun.objects.get(inquiry=inquiry)
    inquiry.refresh_from_db()
    assert outcome.status == AIRun.Status.FAILED
    assert outcome.event_applied == "NO_EVIDENCE"
    assert outcome.pending_reason is None
    assert run.raw_output_text == "[REDACTED_INVALID_AI_RESPONSE]"
    assert run.validated_output_payload is None
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.evidence_mode == Inquiry.EvidenceMode.NO_EVIDENCE
    assert not SymptomAssessment.objects.filter(inquiry=inquiry).exists()
    assert not ConsultationCauseLedger.objects.filter(inquiry=inquiry).exists()
    assert not HumanReview.objects.filter(inquiry=inquiry).exists()
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == "NO_EVIDENCE"
    http_client.close()


def test_cause_ledger_verifier_failure_rolls_back_entire_domain_bundle():
    inquiry = create_inquiry(203)

    def envelope(_response: dict, request: dict) -> dict:
        return internal_envelope_payload(request)

    client, http_client, _calls = make_client(transform=envelope)

    outcome = analyze(
        inquiry,
        client,
        cause_ledger_verifier=lambda _ledger, _inquiry: [
            "synthetic canonical mismatch"
        ],
    )

    run = AIRun.objects.get(inquiry=inquiry)
    inquiry.refresh_from_db()
    assert outcome.status == AIRun.Status.FAILED
    assert outcome.event_applied == "NO_EVIDENCE"
    assert outcome.pending_reason is None
    assert run.error_code == "AI-LEDGER-PERSIST-01"
    assert run.validated_output_payload is None
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert not SymptomAssessment.objects.filter(inquiry=inquiry).exists()
    assert not ConsultationCauseLedger.objects.filter(inquiry=inquiry).exists()
    assert not HumanReview.objects.filter(inquiry=inquiry).exists()
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == "NO_EVIDENCE"
    http_client.close()


def test_internal_envelope_replay_does_not_duplicate_ledger_or_http_call():
    inquiry = create_inquiry(204)

    def envelope(_response: dict, request: dict) -> dict:
        return internal_envelope_payload(request)

    client, http_client, calls = make_client(transform=envelope)
    correlation_id = uuid4()
    ai_request_id = uuid4()

    first = analyze(
        inquiry,
        client,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )
    run = AIRun.objects.get(public_id=first.ai_run_id)
    replay = InquiryAIService._replay_or_conflict(
        run,
        input_digest=run.input_sha256,
        request_payload=run.input_payload,
        validator=AIContractValidator(),
    )

    assert first.saved_cause_ledger is True
    assert replay.idempotent_replay is True
    assert replay.ai_run_id == first.ai_run_id
    assert len(calls) == 1
    assert ConsultationCauseLedger.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_evidence_verifier_failure_is_fail_closed_without_publication_bundle():
    inquiry = create_inquiry(101)
    client, http_client, _calls = make_client()
    publication_state_seen_by_verifier = []

    def unavailable_verifier(_references, _inquiry):
        publication_state_seen_by_verifier.append(
            (
                Guidance.objects.filter(inquiry=inquiry).exists(),
                HumanReview.objects.filter(inquiry=inquiry).exists(),
            )
        )
        raise RuntimeError("synthetic verifier unavailable")

    outcome = analyze(
        inquiry,
        client,
        evidence_verifier=unavailable_verifier,
    )

    inquiry.refresh_from_db()
    assert outcome.status == AIRun.Status.SUCCEEDED
    assert outcome.event_applied == "NO_EVIDENCE"
    assert outcome.pending_reason is None
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.evidence_ids == []
    assert inquiry.requires_fallback is True
    assert publication_state_seen_by_verifier == [(False, False)]
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    assert not HumanReview.objects.filter(inquiry=inquiry).exists()
    assert EvidenceLink.objects.filter(inquiry=inquiry).count() == 0
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == "NO_EVIDENCE"
    http_client.close()


@override_settings(
    AI_MODEL_PROVIDER="openai",
    AI_MODEL_NAME="gpt-4.1-mini",
    AI_PROMPT_VERSION="e2e-baseline-v1",
)
def test_airun_persists_runtime_identity_from_backend_settings():
    inquiry = create_inquiry(102)
    client, http_client, _calls = make_client()

    outcome = analyze(inquiry, client)

    run = AIRun.objects.get(public_id=outcome.ai_run_id)
    assert run.model_provider == "openai"
    assert run.model_name == "gpt-4.1-mini"
    assert run.prompt_version == "e2e-baseline-v1"
    assert run.model_config == {
        "mode": "local",
        "timeout_seconds": 30.0,
        "backend_max_retries": 0,
    }
    http_client.close()


def test_cancelled_before_run_creation_records_cancelled_audit_without_http():
    inquiry = create_inquiry(90)
    cancel_inquiry(inquiry, key="cancel-before-ai-run")
    inquiry.refresh_from_db()
    client, http_client, calls = make_client()

    outcome = analyze(inquiry, client)

    run = AIRun.objects.get(inquiry=inquiry)
    assert calls == []
    assert outcome.status == AIRun.Status.CANCELLED
    assert outcome.stale is True
    assert run.status_code == AIRun.Status.CANCELLED
    assert run.started_at is None
    assert not SymptomAssessment.objects.filter(inquiry=inquiry).exists()
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    http_client.close()


@pytest.mark.parametrize("upstream_status", [200, 503])
def test_cancel_during_http_prevents_late_ai_terminal_overwrite(upstream_status):
    inquiry = create_inquiry(91 + upstream_status)

    def transform(response_payload, request_payload):
        cancel_inquiry(inquiry, key=f"cancel-during-ai-{upstream_status}")
        if upstream_status == 503:
            return error_payload(request_payload)
        return response_payload

    client, http_client, calls = make_client(
        transform=transform,
        status_code=upstream_status,
    )

    outcome = analyze(inquiry, client)

    inquiry.refresh_from_db()
    run = AIRun.objects.get(inquiry=inquiry)
    assert len(calls) == 1
    assert inquiry.status_code == Inquiry.Status.CANCELLED
    assert outcome.status == AIRun.Status.CANCELLED
    assert outcome.stale is True
    assert run.status_code == AIRun.Status.CANCELLED
    assert run.error_code == "CANCELLED_BY_INQUIRY"
    assert not SymptomAssessment.objects.filter(inquiry=inquiry).exists()
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    assert not InquiryQA.objects.filter(inquiry=inquiry).exists()
    http_client.close()


def test_injected_evidence_id_cannot_bypass_backend_mapping():
    inquiry = create_inquiry(2)
    client, http_client, _calls = make_client()

    outcome = analyze(
        inquiry,
        client,
        evidence_verifier=lambda references, _inquiry: [
            references[0]["chunk_id"]
        ],
    )

    assert outcome.event_applied == "NO_EVIDENCE"
    assert outcome.pending_reason is None
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.evidence_mode == Inquiry.EvidenceMode.PARTIAL_EVIDENCE
    assert inquiry.evidence_ids == []
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    assert not HumanReview.objects.filter(inquiry=inquiry).exists()
    assert EvidenceLink.objects.filter(inquiry=inquiry).count() == 0
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == "NO_EVIDENCE"
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
        if "fallback_reason_code" in response:
            response["fallback_reason_code"] = "NO_EVIDENCE"
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
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    http_client.close()


def test_product_runtime_hold_applies_product_validation_failed_once():
    inquiry = create_inquiry(103)
    validator = ContractV4CompatValidator()
    correlation_id = uuid4()
    ai_request_id = uuid4()

    def product_hold(response: dict, request: dict) -> dict:
        response.update(
            {
                "model_code": request["model_code"],
                "status": "FALLBACK",
                "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
                "failure_stage": "RETRIEVING",
                "evidence_references": [],
            }
        )
        response["safety_assessment"].update(
            {
                "risk_level": "caution",
                "priority": "consultation_recommended",
                "requires_consultation": True,
                "matched_safety_rule_ids": [],
                "detected_risks": [],
                "safety_reason": "Public Runtime approval is pending.",
            }
        )
        response["usage_guidance"].update(
            {
                "guidance_status": "PENDING_CONSULTATION",
                "message": "Consultant review is required.",
                "restricted_functions": ["Unverified self-service guidance"],
                "next_actions": ["Request a customer consultation."],
            }
        )
        return response

    client, http_client, calls = make_client(
        transform=product_hold,
        validator=validator,
    )
    outcome = analyze(
        inquiry,
        client,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        validator=validator,
    )

    assert outcome.status == AIRun.Status.SUCCEEDED
    assert outcome.event_candidate == "PRODUCT_VALIDATION_FAILED"
    assert outcome.event_applied == "PRODUCT_VALIDATION_FAILED"
    assert outcome.pending_reason is None
    assert len(calls) == 1

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.risk_level_code == Inquiry.RiskLevel.CAUTION
    assert (
        inquiry.usage_guidance_status
        == Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
    )
    assert inquiry.requires_fallback is True
    assert inquiry.evidence_ids == []
    assert not Guidance.objects.filter(inquiry=inquiry).exists()

    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert history.event_code == "PRODUCT_VALIDATION_FAILED"
    assert history.from_state == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert history.to_state == Inquiry.Status.CONSULTATION_REQUIRED
    assert history.state_version == 3
    assert history.changed_by_type_code == TransitionHistory.ChangedByType.SYSTEM
    assert history.actor is None
    assert history.correlation_id == correlation_id
    assert history.idempotency_key == str(ai_request_id)

    run = AIRun.objects.get(inquiry=inquiry)
    assert run.request_schema_version == "4.0.0"
    assert run.response_schema_version == "4.0.0"
    assert run.validated_output_payload["model_code"] == (
        inquiry.subscription.product_model.model_code
    )
    assert run.validated_output_payload["fallback_reason_code"] == (
        "RUNTIME_PRODUCT_NOT_APPROVED"
    )

    replay = InquiryAIService._replay_or_conflict(
        run,
        input_digest=run.input_sha256,
        request_payload=run.input_payload,
        validator=validator,
    )
    assert replay.idempotent_replay is True
    assert replay.event_candidate == "PRODUCT_VALIDATION_FAILED"
    assert replay.event_applied is None
    assert replay.stale is True
    assert replay.pending_reason == "STALE_STATE_VERSION"
    assert len(calls) == 1
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_product_runtime_hold_preserves_valid_danger_total_stop():
    inquiry = create_inquiry(104)
    validator = ContractV4CompatValidator()

    def dangerous_product_hold(_response: dict, request: dict) -> dict:
        example_path = (
            DEFAULT_CONTRACT_ROOT
            / "examples"
            / "symptom-analysis"
            / "danger-detected.json"
        )
        response = json.loads(example_path.read_text(encoding="utf-8"))[
            "response"
        ]
        for field in (
            "inquiry_id",
            "correlation_id",
            "ai_request_id",
            "state_version",
            "model_code",
        ):
            response[field] = request[field]
        response.update(
            {
                "status": "FALLBACK",
                "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
                "failure_stage": "VALIDATING",
                "evidence_references": [],
            }
        )
        return response

    client, http_client, _calls = make_client(
        transform=dangerous_product_hold,
        validator=validator,
    )
    outcome = analyze(
        inquiry,
        client,
        validator=validator,
    )

    assert outcome.event_candidate == "PRODUCT_VALIDATION_FAILED"
    assert outcome.event_applied == "PRODUCT_VALIDATION_FAILED"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.risk_level_code == Inquiry.RiskLevel.DANGER
    assert (
        inquiry.usage_guidance_status
        == Inquiry.UsageGuidanceStatus.TOTAL_STOP
    )
    assert inquiry.requires_fallback is True
    http_client.close()


def test_other_contract_v4_fallback_routes_fail_closed_to_consultation():
    inquiry = create_inquiry(105)
    validator = ContractV4CompatValidator()

    def mcp_failure(response: dict, request: dict) -> dict:
        response.update(
            {
                "model_code": request["model_code"],
                "status": "FALLBACK",
                "fallback_reason_code": "MCP_TOOL_FAILURE",
                "failure_stage": "VALIDATING",
                "evidence_references": [],
            }
        )
        return response

    client, http_client, _calls = make_client(
        transform=mcp_failure,
        validator=validator,
    )
    outcome = analyze(inquiry, client, validator=validator)

    assert outcome.event_candidate is None
    assert outcome.event_applied == "NO_EVIDENCE"
    assert outcome.pending_reason is None
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.requires_fallback is True
    assert inquiry.evidence_mode == Inquiry.EvidenceMode.NO_EVIDENCE
    assert (
        inquiry.usage_guidance_status
        == Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
    )
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
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


def test_registered_danger_rules_apply_consultation_required_transition():
    inquiry = create_inquiry(10)
    correlation_id = uuid4()
    ai_request_id = uuid4()

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
        if "model_code" in danger_response:
            danger_response["model_code"] = request["model_code"]
        return danger_response

    client, http_client, _calls = make_client(transform=danger)
    outcome = analyze(
        inquiry,
        client,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
    )

    assert outcome.event_candidate == "DANGER_DETECTED"
    assert outcome.event_applied == "DANGER_DETECTED"
    assert outcome.pending_reason is None
    assessment = SymptomAssessment.objects.get(inquiry=inquiry)
    assert assessment.risk_level_code == SymptomAssessment.RiskLevel.DANGER
    assert assessment.requires_consultation is True
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert history.event_code == "DANGER_DETECTED"
    assert history.state_version == 3
    consultation = Consultation.objects.get(inquiry=inquiry)
    assert consultation.status == Consultation.Status.WAITING
    assert consultation.consultant is None
    assert consultation.state_version == 3
    assert consultation.correlation_id == correlation_id
    assert consultation.idempotency_key == f"ai-danger-{ai_request_id}"

    run = AIRun.objects.get(public_id=outcome.ai_run_id)
    replay = InquiryAIService._replay_or_conflict(
        run,
        input_digest=run.input_sha256,
        request_payload=run.input_payload,
        validator=AIContractValidator(),
    )
    assert replay.idempotent_replay is True
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()


def test_hot_water_heater_partial_stop_is_persisted_and_escalated():
    inquiry = create_inquiry(110)

    def hot_water_heater(response: dict, _request: dict) -> dict:
        response["safety_assessment"].update(
            {
                "risk_level": "danger",
                "priority": "priority_consultation",
                "requires_consultation": True,
                "matched_safety_rule_ids": [
                    "SAFETY-HOT-WATER-HEATER-001"
                ],
                "detected_risks": ["온수 히터 이상"],
                "safety_reason": "승인된 온수 히터 위험 Rule이 감지되었습니다.",
            }
        )
        response["usage_guidance"].update(
            {
                "guidance_status": "PARTIAL_STOP",
                "message": "온수 사용을 중단하고 상담을 연결합니다.",
                "restricted_functions": ["온수 출수 및 음용 중지"],
                "next_actions": [
                    "온수 기능 사용과 온수 음용을 중단하세요.",
                    "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
                ],
            }
        )
        response["evidence_references"] = []
        return response

    client, http_client, _calls = make_client(transform=hot_water_heater)

    outcome = analyze(inquiry, client)

    assert outcome.event_candidate == "DANGER_DETECTED"
    assert outcome.event_applied == "DANGER_DETECTED"
    assessment = SymptomAssessment.objects.get(inquiry=inquiry)
    assert assessment.risk_level_code == SymptomAssessment.RiskLevel.DANGER
    assert assessment.usage_guidance_status == "PARTIAL_STOP"
    assert assessment.rule_result["matched_safety_rule_ids"] == [
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.usage_guidance_status == "PARTIAL_STOP"
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
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
    assert replay.stale is True
    assert replay.pending_reason == "STALE_STATE_VERSION"
    assert len(calls) == 1
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert not Guidance.objects.filter(inquiry=inquiry).exists()
    http_client.close()


def test_replay_reports_stale_after_inquiry_is_cancelled_post_success():
    inquiry = create_inquiry(95)
    client, http_client, _calls = make_client()
    ai_request_id = uuid4()

    first = analyze(inquiry, client, ai_request_id=ai_request_id)
    run = AIRun.objects.get(public_id=first.ai_run_id)
    inquiry.refresh_from_db()
    cancel_inquiry(inquiry, key="cancel-after-ai-success")

    replay = InquiryAIService._replay_or_conflict(
        run,
        input_digest=run.input_sha256,
        request_payload=run.input_payload,
        validator=AIContractValidator(),
    )

    assert run.status_code == AIRun.Status.SUCCEEDED
    assert replay.idempotent_replay is True
    assert replay.stale is True
    assert replay.event_applied is None
    assert replay.pending_reason == "STALE_STATE_VERSION"
    assert SymptomAssessment.objects.filter(
        inquiry=inquiry,
        ai_run=run,
    ).exists()
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
    failed_inquiry.refresh_from_db()

    assert failed.status == AIRun.Status.FAILED
    assert failed.event_candidate is None
    assert failed.event_applied == "NO_EVIDENCE"
    assert failed.pending_reason is None
    assert (
        failed_run.schema_validation_status_code
        == AIRun.SchemaValidationStatus.PASSED
    )
    assert failed_run.retry_count == 0
    assert failed_inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert failed_inquiry.state_version == 3
    assert failed_inquiry.evidence_mode == Inquiry.EvidenceMode.NO_EVIDENCE
    assert (
        TransitionHistory.objects.get(inquiry=failed_inquiry).event_code
        == "NO_EVIDENCE"
    )
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
    timeout_correlation_id = uuid4()
    timeout_request_id = uuid4()
    original_text = timeout_inquiry.raw_text
    timed_out = analyze(
        timeout_inquiry,
        timeout_client,
        correlation_id=timeout_correlation_id,
        ai_request_id=timeout_request_id,
    )
    timeout_run = AIRun.objects.get(inquiry=timeout_inquiry)

    assert timed_out.status == AIRun.Status.TIMED_OUT
    assert timed_out.event_candidate == "AI_PROCESSING_TIMEOUT"
    assert timed_out.event_applied == "AI_PROCESSING_TIMEOUT"
    assert timed_out.pending_reason is None
    assert timeout_run.retry_count == 0
    assert timeout_run.error_code == "AI-TIMEOUT-01"
    assert len(timeout_calls) == 1
    timeout_inquiry.refresh_from_db()
    assert timeout_inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert timeout_inquiry.state_version == 3
    assert timeout_inquiry.raw_text == original_text
    assert timeout_inquiry.requires_fallback is True
    assert (
        timeout_inquiry.usage_guidance_status
        == Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
    )
    history = TransitionHistory.objects.get(inquiry=timeout_inquiry)
    assert history.event_code == "AI_PROCESSING_TIMEOUT"
    assert history.from_state == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert history.to_state == Inquiry.Status.CONSULTATION_REQUIRED
    assert history.state_version == 3
    assert history.actor_id is None
    assert history.changed_by_type_code == TransitionHistory.ChangedByType.SYSTEM
    assert history.correlation_id == timeout_correlation_id
    assert history.idempotency_key == str(timeout_request_id)
    assert not Consultation.objects.filter(inquiry=timeout_inquiry).exists()
    assert not Guidance.objects.filter(inquiry=timeout_inquiry).exists()
    assert not EvidenceLink.objects.filter(inquiry=timeout_inquiry).exists()

    replay = InquiryAIService._replay_or_conflict(
        timeout_run,
        input_digest=timeout_run.input_sha256,
        request_payload=timeout_run.input_payload,
        validator=AIContractValidator(),
    )
    assert replay.idempotent_replay is True
    assert replay.event_candidate == "AI_PROCESSING_TIMEOUT"
    assert replay.event_applied is None
    assert replay.stale is True
    assert TransitionHistory.objects.filter(inquiry=timeout_inquiry).count() == 1
    timeout_http_client.close()


def test_timeout_result_does_not_overwrite_a_newer_inquiry_version():
    inquiry = create_inquiry(109)
    calls = []

    def timeout_after_state_change(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        Inquiry.objects.filter(pk=inquiry.pk).update(state_version=3)
        raise httpx.ReadTimeout("timeout", request=request)

    http_client = httpx.Client(
        transport=httpx.MockTransport(timeout_after_state_change)
    )
    client = AIClient(base_url="http://ai.test", http_client=http_client)

    outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.TIMED_OUT
    assert outcome.event_candidate == "AI_PROCESSING_TIMEOUT"
    assert outcome.event_applied is None
    assert outcome.pending_reason == "STALE_STATE_VERSION"
    assert outcome.stale is True
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 3
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert len(calls) == 1
    http_client.close()


def test_terminal_ai_failure_does_not_overwrite_a_newer_inquiry_version():
    inquiry = create_inquiry(110)
    calls = []

    def failure_after_state_change(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        request_payload = json.loads(request.content.decode("utf-8"))
        Inquiry.objects.filter(pk=inquiry.pk).update(state_version=3)
        return httpx.Response(503, json=error_payload(request_payload))

    http_client = httpx.Client(
        transport=httpx.MockTransport(failure_after_state_change)
    )
    client = AIClient(base_url="http://ai.test", http_client=http_client)

    outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.FAILED
    assert outcome.event_applied is None
    assert outcome.pending_reason == "STALE_STATE_VERSION"
    assert outcome.stale is True
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 3
    assert not TransitionHistory.objects.filter(inquiry=inquiry).exists()
    assert not Consultation.objects.filter(inquiry=inquiry).exists()
    assert len(calls) == 1
    http_client.close()


def test_ai_lifecycle_trace_contains_only_safe_identifiers_and_outcome_fields():
    inquiry = create_inquiry(20)
    client, http_client, _calls = make_client()
    correlation_id = uuid4()
    ai_request_id = uuid4()

    with patch(
        "apps.inquiries.services.inquiry_ai_service.ai_trace_logger.info"
    ) as trace_info:
        outcome = analyze(
            inquiry,
            client,
            correlation_id=correlation_id,
            ai_request_id=ai_request_id,
        )

    assert outcome.status == AIRun.Status.SUCCEEDED
    assert [call.args[0] for call in trace_info.call_args_list] == [
        "ai_analysis_started",
        "ai_analysis_terminal",
    ]
    terminal = trace_info.call_args_list[-1].kwargs["extra"]
    assert terminal["correlation_id"] == str(correlation_id)
    assert terminal["inquiry_id"] == str(inquiry.public_id)
    assert terminal["ai_request_id"] == str(ai_request_id)
    assert terminal["ai_run_id"] == outcome.ai_run_id
    assert terminal["trace_stage"] == "ANALYSIS_TERMINAL"
    assert not {
        "raw_text",
        "input_payload",
        "validated_output_payload",
        "error_message",
    } & set(terminal)
    http_client.close()


def test_expected_ai_failure_trace_uses_safe_warning_code():
    inquiry = create_inquiry(21)

    def service_error(_response: dict, request: dict) -> dict:
        return error_payload(request)

    client, http_client, _calls = make_client(
        transform=service_error,
        status_code=503,
    )
    with patch(
        "apps.inquiries.services.inquiry_ai_service.ai_trace_logger.warning"
    ) as trace_warning:
        outcome = analyze(inquiry, client)

    assert outcome.status == AIRun.Status.FAILED
    trace_warning.assert_called_once()
    extra = trace_warning.call_args.kwargs["extra"]
    assert extra["failure_code"] == "AI-FAILED-01"
    assert extra["event_applied"] == "NO_EVIDENCE"
    assert extra["pending_reason"] is None
    assert "The AI service could not complete the request" not in str(extra)
    http_client.close()
