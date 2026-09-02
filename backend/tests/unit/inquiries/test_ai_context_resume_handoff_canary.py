"""Guard and orchestration tests for the automatic Context Canary."""

from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.accounts.models import User
from apps.inquiries.management.commands.run_ai_context_resume_handoff_canary import (
    Command,
)
from apps.inquiries.models import HumanReview, Inquiry
from apps.inquiries.services.human_review_service import HumanReviewService
from apps.inquiries.services.inquiry_transition_service import (
    InquiryTransitionService,
)
from tests.unit.inquiries.test_ai_context_e2e_fixture import (
    invoke,
    seed_canonical_dependency,
)


pytestmark = pytest.mark.django_db
RELEASE_SHA = "a" * 40
TOKEN = "test-only-protected-token-at-least-32-bytes"


def _runtime(monkeypatch) -> None:
    monkeypatch.setenv("RELEASE_SHA", RELEASE_SHA)


@override_settings(
    AI_SERVICE_MODE="local",
    AI_SERVICE_BASE_URL="http://ai:8001",
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
    AI_HANDOFF_INTERNAL_TOKEN=TOKEN,
)
def test_check_mode_accepts_only_fresh_official_jac104_fixture(monkeypatch):
    _runtime(monkeypatch)
    seed_canonical_dependency()
    fixture = invoke("auto-canary-check-001", "--apply")
    output = StringIO()

    call_command(
        "run_ai_context_resume_handoff_canary",
        "--inquiry-id",
        fixture["inquiry_id"],
        "--expected-release-sha",
        RELEASE_SHA,
        "--json",
        stdout=output,
    )

    result = json.loads(output.getvalue())
    assert result["overall_status"] == "READY_FOR_APPLY"
    assert result["writes_performed"] is False
    inquiry = Inquiry.objects.get(public_id=fixture["inquiry_id"])
    assert inquiry.status_code == Inquiry.Status.DRAFT
    assert inquiry.state_version == 1


@override_settings(
    AI_SERVICE_MODE="local",
    AI_SERVICE_BASE_URL="http://ai:8001",
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
    AI_HANDOFF_INTERNAL_TOKEN=TOKEN,
)
def test_consumed_fixture_is_rejected_before_any_new_execution(monkeypatch):
    _runtime(monkeypatch)
    seed_canonical_dependency()
    fixture = invoke("auto-canary-consumed-001", "--apply")
    inquiry = Inquiry.objects.get(public_id=fixture["inquiry_id"])
    inquiry.status_code = Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    inquiry.state_version = 2
    inquiry.save(update_fields=["status_code", "state_version", "updated_at"])

    with pytest.raises(CommandError, match="이미 소비"):
        call_command(
            "run_ai_context_resume_handoff_canary",
            "--inquiry-id",
            fixture["inquiry_id"],
            "--expected-release-sha",
            RELEASE_SHA,
            "--apply",
        )


@override_settings(
    AI_SERVICE_MODE="local",
    AI_SERVICE_BASE_URL="http://ai:8001",
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
    AI_HANDOFF_INTERNAL_TOKEN=TOKEN,
)
def test_apply_orchestrates_one_reject_then_two_read_only_replays(
    monkeypatch,
):
    _runtime(monkeypatch)
    seed_canonical_dependency()
    call_command("seed_demo_accounts")
    fixture = invoke("auto-canary-run-001", "--apply")
    review_id = uuid4()
    handoff_id = uuid4()
    consultation_id = uuid4()
    submit_calls = []
    decision_calls = []
    replay_calls = []
    stable_counts = {
        "ai_runs": 1,
        "consultations": 1,
        "handoffs": 1,
        "human_reviews": 1,
        "resume_dispatches": 1,
    }

    def fake_submit(cls, **kwargs):
        del cls
        submit_calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            data={"idempotent_replay": False},
        )

    def fake_decide(cls, **kwargs):
        del cls
        decision_calls.append(kwargs)
        return SimpleNamespace(
            status_code=200,
            data={"idempotent_replay": len(decision_calls) == 2},
        )

    monkeypatch.setattr(Command, "_require_postgresql", staticmethod(lambda: None))
    monkeypatch.setattr(Command, "_assert_baseline", staticmethod(lambda inquiry: None))
    monkeypatch.setattr(
        InquiryTransitionService,
        "submit_symptom",
        classmethod(fake_submit),
    )
    monkeypatch.setattr(
        HumanReviewService,
        "decide",
        classmethod(fake_decide),
    )
    monkeypatch.setattr(
        Command,
        "_assert_initial_review",
        staticmethod(
            lambda _inquiry_id: (
                SimpleNamespace(pk=7, idempotency_key="ai-request-test"),
                SimpleNamespace(public_id=review_id),
                2,
            )
        ),
    )
    dispatch = SimpleNamespace(
        context_synthesis_status="SUCCEEDED",
        fallback_reason=None,
        provider_calls=1,
        attempt_count=1,
        refresh_from_db=lambda: None,
    )
    handoff = SimpleNamespace(
        public_id=handoff_id,
        payload_sha256="b" * 64,
    )
    consultation = SimpleNamespace(public_id=consultation_id)
    monkeypatch.setattr(
        Command,
        "_assert_automatic_result",
        classmethod(
            lambda cls, **kwargs: (dispatch, handoff, consultation)
        ),
    )
    monkeypatch.setattr(
        Command,
        "_counts",
        staticmethod(lambda _inquiry_id: dict(stable_counts)),
    )
    monkeypatch.setattr(
        Command,
        "_assert_counts_unchanged",
        classmethod(lambda cls, inquiry_id, **kwargs: None),
    )
    monkeypatch.setattr(
        Command,
        "_replay_handoff_http",
        staticmethod(
            lambda target: replay_calls.append(target)
            or {
                "handoff_id": str(handoff_id),
                "idempotent_replay": True,
            }
        ),
    )
    output = StringIO()

    call_command(
        "run_ai_context_resume_handoff_canary",
        "--inquiry-id",
        fixture["inquiry_id"],
        "--expected-release-sha",
        RELEASE_SHA,
        "--apply",
        "--json",
        stdout=output,
    )

    result = json.loads(output.getvalue())
    assert result["overall_status"] == "AWS_AUTO_CONTEXT_HANDOFF_PASS"
    assert result["provider_calls"] == 1
    assert result["context_agent_calls"] == 1
    assert result["initial_context_agent_calls"] == 0
    assert len(submit_calls) == 1
    assert len(decision_calls) == 2
    assert decision_calls[0]["validated_data"] == decision_calls[1][
        "validated_data"
    ]
    assert decision_calls[0]["idempotency_key"] == decision_calls[1][
        "idempotency_key"
    ]
    assert decision_calls[0]["validated_data"]["decision"] == (
        HumanReview.Decision.REJECT
    )
    assert replay_calls == [handoff]
    assert User.objects.filter(
        username="DEMO-CONSULTANT-001",
        is_synthetic=True,
    ).exists()


def test_safe_handoff_payload_rejects_unapproved_or_sensitive_content():
    safe = {
        "routing_reason": "FAIL_CLOSED_CONSULTATION",
        "escalation_reason": "HUMAN_REVIEW_REJECTED",
        "evidence": [{"chunk_id": "chunk-1"}],
        "source_chunk_ids": ["chunk-1"],
        "context_synthesis": {
            "status": "SUCCEEDED",
            "fallback_reason": None,
            "brief": {
                "evidence_based_findings": [
                    {
                        "text": "승인 근거 요약",
                        "source_chunk_ids": ["chunk-1"],
                    }
                ]
            },
        },
    }
    Command._assert_safe_handoff_payload(
        safe,
        customer_raw_text="합성 고객 원문",
    )

    outside = json.loads(json.dumps(safe))
    outside["context_synthesis"]["brief"]["evidence_based_findings"][0][
        "source_chunk_ids"
    ] = ["chunk-2"]
    with pytest.raises(CommandError, match="Evidence"):
        Command._assert_safe_handoff_payload(
            outside,
            customer_raw_text="합성 고객 원문",
        )

    exposed = json.loads(json.dumps(safe))
    exposed["debug_prompt"] = "must not appear"
    with pytest.raises(CommandError, match="보호 필드"):
        Command._assert_safe_handoff_payload(
            exposed,
            customer_raw_text="합성 고객 원문",
        )


@override_settings(
    AI_SERVICE_MODE="mock",
    AI_SERVICE_BASE_URL="http://ai:8001",
    AI_HUMAN_REVIEW_RESUME_ENABLED=False,
    AI_HUMAN_REVIEW_RESUME_TOKEN="",
    AI_HANDOFF_INTERNAL_TOKEN="",
)
def test_runtime_guard_rejects_wrong_release_and_disabled_modes(monkeypatch):
    monkeypatch.setenv("RELEASE_SHA", "b" * 40)
    with pytest.raises(CommandError, match="Release SHA"):
        Command._assert_runtime(expected_sha=RELEASE_SHA)

    monkeypatch.setenv("RELEASE_SHA", RELEASE_SHA)
    with pytest.raises(CommandError, match="HTTP 모드"):
        Command._assert_runtime(expected_sha=RELEASE_SHA)


@override_settings(
    AI_SERVICE_MODE="local",
    AI_SERVICE_BASE_URL="http://127.0.0.1:8001",
    AI_HUMAN_REVIEW_RESUME_ENABLED=True,
    AI_HUMAN_REVIEW_RESUME_TOKEN=TOKEN,
    AI_HANDOFF_INTERNAL_TOKEN=TOKEN,
)
def test_runtime_guard_rejects_non_internal_ai_endpoint(monkeypatch):
    monkeypatch.setenv("RELEASE_SHA", RELEASE_SHA)

    with pytest.raises(CommandError, match="내부 Runtime"):
        Command._assert_runtime(expected_sha=RELEASE_SHA)
