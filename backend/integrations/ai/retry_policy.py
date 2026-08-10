"""Backend AI 호출 재시도 정책.

AI Runtime 내부 재시도와 Backend HTTP 재요청을 분리한다. 현재 계약은
Backend 자동 재시도 0회이므로 모든 오류에서 한 번의 호출로 종료한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackendAIRetryPolicy:
    """자동 재요청을 금지하는 명시적 정책 객체."""

    max_retries: int = 0

    def __post_init__(self) -> None:
        if self.max_retries != 0:
            raise ValueError("Backend AI 자동 재시도는 0회여야 합니다.")

    @property
    def max_attempts(self) -> int:
        return 1

    def should_retry(self, _exception: BaseException) -> bool:
        return False


DEFAULT_BACKEND_AI_RETRY_POLICY = BackendAIRetryPolicy()
