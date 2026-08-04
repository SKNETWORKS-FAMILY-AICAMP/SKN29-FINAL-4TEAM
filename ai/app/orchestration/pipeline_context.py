"""파이프라인 단계 간 데이터 공유 Context 모듈."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..retrieval import RetrievalOutcome
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


class PipelineContext(BaseModel):
    """LangGraph/오케스트레이터 파이프라인 실행 Context"""
    trace_context: TraceContext = Field(..., description="추적 식별 정보")
    raw_symptom: str = Field(..., description="자연어 원문 증상")
    model_code: str = Field("WPUJAC104DWH", description="문의 정수기 모델 코드")
    selected_symptoms: List[str] = Field(default_factory=list, description="선택된 대표 증상 목록")
    previous_answers: List[Dict[str, str]] = Field(default_factory=list, description="이전 문진 답변 목록")

    # 중간 실행 결과
    structured_symptom: Optional[StructuredSymptom] = Field(None, description="구조화 증상")
    missing_fields: List[MissingField] = Field(default_factory=list, description="추가 확인이 필요한 누락 필드")
    followup_questions: List[FollowUpQuestion] = Field(default_factory=list, description="안전한 추가 질문")
    safety_assessment: Optional[SafetyAssessment] = Field(None, description="안전/위험도 평가 결과")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, description="RAG 근거 참조 목록")
    retrieval_outcome: RetrievalOutcome = Field(
        RetrievalOutcome.NOT_RUN,
        description="정상 검색 실행 여부와 근거 발견 결과",
    )
    retry_count: int = Field(0, ge=0, le=1, description="AI 내부 실제 재시도 횟수")
    usage_guidance: Optional[UsageGuidance] = Field(None, description="사용 안내 상태 및 문구")

    # 메타데이터 및 지연 추적
    model_metadata: ModelMetadata = Field(
        default_factory=lambda: ModelMetadata(model_name="single-rag-pipeline-v1", prompt_version="v1"),
        description="실행 메타데이터"
    )
    processing_traces: List[ProcessingTrace] = Field(default_factory=list, description="단계별 지연/상태 기록")
