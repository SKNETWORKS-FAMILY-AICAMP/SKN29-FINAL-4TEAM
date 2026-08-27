from __future__ import annotations

from contextlib import AbstractContextManager
from types import SimpleNamespace
from uuid import UUID

import ai.app.orchestration.handoff.consultation_handoff_agent as handoff_module
import ai.app.orchestration.harness.runner as runner_module
import ai.app.orchestration.hitl.resume as hitl_module
from ai.app.orchestration.harness import (
    HarnessDecision,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.hitl import (
    HumanReviewDecision,
    HumanReviewResume,
    HumanReviewStatus,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import UsageGuidance, UsageGuidanceStatus


class FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class FakeSpanContext(AbstractContextManager):
    def __init__(self, span: FakeSpan) -> None:
        self.span = span

    def __enter__(self) -> FakeSpan:
        return self.span

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []

    def start_as_current_span(self, name: str) -> FakeSpanContext:
        span = FakeSpan(name)
        self.spans.append(span)
        return FakeSpanContext(span)


def _span(tracer: FakeTracer, name: str) -> FakeSpan:
    matches = [span for span in tracer.spans if span.name == name]
    assert len(matches) == 1
    return matches[0]


def _guidance(message: str = "기본 안내") -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=message,
        next_actions=["상태 확인"],
    )


def _ctx():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
            ai_request_id="ai-req-otel-001",
            state_version=4,
        ),
        model_code="WPU-JAC104",
        structured_symptom=None,
        previous_answers=[],
        evidence_references=[],
        safety_assessment=None,
        usage_guidance=_guidance(),
        missing_fields=[],
    )


def _product() -> ProductContext:
    return ProductContext(
        model_code="WPU-JAC104",
        product_family=ProductFamily.DIRECT_WATER_PURIFIER,
        supported_functions={"cold_water", "hot_water"},
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="jac104-otel-1",
        document_title="WPU-JAC104 공식 매뉴얼",
        manual_model="WPU-JAC104",
        model_code="WPU-JAC104",
        content="span attribute로 들어가면 안 되는 공식 근거 본문",
        similarity_score=0.95,
    )


def test_timeout_runtime_emits_harness_and_handoff_spans_without_payload_leak(
    monkeypatch,
):
    harness_tracer = FakeTracer()
    handoff_tracer = FakeTracer()
    monkeypatch.setattr(runner_module, "_HARNESS_TRACER", harness_tracer)
    monkeypatch.setattr(handoff_module, "_HANDOFF_TRACER", handoff_tracer)

    result = HarnessRunner().run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )

    assert result.harness.decision == HarnessDecision.ESCALATE
    assert result.handoff is not None

    verify = _span(harness_tracer, "waterbridge.harness.verify")
    runtime = _span(harness_tracer, "waterbridge.harness.runtime")
    handoff = _span(handoff_tracer, "waterbridge.handoff.create")

    assert verify.attributes["waterbridge.harness.decision"] == "ESCALATE"
    assert (
        verify.attributes["waterbridge.harness.error_code"]
        == "AI_PROCESSING_TIMEOUT"
    )
    assert runtime.attributes["waterbridge.harness.handoff.present"] is True
    assert handoff.attributes["waterbridge.model.code"] == "WPU-JAC104"
    assert handoff.attributes["waterbridge.handoff.redaction.enabled"] is True

    serialized = repr(
        [
            verify.attributes,
            runtime.attributes,
            handoff.attributes,
        ]
    )
    for forbidden in (
        "raw_symptom",
        "system_prompt",
        "reviewer_note",
        "span attribute로 들어가면 안 되는 공식 근거 본문",
        "010-1234-5678",
        "private@example.com",
    ):
        assert forbidden not in serialized


def test_human_review_start_resume_spans_record_decision_not_reviewer_note(
    monkeypatch,
):
    harness_tracer = FakeTracer()
    hitl_tracer = FakeTracer()
    handoff_tracer = FakeTracer()
    monkeypatch.setattr(runner_module, "_HARNESS_TRACER", harness_tracer)
    monkeypatch.setattr(hitl_module, "_HITL_TRACER", hitl_tracer)
    monkeypatch.setattr(handoff_module, "_HANDOFF_TRACER", handoff_tracer)

    runner = HarnessRunner()
    initial = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )

    assert initial.harness.decision == HarnessDecision.HUMAN_REVIEW
    assert initial.human_review is not None
    assert initial.human_review.status == HumanReviewStatus.WAITING_FOR_REVIEW

    private_note = "010-1234-5678 private@example.com 검토 메모"
    resolved = runner.resume_human_review(
        ctx=_ctx(),
        product=_product(),
        interrupted=initial.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.APPROVE,
            state_version=4,
            reviewer_note=private_note,
        ),
    )

    assert resolved.guidance is not None
    assert resolved.handoff is None

    start_span = _span(hitl_tracer, "waterbridge.hitl.start")
    resume_span = _span(hitl_tracer, "waterbridge.hitl.resume")
    harness_resume = _span(
        harness_tracer,
        "waterbridge.harness.resume_review",
    )

    assert start_span.attributes["waterbridge.hitl.status"] == (
        "WAITING_FOR_REVIEW"
    )
    assert resume_span.attributes["waterbridge.hitl.decision"] == "approve"
    assert resume_span.attributes["waterbridge.hitl.reviewer_note.present"] is True
    assert resume_span.attributes["waterbridge.hitl.approved"] is True
    assert harness_resume.attributes["waterbridge.hitl.decision"] == "approve"

    serialized = repr(
        [
            start_span.attributes,
            resume_span.attributes,
            harness_resume.attributes,
        ]
    )
    assert private_note not in serialized
    assert "010-1234-5678" not in serialized
    assert "private@example.com" not in serialized


def test_span_attributes_are_metadata_only(monkeypatch):
    handoff_tracer = FakeTracer()
    harness_tracer = FakeTracer()
    monkeypatch.setattr(handoff_module, "_HANDOFF_TRACER", handoff_tracer)
    monkeypatch.setattr(runner_module, "_HARNESS_TRACER", harness_tracer)

    result = HarnessRunner().run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )

    assert result.handoff is not None
    handoff_span = _span(
        handoff_tracer,
        "waterbridge.handoff.create",
    )
    assert set(handoff_span.attributes) == {
        "waterbridge.inquiry.id",
        "waterbridge.model.code",
        "waterbridge.product.family",
        "waterbridge.handoff.safety_level",
        "waterbridge.handoff.safety_requires_consultation",
        "waterbridge.handoff.evidence_count",
        "waterbridge.handoff.questionnaire_count",
        "waterbridge.handoff.self_help_action_count",
        "waterbridge.handoff.source_chunk_count",
        "waterbridge.handoff.redaction.enabled",
        "waterbridge.handoff.context_synthesis.present",
        "waterbridge.handoff.context_synthesis.status",
    }
    
    assert (
        handoff_span.attributes[
            "waterbridge.handoff.context_synthesis.present"
        ]
        is True
    )

    assert handoff_span.attributes[
        "waterbridge.handoff.context_synthesis.status"
    ] in {"SUCCEEDED", "FALLBACK"}
