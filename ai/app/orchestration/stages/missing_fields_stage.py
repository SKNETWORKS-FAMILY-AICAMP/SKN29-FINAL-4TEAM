"""누락 필드 확인과 중복 없는 추가 질문 생성 Stage."""

import time

from ...retrieval import EvidenceApplicabilityGate
from ...schemas import AiStage, FollowUpQuestion, MissingField, ProcessingTrace
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
    target_field_names: tuple[str, ...] | None = None,
    question_overrides: tuple[FollowUpQuestion, ...] = (),
) -> None:
    """누락은 전체 기록하되 Evidence가 선택한 field만 질문으로 변환한다."""
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
    selected_missing_fields = ctx.missing_fields
    if target_field_names is not None:
        selected = set(target_field_names)
        selected_missing_fields = [
            item for item in ctx.missing_fields if item.field_name in selected
        ]
    override_by_field = {item.target_field: item for item in question_overrides}
    applicability_question = applicability_gate.followup_question(
        symptom_type=ctx.structured_symptom.symptom_type,
        previous_answers=ctx.previous_answers,
    )
    if (
        applicability_question is not None
        and (
            target_field_names is None
            or applicability_gate.TARGET_FIELD in target_field_names
        )
    ):
        override_by_field.setdefault(
            applicability_gate.TARGET_FIELD,
            applicability_question,
        )

    generated = FollowUpQuestionGenerator(llm_client=llm_client).generate(
        selected_missing_fields,
        symptom=ctx.structured_symptom,
        raw_symptom=ctx.raw_symptom,
        selected_symptoms=ctx.selected_symptoms,
        previous_answers=ctx.previous_answers,
        trace_context=ctx.trace_context,
        model_code=ctx.model_code,
        timeout_seconds=timeout_seconds,
        question_overrides=override_by_field,
    )
    ctx.followup_questions = DuplicateQuestionGuard().filter(
        generated,
        ctx.previous_answers,
    )
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.CHECKING_MISSING_FIELDS,
            status="SUCCEEDED",
            latency_ms=round(elapsed_ms, 2),
        )
    )
