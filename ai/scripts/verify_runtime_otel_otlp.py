"""Verify FastAPI bootstrap -> OTLP/HTTP export for reliability spans."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from ai.app.bootstrap import create_app  # noqa: E402
from ai.app.orchestration.harness import (  # noqa: E402
    HarnessDecision,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.hitl import (  # noqa: E402
    HumanReviewDecision,
    HumanReviewResume,
    HumanReviewStatus,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk  # noqa: E402
from ai.app.schemas import UsageGuidance, UsageGuidanceStatus  # noqa: E402


PRIVATE_REVIEW_NOTE = (
    "OTLP_PRIVATE_SENTINEL 010-9876-5432 otlp-private@example.com"
)


def _guidance() -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message="OTLP runtime 검증용 안내",
        next_actions=["상태 확인"],
    )


def _ctx():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
            ai_request_id="ai-req-otel-runtime-001",
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
        chunk_id="jac104-otel-runtime-1",
        document_title="WPU-JAC104 공식 매뉴얼",
        manual_model="WPU-JAC104",
        model_code="WPU-JAC104",
        content="OTLP_PRIVATE_EVIDENCE_BODY",
        similarity_score=0.95,
    )


def _exercise_reliability_runtime() -> None:
    runner = HarnessRunner()

    escalated = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )
    assert escalated.harness.decision == HarnessDecision.ESCALATE
    assert escalated.handoff is not None

    interrupted = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )
    assert interrupted.harness.decision == HarnessDecision.HUMAN_REVIEW
    assert interrupted.human_review is not None
    assert interrupted.human_review.status == HumanReviewStatus.WAITING_FOR_REVIEW

    resolved = runner.resume_human_review(
        ctx=_ctx(),
        product=_product(),
        interrupted=interrupted.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.APPROVE,
            state_version=4,
            reviewer_note=PRIVATE_REVIEW_NOTE,
        ),
    )
    assert resolved.guidance is not None
    assert resolved.handoff is None


def main() -> int:
    app = create_app()
    assert app.title == "SK Watercare AI Service"

    with TestClient(app):
        _exercise_reliability_runtime()

    print("OTLP_RUNTIME_SENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
