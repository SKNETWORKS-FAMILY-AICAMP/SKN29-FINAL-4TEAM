"""상담 맥락 합성 전용 LLM Provider 경계."""

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

from ...generation.consultation_summary.context_models import (
    ConsultationContextSynthesisCandidate,
    ConsultationContextSynthesisRequest,
)
from ...generation.consultation_summary.prompt_identity import PROMPT_VERSION
from .llm_client import (
    LLMConfigurationError,
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMRefusalError,
    LLMUsage,
)


@dataclass(frozen=True, slots=True)
class ConsultationContextLLMResponse:
    output: ConsultationContextSynthesisCandidate
    model_name: str
    usage: LLMUsage
    latency_ms: float


class ConsultationContextLLMClient(Protocol):
    def synthesize_context(
        self,
        request: ConsultationContextSynthesisRequest,
        *,
        timeout_seconds: float,
    ) -> ConsultationContextLLMResponse: ...


class OpenAIResponsesConsultationContextClient:
    """Responses API strict Structured Output으로 상담 브리프 후보만 생성한다."""

    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise LLMConfigurationError("OPENAI_API_KEY가 설정되지 않았습니다.")
        if not model_name.strip():
            raise LLMConfigurationError("consultation_summary 모델명이 비어 있습니다.")
        self._validate_base_url(base_url)
        if not 0.0 <= temperature <= 2.0:
            raise LLMConfigurationError("LLM temperature는 0.0~2.0 범위여야 합니다.")
        if not 1 <= max_output_tokens <= 4000:
            raise LLMConfigurationError("LLM max_output_tokens는 1~4000 범위여야 합니다.")
        self._api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._http_client = http_client

    @classmethod
    def from_environment(cls) -> "OpenAIResponsesConsultationContextClient":
        profile = cls._consultation_summary_profile()
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name=str(profile.get("model_name") or cls.DEFAULT_MODEL),
            base_url=os.getenv("OPENAI_BASE_URL", cls.DEFAULT_BASE_URL),
            temperature=float(profile.get("temperature", 0.2)),
            max_output_tokens=int(profile.get("max_tokens", 800)),
        )

    def synthesize_context(
        self,
        request: ConsultationContextSynthesisRequest,
        *,
        timeout_seconds: float,
    ) -> ConsultationContextLLMResponse:
        if timeout_seconds <= 0:
            raise LLMProviderTimeoutError("상담 맥락 합성 시간 예산이 남아 있지 않습니다.")

        system_prompt, user_prompt = self._prompts(request)
        payload = {
            "model": self.model_name,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "counselor_context_brief",
                    "strict": True,
                    "schema": ConsultationContextSynthesisCandidate.model_json_schema(),
                }
            },
            "store": False,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        started_at = time.perf_counter()
        request_kwargs = {
            "headers": {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            "json": payload,
            "timeout": timeout_seconds,
        }
        try:
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
            raise LLMProviderTimeoutError("OpenAI 상담 맥락 합성 시간이 초과되었습니다.") from exc
        except httpx.TransportError as exc:
            raise LLMProviderConnectionError("OpenAI 상담 맥락 합성 연결에 실패했습니다.") from exc

        if response.status_code in {408, 504}:
            raise LLMProviderTimeoutError(
                f"OpenAI Timeout 상태가 반환되었습니다: {response.status_code}"
            )
        if response.status_code in {409, 429} or response.status_code >= 500:
            raise LLMProviderConnectionError(
                f"OpenAI 일시 오류 상태가 반환되었습니다: {response.status_code}"
            )
        if response.status_code in {401, 403, 404}:
            raise LLMConfigurationError(
                f"OpenAI 인증 또는 Endpoint 구성이 거부되었습니다: {response.status_code}"
            )
        if response.status_code >= 400:
            raise LLMOutputValidationError(
                f"OpenAI 상담 맥락 합성 요청이 거부되었습니다: {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise LLMOutputValidationError("OpenAI 응답이 JSON이 아닙니다.") from exc
        if not isinstance(body, dict) or body.get("status") != "completed":
            raise LLMOutputValidationError("OpenAI 상담 맥락 합성이 완료 상태가 아닙니다.")

        output_text = self._extract_output_text(body)
        try:
            output = ConsultationContextSynthesisCandidate.model_validate_json(output_text)
        except (ValidationError, ValueError) as exc:
            raise LLMOutputValidationError(
                "OpenAI 상담 맥락 합성 출력이 내부 Schema와 일치하지 않습니다."
            ) from exc

        usage_body = body.get("usage")
        usage_body = usage_body if isinstance(usage_body, dict) else {}
        usage = LLMUsage(
            input_tokens=self._nonnegative_int(usage_body.get("input_tokens")),
            output_tokens=self._nonnegative_int(usage_body.get("output_tokens")),
            total_tokens=self._nonnegative_int(usage_body.get("total_tokens")),
        )
        return ConsultationContextLLMResponse(
            output=output,
            model_name=str(body.get("model") or self.model_name),
            usage=usage,
            latency_ms=round((time.perf_counter() - started_at) * 1000.0, 2),
        )

    @staticmethod
    def _extract_output_text(body: dict[str, object]) -> str:
        output_texts: list[str] = []
        output_items = body.get("output", [])
        if not isinstance(output_items, list):
            raise LLMOutputValidationError("OpenAI output 형식이 올바르지 않습니다.")
        for output in output_items:
            if not isinstance(output, dict) or output.get("type") != "message":
                continue
            content_items = output.get("content", [])
            if not isinstance(content_items, list):
                continue
            for item in content_items:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "refusal":
                    raise LLMRefusalError("OpenAI가 상담 맥락 합성을 거부했습니다.")
                if item.get("type") == "output_text" and isinstance(item.get("text"), str):
                    output_texts.append(item["text"])
        if len(output_texts) != 1:
            raise LLMOutputValidationError(
                "OpenAI 응답에는 상담 맥락 합성 출력이 정확히 1개여야 합니다."
            )
        return output_texts[0]

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return 0

    @staticmethod
    def _prompts(
        request: ConsultationContextSynthesisRequest,
    ) -> tuple[str, str]:
        prompt_directory_version = PROMPT_VERSION.rsplit("/", maxsplit=1)[-1]
        prompt_dir = (
            Path(__file__).resolve().parents[3]
            / "prompts"
            / "consultation_summary"
            / prompt_directory_version
        )
        try:
            system_prompt = (prompt_dir / "system.txt").read_text(
                encoding="utf-8"
            ).strip()
            user_template = (prompt_dir / "user_template.txt").read_text(
                encoding="utf-8"
            ).strip()
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
            consultation_context_synthesis_request_json=request_json,
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
        if (
            parsed.scheme != "https"
            or hostname != "api.openai.com"
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
    def _consultation_summary_profile() -> dict[str, object]:
        config_path = (
            Path(__file__).resolve().parents[3] / "configs" / "model_profiles.yaml"
        )
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            profile = config["tasks"]["consultation_summary"]
        except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
            raise LLMConfigurationError(
                "consultation_summary 모델 프로필을 읽을 수 없습니다."
            ) from exc
        if not isinstance(profile, dict) or profile.get("provider") != "openai":
            raise LLMConfigurationError(
                "consultation_summary 모델 프로필이 OpenAI 기준선과 일치하지 않습니다."
            )
        return profile
