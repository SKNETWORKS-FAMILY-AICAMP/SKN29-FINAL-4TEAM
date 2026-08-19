"""제품 모델 및 세대 메타데이터 필터 모듈."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml

from ..models.retrieved_chunk import RetrievedChunk


class ProductFilter:
    """활성 Runtime 정책에 따른 제품 모델 및 세대 메타데이터 검증 필터."""

    def __init__(
        self,
        allowed_generations: Optional[List[str]] = None,
        excluded_models: Optional[List[str]] = None,
        target_models: Optional[List[str]] = None,
    ):
        policy = _active_metadata_filters()
        self.allowed_generations = set(
            allowed_generations
            if allowed_generations is not None
            else policy.get("allowed_generations", [])
        )
        self.excluded_models = set(
            excluded_models
            if excluded_models is not None
            else policy.get("excluded_models", [])
        )
        self.target_models = set(
            target_models
            if target_models is not None
            else policy.get("target_models", [])
        )

    def is_valid_chunk(self, chunk: RetrievedChunk, requested_model: Optional[str] = None) -> bool:
        """청크가 현재 활성 제품·세대 정책과 정확 판매코드에 맞는지 검증."""
        if chunk.product_generation not in self.allowed_generations:
            return False

        if (
            chunk.model_code in self.excluded_models
            or chunk.manual_model in self.excluded_models
        ):
            return False

        if (
            self.target_models
            and chunk.model_code is not None
            and chunk.model_code not in self.target_models
        ):
            return False

        if requested_model and chunk.model_code != requested_model:
            return False

        return True

    def filter_chunks(self, chunks: List[RetrievedChunk], requested_model: Optional[str] = None) -> List[RetrievedChunk]:
        """청크 리스트에 필터 적용"""
        return [c for c in chunks if self.is_valid_chunk(c, requested_model)]


@lru_cache(maxsize=1)
def _active_metadata_filters() -> dict[str, list[str]]:
    config_path = Path(__file__).resolve().parents[3] / "configs" / "retrieval_policy.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    filters = config.get("metadata_filters")
    if not isinstance(filters, dict):
        raise ValueError("retrieval_policy.yaml에 metadata_filters가 필요합니다.")
    return filters
