"""증상 구조화와 Follow-up 표현에 한정한 Responses API Adapter."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock

import httpx
import yaml
from pydantic import ValidationError

from ...structuring.llm_contracts import (
    ALLOWED_SYMPTOM_TYPES,
    ALLOWED_WATER_TYPES,
    FollowUpWording,
    FollowUpWordingLLMResponse,
    FollowUpWordingRequest,
    FollowUpWordingResult,
    SymptomStructuringResult,
    SymptomStructuringLLMResponse,
    SymptomStructuringRequest,
)
from .llm_client import (
    LLMConfigurationError,
    LLMOutputValidationError,
    OpenAIResponsesLLMClient,
)


_SHARED_HTTP_CLIENT: httpx.Client | None = None
_SHARED_HTTP_CLIENT_LOCK = Lock()


def get_shared_natural_language_http_client() -> httpx.Client:
    """증상 구조화와 Follow-up Provider가 TCP/TLS connection pool을 공유한다."""

    global _SHARED_HTTP_CLIENT
    with _SHARED_HTTP_CLIENT_LOCK:
        if _SHARED_HTTP_CLIENT is None or _SHARED_HTTP_CLIENT.is_closed:
            _SHARED_HTTP_CLIENT = httpx.Client(
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                )
            )
        return _SHARED_HTTP_CLIENT


def close_shared_natural_language_http_client() -> None:
    """앱 종료 시 공유 Provider connection pool을 정리한다."""

    global _SHARED_HTTP_CLIENT
    with _SHARED_HTTP_CLIENT_LOCK:
        client = _SHARED_HTTP_CLIENT
        _SHARED_HTTP_CLIENT = None
    if client is not None:
        client.close()


class _TaskConfiguredResponsesClient(OpenAIResponsesLLMClient):
    TASK_NAME: str

    def __init__(self, *, prompt_version: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.prompt_version = prompt_version

    @classmethod
    def from_environment(cls, *, http_client: httpx.Client | None = None):
        profile, prompt_version = _load_task_configuration(cls.TASK_NAME)
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name=str(profile["model_name"]),
            base_url=os.getenv("OPENAI_BASE_URL", cls.DEFAULT_BASE_URL),
            temperature=float(profile.get("temperature", 0.0)),
            max_output_tokens=int(profile.get("max_tokens", 500)),
            prompt_version=prompt_version,
            http_client=http_client,
        )

    def _prompts(self) -> tuple[str, str]:
        task_name, version = self.prompt_version.split("/", maxsplit=1)
        prompt_dir = (
            Path(__file__).resolve().parents[3]
            / "prompts"
            / task_name
            / version
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
                f"{self.prompt_version} Prompt를 읽을 수 없습니다."
            ) from exc
        if not system_prompt or not user_template:
            raise LLMConfigurationError(
                f"{self.prompt_version} Prompt가 비어 있습니다."
            )
        return system_prompt, user_template


class OpenAIResponsesSymptomStructuringClient(_TaskConfiguredResponsesClient):
    """자연어를 canonical StructuredSymptom으로만 변환한다."""

    TASK_NAME = "symptom_structuring"

    def structure_symptom(
        self,
        request: SymptomStructuringRequest,
        *,
        timeout_seconds: float,
    ) -> SymptomStructuringLLMResponse:
        system_prompt, user_template = self._prompts()
        previous_answers = [
            {
                "question_id": str(item.get("question_id", ""))[:100],
                "answer_text": _redact_customer_text(
                    str(item.get("answer_text", "")),
                    limit=500,
                ),
            }
            for item in request.previous_answers
            if isinstance(item, dict)
        ]
        user_prompt = user_template.format(
            raw_symptom=_redact_customer_text(request.raw_symptom, limit=2000),
            selected_symptoms=json.dumps(
                [
                    _redact_customer_text(value, limit=100)
                    for value in request.selected_symptoms
                ],
                ensure_ascii=False,
            ),
            previous_answers=json.dumps(
                previous_answers,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        response = self._request_structured_output(
            schema_name="symptom_structuring",
            schema=self._schema(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=timeout_seconds,
        )
        try:
            result = SymptomStructuringResult.model_validate_json(
                response.output_text
            )
        except (ValidationError, ValueError) as exc:
            raise LLMOutputValidationError(
                "증상 구조화 출력이 canonical Schema와 일치하지 않습니다."
            ) from exc
        return SymptomStructuringLLMResponse(
            output=result.structured_symptom,
            evidence_claims=tuple(result.evidence_claims),
            safety_signals=result.safety_signals,
            model_name=response.model_name,
            prompt_version=self.prompt_version,
            usage=response.usage,
            latency_ms=response.latency_ms,
        )

    @staticmethod
    def _schema() -> dict[str, object]:
        schema = SymptomStructuringResult.model_json_schema()
        symptom_schema = schema["$defs"]["StructuredSymptom"]
        properties = symptom_schema["properties"]
        properties["symptom_type"]["enum"] = list(ALLOWED_SYMPTOM_TYPES)
        properties["target_water_type"] = {
            "anyOf": [
                {"type": "string", "enum": list(ALLOWED_WATER_TYPES)},
                {"type": "null"},
            ],
            "description": "대상 출수 종류",
        }
        symptom_schema["required"] = list(properties)
        claim_schema = schema["$defs"]["SymptomEvidenceClaim"]
        claim_schema["required"] = list(claim_schema["properties"])
        signal_schema = schema["$defs"]["SafetySignals"]
        signal_schema["required"] = list(signal_schema["properties"])
        safety_evidence_schema = schema["$defs"]["SafetySignalEvidence"]
        safety_evidence_schema["required"] = list(
            safety_evidence_schema["properties"]
        )
        schema["required"] = list(schema["properties"])
        return schema


class OpenAIResponsesFollowUpWordingClient(_TaskConfiguredResponsesClient):
    """결정된 target field의 질문 문구만 자연스럽게 표현한다."""

    TASK_NAME = "followup_question"

    def generate_followup_wording(
        self,
        request: FollowUpWordingRequest,
        *,
        timeout_seconds: float,
    ) -> FollowUpWordingLLMResponse:
        if not request.target_fields:
            raise LLMOutputValidationError("Follow-up target field가 비어 있습니다.")
        system_prompt, user_template = self._prompts()
        selected_symptoms = [
            _redact_customer_text(str(value), limit=100)
            for value in request.selected_symptoms
            if str(value).strip()
        ]
        previous_answers = [
            {
                "question_id": str(item.get("question_id", ""))[:100],
                "answer_text": _redact_customer_text(
                    str(item.get("answer_text", "")),
                    limit=500,
                ),
            }
            for item in request.previous_answers
            if isinstance(item, dict)
            and str(item.get("question_id", "")).strip()
            and str(item.get("answer_text", "")).strip()
        ]
        missing_field_contexts = [
            {
                "target_field": item.target_field[:100],
                "reason": _redact_customer_text(item.reason, limit=500),
                "importance": item.importance,
            }
            for item in request.missing_field_contexts
            if item.target_field in request.target_fields
        ]
        symptom_json = _redact_customer_text(
            json.dumps(
                request.structured_symptom.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ),
            limit=4000,
        )
        user_prompt = user_template.format(
            raw_symptom=_redact_customer_text(request.raw_symptom, limit=2000),
            selected_symptoms_json=json.dumps(
                selected_symptoms,
                ensure_ascii=False,
            ),
            structured_symptom_json=symptom_json,
            previous_answers_json=json.dumps(
                previous_answers,
                ensure_ascii=False,
                sort_keys=True,
            ),
            missing_field_contexts_json=json.dumps(
                missing_field_contexts,
                ensure_ascii=False,
                sort_keys=True,
            ),
            target_fields_json=json.dumps(
                list(request.target_fields),
                ensure_ascii=False,
            ),
        )
        response = self._request_structured_output(
            schema_name="followup_question_wording",
            schema=self._schema(request.target_fields),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=timeout_seconds,
        )
        try:
            output = FollowUpWordingResult.model_validate_json(
                response.output_text
            )
        except (ValidationError, ValueError) as exc:
            raise LLMOutputValidationError(
                "Follow-up 문구 출력이 내부 Schema와 일치하지 않습니다."
            ) from exc
        return FollowUpWordingLLMResponse(
            output=output,
            model_name=response.model_name,
            prompt_version=self.prompt_version,
            usage=response.usage,
            latency_ms=response.latency_ms,
        )

    @staticmethod
    def _schema(target_fields: tuple[str, ...]) -> dict[str, object]:
        schema = FollowUpWordingResult.model_json_schema()
        question_schema = schema["$defs"]["FollowUpWording"]
        question_schema["properties"]["target_field"]["enum"] = list(
            target_fields
        )
        question_schema["required"] = list(question_schema["properties"])
        questions = schema["properties"]["questions"]
        questions["minItems"] = len(target_fields)
        questions["maxItems"] = len(target_fields)
        schema["required"] = ["questions"]
        return schema


def _load_task_configuration(task_name: str) -> tuple[dict[str, object], str]:
    root = Path(__file__).resolve().parents[3]
    try:
        profiles = yaml.safe_load(
            (root / "configs" / "model_profiles.yaml").read_text(encoding="utf-8")
        )
        registry = yaml.safe_load(
            (root / "prompts" / "prompt_registry.yaml").read_text(encoding="utf-8")
        )
        profile = profiles["tasks"][task_name]
        prompt_entry = registry["tasks"][task_name]
        active_version = str(prompt_entry["active_version"])
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise LLMConfigurationError(
            f"{task_name} Model Profile 또는 Prompt Registry를 읽을 수 없습니다."
        ) from exc
    if not isinstance(profile, dict) or profile.get("provider") != "openai":
        raise LLMConfigurationError(
            f"{task_name} Model Profile이 OpenAI 활성 계약과 일치하지 않습니다."
        )
    if not isinstance(prompt_entry, dict) or prompt_entry.get("status") != "ACTIVE":
        raise LLMConfigurationError(
            f"{task_name} Prompt가 ACTIVE 상태가 아닙니다."
        )
    model_name = profile.get("model_name")
    if not isinstance(model_name, str) or not model_name.strip():
        raise LLMConfigurationError(f"{task_name} model_name이 비어 있습니다.")
    if re.fullmatch(r"v[1-9]\d*", active_version) is None:
        raise LLMConfigurationError(
            f"{task_name} active prompt version 형식이 올바르지 않습니다."
        )
    return profile, f"{task_name}/{active_version}"


_PRIVATE_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
    re.compile(r"https?://\S+", flags=re.IGNORECASE),
)


def _redact_customer_text(value: str, *, limit: int) -> str:
    sanitized = value
    for pattern in _PRIVATE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized[:limit]
