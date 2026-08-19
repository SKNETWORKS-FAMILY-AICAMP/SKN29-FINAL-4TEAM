"""Approve/modify/reject resume handling for LangGraph HITL."""

from __future__ import annotations

from enum import Enum
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...schemas import UsageGuidance
from .checkpoint import HumanReviewCheckpoint, build_hitl_thread_id, create_hitl_checkpointer
from .interrupt import HumanReviewRequest, human_review_interrupt_node


class HumanReviewDecision(str, Enum):
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"


class HumanReviewStatus(str, Enum):
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    COMPLETED = "COMPLETED"


class HumanReviewResume(BaseModel):
    """Human decision submitted by the counselor UI/backend."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: HumanReviewDecision
    state_version: int = Field(..., ge=1)
    modified_guidance: UsageGuidance | None = None
    reviewer_note: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_modify_payload(self) -> "HumanReviewResume":
        if self.decision == HumanReviewDecision.MODIFY and self.modified_guidance is None:
            raise ValueError("modify decision requires modified_guidance")
        if self.decision != HumanReviewDecision.MODIFY and self.modified_guidance is not None:
            raise ValueError("modified_guidance is allowed only for modify decision")
        return self


class HumanReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: HumanReviewDecision
    state_version: int = Field(..., ge=1)
    approved: bool
    guidance: UsageGuidance | None = None
    reviewer_note: str | None = Field(None, max_length=1000)


class HumanReviewExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HumanReviewStatus
    checkpoint: HumanReviewCheckpoint
    interrupt_payload: dict[str, Any] | None = None
    outcome: HumanReviewOutcome | None = None


class HumanReviewWorkflow:
    """Small checkpointed graph placed after Harness HUMAN_REVIEW."""

    def __init__(self, *, checkpointer=None) -> None:
        self.checkpointer = checkpointer or create_hitl_checkpointer()
        graph = StateGraph(dict)
        graph.add_node("human_review", human_review_interrupt_node)
        graph.add_node("resolve_review", self._resolve_review_node)
        graph.add_edge(START, "human_review")
        graph.add_edge("human_review", "resolve_review")
        graph.add_edge("resolve_review", END)
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def start(self, request: HumanReviewRequest) -> HumanReviewExecutionResult:
        checkpoint = self._checkpoint_for(request)
        raw = self.graph.invoke(
            {"request": request.model_dump(mode="json")},
            config=checkpoint.langgraph_config(),
        )
        return self._execution_result(raw, checkpoint)

    def resume(
        self,
        *,
        checkpoint: HumanReviewCheckpoint,
        response: HumanReviewResume,
    ) -> HumanReviewExecutionResult:
        raw = self.graph.invoke(
            Command(resume=response.model_dump(mode="json")),
            config=checkpoint.langgraph_config(),
        )
        return self._execution_result(raw, checkpoint)

    @staticmethod
    def _resolve_review_node(state: dict) -> dict:
        request = HumanReviewRequest.model_validate(state["request"])
        response = HumanReviewResume.model_validate(state["resume_payload"])
        if response.state_version != request.state_version:
            raise ValueError("human review state_version does not match the checkpointed request")

        if response.decision == HumanReviewDecision.APPROVE:
            guidance = request.proposed_guidance
            approved = True
        elif response.decision == HumanReviewDecision.MODIFY:
            guidance = response.modified_guidance
            approved = True
        else:
            guidance = None
            approved = False

        outcome = HumanReviewOutcome(
            decision=response.decision,
            state_version=response.state_version,
            approved=approved,
            guidance=guidance,
            reviewer_note=response.reviewer_note,
        )
        return {**state, "outcome": outcome.model_dump(mode="json")}

    @staticmethod
    def _checkpoint_for(request: HumanReviewRequest) -> HumanReviewCheckpoint:
        return HumanReviewCheckpoint(
            thread_id=build_hitl_thread_id(
                inquiry_id=request.inquiry_id,
                ai_request_id=request.ai_request_id,
                state_version=request.state_version,
            ),
            state_version=request.state_version,
        )

    @staticmethod
    def _execution_result(raw: dict, checkpoint: HumanReviewCheckpoint) -> HumanReviewExecutionResult:
        interrupts = raw.get("__interrupt__", ())
        if interrupts:
            first = interrupts[0]
            payload = getattr(first, "value", first)
            return HumanReviewExecutionResult(
                status=HumanReviewStatus.WAITING_FOR_REVIEW,
                checkpoint=checkpoint,
                interrupt_payload=payload,
            )

        outcome_raw = raw.get("outcome")
        if outcome_raw is None:
            raise RuntimeError("HITL graph completed without an outcome")
        return HumanReviewExecutionResult(
            status=HumanReviewStatus.COMPLETED,
            checkpoint=checkpoint,
            outcome=HumanReviewOutcome.model_validate(outcome_raw),
        )
