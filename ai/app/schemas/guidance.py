"""사용 안내 상태 및 조치 가이드 Pydantic 데이터 모델."""

from typing import List
from pydantic import Field
from .common import ContractModel, UsageGuidanceStatus


class UsageGuidance(ContractModel):
    """현재 사용 안내 상태 및 다음 행동 가이드 모델"""
    guidance_status: UsageGuidanceStatus = Field(..., description="사용 안내 상태 (NORMAL, PARTIAL_STOP, TOTAL_STOP, PENDING_CONSULTATION)")
    message: str = Field(..., description="고객 친화적 현재 정수기 사용 상태 안내 문구")
    restricted_functions: List[str] = Field(default_factory=list, description="사용이 제한되는 기능 목록 (예: 온수 기능 중지, 전체 출수 중지)")
    next_actions: List[str] = Field(default_factory=list, description="고객이 수행해야 할 안전한 다음 행동 목록")
