"""제품 모델 및 세대 메타데이터 필터 모듈."""

from typing import List, Optional

from ..models.retrieved_chunk import RetrievedChunk


class ProductFilter:
    """제품 모델 및 세대(D세대) 메타데이터 검증 필터"""

    def __init__(self, allowed_generations: Optional[List[str]] = None, excluded_models: Optional[List[str]] = None):
        self.allowed_generations = allowed_generations or ["D"]
        self.excluded_models = excluded_models or ["WPUIAC425SNW", "WPU-IAC506"]

    def is_valid_chunk(self, chunk: RetrievedChunk, requested_model: Optional[str] = None) -> bool:
        """청크가 MVP 제품 세대(D) 및 대상 모델 조건에 맞는지 검증"""
        # 1. 세대 검증 (S 세대 등 배제)
        if chunk.product_generation not in self.allowed_generations:
            return False

        # 2. 제외 대상 모델 검증
        if chunk.manual_model in self.excluded_models:
            return False

        if requested_model and chunk.model_code != requested_model:
            return False

        return True

    def filter_chunks(self, chunks: List[RetrievedChunk], requested_model: Optional[str] = None) -> List[RetrievedChunk]:
        """청크 리스트에 필터 적용"""
        return [c for c in chunks if self.is_valid_chunk(c, requested_model)]
