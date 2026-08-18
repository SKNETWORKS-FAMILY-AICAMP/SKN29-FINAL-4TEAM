"""보호 DSN을 사용하는 DB 작업의 공개 오류 경계."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import psycopg


T = TypeVar("T")


class ProtectedDatabaseOperationError(RuntimeError):
    """연결정보나 Driver 예외 원문을 포함하지 않는 DB 작업 실패."""


def run_protected_database_operation(
    operation: Callable[[], T],
    *,
    public_message: str,
) -> T:
    """psycopg 오류의 원문·Context를 제거하고 고정 메시지만 반환한다."""

    try:
        return operation()
    except psycopg.Error:
        raise ProtectedDatabaseOperationError(public_message) from None
