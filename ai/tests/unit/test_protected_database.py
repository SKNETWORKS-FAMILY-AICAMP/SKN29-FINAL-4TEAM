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
    assert captured.value.retryable is True
    assert secret_sentinel not in str(captured.value)
    assert captured.value.__suppress_context__ is True
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_non_retryable_database_error_is_sanitized_without_context():
    secret_sentinel = "SENSITIVE_DATABASE_SCHEMA_SENTINEL"

    def fail_with_schema_error():
        raise psycopg.ProgrammingError(
            f"schema failure with protected value {secret_sentinel}"
        )

    with pytest.raises(ProtectedDatabaseOperationError) as captured:
        run_protected_database_operation(
            fail_with_schema_error,
            public_message="보호 DB 작업에 실패했습니다.",
        )

    assert captured.value.retryable is False
    assert secret_sentinel not in str(captured.value)
    assert captured.value.__context__ is None


def test_authentication_sqlstate_is_not_retried_even_if_operational():
    def fail_with_authentication_error():
        raise psycopg.errors.InvalidPassword("protected authentication failure")

    with pytest.raises(ProtectedDatabaseOperationError) as captured:
        run_protected_database_operation(
            fail_with_authentication_error,
            public_message="보호 DB 작업에 실패했습니다.",
        )

    assert captured.value.retryable is False
    assert captured.value.__context__ is None


def test_statement_timeout_sqlstate_remains_retryable_once():
    def fail_with_statement_timeout():
        raise psycopg.errors.QueryCanceled("protected statement timeout")

    with pytest.raises(ProtectedDatabaseOperationError) as captured:
        run_protected_database_operation(
            fail_with_statement_timeout,
            public_message="보호 DB 작업에 실패했습니다.",
        )

    assert captured.value.retryable is True
    assert captured.value.__context__ is None


def test_non_database_assertion_is_not_hidden():
    def fail_with_assertion():
        raise AssertionError("계약 불일치")

    with pytest.raises(AssertionError, match="계약 불일치"):
        run_protected_database_operation(
            fail_with_assertion,
            public_message="보호 DB 작업에 실패했습니다.",
        )
