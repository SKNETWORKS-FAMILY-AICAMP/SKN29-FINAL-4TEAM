"""보호 DSN을 사용하는 DB 작업의 공개 오류 경계."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import psycopg


T = TypeVar("T")


class ProtectedDatabaseOperationError(RuntimeError):
    """연결정보나 Driver 예외 원문을 포함하지 않는 DB 작업 실패."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


_NON_RETRYABLE_SQLSTATE_PREFIXES = frozenset(
    {
        "22",  # Data exception
        "23",  # Integrity constraint violation
        "28",  # Invalid authorization specification
        "3D",  # Invalid catalog name
        "3F",  # Invalid schema name
        "42",  # Syntax error or access rule violation
    }
)
_RETRYABLE_SQLSTATE_PREFIXES = frozenset(
    {
        "08",  # Connection exception
        "40",  # Transaction rollback
        "53",  # Insufficient resources
    }
)
_RETRYABLE_SQLSTATES = frozenset(
    {
        "57014",  # Query cancelled, including statement timeout
        "57P01",  # Admin shutdown
        "57P02",  # Crash shutdown
        "57P03",  # Cannot connect now
    }
)


def _is_retryable_database_error(exc: psycopg.Error) -> bool:
    """Classify without inspecting or retaining the protected error message."""

    sqlstate = getattr(exc, "sqlstate", None)
    if isinstance(sqlstate, str):
        normalized = sqlstate.upper()
        if normalized in _RETRYABLE_SQLSTATES:
            return True
        if normalized[:2] in _NON_RETRYABLE_SQLSTATE_PREFIXES:
            return False
        if normalized[:2] in _RETRYABLE_SQLSTATE_PREFIXES:
            return True
    return isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError))


def run_protected_database_operation(
    operation: Callable[[], T],
    *,
    public_message: str,
) -> T:
    """Return only a fixed error while preserving safe retry semantics.

    The replacement exception is raised after leaving the ``except`` block.
    This prevents the original Driver exception from remaining reachable via
    ``__context__`` by deployment APM or traceback collectors.
    """

    retryable: bool | None = None
    try:
        return operation()
    except psycopg.Error as exc:
        retryable = _is_retryable_database_error(exc)

    if retryable is None:  # Defensive: the operation either returned or failed.
        raise RuntimeError("보호 DB 오류 분류 상태가 올바르지 않습니다.")
    raise ProtectedDatabaseOperationError(
        public_message,
        retryable=retryable,
    ) from None
