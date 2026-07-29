"""FastAPI HTTP 응답 DTO 모델."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Health Check 응답 DTO"""
    status: str = Field("ok", description="서버 Liveness 상태 (ok, degraded, error)")
    service: str = Field("ai-service", description="서비스명")
    version: str = Field("1.0.0", description="서비스 버전")
    config_loaded: bool = Field(True, description="안전 규칙 및 설정 로딩 여부")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="현재 시각 (UTC)")


class ApiErrorDetail(BaseModel):
    """업무 오류 상세 구조"""
    code: str = Field(..., description="공통 오류 코드")
    message: str = Field(..., description="사용자 친화적 오류 메시지")
    details: Optional[Dict[str, Any]] = Field(None, description="오류 상세 메타데이터")
    retryable: bool = Field(False, description="재시도 가능 여부")


class ApiErrorResponse(BaseModel):
    """FastAPI 공통 오류 응답 Wrapper"""
    success: bool = Field(False, description="성공 여부 (항상 False)")
    error: ApiErrorDetail = Field(..., description="오류 상세")
