import asyncio

# 실제 MCP Client를 사용합니다.
#
# 이 Client는:
#
# Python 테스트
# → MCP Client
# → stdio
# → 별도 MCP Server 프로세스
#
# 구조로 통신합니다.
from app.integrations.mcp.client import WaterBridgeMCPClient

# MCP를 거치지 않고 직접 호출할 함수입니다.
from app.integrations.mcp.server import search_official_evidence


# -------------------------------------------------------------------
# Direct 호출과 실제 MCP 호출 결과가 같은지 확인하는 테스트
# -------------------------------------------------------------------


def test_search_official_evidence_stdio_matches_direct_call():
    # 현재 Runtime에서 HOLD 상태인 모델을 사용합니다.
    #
    # IAC425는 정책 Gate에서 차단되므로:
    #
    # Embedding 실행 X
    # Vector DB 실행 X
    #
    # 따라서 별도의 실제 Vector DB 환경 없이도
    # MCP 전체 통신 경로를 안전하게 검증할 수 있습니다.

    model_code = "WPUIAC425SNW"

    customer_query = "얼음이 나오지 않아요"


    # ---------------------------------------------------------------
    # 1. Python 함수 직접 호출
    # ---------------------------------------------------------------

    direct_result = search_official_evidence(
        customer_query=customer_query,
        model_code=model_code,
        symptom_type=None,
        previous_answers=[],
    )


    # Pydantic 결과를 일반 JSON 형태의 dict로 변환합니다.
    direct_data = direct_result.model_dump(
        mode="json"
    )


    # ---------------------------------------------------------------
    # 2. 실제 MCP stdio 호출
    # ---------------------------------------------------------------

    async def call_through_mcp():
        # WaterBridgeMCPClient를 열면
        # 실제 server.py가 별도 프로세스로 실행됩니다.
        async with WaterBridgeMCPClient() as client:

            result = await client.call_tool(
                "search_official_evidence",
                {
                    "customer_query": customer_query,
                    "model_code": model_code,
                    "symptom_type": None,
                    "previous_answers": [],
                },
            )

            # MCP가 반환한 구조화 JSON 결과를 가져옵니다.
            return result.structured_content


    # pytest-asyncio를 추가하지 않고
    # Python 기본 asyncio.run()으로 비동기 함수를 실행합니다.
    mcp_data = asyncio.run(
        call_through_mcp()
    )


    # ---------------------------------------------------------------
    # 3. 가장 중요한 검증
    # ---------------------------------------------------------------
    #
    # MCP라는 통신 계층을 하나 추가했더라도
    # 실제 업무 결과는 직접 호출했을 때와 완전히 같아야 합니다.

    assert mcp_data == direct_data


    # ---------------------------------------------------------------
    # 4. HOLD 모델 정책도 함께 확인
    # ---------------------------------------------------------------

    assert mcp_data["policy_blocked"] is True

    assert (
        mcp_data["policy_execution_path"]
        == "POLICY_BLOCK_UNSUPPORTED_MODEL"
    )

    assert (
        mcp_data["applied_rule_id"]
        == "GATE-MODEL-001"
    )


    # 정책에서 검색 전에 차단되었으므로
    # 실제 pgvector 검색은 실행되면 안 됩니다.
    assert (
        mcp_data["vector_search_executed"]
        is False
    )


    # 당연히 고객에게 사용할 Evidence도 없어야 합니다.
    assert (
        mcp_data["evidence_found"]
        is False
    )