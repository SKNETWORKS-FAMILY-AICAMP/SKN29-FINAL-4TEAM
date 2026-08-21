"""AI 파이프라인 통합 응답 Pydantic 데이터 모델."""

from enum import Enum
from typing import List, Literal, Optional
from pydantic import Field, model_validator
from uuid import UUID
from .common import AiExecutionStatus, AiStage, ContractModel
from .guidance import UsageGuidance
from .retrieval import EvidenceReference
from .safety import SafetyAssessment
from .symptom import FollowUpQuestion, MissingField, StructuredSymptom


AnalysisFailureStage = Literal[
    AiStage.STRUCTURING,
    AiStage.CHECKING_MISSING_FIELDS,
    AiStage.SAFETY_CHECK,
    AiStage.RETRIEVING,
    AiStage.RERANKING,
    AiStage.GENERATING,
    AiStage.VALIDATING,
    AiStage.FAILED,
    AiStage.CANCELLED,
]


class FallbackReasonCode(str, Enum):
    """Backend가 상태 전이 후보를 안전하게 판별하는 공개 Fallback 사유."""

    RUNTIME_PRODUCT_NOT_APPROVED = "RUNTIME_PRODUCT_NOT_APPROVED"
    NO_EVIDENCE = "NO_EVIDENCE"
    MCP_TOOL_FAILURE = "MCP_TOOL_FAILURE"
    OUTPUT_SCHEMA_INVALID = "OUTPUT_SCHEMA_INVALID"
    UNSPECIFIED_FALLBACK = "UNSPECIFIED_FALLBACK"


class SymptomAnalysisResult(ContractModel):
    """증상 분석 통합 파이프라인 결과 모델"""
    inquiry_id: UUID = Field(..., description="Backend가 발급한 Public UUID")
    correlation_id: UUID = Field(..., description="Backend가 발급한 요청 추적 UUID")
    ai_request_id: str = Field(..., min_length=1, max_length=100, description="요청에서 받은 AI 호출 멱등 식별자")
    state_version: int = Field(..., ge=1, description="요청에서 받은 호출 시작 시점 상태 버전")
    model_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="AI가 판정 대상으로 사용한 Exact 제품 코드",
    )
    status: AiExecutionStatus = Field(AiExecutionStatus.SUCCEEDED, description="AI 실행 결과 상태")
    fallback_reason_code: Optional[FallbackReasonCode] = Field(
        ...,
        description="FALLBACK의 기계 판독 사유. SUCCEEDED이면 null",
    )
    failure_stage: Optional[AnalysisFailureStage] = Field(None, description="Fallback 발생 단계")
    retry_count: int = Field(0, ge=0, le=1, description="AI 내부 재시도 횟수")
    structured_symptom: StructuredSymptom = Field(..., description="구조화 증상 결과")
    missing_fields: List[MissingField] = Field(default_factory=list, description="추가 파악이 필요한 누락 필드 목록")
    followup_questions: List[FollowUpQuestion] = Field(default_factory=list, description="생성된 추가 질문 목록")
    safety_assessment: SafetyAssessment = Field(..., description="위험도 및 안전 평가 결과")
    usage_guidance: UsageGuidance = Field(..., description="현재 정수기 사용 안내 상태 및 다음 행동")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, description="공식 매뉴얼/FAQ 근거 참조 목록")

    @model_validator(mode="after")
    def validate_fallback_reason(self) -> "SymptomAnalysisResult":
        """실행 상태와 공개 Fallback 사유의 동시 누락·오표기를 차단한다."""

        if (
            self.status == AiExecutionStatus.FALLBACK
            and self.fallback_reason_code is None
        ):
            raise ValueError("FALLBACK에는 fallback_reason_code가 필요합니다.")
        if (
            self.status == AiExecutionStatus.SUCCEEDED
            and self.fallback_reason_code is not None
        ):
            raise ValueError("SUCCEEDED의 fallback_reason_code는 null이어야 합니다.")
        return self
