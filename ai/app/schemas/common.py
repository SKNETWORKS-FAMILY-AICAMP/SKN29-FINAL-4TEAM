"""공통 Pydantic 데이터 모델 및 Enum 정의."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


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


class DataClassification(str, Enum):
    """데이터 분류 Enum"""
    OFFICIAL = "official"
    TEAM_DESIGNED = "team_designed"
    SYNTHETIC = "synthetic"


class TraceContext(BaseModel):
    """요청 추적 Context 모델"""
    inquiry_id: str = Field(..., description="공개 문의 식별자 (예: DEMO-INQ-002)")
    correlation_id: str = Field(..., description="시스템 전반 공통 추적 ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="요청 시각 (ISO 8601 UTC)")


class ModelMetadata(BaseModel):
    """AI 모델 실행 메타데이터"""
    model_name: str = Field(..., description="사용된 LLM/Embedding 모델명")
    prompt_version: str = Field(..., description="적용된 프롬프트 버전 (예: symptom_structuring/v1)")
    tokens_used: Optional[int] = Field(None, description="사용한 토큰 수")
    latency_ms: Optional[float] = Field(None, description="처리 지연 시간 (ms)")


class ProcessingTrace(BaseModel):
    """파이프라인 단계별 처리 추적"""
    stage: str = Field(..., description="처리 단계명 (structuring, safety_check, retrieval 등)")
    status: str = Field(..., description="처리 상태 (success, failed, skipped)")
    latency_ms: float = Field(..., description="단계별 소요 시간 (ms)")
    error: Optional[str] = Field(None, description="오류 발생 시 상세 메시지")
