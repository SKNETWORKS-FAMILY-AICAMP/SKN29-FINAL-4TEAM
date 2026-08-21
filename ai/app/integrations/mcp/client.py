"""WaterBridge MCP stdio client bootstrap."""

from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class WaterBridgeMCPClient:
    """WaterBridge MCP Server와 stdio로 통신하는 Client."""

    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None

    @staticmethod
    def _ai_root() -> Path:
        """
        ai/ 루트 경로를 반환한다.

        client.py:
        ai/app/integrations/mcp/client.py
        """
        return Path(__file__).resolve().parents[3]

    @classmethod
    def _server_path(cls) -> Path:
        return cls._ai_root() / "app" / "integrations" / "mcp" / "server.py"

    @classmethod
    def _repository_root(cls) -> Path:
        return cls._ai_root().parent

    @classmethod
    def _server_environment(cls) -> dict[str, str]:
        """
        MCP Server subprocess에 필요한 환경변수만 명시적으로 전달한다.

        Secret을 로그에 출력하거나 Tool Argument로 전달하지 않는다.
        """
        environment = {
            "PYTHONPATH": str(cls._repository_root()),
        }

        optional_keys = (
            "AI_VECTOR_DSN",
            "AI_VECTOR_TABLE_NAME",
            "AI_EMBEDDING_REVISION",
            "AI_RAG_RUNTIME_PROFILE",
            "AI_BACKEND_BASE_URL",
            "AI_HANDOFF_INTERNAL_TOKEN",
            "AI_BACKEND_CONTEXT_TIMEOUT_SECONDS",
            "HF_HOME",
            "HUGGINGFACE_HUB_CACHE",
            "SENTENCE_TRANSFORMERS_HOME",
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
        )

        for key in optional_keys:
            value = os.getenv(key)
            if value:
                environment[key] = value

        return environment

    async def connect(self) -> None:
        """MCP Server를 실행하고 ClientSession을 초기화한다."""

        if self._session is not None:
            return

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ai.app.integrations.mcp.server"],
            env=self._server_environment(),
            cwd=str(self._repository_root()),
        )

        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await session.initialize()

        self._session = session

    async def close(self) -> None:
        """MCP Client/Server 연결을 종료한다."""

        await self._exit_stack.aclose()
        self._session = None
        self._exit_stack = AsyncExitStack()

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError(
                "MCP Client가 연결되지 않았습니다. connect()를 먼저 호출하세요."
            )

        return self._session

    async def list_tools(self):
        """MCP Server에 등록된 Tool 목록을 조회한다."""

        session = self._require_session()
        return await session.list_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ):
        """MCP Tool을 호출한다."""

        session = self._require_session()

        return await session.call_tool(
            tool_name,
            arguments or {},
        )

    async def __aenter__(self) -> "WaterBridgeMCPClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        await self.close()
