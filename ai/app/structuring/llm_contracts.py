"""자연어 LLM과 구조화 도메인 사이의 Provider 중립 계약."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..schemas import StructuredSymptom


ALLOWED_SYMPTOM_TYPES = (
    "제품 누수",
    "전기 이상",
    "온도 이상",
    "출수량 저하",
    "물맛/냄새 이상",
    "소음 이상",
    "필터/관리 문의",
    "기타 증상",
)
ALLOWED_WATER_TYPES = ("냉수", "온수", "정수", "전체")


class SymptomEvidenceClaim(BaseModel):
    """내부 LLM 후보 필드와 실제 고객 입력 사이의 출처 주장."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_name: Literal[
        "symptom_type",
        "occurrence_time",
        "target_water_type",
        "occurrence_condition",
        "error_code",
        "accompanying_symptoms",
        "actions_taken",
    ]
    value: str = Field(min_length=1, max_length=500)
    source: Literal["RAW_SYMPTOM", "SELECTED_SYMPTOM", "PREVIOUS_ANSWER"]
    evidence_quote: str = Field(min_length=1, max_length=500)


class SymptomStructuringResult(BaseModel):
    """Provider 전용 결과이며 외부 DTO는 StructuredSymptom으로 유지한다."""

    model_config = ConfigDict(extra="forbid")

    structured_symptom: StructuredSymptom
    evidence_claims: list[SymptomEvidenceClaim] = Field(max_length=60)


class LLMUsageMetadata(Protocol):
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class SymptomStructuringRequest:
    raw_symptom: str
    selected_symptoms: tuple[str, ...] = ()
    previous_answers: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SymptomStructuringLLMResponse:
    output: StructuredSymptom
    model_name: str
    prompt_version: str
    usage: LLMUsageMetadata
    latency_ms: float
    evidence_claims: tuple[SymptomEvidenceClaim, ...] = ()


class SymptomStructuringLLMClient(Protocol):
    def structure_symptom(
        self,
        request: SymptomStructuringRequest,
        *,
        timeout_seconds: float,
    ) -> SymptomStructuringLLMResponse: ...


class FollowUpWording(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_field: str = Field(min_length=1, max_length=100)
    question_text: str = Field(min_length=1, max_length=200)


class FollowUpWordingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[FollowUpWording] = Field(min_length=1, max_length=10)


@dataclass(frozen=True, slots=True)
class FollowUpWordingRequest:
    structured_symptom: StructuredSymptom
    target_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FollowUpWordingLLMResponse:
    output: FollowUpWordingResult
    model_name: str
    prompt_version: str
    usage: LLMUsageMetadata
    latency_ms: float


class FollowUpWordingLLMClient(Protocol):
    def generate_followup_wording(
        self,
        request: FollowUpWordingRequest,
        *,
        timeout_seconds: float,
    ) -> FollowUpWordingLLMResponse: ...
