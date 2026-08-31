"""Provider 호출에 HTTP client와 독립적인 wall-clock deadline을 적용한다."""

from __future__ import annotations

from collections.abc import Callable
from queue import Empty, Queue
from threading import Thread
from typing import TypeVar, cast


_T = TypeVar("_T")


def call_with_wall_clock_timeout(
    callback: Callable[[], _T],
    *,
    timeout_seconds: float,
) -> _T:
    """HTTP timeout을 무시하는 Provider도 실제 경과 시간 안에 차단한다.

    시간을 넘긴 작업은 daemon thread에서 자연 종료되며, 현재 파이프라인은
    즉시 deterministic fallback을 사용할 수 있다.
    """

    if timeout_seconds <= 0:
        raise TimeoutError("Provider 호출 시간 예산이 남아 있지 않습니다.")

    result_queue: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def invoke() -> None:
        try:
            result_queue.put((True, callback()))
        except BaseException as exc:  # 원본 Provider 예외를 호출자에게 그대로 전달한다.
            result_queue.put((False, exc))

    Thread(
        target=invoke,
        name="waterbridge-provider-deadline",
        daemon=True,
    ).start()
    try:
        succeeded, value = result_queue.get(timeout=timeout_seconds)
    except Empty as exc:
        raise TimeoutError("Provider wall-clock deadline을 초과했습니다.") from exc

    if succeeded:
        return cast(_T, value)
    raise cast(BaseException, value)


__all__ = ["call_with_wall_clock_timeout"]
