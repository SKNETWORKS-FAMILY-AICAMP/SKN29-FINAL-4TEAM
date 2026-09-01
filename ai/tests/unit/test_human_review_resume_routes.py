"""Protected rejected HumanReview resume API invariants."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ai.app.bootstrap import create_app
from ai.app.orchestration.hitl.checkpoint import build_hitl_thread_id
from ai.app.orchestration.hitl.reconstructed_resume import (
    ReconstructedHumanReviewResume,
)


TOKEN = "test-only-distinct-resume-token-32-bytes"


def _payload(*, review_id=None, condition: str = "합성 조건"):
    inquiry_id = uuid4()
    correlation_id = uuid4()
    decision_correlation_id = uuid4()
    ai_request_id = f"ai-resume-{uuid4().hex}"
    state_version = 4
    return {
        "contract_version": "1.0.0",
        "backend_review_id": str(review_id or uuid4()),
        "review_state_version": 2,
        "decision": "REJECT",
        "decision_correlation_id": str(decision_correlation_id),
        "source_inquiry_state_version": state_version,
        "current_inquiry_state_version": state_version + 1,
        "checkpoint_thread_id": build_hitl_thread_id(
            inquiry_id=inquiry_id,
            ai_request_id=ai_request_id,
            state_version=state_version,
        ),
        "analysis_result": {
            "inquiry_id": str(inquiry_id),
            "correlation_id": str(correlation_id),
            "ai_request_id": ai_request_id,
            "state_version": state_version,
            "model_code": "WPUJAC104DWH",
            "status": "SUCCEEDED",
            "fallback_reason_code": None,
            "failure_stage": None,
            "retry_count": 0,
            "structured_symptom": {
                "symptom_type": "출수량 저하",
                "occurrence_time": None,
                "target_water_type": "냉수",
                "occurrence_condition": condition,
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
                "safety_reason": "상담사 검토가 필요합니다.",
            },
            "usage_guidance": {
                "guidance_status": "PENDING_CONSULTATION",
                "message": "상담사 확인을 기다려 주세요.",
                "restricted_functions": [],
                "next_actions": [],
            },
            "evidence_references": [],
        },
    }


def _headers(payload, *, token: str = TOKEN):
    return {
        "X-Backend-Resume-Token": token,
        "Idempotency-Key": (
            "human-review-resume:"
            f"{payload['backend_review_id']}:{payload['review_state_version']}"
        ),
        "X-Correlation-ID": payload["decision_correlation_id"],
    }


def _fake_resume_result(*, provider_called: bool = True):
    context_synthesis = SimpleNamespace(
        status="SUCCEEDED" if provider_called else "FALLBACK",
        provider_called=provider_called,
        fallback_reason=None if provider_called else "CONFIGURATION",
    )
    return ReconstructedHumanReviewResume(
        resolution=SimpleNamespace(
            handoff=SimpleNamespace(context_synthesis=context_synthesis)
        )
    )


def test_protected_resume_runs_once_and_replay_does_not_call_provider(
    monkeypatch,
):
    from ai.app.interfaces.http.routes import human_review_resume_routes

    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "true")
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_TOKEN", TOKEN)
    monkeypatch.setenv("AI_HANDOFF_BACKEND_ENABLED", "false")
    calls = []

    def fake_resume(body):
        calls.append(body.backend_review_id)
        return _fake_resume_result()

    monkeypatch.setattr(
        human_review_resume_routes,
        "resume_rejected_review_from_backend",
        fake_resume,
    )
    payload = _payload()
    client = TestClient(create_app())

    first = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )
    replay = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )

    assert first.status_code == replay.status_code == 200
    assert len(calls) == 1
    assert first.json()["idempotent_replay"] is False
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["provider_calls"] == 1
    assert replay.json()["handoff_delivery_scheduled"] is False


def test_same_idempotency_key_with_changed_body_fails_closed(monkeypatch):
    from ai.app.interfaces.http.routes import human_review_resume_routes

    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "true")
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_TOKEN", TOKEN)
    monkeypatch.setenv("AI_HANDOFF_BACKEND_ENABLED", "false")
    calls = []
    monkeypatch.setattr(
        human_review_resume_routes,
        "resume_rejected_review_from_backend",
        lambda body: calls.append(body) or _fake_resume_result(),
    )
    payload = _payload()
    changed = {
        **payload,
        "decision_correlation_id": str(uuid4()),
    }
    client = TestClient(create_app())

    first = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )
    conflict = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=changed,
        headers=_headers(changed),
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert len(calls) == 1


def test_failed_resume_is_not_automatically_reexecuted_in_same_process(
    monkeypatch,
):
    from ai.app.interfaces.http.routes import human_review_resume_routes

    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "true")
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_TOKEN", TOKEN)
    calls = []

    def fail_once(body):
        calls.append(body.backend_review_id)
        raise RuntimeError("provider sentinel must not be exposed")

    monkeypatch.setattr(
        human_review_resume_routes,
        "resume_rejected_review_from_backend",
        fail_once,
    )
    payload = _payload()
    client = TestClient(create_app(), raise_server_exceptions=False)

    first = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )
    replay = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )

    assert first.status_code == replay.status_code == 503
    assert len(calls) == 1
    assert "provider sentinel" not in first.text
    assert "provider sentinel" not in replay.text


def test_resume_requires_enabled_feature_valid_token_and_exact_versions(
    monkeypatch,
):
    payload = _payload()
    client = TestClient(create_app())

    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "false")
    disabled = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "true")
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_TOKEN", TOKEN)
    forbidden = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload, token="wrong-token"),
    )
    stale = {
        **payload,
        "current_inquiry_state_version": payload[
            "source_inquiry_state_version"
        ],
    }
    invalid_version = client.post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=stale,
        headers=_headers(stale),
    )

    assert disabled.status_code == 503
    assert forbidden.status_code == 403
    assert invalid_version.status_code == 422
    assert (
        "/api/v1/internal/ai/human-reviews/resume"
        not in client.get("/openapi.json").json()["paths"]
    )


def test_resume_receipt_does_not_expose_structured_body_or_secret(
    monkeypatch,
):
    from ai.app.interfaces.http.routes import human_review_resume_routes

    sentinel = "OPENAI_API_KEY=secret-value-must-not-leak"
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "true")
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_TOKEN", TOKEN)
    monkeypatch.setenv("AI_HANDOFF_BACKEND_ENABLED", "false")
    monkeypatch.setattr(
        human_review_resume_routes,
        "resume_rejected_review_from_backend",
        lambda body: _fake_resume_result(provider_called=False),
    )
    payload = _payload(condition=sentinel)

    response = TestClient(create_app()).post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )

    assert response.status_code == 200
    assert sentinel not in response.text
    assert "secret-value-must-not-leak" not in response.text


@pytest.mark.parametrize(
    "model_code",
    ["WPUIAC425SNW", "WPUIAC606SNW"],
)
def test_non_activated_iac_models_remain_fail_closed_without_provider(
    monkeypatch,
    model_code,
):
    from ai.app.orchestration.hitl import reconstructed_resume

    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "true")
    monkeypatch.setenv("AI_HUMAN_REVIEW_RESUME_TOKEN", TOKEN)
    monkeypatch.setenv("AI_HANDOFF_BACKEND_ENABLED", "false")
    payload = _payload()
    payload["analysis_result"]["model_code"] = model_code
    runner_constructions = []
    monkeypatch.setattr(
        reconstructed_resume,
        "HarnessRunner",
        lambda: runner_constructions.append(model_code),
    )

    response = TestClient(
        create_app(),
        raise_server_exceptions=False,
    ).post(
        "/api/v1/internal/ai/human-reviews/resume",
        json=payload,
        headers=_headers(payload),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AI-FAILED-01"
    assert runner_constructions == []
