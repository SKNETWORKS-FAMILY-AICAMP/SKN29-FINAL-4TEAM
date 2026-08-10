"""AI HTTP 계약 오류 정의."""

from dataclasses import dataclass
from uuid import UUID

from ...schemas import AiStage


@dataclass
class AiServiceError(Exception):
    """공통 Error Registry로 직렬화할 수 있는 안전한 서비스 오류."""

    code: str
    http_status: int
    message: str
    retryable: bool
    failure_stage: AiStage
    correlation_id: UUID | None = None
    inquiry_id: UUID | None = None
    ai_request_id: str | None = None
    state_version: int | None = None
    retry_count: int = 0
