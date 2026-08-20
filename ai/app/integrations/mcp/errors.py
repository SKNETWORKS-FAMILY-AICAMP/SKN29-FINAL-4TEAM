from __future__ import annotations


# -------------------------------------------------------------------
# MCP Context 관련 오류를 한 곳에서 관리하는 파일
# -------------------------------------------------------------------
#
# 지금까지는 문제가 생기면 단순히:
#
# raise RuntimeError(...)
#
# 형태로 처리했습니다.
#
# 하지만 이렇게 하면 사용하는 쪽에서:
#
# "제품이 없는 건가?"
# "Backend가 느린 건가?"
# "Backend가 죽은 건가?"
# "잘못된 문의를 받은 건가?"
#
# 를 구분하기 어렵습니다.
#
# 그래서 오류마다 별도의 이름과 코드를 부여합니다.


class MCPContextConfigurationError(RuntimeError):
    # Backend Context API 주소나 설정 자체가 없는 경우입니다.
    #
    # 예:
    # 아직 Backend 내부 MCP Context API가 연결되지 않음
    #
    # 설정 문제이므로 자동 재시도한다고 해결되는 문제가 아닙니다.

    code = "MCP_CONTEXT_CONFIGURATION_ERROR"
    retryable = False


class MCPContextNotFoundError(LookupError):
    # 요청한 제품이나 문의가 실제로 존재하지 않는 경우입니다.
    #
    # 예:
    # inquiry_id로 조회했지만 해당 문의가 없음
    #
    # 같은 요청을 바로 다시 보내도 결과가 달라질 가능성이 낮으므로
    # 기본적으로 재시도하지 않습니다.

    code = "MCP_CONTEXT_NOT_FOUND"
    retryable = False


class MCPContextTimeoutError(TimeoutError):
    # Backend에 요청은 보냈지만
    # 정해진 시간 안에 응답이 오지 않은 경우입니다.
    #
    # TimeoutError를 상속한 이유는
    # 프로젝트의 기존 Retry 정책과 같은 방식으로
    # Timeout 계열 오류임을 구분하기 위해서입니다.

    code = "MCP_CONTEXT_TIMEOUT"
    retryable = True


class MCPContextUnavailableError(ConnectionError):
    # Backend에 연결하지 못했거나
    # Backend가 일시적으로 정상 응답하지 못하는 경우입니다.
    #
    # 예:
    # 네트워크 연결 실패
    # Backend 5xx
    #
    # ConnectionError 계열로 만들어
    # 일시적인 연결 문제라는 의미를 명확하게 합니다.

    code = "MCP_CONTEXT_UNAVAILABLE"
    retryable = True


class MCPContextMismatchError(ValueError):
    # 요청한 데이터와 Backend가 반환한 데이터가 다른 경우입니다.
    #
    # 예:
    #
    # 요청:
    # inquiry-A
    #
    # Backend 반환:
    # inquiry-B
    #
    # 또는
    #
    # 요청:
    # WPUIAC425SNW
    #
    # Backend 반환:
    # WPUIAC606SNW
    #
    # 이런 경우 다른 고객이나 다른 제품 정보가 섞일 위험이 있으므로
    # Fail-closed 방식으로 즉시 중단합니다.

    code = "MCP_CONTEXT_MISMATCH"
    retryable = False


class MCPContextValidationError(ValueError):
    # Backend 응답은 왔지만
    # 우리가 약속한 Schema와 맞지 않는 경우입니다.
    #
    # 예:
    # 필수 model_code가 없음
    # inquiry_id가 UUID가 아님
    #
    # 잘못된 데이터를 억지로 사용하지 않고 차단합니다.

    code = "MCP_CONTEXT_VALIDATION_ERROR"
    retryable = False