"""AI/RAG evaluation 패키지 모듈."""

from .eval_dataset_loader import EvalDatasetLoader
from .metrics import calculate_mrr, calculate_recall_at_k, is_safety_compliant

__all__ = [
    "calculate_recall_at_k",
    "calculate_mrr",
    "is_safety_compliant",
    "EvalDatasetLoader",
    "EvaluationRunner"
]


def __getattr__(name: str):
    """실행기 간 순환 Import 없이 기존 공개 API를 지연 로딩한다."""
    if name == "EvaluationRunner":
        from .evaluation_runner import EvaluationRunner

        return EvaluationRunner
    raise AttributeError(name)
