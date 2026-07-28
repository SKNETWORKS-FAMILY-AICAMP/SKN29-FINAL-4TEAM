"""RAG 근거 참조 Pydantic 데이터 모델."""

from typing import Optional
from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    """공식 문서 RAG 근거 참조 모델"""
    document_title: str = Field(..., description="공식 매뉴얼/FAQ 문서명")
    document_version: Optional[str] = Field(None, description="문서 버전")
    page: Optional[int] = Field(None, description="인용 페이지 번호")
    chunk_id: str = Field(..., description="내부 검색 청크 식별자")
    official_url: Optional[str] = Field(None, description="공식 랜딩 페이지 URL")
    summary: str = Field(..., description="검색 구간 요약 내용")
    similarity_score: Optional[float] = Field(None, description="검색 코사인 유사도 점수")
    verification_status: str = Field("official_verified", description="근거 검증 상태 (official_verified, team_verified)")
