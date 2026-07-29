"""Health Check API 라우터 모듈."""

from fastapi import APIRouter
from ai.app.interfaces.http.response_models import HealthCheckResponse
from ai.app.safety.rule_loader import SafetyRuleLoader

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthCheckResponse, summary="AI 서비스 Liveness 점검")
@router.get("/api/v1/ai/health", response_model=HealthCheckResponse, summary="AI 서비스 Liveness 점검 (v1)")
async def get_health():
    """서버 Liveness 및 안전 규칙 로딩 상태 확인"""
    loader = SafetyRuleLoader()
    rules = loader.get_safety_rules()
    config_loaded = bool(rules and "rules" in rules)

    return HealthCheckResponse(
        status="ok",
        service="ai-service",
        version="1.0.0",
        config_loaded=config_loaded
    )
