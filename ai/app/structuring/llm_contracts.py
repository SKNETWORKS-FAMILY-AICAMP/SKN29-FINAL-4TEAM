"""자연어 LLM과 구조화 도메인 사이의 Provider 중립 계약."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
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


class SafetySignalEvidence(BaseModel):
    """Safety Signal과 고객 입력 원문을 연결하는 내부 근거 계약."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    signal_name: Literal[
        "electrical_component_damage",
        "exposed_wire",
        "water_near_electrical_part",
        "smoke_or_burn",
        "shock_or_spark",
    ]
    evidence_quote: str = Field(min_length=1, max_length=500)
    source: Literal["RAW_SYMPTOM", "PREVIOUS_ANSWER"]


class SafetySignals(BaseModel):
    """LLM이 추출하고 근거 검증 후에만 정책 입력이 되는 내부 안전 feature."""

    model_config = ConfigDict(extra="forbid")

    electrical_component_damage: bool = False
    exposed_wire: bool = False
    water_near_electrical_part: bool = False
    smoke_or_burn: bool = False
    shock_or_spark: bool = False
    evidence: list[SafetySignalEvidence] = Field(default_factory=list, max_length=10)

    @property
    def requires_danger_policy(self) -> bool:
        return any(
            (
                self.electrical_component_damage,
                self.exposed_wire,
                self.water_near_electrical_part,
                self.smoke_or_burn,
                self.shock_or_spark,
            )
        )


class SymptomStructuringResult(BaseModel):
    """Provider 전용 결과이며 외부 DTO는 StructuredSymptom으로 유지한다."""

    model_config = ConfigDict(extra="forbid")

    structured_symptom: StructuredSymptom
    evidence_claims: list[SymptomEvidenceClaim] = Field(max_length=60)
    safety_signals: SafetySignals = Field(default_factory=SafetySignals)


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
    safety_signals: SafetySignals = dataclass_field(default_factory=SafetySignals)


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
    options: list[str] = Field(default_factory=list, max_length=5)
    allow_free_text: bool = False


class FollowUpWordingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[FollowUpWording] = Field(min_length=1, max_length=10)


@dataclass(frozen=True, slots=True)
class MissingFieldContext:
    target_field: str
    reason: str
    importance: Literal["high", "medium", "low"]


@dataclass(frozen=True, slots=True)
class FollowUpWordingRequest:
    structured_symptom: StructuredSymptom
    target_fields: tuple[str, ...]
    raw_symptom: str = ""
    selected_symptoms: tuple[str, ...] = ()
    previous_answers: tuple[dict[str, str], ...] = ()
    missing_field_contexts: tuple[MissingFieldContext, ...] = ()


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
