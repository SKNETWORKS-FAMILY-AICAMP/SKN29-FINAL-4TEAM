"""LLM에 허용된 고객 안내 전용 내부 Structured Output 계약."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class GuidanceInternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GuidanceGenerationRequest(GuidanceInternalModel):
    """Safety·Evidence·Trace의 권위를 넘기지 않는 생성 입력."""

    model_code: str = Field(..., min_length=1, max_length=100)
    symptom_summary: str = Field(..., min_length=1, max_length=2000)
    risk_level: Literal["general", "caution"]
    guidance_status: Literal["NORMAL", "PARTIAL_STOP"]
    safety_reason: str = Field(..., min_length=1, max_length=1000)
    restricted_functions: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list,
        max_length=10,
    )
    allowed_next_actions: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        ...,
        min_length=1,
        max_length=10,
    )
    evidence_summaries: list[Annotated[str, Field(min_length=1, max_length=4000)]] = Field(
        ...,
        min_length=1,
        max_length=5,
    )


class GuidanceGenerationResult(GuidanceInternalModel):
    """LLM이 공식 Evidence 선택과 허용 행동만 결정하도록 제한한다."""

    selected_evidence_index: int = Field(
        ...,
        ge=0,
        le=4,
        strict=True,
        description="evidence_summaries에서 선택한 0 기반 항목 번호",
    )
    next_actions: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        ...,
        min_length=1,
        max_length=5,
    )
