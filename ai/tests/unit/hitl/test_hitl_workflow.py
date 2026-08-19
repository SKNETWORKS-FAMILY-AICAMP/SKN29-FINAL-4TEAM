from uuid import UUID

import pytest

from ai.app.orchestration.hitl import (
    HumanReviewDecision,
    HumanReviewRequest,
    HumanReviewResume,
    HumanReviewStatus,
    HumanReviewWorkflow,
)
from ai.app.schemas import UsageGuidance, UsageGuidanceStatus


def _guidance(message: str = "기본 안내") -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=message,
        next_actions=["상태 확인"],
    )


def _request() -> HumanReviewRequest:
    return HumanReviewRequest(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
        ai_request_id="ai-req-hitl-001",
        state_version=7,
        model_code="WPU-JAC104",
        product_family="DIRECT_WATER_PURIFIER",
        review_reason="HARNESS_HUMAN_REVIEW:UNSUPPORTED_FUNCTION",
        verification_issue_codes=["UNSUPPORTED_FUNCTION"],
        evidence_chunk_ids=["chunk-1"],
        proposed_guidance=_guidance(),
    )


def test_interrupt_then_approve_resume_preserves_original_guidance():
    workflow = HumanReviewWorkflow()
    interrupted = workflow.start(_request())

    assert interrupted.status == HumanReviewStatus.WAITING_FOR_REVIEW
    assert interrupted.interrupt_payload["model_code"] == "WPU-JAC104"
    assert interrupted.interrupt_payload["state_version"] == 7

    resumed = workflow.resume(
        checkpoint=interrupted.checkpoint,
        response=HumanReviewResume(
            decision=HumanReviewDecision.APPROVE,
            state_version=7,
        ),
    )
    assert resumed.status == HumanReviewStatus.COMPLETED
    assert resumed.outcome.approved is True
    assert resumed.outcome.guidance.message == "기본 안내"


def test_modify_resume_uses_only_human_modified_guidance():
    workflow = HumanReviewWorkflow()
    interrupted = workflow.start(_request())
    modified = _guidance("상담사가 수정한 안내")

    resumed = workflow.resume(
        checkpoint=interrupted.checkpoint,
        response=HumanReviewResume(
            decision=HumanReviewDecision.MODIFY,
            state_version=7,
            modified_guidance=modified,
            reviewer_note="표현 수정",
        ),
    )

    assert resumed.outcome.approved is True
    assert resumed.outcome.guidance.message == "상담사가 수정한 안내"
    assert resumed.outcome.reviewer_note == "표현 수정"


def test_reject_resume_returns_no_guidance():
    workflow = HumanReviewWorkflow()
    interrupted = workflow.start(_request())

    resumed = workflow.resume(
        checkpoint=interrupted.checkpoint,
        response=HumanReviewResume(
            decision=HumanReviewDecision.REJECT,
            state_version=7,
        ),
    )

    assert resumed.outcome.approved is False
    assert resumed.outcome.guidance is None


def test_resume_fails_closed_on_state_version_mismatch():
    workflow = HumanReviewWorkflow()
    interrupted = workflow.start(_request())

    with pytest.raises(ValueError, match="state_version"):
        workflow.resume(
            checkpoint=interrupted.checkpoint,
            response=HumanReviewResume(
                decision=HumanReviewDecision.APPROVE,
                state_version=8,
            ),
        )
