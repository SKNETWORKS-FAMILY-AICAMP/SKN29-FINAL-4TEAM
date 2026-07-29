"""파이프라인 라우터 모듈."""

from typing import Any, Dict, List, Optional
from .pipeline_context import PipelineContext
from .pipeline_result import PipelineResult
from .pipelines.single_rag_pipeline import SingleRAGPipeline
from ..schemas import TraceContext


class PipelineRouter:
    """파이프라인 실행 라우터 싱글톤"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PipelineRouter, cls).__new__(cls)
        return cls._instance

    def run_pipeline(
        self,
        inquiry_id: str,
        correlation_id: str,
        raw_symptom: str,
        model_code: str = "WPUJAC104DWH",
        selected_symptoms: Optional[List[str]] = None,
        previous_answers: Optional[List[Dict[str, str]]] = None
    ) -> PipelineResult:
        """단일 RAG 파이프라인 가동 및 결과 반환"""
        ctx = PipelineContext(
            trace_context=TraceContext(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id
            ),
            raw_symptom=raw_symptom,
            model_code=model_code,
            selected_symptoms=selected_symptoms or [],
            previous_answers=previous_answers or []
        )

        pipeline = SingleRAGPipeline()
        return pipeline.run(ctx)
