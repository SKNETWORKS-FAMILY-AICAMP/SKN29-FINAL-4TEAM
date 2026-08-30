"""고객 안내 생성에 한정한 LLM Provider 경계."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

import httpx
import yaml
from pydantic import ValidationError

from ...generation.customer_guidance.models import (
    GuidanceGenerationRequest,
    GuidanceGenerationResult,
)
from ...generation.customer_guidance.prompt_identity import PROMPT_VERSION


class LLMConfigurationError(RuntimeError):
    """실제 LLM 호출에 필요한 환경 구성이 누락되었다."""


class LLMProviderConnectionError(ConnectionError):
    """재시도 가능한 Provider 연결·일시 오류."""


class LLMProviderTimeoutError(TimeoutError):
    """Provider 호출 시간이 초과되었다."""


class LLMOutputValidationError(ValueError):
    """Provider 출력이 요청된 strict Structured Output 계약을 충족하지 못했다."""


class LLMRefusalError(ValueError):
    """Provider가 요청 처리를 거부했다."""


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Provider가 반환한 토큰 사용량."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class GuidanceLLMResponse:
    """Provider 종속 응답을 제거한 Guidance 생성 결과."""

    output: GuidanceGenerationResult
    model_name: str
    usage: LLMUsage
    latency_ms: float


@dataclass(frozen=True, slots=True)
class StructuredOutputLLMResponse:
    """Responses API의 공통 strict JSON Schema 호출 결과."""

    output_text: str
    model_name: str
    usage: LLMUsage
    latency_ms: float


class GuidanceLLMClient(Protocol):
    """고객 안내 하위 계약만 생성하는 Provider Protocol."""

    def generate_guidance(
        self,
        request: GuidanceGenerationRequest,
        *,
        timeout_seconds: float,
    ) -> GuidanceLLMResponse: ...


class OpenAIResponsesLLMClient:
    """OpenAI Responses API Structured Output Adapter."""

    DEFAULT_MODEL = "gpt-4.1-mini"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.0,
        max_output_tokens: int = 500,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise LLMConfigurationError("OPENAI_API_KEY가 설정되지 않았습니다.")
        if not model_name.strip():
            raise LLMConfigurationError("AI_LLM_MODEL이 비어 있습니다.")
        self._validate_base_url(base_url)
        if not 0.0 <= temperature <= 2.0:
            raise LLMConfigurationError("LLM temperature는 0.0~2.0 범위여야 합니다.")
        if not 1 <= max_output_tokens <= 2000:
            raise LLMConfigurationError("LLM max_output_tokens는 1~2000 범위여야 합니다.")
        self._api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._http_client = http_client

    @classmethod
    def from_environment(cls) -> "OpenAIResponsesLLMClient":
        api_key = os.getenv("OPENAI_API_KEY", "")
        profile = cls._grounded_guidance_profile()
        approved_model = str(profile.get("model_name") or cls.DEFAULT_MODEL)
        configured_model = os.getenv("AI_LLM_MODEL", approved_model)
        if configured_model != approved_model:
            raise LLMConfigurationError(
                "AI_LLM_MODEL이 승인된 grounded_guidance Profile과 일치하지 않습니다."
            )
        return cls(
            api_key=api_key,
            model_name=configured_model,
            base_url=os.getenv("OPENAI_BASE_URL", cls.DEFAULT_BASE_URL),
            temperature=float(profile.get("temperature", 0.0)),
            max_output_tokens=int(profile.get("max_tokens", 500)),
        )

    def generate_guidance(
        self,
        request: GuidanceGenerationRequest,
        *,
        timeout_seconds: float,
    ) -> GuidanceLLMResponse:
        if timeout_seconds <= 0:
            raise LLMProviderTimeoutError("LLM 호출 시간 예산이 남아 있지 않습니다.")

        schema = self._guidance_schema(request)
        system_prompt, user_prompt = self._prompts(request)
        raw_response = self._request_structured_output(
            schema_name="customer_guidance",
            schema=schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=timeout_seconds,
        )
        try:
            output = GuidanceGenerationResult.model_validate_json(
                raw_response.output_text
            )
        except (ValidationError, ValueError) as exc:
            raise LLMOutputValidationError(
                "OpenAI Guidance 출력이 내부 Schema와 일치하지 않습니다."
            ) from exc
        return GuidanceLLMResponse(
            output=output,
            model_name=raw_response.model_name,
            usage=raw_response.usage,
            latency_ms=raw_response.latency_ms,
        )

    def _request_structured_output(
        self,
        *,
        schema_name: str,
        schema: dict[str, object],
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> StructuredOutputLLMResponse:
        """공식 Responses API strict Structured Output 전송을 공통 처리한다."""

        if timeout_seconds <= 0:
            raise LLMProviderTimeoutError("LLM 호출 시간 예산이 남아 있지 않습니다.")
        payload = {
            "model": self.model_name,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
            "store": False,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        started_at = time.perf_counter()
        try:
            request_kwargs = {
                "headers": {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                "json": payload,
                "timeout": timeout_seconds,
            }
            if self._http_client is not None:
                response = self._http_client.post(
                    f"{self.base_url}/responses",
                    **request_kwargs,
                )
            else:
                with httpx.Client() as client:
                    response = client.post(
                        f"{self.base_url}/responses",
                        **request_kwargs,
                    )
        except httpx.TimeoutException as exc:
            raise LLMProviderTimeoutError("OpenAI 응답 시간이 초과되었습니다.") from exc
        except httpx.TransportError as exc:
            raise LLMProviderConnectionError("OpenAI 연결을 완료하지 못했습니다.") from exc

        if response.status_code in {408, 504}:
            raise LLMProviderTimeoutError(
                f"OpenAI Timeout 상태가 반환되었습니다: {response.status_code}"
            )
        if response.status_code in {409, 429} or response.status_code >= 500:
            raise LLMProviderConnectionError(
                f"OpenAI 일시 오류 상태가 반환되었습니다: {response.status_code}"
            )
        if response.status_code >= 400:
            raise LLMOutputValidationError(
                f"OpenAI 요청이 거부되었습니다: {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise LLMOutputValidationError("OpenAI 응답이 JSON이 아닙니다.") from exc

        if not isinstance(body, dict):
            raise LLMOutputValidationError("OpenAI 응답 객체가 올바르지 않습니다.")
        if body.get("status") != "completed":
            raise LLMOutputValidationError("OpenAI 응답이 완료 상태가 아닙니다.")

        output_text = self._extract_output_text(body)
        usage_body = body.get("usage") if isinstance(body, dict) else None
        usage_body = usage_body if isinstance(usage_body, dict) else {}
        usage = LLMUsage(
            input_tokens=self._nonnegative_int(usage_body.get("input_tokens")),
            output_tokens=self._nonnegative_int(usage_body.get("output_tokens")),
            total_tokens=self._nonnegative_int(usage_body.get("total_tokens")),
        )
        return StructuredOutputLLMResponse(
            output_text=output_text,
            model_name=str(body.get("model") or self.model_name),
            usage=usage,
            latency_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
        )

    @staticmethod
    def _guidance_schema(request: GuidanceGenerationRequest) -> dict[str, object]:
        """Keep free-form grounded wording while constraining executable actions."""

        schema = GuidanceGenerationResult.model_json_schema()
        properties = schema["properties"]
        properties["message"]["description"] = (
            "공식 evidence_summaries의 사실, 조건, 수치, 경고 범위를 벗어나지 않는 "
            "고객 친화적 안내 문구"
        )
        properties["next_actions"]["items"]["enum"] = list(
            dict.fromkeys(request.allowed_next_actions)
        )
        return schema

    @staticmethod
    def _extract_output_text(body: object) -> str:
        if not isinstance(body, dict):
            raise LLMOutputValidationError("OpenAI 응답 객체가 올바르지 않습니다.")
        output_texts: list[str] = []
        for output in body.get("output", []):
            if not isinstance(output, dict) or output.get("type") != "message":
                continue
            for item in output.get("content", []):
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "refusal":
                    raise LLMRefusalError("OpenAI가 Structured Output 생성을 거부했습니다.")
                if item.get("type") == "output_text" and isinstance(item.get("text"), str):
                    output_texts.append(item["text"])
        if len(output_texts) != 1:
            raise LLMOutputValidationError(
                "OpenAI 응답에는 Structured Output이 정확히 1개여야 합니다."
            )
        return output_texts[0]

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        return (
            value
            if isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
            else 0
        )

    @staticmethod
    def _prompts(request: GuidanceGenerationRequest) -> tuple[str, str]:
        prompt_directory_version = PROMPT_VERSION.rsplit("/", maxsplit=1)[-1]
        prompt_dir = (
            Path(__file__).resolve().parents[3]
            / "prompts"
            / "customer_guidance"
            / prompt_directory_version
        )
        try:
            system_prompt = (prompt_dir / "system.txt").read_text(encoding="utf-8").strip()
            user_template = (prompt_dir / "user_template.txt").read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise LLMConfigurationError(
                f"{PROMPT_VERSION} Prompt를 읽을 수 없습니다."
            ) from exc
        request_json = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        return system_prompt, user_template.format(
            guidance_generation_request_json=request_json,
        )

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        parsed = urlsplit(base_url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise LLMConfigurationError(
                "OPENAI_BASE_URL의 Port가 올바르지 않습니다."
            ) from exc
        hostname = (parsed.hostname or "").casefold()
        official_host = hostname == "api.openai.com"
        if (
            parsed.scheme != "https"
            or not official_host
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/v1"
        ):
            raise LLMConfigurationError(
                "OPENAI_BASE_URL은 승인된 공식 HTTPS /v1 Endpoint여야 합니다."
            )

    @staticmethod
    def _grounded_guidance_profile() -> dict[str, object]:
        config_path = (
            Path(__file__).resolve().parents[3] / "configs" / "model_profiles.yaml"
        )
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            profile = config["tasks"]["safety_and_guidance"]["grounded_guidance"]
        except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
            raise LLMConfigurationError(
                "safety_and_guidance 모델 프로필을 읽을 수 없습니다."
            ) from exc
        if not isinstance(profile, dict) or profile.get("provider") != "openai":
            raise LLMConfigurationError(
                "safety_and_guidance 모델 프로필이 OpenAI 기준선과 일치하지 않습니다."
            )
        return profile
