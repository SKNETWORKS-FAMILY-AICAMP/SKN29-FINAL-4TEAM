"""단일 RAG 오케스트레이터 파이프라인 모듈."""

from ..pipeline_context import PipelineContext
from ..pipeline_result import PipelineResult
from ..stages import (
    execute_generation_stage,
    execute_retrieval_stage,
    execute_safety_check_stage,
    execute_structuring_stage,
    execute_validation_stage,
)


class SingleRAGPipeline:
    """단일 RAG 파이프라인 순차 오케스트레이터"""

    def run(self, ctx: PipelineContext) -> PipelineResult:
        """Stage 1 -> 2 -> 3 -> 4 -> 5 순차 가동"""
        # 1. 증상 필드 구조화 Stage
        execute_structuring_stage(ctx)

        # 2. 명시적 안전 분기 Stage
        execute_safety_check_stage(ctx)

        # 3. RAG 공식 문서 검색 Stage
        execute_retrieval_stage(ctx)

        # 4. 사용 안내 상태 판정 & 메시지 생성 Stage
        execute_generation_stage(ctx)

        # 5. 금지 표현 가드레일 & 스키마 2차 검증 Stage
        execute_validation_stage(ctx)

        return PipelineResult(success=True, context=ctx)
