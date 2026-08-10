"""HTTP·단계별 Timeout을 파이프라인 경계에 전달하는 협력적 취소 토큰."""

from contextlib import contextmanager
from threading import Event
import time
from typing import Iterator


class PipelineCancelledError(RuntimeError):
    """상위 요청이 취소되어 파이프라인을 중단해야 함을 나타낸다."""


class PipelineStageTimeoutError(PipelineCancelledError):
    """단계별 협력적 시간 예산을 초과했다."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"AI 파이프라인 단계 시간이 초과되었습니다: {stage}")


class CancellationToken:
    """Thread 작업에 안전하게 전달할 수 있는 취소 신호."""

    def __init__(self) -> None:
        self._event = Event()
        self._deadline: float | None = None
        self._deadline_stage: str | None = None
        self._retry_count = 0

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def record_retry(self, retry_count: int) -> None:
        if not 0 <= retry_count <= 1:
            raise ValueError("AI 내부 재시도 횟수는 0~1 범위여야 합니다.")
        self._retry_count = max(self._retry_count, retry_count)

    def wait(self, seconds: float) -> None:
        """취소와 현재 단계 Deadline을 존중하며 Backoff를 대기한다."""
        if seconds < 0:
            raise ValueError("대기 시간은 0 이상이어야 합니다.")
        timeout = seconds
        if self._deadline is not None:
            timeout = min(timeout, max(0.0, self._deadline - time.monotonic()))
        if self._event.wait(timeout=timeout):
            raise PipelineCancelledError("AI 요청이 취소되었습니다.")
        self.raise_if_cancelled()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise PipelineCancelledError("AI 요청이 취소되었습니다.")
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise PipelineStageTimeoutError(self._deadline_stage or "UNKNOWN")

    @contextmanager
    def deadline_scope(self, seconds: float, stage: str) -> Iterator[None]:
        """현재 Thread의 Stage 경계에 임시 협력적 Deadline을 적용한다."""
        if seconds <= 0:
            raise ValueError("단계별 Timeout은 0보다 커야 합니다.")
        previous_deadline = self._deadline
        previous_stage = self._deadline_stage
        candidate = time.monotonic() + seconds
        if previous_deadline is None or candidate < previous_deadline:
            self._deadline = candidate
            self._deadline_stage = stage
        try:
            self.raise_if_cancelled()
            yield
            self.raise_if_cancelled()
        finally:
            self._deadline = previous_deadline
            self._deadline_stage = previous_stage
