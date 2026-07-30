"""FastAPI HTTP 응답 DTO 모델."""

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from uuid import UUID
from pydantic import Field
from ...schemas import AiErrorCode, AiStage, ContractModel


ErrorFailureStage = Literal[
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


class HealthCheckResponse(ContractModel):
    """Health Check 응답 DTO"""
    status: str = Field("ok", description="서버 Liveness 상태 (ok, degraded, error)")
    service: str = Field("ai-service", description="서비스명")
    version: str = Field("1.0.0", description="서비스 버전")
    config_loaded: bool = Field(True, description="안전 규칙 및 설정 로딩 여부")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="현재 시각 (UTC)")


class ApiErrorDetail(ContractModel):
    """업무 오류 상세 구조"""
    code: AiErrorCode = Field(..., description="공통 오류 코드")
    message: str = Field(..., min_length=1, max_length=500, description="사용자 친화적 오류 메시지")
    details: Optional[Dict[str, Any]] = Field(None, description="오류 상세 메타데이터")
    retryable: bool = Field(False, description="재시도 가능 여부")
    failure_stage: ErrorFailureStage = Field(..., description="실패한 표준 AI Stage")
    retry_count: int = Field(0, ge=0, le=1, description="AI 내부 재시도 횟수")


class ApiErrorResponse(ContractModel):
    """FastAPI 공통 오류 응답 Wrapper"""
    success: Literal[False] = Field(False, description="성공 여부 (항상 False)")
    inquiry_id: Optional[UUID] = Field(None, description="Backend Public UUID")
    correlation_id: Optional[str] = Field(None, description="요청·응답·로그 추적 식별자")
    ai_request_id: Optional[str] = Field(None, description="AI 호출 멱등 식별자")
    state_version: Optional[int] = Field(None, ge=1, description="호출 시작 시점 상태 버전")
    error: ApiErrorDetail = Field(..., description="오류 상세")
