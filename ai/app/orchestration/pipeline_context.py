"""파이프라인 단계 간 데이터 공유 Context 모듈."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..retrieval import EvidenceApplicability, RetrievalOutcome
from ..schemas import (
    EvidenceReference,
    FollowUpQuestion,
    MissingField,
    ModelMetadata,
    ProcessingTrace,
    SafetyAssessment,
    StructuredSymptom,
    TraceContext,
    UsageGuidance,
)
from ..structuring.llm_contracts import SafetySignals


class PipelineContext(BaseModel):
    """LangGraph/오케스트레이터 파이프라인 실행 Context"""
    trace_context: TraceContext = Field(..., description="추적 식별 정보")
    raw_symptom: str = Field(..., description="자연어 원문 증상")
    model_code: str = Field("WPUJAC104DWH", description="문의 정수기 모델 코드")
    selected_symptoms: List[str] = Field(default_factory=list, description="선택된 대표 증상 목록")
    previous_answers: List[Dict[str, str]] = Field(default_factory=list, description="이전 문진 답변 목록")

    # 중간 실행 결과
    structured_symptom: Optional[StructuredSymptom] = Field(None, description="구조화 증상")
    safety_signals: SafetySignals = Field(
        default_factory=SafetySignals,
        description="내부 semantic layer가 추출한 안전 feature",
    )
    missing_fields: List[MissingField] = Field(default_factory=list, description="추가 확인이 필요한 누락 필드")
    followup_questions: List[FollowUpQuestion] = Field(default_factory=list, description="안전한 추가 질문")
    safety_assessment: Optional[SafetyAssessment] = Field(None, description="안전/위험도 평가 결과")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, description="RAG 근거 참조 목록")
    evidence_applicability: Optional[EvidenceApplicability] = Field(
        None,
        description="조건부 공식 근거에 적용하는 비식별 고정 문진 코드",
    )
    retrieval_outcome: RetrievalOutcome = Field(
        RetrievalOutcome.NOT_RUN,
        description="정상 검색 실행 여부와 근거 발견 결과",
    )
    retry_count: int = Field(0, ge=0, le=1, description="AI 내부 실제 재시도 횟수")
    usage_guidance: Optional[UsageGuidance] = Field(None, description="사용 안내 상태 및 문구")
    awaiting_customer_input: bool = Field(
        False,
        description="Runtime이 근거 적용·NO_EVIDENCE 확정 전에 추가 질문 답변을 기다리는 내부 상태",
    )
    retrieval_query_text: Optional[str] = Field(
        None,
        description="PII 제거 후 구조화 문맥을 결합한 내부 검색 질의",
    )
    evidence_selection_reasons: List[str] = Field(
        default_factory=list,
        description="고객 원문을 제외한 scenario 근거 선택 내부 trace",
    )
    evidence_sufficient: bool = Field(
        False,
        description="현재 근거만으로 Care Decision을 진행할 수 있는지 표시",
    )
    evidence_clarification_reason: Optional[str] = Field(
        None,
        description="원문 없이 남기는 Evidence clarification 결정 코드",
    )
    evidence_clarification_allowed: bool = Field(
        True,
        description="제품·근거 무결성 Guard가 clarification을 허용하는지 표시",
    )
    synthetic_scenario_candidate_count: int = Field(
        0,
        ge=0,
        description="공식 Evidence와 분리된 합성 Scenario 후보 수",
    )
    synthetic_scenario_ids: List[str] = Field(
        default_factory=list,
        description="고객 응답에 노출하지 않는 합성 Scenario 내부 식별자",
    )
    synthetic_clarification_requested: bool = Field(
        False,
        description="합성 Scenario 모호성으로 추가질문을 요청했는지 표시",
    )
    synthetic_clarification_target_field: Optional[str] = Field(
        None,
        description="합성 Scenario가 결정한 canonical 질문 대상 필드",
    )
    synthetic_clarification_reason: Optional[str] = Field(
        None,
        description="고객 원문 없이 남기는 합성 Scenario 결정 코드",
    )

    # 메타데이터 및 지연 추적
    model_metadata: ModelMetadata = Field(
        default_factory=lambda: ModelMetadata(model_name="single-rag-pipeline-v1", prompt_version="v1"),
        description="실행 메타데이터"
    )
    processing_traces: List[ProcessingTrace] = Field(default_factory=list, description="단계별 지연/상태 기록")
