"""A4 Experiment Playground v0 페이지 및 단일 Query API."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import Field

from ai.app.experiments.playground import (
    DEFAULT_INDEX,
    ExperimentPlaygroundEngine,
    PlaygroundIndexError,
    REPOSITORY_ROOT,
)
from ai.app.schemas.common import ContractModel


router = APIRouter(tags=["Experiment Playground"])
PAGE_PATH = Path(__file__).resolve().parents[1] / "static" / "experiment_playground_v0.html"


class ExperimentPlaygroundRequest(ContractModel):
    product_model_code: str = Field(..., min_length=1, max_length=100)
    query: str = Field(..., min_length=1, max_length=4000)
    corpus_variant: Literal[
        "JAC104_ONLY",
        "IAC425_ONLY",
        "JAC104_IAC425_COMBINED",
    ] = "JAC104_IAC425_COMBINED"
    chunking_profile: Literal["current_source_page_v1"] = "current_source_page_v1"
    embedding_profile: Literal["bge_m3"] = "bge_m3"
    retrieval_profile: Literal["dense_cosine_exact_v1"] = "dense_cosine_exact_v1"
    top_k: int = Field(5, ge=1, le=10)
    product_filter: bool = True


@lru_cache(maxsize=1)
def get_playground_engine() -> ExperimentPlaygroundEngine:
    return ExperimentPlaygroundEngine()


@router.get("/experiments/playground", response_class=HTMLResponse, include_in_schema=False)
def experiment_playground_page() -> HTMLResponse:
    return HTMLResponse(PAGE_PATH.read_text(encoding="utf-8"))


@router.get("/api/v1/ai/experiments/playground/options")
def experiment_playground_options() -> dict:
    index_ready = (REPOSITORY_ROOT / DEFAULT_INDEX).is_file()
    return {
        "status": "READY" if index_ready else "INDEX_REQUIRED",
        "products": ["WPUJAC104DWH", "WPUIAC425SNW"],
        "corpus_variants": [
            "JAC104_ONLY",
            "IAC425_ONLY",
            "JAC104_IAC425_COMBINED",
        ],
        "chunking_profiles": ["current_source_page_v1"],
        "embedding_profiles": ["bge_m3"],
        "retrieval_profiles": ["dense_cosine_exact_v1"],
        "top_k": {"default": 5, "min": 1, "max": 10},
        "generation": {"status": "NOT_IMPLEMENTED_V0"},
        "official_metrics_allowed": False,
    }


@router.post("/api/v1/ai/experiments/playground/retrieval")
async def run_experiment_playground_retrieval(
    payload: ExperimentPlaygroundRequest,
) -> dict:
    try:
        engine = get_playground_engine()
        return await asyncio.to_thread(engine.search, **payload.model_dump())
    except (PlaygroundIndexError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
