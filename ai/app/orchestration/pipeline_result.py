"""파이프라인 실행 결과 Wrapper 모듈."""

from typing import Literal

from pydantic import BaseModel, Field
from ..retrieval import RetrievalOutcome
from ..schemas import AiExecutionStatus, AiStage, SymptomAnalysisResult, UsageGuidanceStatus
from .agents.contracts import MultiAgentRunMetadata
from .pipeline_context import PipelineContext


class PipelineResult(BaseModel):
    """파이프라인 반환 결과 Wrapper"""
    success: bool = Field(True, description="파이프라인 정상 완수 여부")
    context: PipelineContext = Field(..., description="실행 완료된 Context")
    runtime_name: Literal["single_rag", "multi_agent"] = Field(
        "single_rag",
        description="내부 Runtime 종류. 공개 AI 응답에는 포함하지 않음",
    )
    multi_agent_metadata: MultiAgentRunMetadata | None = Field(
        None,
        description="Multi-Agent Handoff 내부 증거. 공개 AI 응답에는 포함하지 않음",
    )

    def to_analysis_result(self) -> SymptomAnalysisResult:
        """SymptomAnalysisResult DTO 변환"""
        ctx = self.context
        is_no_evidence_fallback = (
            ctx.retrieval_outcome == RetrievalOutcome.NO_MATCH
            and not ctx.evidence_references
            and not ctx.awaiting_customer_input
            and ctx.usage_guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
        )
        return SymptomAnalysisResult(
            inquiry_id=ctx.trace_context.inquiry_id,
            correlation_id=ctx.trace_context.correlation_id,
            ai_request_id=ctx.trace_context.ai_request_id,
            state_version=ctx.trace_context.state_version,
            status=AiExecutionStatus.FALLBACK if is_no_evidence_fallback else AiExecutionStatus.SUCCEEDED,
            failure_stage=AiStage.RETRIEVING if is_no_evidence_fallback else None,
            retry_count=ctx.retry_count,
            structured_symptom=ctx.structured_symptom,
            missing_fields=ctx.missing_fields,
            followup_questions=ctx.followup_questions,
            safety_assessment=ctx.safety_assessment,
            usage_guidance=ctx.usage_guidance,
            evidence_references=ctx.evidence_references,
        )
