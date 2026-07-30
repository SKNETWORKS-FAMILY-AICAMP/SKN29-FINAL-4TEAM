"""RAG 검색 쿼리 DTO 모델."""

from typing import Optional
from pydantic import BaseModel, Field


class RetrievalQuery(BaseModel):
    """RAG 검색 요청 쿼리 및 메타데이터 필터 DTO"""
    query_text: str = Field(..., min_length=1, max_length=4000, description="검색할 질의 문장")
    model_code: Optional[str] = Field("WPUJAC104DWH", description="문의 정수기 모델 코드")
    product_generation: Optional[str] = Field("D", description="제품 세대 (MVP 기본값: D)")
    top_k: int = Field(5, ge=1, le=20, description="검색 결과 반환 개수 (기본 5)")
    require_official_verified: bool = Field(True, description="공식 검증 문서만 검색할지 여부")
