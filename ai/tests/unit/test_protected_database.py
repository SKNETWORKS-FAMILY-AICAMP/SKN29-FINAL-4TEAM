"""보호 DB 예외가 자격증명을 노출하지 않는지 검증."""

import psycopg
import pytest

from ai.app.common.protected_database import (
    ProtectedDatabaseOperationError,
    run_protected_database_operation,
)


def test_psycopg_exception_context_and_secret_are_suppressed():
    secret_sentinel = "SENSITIVE_DSN_AND_PASSWORD_SENTINEL"

    def fail_with_driver_message():
        raise psycopg.OperationalError(
            f"connection failed with protected value {secret_sentinel}"
        )

    with pytest.raises(ProtectedDatabaseOperationError) as captured:
        run_protected_database_operation(
            fail_with_driver_message,
            public_message="보호 DB 작업에 실패했습니다.",
        )

    assert str(captured.value) == "보호 DB 작업에 실패했습니다."
    assert secret_sentinel not in str(captured.value)
    assert captured.value.__suppress_context__ is True


def test_non_database_assertion_is_not_hidden():
    def fail_with_assertion():
        raise AssertionError("계약 불일치")

    with pytest.raises(AssertionError, match="계약 불일치"):
        run_protected_database_operation(
            fail_with_assertion,
            public_message="보호 DB 작업에 실패했습니다.",
        )
