"""RAG 검색 청크 DTO 모델."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """Vector Store에서 검색된 매뉴얼/FAQ 청크 DTO"""
    chunk_id: str = Field(..., description="청크 고유 식별자")
    document_id: Optional[str] = Field(None, description="공식 문서 식별자")
    document_title: str = Field(..., description="공식 매뉴얼/FAQ 문서명")
    document_version: Optional[str] = Field("1.0", description="문서 버전")
    page: Optional[int] = Field(None, description="해당 내용 페이지 번호")
    page_refs: List[int] = Field(default_factory=list, description="전체 근거 페이지 번호")
    manual_model: str = Field(..., description="해당 청크 제품 모델명")
    model_code: Optional[str] = Field(None, description="정확한 판매 모델 코드")
    product_generation: str = Field("D", description="제품 세대")
    content: str = Field(..., description="청크 원문 텍스트")
    similarity_score: float = Field(..., description="코사인 유사도 점수 (0.0~1.0)")
    official_url: Optional[str] = Field(None, description="공식 랜딩 페이지 URL")
    verification_status: str = Field("official_verified", description="검증 상태")
    allowed_use: bool = Field(True, description="고객 안내 제공 허용 여부")
    source_hash: Optional[str] = Field(None, description="원문 SHA-256")
    embedding_model: Optional[str] = Field(None, description="적재에 사용한 Embedding 모델")
    embedding_model_revision: Optional[str] = Field(None, description="Embedding 모델 Commit SHA")
    index_version: Optional[str] = Field(None, description="적재·검색 설정 버전")
    chunk_set_sha256: Optional[str] = Field(None, description="적재 청크 집합 SHA-256")
    safe_actions: List[str] = Field(default_factory=list, description="근거에 명시된 안전 행동")
    topic_code: Optional[str] = Field(None, description="공식 근거의 증상 주제 코드")
