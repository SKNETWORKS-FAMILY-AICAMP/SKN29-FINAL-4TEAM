"""파이프라인 실행 결과 Wrapper 모듈."""

from pydantic import BaseModel, Field
from ..schemas import SymptomAnalysisResult
from .pipeline_context import PipelineContext


class PipelineResult(BaseModel):
    """파이프라인 반환 결과 Wrapper"""
    success: bool = Field(True, description="파이프라인 정상 완수 여부")
    context: PipelineContext = Field(..., description="실행 완료된 Context")

    def to_analysis_result(self) -> SymptomAnalysisResult:
        """SymptomAnalysisResult DTO 변환"""
        ctx = self.context
        return SymptomAnalysisResult(
            inquiry_id=ctx.trace_context.inquiry_id,
            correlation_id=ctx.trace_context.correlation_id,
            structured_symptom=ctx.structured_symptom,
            missing_fields=[],
            followup_questions=[],
            safety_assessment=ctx.safety_assessment,
            usage_guidance=ctx.usage_guidance,
            evidence_references=ctx.evidence_references,
        )
