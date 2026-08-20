"""WaterBridge Safety Agent A2A HTTP Server.

A2A SDK 1.1.2 기준:
- Agent Card: /.well-known/agent-card.json
- JSON-RPC: /a2a
- 실제 Safety 판정: 기존 RiskClassifier 재사용
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import uuid4

from a2a.server.agent_execution import (
    AgentExecutor,
    RequestContext,
)
from a2a.server.events import EventQueue
from a2a.server.request_handlers import (
    DefaultRequestHandler,
)
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import Message, Part, Role
from fastapi import FastAPI

from .agent_card import build_safety_agent_card
from .safety_adapter import (
    SafetyA2AAdapter,
    SafetyA2ARequest,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9101
DEFAULT_RPC_PATH = "/a2a"


class SafetyAgentExecutor(AgentExecutor):
    """A2A 요청을 기존 WaterBridge Safety 로직에 연결합니다."""

    def __init__(
        self,
        *,
        adapter: SafetyA2AAdapter | None = None,
    ) -> None:
        # 새 Safety 정책을 만들지 않습니다.
        #
        # 실제 판단:
        # SafetyA2AAdapter
        #   → 기존 RiskClassifier
        self.adapter = adapter or SafetyA2AAdapter()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # -----------------------------------------------------------
        # Client에서 Message.text에 넣었던 JSON 문자열을 읽습니다.
        # -----------------------------------------------------------
        raw_input = context.get_user_input()

        # -----------------------------------------------------------
        # Pydantic Schema가 입력 경계를 검증합니다.
        #
        # 잘못된 inquiry_id / model_code / product_family 등이 들어오면
        # 임의 보정하지 않고 요청 실패로 처리합니다.
        # -----------------------------------------------------------
        request = SafetyA2ARequest.model_validate_json(
            raw_input
        )

        # -----------------------------------------------------------
        # 실제 Safety 판단은 기존 RiskClassifier에 위임됩니다.
        # -----------------------------------------------------------
        response = self.adapter.execute(request)

        # UUID 및 Enum을 JSON 문자열로 변환합니다.
        response_text = json.dumps(
            response.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        # -----------------------------------------------------------
        # Safety는 즉시 응답형 Agent이므로 Task를 만들 필요 없이
        # Message 하나만 반환합니다.
        #
        # A2A 1.1.2 AgentExecutor 계약상 허용되는 방식입니다.
        # -----------------------------------------------------------
        response_message = Message(
            message_id=str(uuid4()),
            context_id=str(request.correlation_id),
            role=Role.ROLE_AGENT,
            parts=[
                Part(
                    text=response_text,
                ),
            ],
        )

        await event_queue.enqueue_event(
            response_message
        )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Safety Agent는 한 번의 즉시 응답으로 끝나므로
        # 장기 실행 Task가 없습니다.
        #
        # AgentExecutor interface 구현을 위해 메서드는 유지합니다.
        return None


def create_app(
    *,
    public_base_url: str = (
        f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    ),
) -> FastAPI:
    """Safety A2A Agent용 FastAPI App을 생성합니다."""

    # ---------------------------------------------------------------
    # Agent Card에는 실제 JSON-RPC Endpoint를 광고합니다.
    #
    # Client:
    #   base URL
    #       ↓
    #   /.well-known/agent-card.json
    #       ↓
    #   supported_interfaces.url
    #       ↓
    #   /a2a
    # ---------------------------------------------------------------
    agent_card = build_safety_agent_card(
        url=(
            public_base_url.rstrip("/")
            + DEFAULT_RPC_PATH
        ),
    )

    executor = SafetyAgentExecutor()

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    @asynccontextmanager
    async def lifespan(
        app: FastAPI,
    ):
        try:
            yield
        finally:
            # A2A 1.1.2 DefaultRequestHandlerV2는
            # 종료 시 active task를 정리할 수 있습니다.
            close = getattr(
                request_handler,
                "aclose",
                None,
            )

            if close is not None:
                await close()

    app = FastAPI(
        title="WaterBridge Safety A2A Agent",
        lifespan=lifespan,
    )

    # A2A Agent Card endpoint
    agent_card_routes = create_agent_card_routes(
        agent_card
    )

    # A2A JSON-RPC endpoint
    jsonrpc_routes = create_jsonrpc_routes(
        request_handler,
        rpc_url=DEFAULT_RPC_PATH,
    )

    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=agent_card_routes,
        jsonrpc_routes=jsonrpc_routes,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "agent": "waterbridge-safety",
        }

    return app


# uvicorn에서 바로 사용할 기본 App
app = create_app()
