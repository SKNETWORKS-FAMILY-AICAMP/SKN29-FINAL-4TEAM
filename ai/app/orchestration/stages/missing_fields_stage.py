"""누락 필드 확인과 중복 없는 추가 질문 생성 Stage."""

import time

from ...retrieval import EvidenceApplicabilityGate
from ...schemas import AiStage, MissingField, ProcessingTrace
from ...structuring import (
    DuplicateQuestionGuard,
    FollowUpQuestionGenerator,
    MissingFieldChecker,
)
from ...structuring.llm_contracts import FollowUpWordingLLMClient
from ..pipeline_context import PipelineContext


def execute_missing_fields_stage(
    ctx: PipelineContext,
    llm_client: FollowUpWordingLLMClient | None = None,
    *,
    timeout_seconds: float = 4.0,
) -> None:
    """구조화 결과에서 누락된 값만 질문으로 변환한다."""
    started_at = time.perf_counter()
    if ctx.structured_symptom is None:
        raise RuntimeError("누락 필드 검사 전에 증상 구조화가 필요합니다.")

    applicability_gate = EvidenceApplicabilityGate()
    applicability = applicability_gate.classify_for_symptom(
        symptom_type=ctx.structured_symptom.symptom_type,
        previous_answers=ctx.previous_answers,
    )
    if applicability is not None:
        ctx.structured_symptom.occurrence_condition = applicability.questionnaire_label

    ctx.missing_fields = MissingFieldChecker().check(ctx.structured_symptom)
    if (
        ctx.structured_symptom.symptom_type == "물맛/냄새 이상"
        and applicability is None
    ):
        ctx.missing_fields = [
            item
            for item in ctx.missing_fields
            if item.field_name != "occurrence_condition"
        ]
        ctx.missing_fields.append(
            MissingField(
                field_name=applicability_gate.TARGET_FIELD,
                reason=(
                    "물맛·냄새 공식 근거의 장기 부재·미사용·설치 조건을 "
                    "확인해야 합니다."
                ),
                importance="medium",
            )
        )
    generated = FollowUpQuestionGenerator(llm_client=llm_client).generate(
        ctx.missing_fields,
        symptom=ctx.structured_symptom,
        trace_context=ctx.trace_context,
        model_code=ctx.model_code,
        timeout_seconds=timeout_seconds,
    )
    ctx.followup_questions = DuplicateQuestionGuard().filter(
        generated,
        ctx.previous_answers,
    )
    applicability_question = applicability_gate.followup_question(
        symptom_type=ctx.structured_symptom.symptom_type,
        previous_answers=ctx.previous_answers,
    )
    if applicability_question is not None:
        ctx.followup_questions.append(applicability_question)
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.CHECKING_MISSING_FIELDS,
            status="SUCCEEDED",
            latency_ms=round(elapsed_ms, 2),
        )
    )
