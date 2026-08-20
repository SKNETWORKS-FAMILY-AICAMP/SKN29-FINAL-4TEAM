"""WaterBridge Safety Agent용 A2A Client와 Local Safety Fallback."""

from __future__ import annotations

import asyncio
import json
import os
from enum import Enum
from typing import Protocol
from uuid import uuid4

import httpx
from a2a.client import ClientConfig, create_client
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
)
from pydantic import BaseModel, ConfigDict

from .safety_adapter import (
    SafetyA2AAdapter,
    SafetyA2ARequest,
    SafetyA2AResponse,
)


# -------------------------------------------------------------------
# 1. A2A Remote 실패 종류
# -------------------------------------------------------------------
#
# Remote 오류 원문을 Runtime 밖으로 그대로 노출하지 않고
# "어떤 종류의 실패였는지"만 표준화해서 남깁니다.
class A2ASafetyFailureKind(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"


# -------------------------------------------------------------------
# 2. 최종 Safety 호출 결과
# -------------------------------------------------------------------
class A2ASafetyCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: SafetyA2AResponse

    # True라면 Remote A2A가 아니라 기존 Local RiskClassifier가
    # 실제 Safety 판단을 수행했다는 뜻입니다.
    used_local_fallback: bool

    # Remote 성공이면 None.
    # Local fallback이면 실패 종류만 기록합니다.
    failure_kind: A2ASafetyFailureKind | None = None


# -------------------------------------------------------------------
# 3. Remote Safety Transport가 따라야 하는 최소 Interface
# -------------------------------------------------------------------
#
# 실제 Runtime에서는 SdkA2ASafetyTransport를 사용하고,
# 단위 테스트에서는 Fake Remote를 넣을 수 있습니다.
class SafetyRemoteTransport(Protocol):
    async def execute(
        self,
        request: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        ...


class A2ASafetyInvalidResponseError(RuntimeError):
    """Remote A2A 응답이 WaterBridge Safety 계약과 맞지 않을 때 사용."""


# -------------------------------------------------------------------
# 4. 실제 a2a-sdk 1.1.2 기반 Remote Transport
# -------------------------------------------------------------------
class SdkA2ASafetyTransport:
    """
    공식 a2a-sdk를 사용해서 Remote Safety Agent에 요청합니다.

    Agent URL에는 A2A Agent의 base URL을 넣습니다.
    create_client()가 해당 URL에서 Agent Card를 조회하고
    Agent Card의 JSONRPC Interface로 실제 요청을 전송합니다.
    """

    def __init__(
        self,
        *,
        agent_url: str,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.agent_url = agent_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def execute(
        self,
        request: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        # -----------------------------------------------------------
        # Pydantic Request를 JSON으로 직렬화합니다.
        #
        # UUID도 mode="json"을 사용하면 문자열로 안전하게 변환됩니다.
        # A2A Message의 text Part 안에 JSON을 담는 단순 PoC 방식입니다.
        # -----------------------------------------------------------
        payload = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )

        message = Message(
            message_id=str(uuid4()),
            context_id=str(request.correlation_id),
            role=Role.ROLE_USER,
            parts=[
                Part(text=payload),
            ],
        )

        send_request = SendMessageRequest(
            message=message,
        )

        # -----------------------------------------------------------
        # 현재 Safety PoC는 Streaming이 필요하지 않습니다.
        # JSONRPC + application/json 응답만 허용합니다.
        # -----------------------------------------------------------
        http_client = httpx.AsyncClient(
            timeout=self.timeout_seconds,
        )

        client = None

        try:
            config = ClientConfig(
                streaming=False,
                httpx_client=http_client,
                supported_protocol_bindings=[
                    "JSONRPC",
                ],
                accepted_output_modes=[
                    "application/json",
                ],
            )

            # 문자열 URL을 전달하면 SDK가 먼저 Agent Card를 조회합니다.
            client = await create_client(
                self.agent_url,
                client_config=config,
            )

            async for chunk in client.send_message(send_request):
                # ---------------------------------------------------
                # Safety PoC의 정상 응답 형식:
                #
                # StreamResponse
                #   └─ message
                #       └─ parts
                #           └─ text = SafetyA2AResponse JSON
                # ---------------------------------------------------
                if chunk.HasField("message"):
                    return self._parse_message(
                        chunk.message,
                    )

                # Task 형태로 응답한 Agent도 최소한 status.message가 있으면
                # 같은 계약으로 읽을 수 있게 합니다.
                if chunk.HasField("task"):
                    task = chunk.task

                    if (
                        task.HasField("status")
                        and task.status.HasField("message")
                    ):
                        return self._parse_message(
                            task.status.message,
                        )

            raise A2ASafetyInvalidResponseError(
                "A2A Safety Agent가 해석 가능한 응답을 반환하지 않았습니다."
            )

        finally:
            if client is not None:
                await client.close()

            # client.close()가 transport 내부 client를 닫더라도
            # aclose()는 중복 호출에 안전합니다.
            await http_client.aclose()

    @staticmethod
    def _parse_message(
        message: Message,
    ) -> SafetyA2AResponse:
        for part in message.parts:
            text = getattr(part, "text", "")

            if not text or not text.strip():
                continue

            try:
                return SafetyA2AResponse.model_validate_json(
                    text
                )
            except Exception as exc:
                # 응답 Body 전체나 내부 예외를 외부로 노출하지 않습니다.
                raise A2ASafetyInvalidResponseError(
                    "A2A Safety 응답 Schema 검증에 실패했습니다."
                ) from exc

        raise A2ASafetyInvalidResponseError(
            "A2A Safety 응답에 JSON text Part가 없습니다."
        )


# -------------------------------------------------------------------
# 5. Remote A2A + Local Safety Fallback Facade
# -------------------------------------------------------------------
class WaterBridgeA2ASafetyClient:
    """
    Orchestrator가 최종적으로 사용하게 될 Safety 호출 Facade.

    Remote A2A 성공
        → Remote Safety 결과 사용

    Remote Timeout / 연결 실패 / 잘못된 응답
        → 기존 Local RiskClassifier로 Fallback

    중요한 점:
    Fallback에서도 새로운 Safety 규칙은 만들지 않습니다.
    SafetyA2AAdapter → RiskClassifier를 그대로 재사용합니다.
    """

    def __init__(
        self,
        *,
        remote_transport: SafetyRemoteTransport | None,
        local_adapter: SafetyA2AAdapter | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.remote_transport = remote_transport
        self.local_adapter = (
            local_adapter or SafetyA2AAdapter()
        )
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(
        cls,
    ) -> "WaterBridgeA2ASafetyClient":
        raw_url = os.getenv(
            "AI_A2A_SAFETY_AGENT_URL",
            "",
        ).strip()

        timeout_seconds = float(
            os.getenv(
                "AI_A2A_SAFETY_TIMEOUT_SECONDS",
                "3",
            )
        )

        remote_transport = (
            SdkA2ASafetyTransport(
                agent_url=raw_url,
                timeout_seconds=timeout_seconds,
            )
            if raw_url
            else None
        )

        return cls(
            remote_transport=remote_transport,
            timeout_seconds=timeout_seconds,
        )

    async def assess(
        self,
        request: SafetyA2ARequest,
    ) -> A2ASafetyCallResult:
        # Remote Agent URL 자체가 없는 환경에서는
        # 기존 Local Safety를 사용합니다.
        if self.remote_transport is None:
            return self._local_fallback(
                request=request,
                failure_kind=(
                    A2ASafetyFailureKind.CONFIGURATION
                ),
            )

        try:
            remote_response = await asyncio.wait_for(
                self.remote_transport.execute(request),
                timeout=self.timeout_seconds,
            )

            # -------------------------------------------------------
            # 다른 Inquiry / Correlation / Product의 응답이
            # 섞였다면 Remote 성공으로 인정하면 안 됩니다.
            # -------------------------------------------------------
            self._validate_remote_identity(
                request=request,
                response=remote_response,
            )

            return A2ASafetyCallResult(
                response=remote_response,
                used_local_fallback=False,
                failure_kind=None,
            )

        except TimeoutError:
            return self._local_fallback(
                request=request,
                failure_kind=A2ASafetyFailureKind.TIMEOUT,
            )

        except A2ASafetyInvalidResponseError:
            return self._local_fallback(
                request=request,
                failure_kind=(
                    A2ASafetyFailureKind.INVALID_RESPONSE
                ),
            )

        except Exception:
            # 연결 거부, Agent Card 조회 실패,
            # HTTP 오류 등은 Remote unavailable로 취급합니다.
            #
            # 예외 원문은 고객/상위 Runtime에 전달하지 않습니다.
            return self._local_fallback(
                request=request,
                failure_kind=(
                    A2ASafetyFailureKind.UNAVAILABLE
                ),
            )

    @staticmethod
    def _validate_remote_identity(
        *,
        request: SafetyA2ARequest,
        response: SafetyA2AResponse,
    ) -> None:
        if response.inquiry_id != request.inquiry_id:
            raise A2ASafetyInvalidResponseError(
                "A2A Safety inquiry identity mismatch"
            )

        if (
            response.correlation_id
            != request.correlation_id
        ):
            raise A2ASafetyInvalidResponseError(
                "A2A Safety correlation identity mismatch"
            )

        # Backend Context의 정확한 model_code가
        # A2A 경계에서도 유지되어야 합니다.
        if response.model_code != request.model_code:
            raise A2ASafetyInvalidResponseError(
                "A2A Safety product identity mismatch"
            )

        if (
            response.product_family
            != request.product_family
        ):
            raise A2ASafetyInvalidResponseError(
                "A2A Safety product family mismatch"
            )

    def _local_fallback(
        self,
        *,
        request: SafetyA2ARequest,
        failure_kind: A2ASafetyFailureKind,
    ) -> A2ASafetyCallResult:
        response = self.local_adapter.execute(
            request,
        )

        return A2ASafetyCallResult(
            response=response,
            used_local_fallback=True,
            failure_kind=failure_kind,
        )
