"""HTTP Timeout을 파이프라인과 검색 경계에 전달하는 협력적 취소 토큰."""

from threading import Event


class PipelineCancelledError(RuntimeError):
    """상위 요청이 취소되어 파이프라인을 중단해야 함을 나타낸다."""


class CancellationToken:
    """Thread 작업에 안전하게 전달할 수 있는 취소 신호."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise PipelineCancelledError("AI 요청이 취소되었습니다.")
