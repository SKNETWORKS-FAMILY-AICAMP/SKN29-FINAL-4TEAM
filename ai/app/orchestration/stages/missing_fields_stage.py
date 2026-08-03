"""누락 필드 확인과 중복 없는 추가 질문 생성 Stage."""

import time

from ...schemas import AiStage, ProcessingTrace
from ...structuring import DuplicateQuestionGuard, FollowUpQuestionGenerator, MissingFieldChecker
from ..pipeline_context import PipelineContext


def execute_missing_fields_stage(ctx: PipelineContext) -> None:
    """구조화 결과에서 누락된 값만 질문으로 변환한다."""
    started_at = time.perf_counter()
    if ctx.structured_symptom is None:
        raise RuntimeError("누락 필드 검사 전에 증상 구조화가 필요합니다.")

    ctx.missing_fields = MissingFieldChecker().check(ctx.structured_symptom)
    generated = FollowUpQuestionGenerator().generate(ctx.missing_fields)
    ctx.followup_questions = DuplicateQuestionGuard().filter(generated, ctx.previous_answers)
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.CHECKING_MISSING_FIELDS,
            status="SUCCEEDED",
            latency_ms=round(elapsed_ms, 2),
        )
    )
