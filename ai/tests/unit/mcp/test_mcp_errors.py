from app.integrations.mcp.errors import (
    MCPContextConfigurationError,
    MCPContextMismatchError,
    MCPContextNotFoundError,
    MCPContextTimeoutError,
    MCPContextUnavailableError,
    MCPContextValidationError,
)


def test_timeout_error_is_retryable():
    # Timeout은 일시적인 문제일 가능성이 있기 때문에
    # 재시도 가능한 오류로 분류합니다.

    assert issubclass(
        MCPContextTimeoutError,
        TimeoutError,
    )

    assert MCPContextTimeoutError.retryable is True

    assert (
        MCPContextTimeoutError.code
        == "MCP_CONTEXT_TIMEOUT"
    )


def test_unavailable_error_is_retryable():
    # Backend 연결 실패도 일시적인 네트워크 문제일 수 있으므로
    # 재시도 가능한 오류입니다.

    assert issubclass(
        MCPContextUnavailableError,
        ConnectionError,
    )

    assert MCPContextUnavailableError.retryable is True

    assert (
        MCPContextUnavailableError.code
        == "MCP_CONTEXT_UNAVAILABLE"
    )


def test_not_found_error_is_not_retryable():
    # 데이터 자체가 없는 경우에는
    # 같은 요청을 바로 다시 보내도 해결되지 않으므로
    # 재시도하지 않습니다.

    assert MCPContextNotFoundError.retryable is False

    assert (
        MCPContextNotFoundError.code
        == "MCP_CONTEXT_NOT_FOUND"
    )


def test_mismatch_error_is_not_retryable():
    # 다른 제품이나 다른 문의가 반환된 경우
    # 안전 문제이므로 자동으로 다시 시도하지 않습니다.

    assert issubclass(
        MCPContextMismatchError,
        ValueError,
    )

    assert MCPContextMismatchError.retryable is False

    assert (
        MCPContextMismatchError.code
        == "MCP_CONTEXT_MISMATCH"
    )


def test_configuration_and_validation_errors_are_not_retryable():
    # 설정 오류와 Schema 오류 역시
    # 단순 재시도로 해결되는 문제가 아닙니다.

    assert MCPContextConfigurationError.retryable is False
    assert MCPContextValidationError.retryable is False