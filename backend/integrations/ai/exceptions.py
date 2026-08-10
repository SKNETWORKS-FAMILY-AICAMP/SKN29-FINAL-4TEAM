"""Backend와 AI Runtime 사이의 안정적인 예외 계약."""

from __future__ import annotations

from typing import Any


class AIIntegrationError(Exception):
    """외부 예외와 원문 응답을 공개 계층으로 누출하지 않는 기본 예외."""

    default_code = "AI-INTEGRATION-01"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        retryable: bool = False,
        failure_stage: str | None = None,
        retry_count: int = 0,
        payload: dict[str, Any] | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code or self.default_code
        self.http_status = http_status
        self.retryable = retryable
        self.failure_stage = failure_stage
        self.retry_count = retry_count
        self.payload = payload
        self.validation_errors = validation_errors or []


class AIConfigurationError(AIIntegrationError):
    """필수 AI 연동 설정이 비어 있거나 허용 범위를 벗어남."""

    default_code = "AI-CONFIGURATION-01"


class AIRequestValidationError(AIIntegrationError):
    """AI로 보내기 전 Backend 요청 계약 검증 실패."""

    default_code = "AI-REQUEST-SCHEMA-01"


class AIResponseValidationError(AIIntegrationError):
    """AI 성공 또는 오류 응답 계약 검증 실패."""

    default_code = "AI-RESPONSE-SCHEMA-01"


class AIIdentifierMismatchError(AIResponseValidationError):
    """요청 식별자와 AI 응답 Echo가 다름."""

    default_code = "AI-IDENTIFIER-MISMATCH-01"


class AITransportError(AIIntegrationError):
    """HTTP 연결·프로토콜 단계에서 발생한 오류."""

    default_code = "AI-TRANSPORT-01"


class AITimeoutError(AITransportError):
    """Backend의 전체 AI 호출 제한 시간을 초과함."""

    default_code = "AI-TIMEOUT-01"


class AIServiceResponseError(AIIntegrationError):
    """계약 검증을 통과한 AI 4xx·5xx 응답."""

    default_code = "AI-FAILED-01"


class AIIdempotencyConflictError(AIIntegrationError):
    """같은 AI 요청 ID가 다른 입력에 재사용됨."""

    default_code = "AI-IDEMPOTENCY-CONFLICT-01"
