"""실제 FastAPI AI Runtime을 호출하는 단일 시도 HTTP Client."""

from __future__ import annotations

from typing import Any

import httpx

from integrations.ai.exceptions import (
    AIConfigurationError,
    AIResponseValidationError,
    AIServiceResponseError,
    AITimeoutError,
    AITransportError,
)
from integrations.ai.response_mapper import (
    AIAnalysisResult,
    map_error_response,
    map_success_response,
)
from integrations.ai.retry_policy import (
    DEFAULT_BACKEND_AI_RETRY_POLICY,
    BackendAIRetryPolicy,
)
from integrations.ai.schema_validator import AIContractValidator


class AIClient:
    """Timeout 30초·자동 재시도 0회의 AI 분석 Client."""

    analysis_path = "/api/v1/ai/analyze"

    def __init__(
        self,
        *,
        base_url: str,
        mode: str = "local",
        timeout_seconds: float = 30.0,
        validator: AIContractValidator | None = None,
        retry_policy: BackendAIRetryPolicy | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url:
            raise AIConfigurationError("AI_SERVICE_BASE_URL이 필요합니다.")
        if mode not in {"mock", "local"}:
            raise AIConfigurationError("AI mode는 mock 또는 local이어야 합니다.")
        if timeout_seconds != 30.0:
            raise AIConfigurationError("Backend AI Timeout은 30초여야 합니다.")

        self.base_url = normalized_url
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.validator = validator or AIContractValidator()
        self.retry_policy = (
            retry_policy or DEFAULT_BACKEND_AI_RETRY_POLICY
        )
        self._http_client = http_client

    def analyze(self, request_payload: dict[str, Any]) -> AIAnalysisResult:
        """요청 검증 후 정확히 한 번 호출하고 응답을 검증한다."""

        self.validator.validate_request(request_payload)
        client = self._http_client or httpx.Client(
            timeout=httpx.Timeout(self.timeout_seconds),
        )
        owns_client = self._http_client is None
        try:
            response = client.post(
                f"{self.base_url}{self.analysis_path}",
                params={"mode": self.mode},
                headers={
                    "X-Correlation-ID": request_payload["correlation_id"],
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError(
                "AI 서비스 호출 시간이 초과되었습니다.",
                http_status=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise AITransportError(
                "AI 서비스에 연결할 수 없습니다.",
            ) from exc
        finally:
            if owns_client:
                client.close()

        payload = self._json_payload(response)
        if 200 <= response.status_code < 300:
            return map_success_response(
                payload,
                expected_request=request_payload,
                validator=self.validator,
            )

        error_result = map_error_response(
            payload,
            expected_request=request_payload,
            validator=self.validator,
        )
        detail = error_result.detail
        raise AIServiceResponseError(
            "AI 서비스가 오류를 반환했습니다.",
            code=detail["code"],
            http_status=response.status_code,
            retryable=detail["retryable"],
            failure_stage=detail["failure_stage"],
            retry_count=detail["retry_count"],
            payload=payload,
        )

    @staticmethod
    def _json_payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIResponseValidationError(
                "AI 응답이 JSON 객체가 아닙니다.",
            ) from exc
        if not isinstance(payload, dict):
            raise AIResponseValidationError(
                "AI 응답 최상위 값은 JSON 객체여야 합니다.",
            )
        return payload
