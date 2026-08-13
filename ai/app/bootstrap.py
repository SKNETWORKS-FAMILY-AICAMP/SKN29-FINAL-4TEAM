"""FastAPI 애플리케이션 팩토리 모듈."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .interfaces.http.error_handlers import register_error_handlers
from .interfaces.http.routes.analysis_routes import router as analysis_router
from .interfaces.http.routes.experiment_playground_routes import router as experiment_playground_router
from .interfaces.http.routes.health_routes import router as health_router
from .interfaces.http.runtime_policy import get_runtime_policy
from .interfaces.http.structured_logging import configure_structured_logging
from .integrations.llm.token_usage import configure_llm_usage_logging
from .orchestration.pipeline_router import warmup_configured_search_service


EXPERIMENT_PLAYGROUND_ENV = "AI_ENABLE_EXPERIMENT_PLAYGROUND"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Local RAG 모델을 요청 Timeout 밖인 애플리케이션 시작 단계에서 준비한다."""

    if os.getenv("AI_VECTOR_DSN"):
        await asyncio.to_thread(warmup_configured_search_service)
    yield


def experiment_playground_enabled() -> bool:
    """Keep LAB-only routes closed unless the process explicitly opts in."""

    return os.getenv(EXPERIMENT_PLAYGROUND_ENV, "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def create_app() -> FastAPI:
    """FastAPI 인스턴스 생성 및 라우터·미들웨어·오류핸들러 설정"""
    get_runtime_policy()
    configure_structured_logging()
    configure_llm_usage_logging()
    app = FastAPI(
        title="SK Watercare AI Service",
        description="정수기 구독 고객 케어 및 A/S 업무 지원 시스템 - AI/RAG 분석 서비스",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    # 1. CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. 오류 핸들러 등록
    register_error_handlers(app)

    # 3. 라우터 등록
    app.include_router(health_router)
    app.include_router(analysis_router)
    if experiment_playground_enabled():
        app.include_router(experiment_playground_router)

    return app
