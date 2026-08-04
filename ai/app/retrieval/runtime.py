"""검색 실행 결과와 설정·실행 실패를 구분하는 내부 Runtime 타입."""

from enum import Enum


class RetrievalOutcome(str, Enum):
    """정상적으로 완료된 검색 단계의 결과."""

    NOT_RUN = "NOT_RUN"
    AVAILABLE = "AVAILABLE"
    NO_MATCH = "NO_MATCH"


class RetrievalConfigurationError(RuntimeError):
    """Vector Store 검색을 시작하는 데 필요한 설정이 없다."""


class RetrievalExecutionError(RuntimeError):
    """설정된 검색 Provider가 실행 중 실패했다."""


__all__ = [
    "RetrievalConfigurationError",
    "RetrievalExecutionError",
    "RetrievalOutcome",
]
