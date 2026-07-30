"""공통 Pydantic 데이터 모델 및 Enum 정의."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """공개 계약과 동일하게 미정의 속성을 거부하는 기본 모델."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RiskLevel(str, Enum):
    """위험도 레벨 Enum"""
    GENERAL = "general"
    CAUTION = "caution"
    DANGER = "danger"


class UsageGuidanceStatus(str, Enum):
    """사용 안내 상태 Enum (팀 공통 규칙)"""
    NORMAL = "NORMAL"
    PARTIAL_STOP = "PARTIAL_STOP"
    TOTAL_STOP = "TOTAL_STOP"
    PENDING_CONSULTATION = "PENDING_CONSULTATION"


class AiExecutionStatus(str, Enum):
    """Backend가 소비하는 AI 실행 결과 상태."""

    SUCCEEDED = "SUCCEEDED"
    FALLBACK = "FALLBACK"


class AiStage(str, Enum):
    """contracts/codes/ai-stages.yaml과 동일한 표준 단계 코드."""

    STRUCTURING = "STRUCTURING"
    CHECKING_MISSING_FIELDS = "CHECKING_MISSING_FIELDS"
    SAFETY_CHECK = "SAFETY_CHECK"
    RETRIEVING = "RETRIEVING"
    RERANKING = "RERANKING"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DataClassification(str, Enum):
    """데이터 분류 Enum"""
    OFFICIAL = "official"
    TEAM_DESIGNED = "team_designed"
    SYNTHETIC = "synthetic"


class TraceContext(ContractModel):
    """요청 추적 Context 모델"""
    inquiry_id: str = Field(..., description="공개 문의 식별자 (예: DEMO-INQ-002)")
    correlation_id: str = Field(..., description="시스템 전반 공통 추적 ID")
    ai_request_id: str = Field(..., description="Backend가 발급한 AI 호출 멱등 식별자")
    state_version: int = Field(..., ge=1, description="AI 호출 시작 시점 문의 상태 버전")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="요청 시각 (ISO 8601 UTC)")


class ModelMetadata(ContractModel):
    """AI 모델 실행 메타데이터"""
    model_name: str = Field(..., description="사용된 LLM/Embedding 모델명")
    prompt_version: str = Field(..., description="적용된 프롬프트 버전 (예: symptom_structuring/v1)")
    tokens_used: Optional[int] = Field(None, description="사용한 토큰 수")
    latency_ms: Optional[float] = Field(None, description="처리 지연 시간 (ms)")


class ProcessingTrace(ContractModel):
    """파이프라인 단계별 처리 추적"""
    stage: AiStage = Field(..., description="표준 AI 단계 코드")
    status: str = Field(..., pattern="^(SUCCEEDED|FAILED|SKIPPED)$", description="단계 처리 상태")
    latency_ms: float = Field(..., ge=0, description="단계별 소요 시간 (ms)")
    retry_count: int = Field(0, ge=0, le=1, description="해당 단계 내부 재시도 횟수")
    error_code: Optional[str] = Field(None, description="공통 오류 코드. 예외 원문은 공개하지 않음")
