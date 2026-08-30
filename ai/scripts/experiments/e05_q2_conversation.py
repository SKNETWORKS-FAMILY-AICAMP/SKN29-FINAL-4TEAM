from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import httpx
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.integrations.llm import (
    GuidanceLLMResponse,
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMUsage,
    OpenAIResponsesLLMClient,
)
from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.orchestration.pipelines.multi_agent_pipeline import MultiAgentPipeline
from ai.app.orchestration.pipelines.single_rag_pipeline import SingleRAGPipeline
from ai.app.retrieval import RetrievedChunk
from ai.app.schemas import TraceContext

OUT_DIR = ROOT / "ai/experiment_results/e05/q2_conversation"
ENV_PATH = ROOT / "backend/.env"
MANUAL_PATH = ROOT / "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl"

MODEL_CODE = "WPUJAC104DWH"
DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
ORIGINAL_E05_SHA = "68666b88fcf33273906710f23a8d17f7f1faa07f"


def load_backend_env() -> None:
    """backend/.env를 실행하지 않고 환경변수로 읽는다. Secret은 출력하지 않는다."""
    if not ENV_PATH.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {"'", '"'}
            ):
                value = value[1:-1]
            os.environ.setdefault(key, value)
    else:
        load_dotenv(ENV_PATH, override=False)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
    except Exception:
        return "UNKNOWN"


def enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def model_dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


@dataclass(frozen=True)
class Scenario:
    case_id: str
    topic: str
    first_query: str
    second_customer_answer: str
    previous_answers: tuple[tuple[str, str], ...]
    evidence_key: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "Q2-COLD-01", "냉수 온도",
        "냉수가 좀 이상해요.",
        "어제부터 냉수 버튼을 누르면 예전보다 미지근합니다. 전원은 껐다 켜봤어요.",
        (
            ("followup-occurrence-time", "어제부터"),
            ("followup-target-water-type", "냉수"),
            ("followup-occurrence-condition", "냉수 버튼을 누를 때 계속 미지근함"),
            ("followup-actions-taken", "전원 재부팅"),
        ),
        "cold_temperature",
    ),
    Scenario(
        "Q2-COLD-02", "냉수 온도",
        "냉수가 예전처럼 시원하지 않아요.",
        "오늘 아침부터 그렇고 냉수를 여러 번 받아도 차갑지 않습니다. 아직 다른 조치는 안 했어요.",
        (
            ("followup-occurrence-time", "오늘 아침부터"),
            ("followup-target-water-type", "냉수"),
            ("followup-occurrence-condition", "여러 번 출수해도 차갑지 않음"),
            ("followup-actions-taken", "별도 조치 없음"),
        ),
        "cold_temperature",
    ),
    Scenario(
        "Q2-COLD-03", "냉수 온도",
        "냉수 온도가 평소랑 다른 것 같아요.",
        "이틀 전부터 냉수를 받을 때 계속 덜 차갑습니다. 잠깐 기다렸다가 다시 받아봤어요.",
        (
            ("followup-occurrence-time", "이틀 전부터"),
            ("followup-target-water-type", "냉수"),
            ("followup-occurrence-condition", "냉수 출수 시 계속 덜 차가움"),
            ("followup-actions-taken", "잠시 기다린 뒤 재출수"),
        ),
        "cold_temperature",
    ),
    Scenario(
        "Q2-NOWATER-01", "출수 안 됨",
        "물이 안 나오는 것 같아요.",
        "오늘부터 정수 버튼을 눌러도 물이 전혀 안 나옵니다. 전원을 다시 켜봤어요.",
        (
            ("followup-occurrence-time", "오늘부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "정수 버튼을 눌러도 출수되지 않음"),
            ("followup-actions-taken", "전원 재부팅"),
        ),
        "no_water",
    ),
    Scenario(
        "Q2-NOWATER-02", "출수 안 됨",
        "정수기에서 물이 잘 안 나와요.",
        "어제 저녁부터 냉수와 정수가 거의 나오지 않습니다. 다른 수도는 정상입니다.",
        (
            ("followup-occurrence-time", "어제 저녁부터"),
            ("followup-target-water-type", "전체"),
            ("followup-occurrence-condition", "냉수와 정수가 거의 출수되지 않음"),
            ("followup-actions-taken", "다른 수도의 급수 상태 확인"),
        ),
        "no_water",
    ),
    Scenario(
        "Q2-NOWATER-03", "출수 안 됨",
        "버튼을 눌러도 물이 이상해요.",
        "오늘 아침부터 정수 버튼을 눌러도 출수가 안 됩니다. 필터 교체 시기도 확인해봤어요.",
        (
            ("followup-occurrence-time", "오늘 아침부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "정수 버튼을 눌러도 출수 안 됨"),
            ("followup-actions-taken", "필터 교체 시기 확인"),
        ),
        "no_water",
    ),
    Scenario(
        "Q2-NOISE-01", "소음",
        "정수기에서 이상한 소리가 나요.",
        "어제부터 사용하지 않을 때도 윙 하는 소리가 평소보다 크게 들립니다.",
        (
            ("followup-occurrence-time", "어제부터"),
            ("followup-target-water-type", "전체"),
            ("followup-occurrence-condition", "사용하지 않을 때도 윙 소리가 크게 남"),
            ("followup-actions-taken", "별도 조치 없음"),
        ),
        "noise",
    ),
    Scenario(
        "Q2-NOISE-02", "소음",
        "소리가 평소랑 달라요.",
        "오늘부터 출수할 때 툭 하는 소리가 들립니다. 물은 정상적으로 나옵니다.",
        (
            ("followup-occurrence-time", "오늘부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "출수할 때 툭 소리가 남"),
            ("followup-actions-taken", "출수 상태 확인"),
        ),
        "noise",
    ),
    Scenario(
        "Q2-NOISE-03", "소음",
        "정수기 소음이 좀 커진 것 같아요.",
        "3일 전부터 윙 하는 소리가 이전보다 커졌고 계속 반복됩니다.",
        (
            ("followup-occurrence-time", "3일 전부터"),
            ("followup-target-water-type", "전체"),
            ("followup-occurrence-condition", "윙 소리가 이전보다 크게 반복됨"),
            ("followup-actions-taken", "제품 주변 확인"),
        ),
        "noise",
    ),
    Scenario(
        "Q2-FLOW-01", "출수량 저하",
        "물이 너무 약하게 나와요.",
        "어제부터 냉수를 받을 때 졸졸 나오고 다른 수전을 같이 쓰지 않아도 그렇습니다.",
        (
            ("followup-occurrence-time", "어제부터"),
            ("followup-target-water-type", "냉수"),
            ("followup-occurrence-condition", "다른 수전을 사용하지 않아도 출수량이 적음"),
            ("followup-actions-taken", "다른 수전 사용 여부 확인"),
        ),
        "low_flow",
    ),
    Scenario(
        "Q2-FLOW-02", "출수량 저하",
        "출수량이 줄어든 것 같아요.",
        "오늘부터 정수가 평소보다 약하게 나옵니다. 필터 교체 시기는 확인했습니다.",
        (
            ("followup-occurrence-time", "오늘부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "정수 출수량이 평소보다 적음"),
            ("followup-actions-taken", "필터 교체 시기 확인"),
        ),
        "low_flow",
    ),
    Scenario(
        "Q2-FLOW-03", "출수량 저하",
        "냉수가 졸졸 나와요.",
        "이틀 전부터 냉수만 출수 속도가 느립니다. 조리수는 같이 사용하지 않았어요.",
        (
            ("followup-occurrence-time", "이틀 전부터"),
            ("followup-target-water-type", "냉수"),
            ("followup-occurrence-condition", "냉수만 출수 속도가 느림"),
            ("followup-actions-taken", "조리수 동시 사용 여부 확인"),
        ),
        "low_flow",
    ),
    Scenario(
        "Q2-PARTICLE-01", "미세입자",
        "물에 뭔가 보이는 것 같아요.",
        "오늘 정수를 컵에 받았는데 작은 입자처럼 보이는 게 있습니다. 5분 정도 두고 봤어요.",
        (
            ("followup-occurrence-time", "오늘부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "컵에 받은 정수에서 작은 입자가 보임"),
            ("followup-actions-taken", "물을 받은 뒤 5분간 확인"),
        ),
        "fine_particles",
    ),
    Scenario(
        "Q2-PARTICLE-02", "미세입자",
        "정수된 물 상태가 좀 이상해요.",
        "어제부터 컵에 정수를 받으면 미세한 입자처럼 보이는 게 남아 있습니다.",
        (
            ("followup-occurrence-time", "어제부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "컵에 받은 정수에서 미세입자가 보임"),
            ("followup-actions-taken", "컵 상태 확인"),
        ),
        "fine_particles",
    ),
    Scenario(
        "Q2-PARTICLE-03", "미세입자",
        "컵에 받은 물이 평소랑 달라 보여요.",
        "오늘 아침부터 정수에 작은 입자가 보이고 컵을 흔들어도 계속 보입니다.",
        (
            ("followup-occurrence-time", "오늘 아침부터"),
            ("followup-target-water-type", "정수"),
            ("followup-occurrence-condition", "컵을 흔든 뒤에도 작은 입자가 보임"),
            ("followup-actions-taken", "물컵을 흔들어 확인"),
        ),
        "fine_particles",
    ),
)


EVIDENCE_SPECS = {
    # 실제 repo의 공식 매뉴얼 processed text에서 런타임에 잘라 사용한다.
    # Production Grounding Guard가 Evidence 원문과 완전 일치하는 추출형 message만 허용하므로,
    # 한 페이지 전체가 아니라 실제 Parent-Child 검색의 Child에 가까운 짧은 증상별 구간을 사용한다.
    "cold_temperature": (37, "● 출수량 많음", "● 냉수 기능 꺼짐"),
    "no_water": (37, "● 필터 수명 종료", "● 기계적 작동 및 온도변화"),
    "noise": (37, "● 기계적 작동 및 온도변화", None),
    "fine_particles": (38, "● 급수 시 발생하는 기포임", "● 조리수 또는 그외 수전 동시 사용"),
    "low_flow": (38, "● 조리수 또는 그외 수전 동시 사용", "● 순간 온수 가동 중"),
}


def load_manual_pages() -> dict[int, dict[str, Any]]:
    if not MANUAL_PATH.exists():
        raise FileNotFoundError(f"공식 매뉴얼 processed JSONL을 찾을 수 없습니다: {MANUAL_PATH}")
    pages: dict[int, dict[str, Any]] = {}
    for line in MANUAL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pages[int(row["page"])] = row
    return pages


def slice_text(text: str, start: str, end: str | None) -> str:
    start_i = text.find(start)
    if start_i < 0:
        raise RuntimeError(f"Evidence 시작 marker를 찾지 못했습니다: {start}")
    if end is None:
        out = text[start_i:]
    else:
        end_i = text.find(end, start_i + len(start))
        if end_i < 0:
            raise RuntimeError(f"Evidence 종료 marker를 찾지 못했습니다: {end}")
        out = text[start_i:end_i]
    return out.strip()


def build_evidence(scenario: Scenario, pages: dict[int, dict[str, Any]]) -> RetrievedChunk:
    page_no, start, end = EVIDENCE_SPECS[scenario.evidence_key]
    page = pages[page_no]
    content = slice_text(str(page["text"]), start, end)
    return RetrievedChunk(
        chunk_id=f"E05Q2-{scenario.evidence_key.upper()}-P{page_no}",
        document_title="WPU-JAC104D 사용설명서",
        document_version=str(page.get("version") or "REV.00"),
        page=page_no,
        page_refs=[page_no],
        manual_model=MODEL_CODE,
        model_code=MODEL_CODE,
        product_generation="D",
        content=content,
        similarity_score=0.99,
        official_url=page.get("source_url"),
        verification_status="official_verified",
        allowed_use=True,
        runtime_eligible=True,
        topic_code=f"e05q2_{scenario.evidence_key}",
    )


class E05Q2OpenAIClient:
    """Same experiment-local OpenAI adapter for both runtimes."""

    def __init__(self, *, api_key: str, model_name: str, base_url: str, max_output_tokens: int):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.max_output_tokens = max_output_tokens

    def generate_guidance(self, request, *, timeout_seconds: float) -> GuidanceLLMResponse:
        if not request.evidence_summaries:
            raise LLMOutputValidationError("승인 Evidence가 없습니다.")
        if not request.allowed_next_actions:
            raise LLMOutputValidationError("허용된 next action이 없습니다.")

        # IMPORTANT:
        # OpenAI strict Structured Outputs rejects newline-containing string literals
        # inside enum values. Official manual evidence naturally contains newlines.
        # Therefore the schema contains ONLY integer indices. The selected indices are
        # deterministically mapped back to the exact approved evidence/action below.
        evidence_options = list(dict.fromkeys(request.evidence_summaries))
        action_options = list(dict.fromkeys(request.allowed_next_actions))

        schema = {
            "type": "object",
            "properties": {
                "evidence_index": {
                    "type": "integer",
                    "enum": list(range(len(evidence_options))),
                },
                "action_index": {
                    "type": "integer",
                    "enum": list(range(len(action_options))),
                },
            },
            "required": ["evidence_index", "action_index"],
            "additionalProperties": False,
        }

        user_payload = {
            "model_code": request.model_code,
            "symptom_summary": request.symptom_summary,
            "risk_level": request.risk_level,
            "guidance_status": request.guidance_status,
            "safety_reason": request.safety_reason,
            "restricted_functions": request.restricted_functions,
            "approved_evidence_options": [
                {"index": i, "text": value}
                for i, value in enumerate(evidence_options)
            ],
            "allowed_next_action_options": [
                {"index": i, "text": value}
                for i, value in enumerate(action_options)
            ],
        }

        payload = {
            "model": self.model_name,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON matching the schema exactly. "
                        "Select the integer index of the best approved evidence option "
                        "and the integer index of one allowed next action. "
                        "Do not return the evidence text itself."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "e05q2_grounded_guidance",
                    "strict": True,
                    "schema": schema,
                }
            },
            "store": False,
            "temperature": 0.0,
            "max_output_tokens": self.max_output_tokens,
        }

        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise LLMProviderTimeoutError("OpenAI 응답 시간이 초과되었습니다.") from exc
        except httpx.TransportError as exc:
            raise LLMProviderConnectionError("OpenAI 연결에 실패했습니다.") from exc

        if response.status_code >= 400:
            try:
                body_text = json.dumps(response.json(), ensure_ascii=False)
            except Exception:
                body_text = response.text
            raise LLMOutputValidationError(
                f"OpenAI HTTP {response.status_code}: {body_text[:1500]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise LLMOutputValidationError("OpenAI 응답이 JSON이 아닙니다.") from exc

        if body.get("status") != "completed":
            raise LLMOutputValidationError(
                f"OpenAI 응답 status={body.get('status')}"
            )

        output_texts = []
        for output in body.get("output", []):
            if not isinstance(output, dict) or output.get("type") != "message":
                continue
            for item in output.get("content", []):
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "refusal":
                    raise LLMOutputValidationError("OpenAI가 요청을 거부했습니다.")
                if item.get("type") == "output_text" and isinstance(item.get("text"), str):
                    output_texts.append(item["text"])

        if len(output_texts) != 1:
            raise LLMOutputValidationError(
                f"output_text 개수가 1개가 아닙니다: {len(output_texts)}"
            )

        try:
            parsed = json.loads(output_texts[0])
        except json.JSONDecodeError as exc:
            raise LLMOutputValidationError("Structured Output JSON 파싱 실패") from exc

        evidence_index = parsed.get("evidence_index")
        action_index = parsed.get("action_index")
        if (
            not isinstance(evidence_index, int)
            or isinstance(evidence_index, bool)
            or not 0 <= evidence_index < len(evidence_options)
        ):
            raise LLMOutputValidationError(
                f"evidence_index가 허용 범위 밖입니다: {evidence_index}"
            )
        if (
            not isinstance(action_index, int)
            or isinstance(action_index, bool)
            or not 0 <= action_index < len(action_options)
        ):
            raise LLMOutputValidationError(
                f"action_index가 허용 범위 밖입니다: {action_index}"
            )

        # Deterministic materialization:
        # returned customer text is byte-for-byte from the approved evidence set,
        # so the existing production Grounding Guard remains authoritative.
        message = evidence_options[evidence_index]
        next_action = action_options[action_index]

        usage_body = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        usage = LLMUsage(
            input_tokens=int(usage_body.get("input_tokens") or 0),
            output_tokens=int(usage_body.get("output_tokens") or 0),
            total_tokens=int(usage_body.get("total_tokens") or 0),
        )
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message=message,
                next_actions=[next_action],
            ),
            model_name=str(body.get("model") or self.model_name),
            usage=usage,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 2),
        )


class EmptySearchService:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        return []


class OneEvidenceSearchService:
    def __init__(self, evidence: RetrievedChunk) -> None:
        self.evidence = evidence
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        return [self.evidence.model_copy(deep=True)]


def make_context(
    scenario: Scenario,
    *,
    runtime: str,
    repeat: int,
    turn: int,
    previous_answers: list[dict[str, str]] | None = None,
) -> PipelineContext:
    seed = f"waterbridge-e05q2:{scenario.case_id}:{runtime}:{repeat}:{turn}"
    inquiry = uuid5(NAMESPACE_URL, seed + ":inquiry")
    correlation = uuid5(NAMESPACE_URL, seed + ":correlation")
    return PipelineContext(
        trace_context=TraceContext(
            inquiry_id=inquiry,
            correlation_id=correlation,
            ai_request_id=f"e05q2-{scenario.case_id}-{runtime}-r{repeat}-t{turn}",
            state_version=turn,
        ),
        raw_symptom=scenario.first_query,
        model_code=MODEL_CODE,
        previous_answers=previous_answers or [],
    )


def questions_from(result) -> list[str]:
    response = result.to_analysis_result()
    rows: list[str] = []
    for item in response.followup_questions or []:
        data = model_dump(item)
        if isinstance(data, dict):
            text = (
                data.get("question_text")
                or data.get("question")
                or data.get("text")
                or data.get("prompt")
            )
            rows.append(str(text) if text else json.dumps(data, ensure_ascii=False))
        else:
            rows.append(str(data))
    return rows


def handoffs_from(result) -> list[str]:
    meta = result.multi_agent_metadata
    if meta is None:
        return []
    rows = []
    for item in meta.handoffs:
        data = item.model_dump(mode="json")
        rows.append(str(data.get("reason_code")))
    return rows


def result_view(result, elapsed_ms: float, search_calls: int) -> dict[str, Any]:
    response = result.to_analysis_result()
    guidance = response.usage_guidance
    evidence_ids = [
        getattr(item, "chunk_id", None)
        for item in (response.evidence_references or [])
    ]
    return {
        "status": enum_value(response.status),
        "failure_stage": enum_value(response.failure_stage),
        "routing_disposition": enum_value(result.routing_disposition),
        "retrieval_outcome": enum_value(result.context.retrieval_outcome),
        "awaiting_customer_input": bool(result.context.awaiting_customer_input),
        "guidance_status": enum_value(guidance.guidance_status),
        "message": guidance.message,
        "next_actions": list(guidance.next_actions),
        "followup_questions": questions_from(result),
        "handoffs": handoffs_from(result),
        "evidence_chunk_ids": evidence_ids,
        "model_name": result.context.model_metadata.model_name,
        "tokens_used": int(result.context.model_metadata.tokens_used or 0),
        "llm_latency_ms": float(result.context.model_metadata.latency_ms or 0.0),
        "pipeline_elapsed_ms": round(elapsed_ms, 3),
        "search_calls": search_calls,
    }


def exception_chain(exc: BaseException) -> list[dict[str, str]]:
    """Wrapper 예외 뒤의 실제 원인까지 발표 실험 로그에 남긴다."""
    rows: list[dict[str, str]] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        rows.append({
            "type": type(current).__name__,
            "message": str(current),
        })
        current = current.__cause__ or current.__context__
    return rows


def run_pipeline(
    *,
    runtime: str,
    ctx: PipelineContext,
    search_service,
    llm_client,
) -> dict[str, Any]:
    pipeline_cls = SingleRAGPipeline if runtime == "single_rag" else MultiAgentPipeline
    pipeline = pipeline_cls(search_service=search_service, llm_client=llm_client)
    started = time.perf_counter()
    try:
        result = pipeline.run(ctx)
    except Exception as exc:
        return {
            "error": type(exc).__name__,
            "error_message": str(exc),
            "error_chain": exception_chain(exc),
            "pipeline_elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "search_calls": getattr(search_service, "calls", 0),
        }
    return result_view(
        result,
        (time.perf_counter() - started) * 1000.0,
        getattr(search_service, "calls", 0),
    )


def is_success(row: dict[str, Any]) -> bool:
    return row.get("status") == "SUCCEEDED" and not row.get("error")


def has_feedback_handoff(row: dict[str, Any]) -> bool:
    return "MORE_INFORMATION_REQUIRED" in (row.get("handoffs") or [])


def run_trial(
    scenario: Scenario,
    *,
    repeat: int,
    llm_client,
    pages: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    evidence = build_evidence(scenario, pages)

    # TURN 1: 동일하게 NO MATCH를 주입해 "검색 후 근거 부족" 상황만 비교한다.
    single_search_t1 = EmptySearchService()
    multi_search_t1 = EmptySearchService()
    single_t1 = run_pipeline(
        runtime="single_rag",
        ctx=make_context(scenario, runtime="single_rag", repeat=repeat, turn=1),
        search_service=single_search_t1,
        llm_client=llm_client,
    )
    multi_t1 = run_pipeline(
        runtime="multi_agent",
        ctx=make_context(scenario, runtime="multi_agent", repeat=repeat, turn=1),
        search_service=multi_search_t1,
        llm_client=llm_client,
    )

    answers = [
        {"question_id": question_id, "answer_text": answer_text}
        for question_id, answer_text in scenario.previous_answers
    ]

    # Native continuation eligibility:
    # Single은 awaiting_customer_input=False면 제품 Runtime 관점에서 자연스럽게 2턴을 이어가지 않는다.
    single_native_eligible = bool(single_t1.get("awaiting_customer_input"))
    multi_native_eligible = bool(multi_t1.get("awaiting_customer_input"))

    # TURN 2-A: Multi native continuation. Pending 상태였다면 고객 답변 후 재진입.
    if multi_native_eligible:
        multi_search_t2 = OneEvidenceSearchService(evidence)
        multi_t2_native = run_pipeline(
            runtime="multi_agent",
            ctx=make_context(
                scenario,
                runtime="multi_agent",
                repeat=repeat,
                turn=2,
                previous_answers=answers,
            ),
            search_service=multi_search_t2,
            llm_client=llm_client,
        )
    else:
        multi_t2_native = {
            "skipped": True,
            "skip_reason": "FIRST_TURN_NOT_CUSTOMER_INPUT_PENDING",
        }

    # TURN 2-B: Single forced re-entry diagnostic.
    # Single이 FALLBACK으로 끝났더라도 외부 오케스트레이터가 강제로 동일 답변을 넣어 재호출하면
    # 실제 answering capability가 있는지 별도 확인한다. Native continuation과 섞어 해석하지 않는다.
    single_search_t2 = OneEvidenceSearchService(evidence)
    single_t2_forced = run_pipeline(
        runtime="single_rag",
        ctx=make_context(
            scenario,
            runtime="single_rag",
            repeat=repeat,
            turn=2,
            previous_answers=answers,
        ),
        search_service=single_search_t2,
        llm_client=llm_client,
    )

    return {
        "case_id": scenario.case_id,
        "topic": scenario.topic,
        "repeat": repeat,
        "first_query": scenario.first_query,
        "second_customer_answer": scenario.second_customer_answer,
        "previous_answers": answers,
        "evidence_key": scenario.evidence_key,
        "evidence_chunk_id": evidence.chunk_id,
        "turn1": {
            "single_rag": single_t1,
            "multi_agent": multi_t1,
        },
        "native_continuation_eligible": {
            "single_rag": single_native_eligible,
            "multi_agent": multi_native_eligible,
        },
        "turn2": {
            "multi_agent_native": multi_t2_native,
            "single_rag_forced_reentry": single_t2_forced,
        },
    }


def safe_rate(values: list[bool]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return round(xs[0], 3)
    pos = (len(xs) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return round(xs[lo] * (1 - frac) + xs[hi] * frac, 3)


def summarize(trials: list[dict[str, Any]]) -> dict[str, Any]:
    single_t1_fallback = []
    multi_t1_pending = []
    multi_feedback = []
    single_native = []
    multi_native = []
    multi_t2_success = []
    single_forced_success = []
    multi_t2_grounded = []
    single_forced_grounded = []
    total_tokens = {"multi_agent_native_t2": 0, "single_rag_forced_t2": 0}
    llm_latencies = {"multi_agent_native_t2": [], "single_rag_forced_t2": []}
    errors: list[dict[str, Any]] = []

    for t in trials:
        s1 = t["turn1"]["single_rag"]
        m1 = t["turn1"]["multi_agent"]
        m2 = t["turn2"]["multi_agent_native"]
        s2 = t["turn2"]["single_rag_forced_reentry"]

        single_t1_fallback.append(s1.get("status") == "FALLBACK")
        multi_t1_pending.append(bool(m1.get("awaiting_customer_input")))
        multi_feedback.append(has_feedback_handoff(m1))
        single_native.append(bool(t["native_continuation_eligible"]["single_rag"]))
        multi_native.append(bool(t["native_continuation_eligible"]["multi_agent"]))

        if not m2.get("skipped"):
            multi_t2_success.append(is_success(m2))
            multi_t2_grounded.append(bool(m2.get("evidence_chunk_ids")))
            total_tokens["multi_agent_native_t2"] += int(m2.get("tokens_used") or 0)
            if m2.get("llm_latency_ms"):
                llm_latencies["multi_agent_native_t2"].append(float(m2["llm_latency_ms"]))

        single_forced_success.append(is_success(s2))
        single_forced_grounded.append(bool(s2.get("evidence_chunk_ids")))
        total_tokens["single_rag_forced_t2"] += int(s2.get("tokens_used") or 0)
        if s2.get("llm_latency_ms"):
            llm_latencies["single_rag_forced_t2"].append(float(s2["llm_latency_ms"]))

        for label, row in (
            ("single_t1", s1),
            ("multi_t1", m1),
            ("multi_t2_native", m2),
            ("single_t2_forced", s2),
        ):
            if row.get("error"):
                errors.append({
                    "case_id": t["case_id"],
                    "repeat": t["repeat"],
                    "stage": label,
                    "error": row.get("error"),
                    "message": row.get("error_message"),
                    "error_chain": row.get("error_chain", []),
                })

    metrics = {
        "single_turn1_fallback_rate": safe_rate(single_t1_fallback),
        "multi_turn1_customer_input_pending_rate": safe_rate(multi_t1_pending),
        "multi_turn1_feedback_handoff_rate": safe_rate(multi_feedback),
        "native_continuation_eligibility_single": safe_rate(single_native),
        "native_continuation_eligibility_multi": safe_rate(multi_native),
        "multi_native_turn2_success_rate": safe_rate(multi_t2_success),
        "single_forced_reentry_turn2_success_rate": safe_rate(single_forced_success),
        "multi_native_turn2_grounded_rate": safe_rate(multi_t2_grounded),
        "single_forced_turn2_grounded_rate": safe_rate(single_forced_grounded),
    }

    if (
        metrics["multi_native_turn2_success_rate"] >= 0.8
        and metrics["native_continuation_eligibility_multi"] >= 0.8
        and metrics["native_continuation_eligibility_single"] <= 0.2
    ):
        if metrics["single_forced_reentry_turn2_success_rate"] >= 0.8:
            claim = (
                "Multi-Agent의 핵심 우위는 'Single이 답을 생성할 능력이 없다'는 것이 아니라, "
                "검색 실패 후 CUSTOMER_INPUT_PENDING과 Feedback Handoff를 Runtime 계약으로 유지해 "
                "다음 고객 턴을 자연스럽게 이어가는 데 있다. Single도 외부에서 강제 재진입시키면 "
                "근거가 주어진 2턴 답변을 생성할 수 있으므로, 발표에서는 답변 지능보다 "
                "상태 기반 실패 복구 능력을 강조해야 한다."
            )
        else:
            claim = (
                "이 실행 범위에서는 Multi-Agent가 검색 실패 후 고객 입력 대기 상태를 유지하고 "
                "2턴에서 근거 기반 안내로 복구했으며, Single의 강제 재진입 성공률도 낮았다."
            )
    else:
        claim = (
            "예상한 Multi-Agent Feedback branch가 모든 Case에서 재현되지 않았다. "
            "Case별 trace를 확인하고 일반화된 우위 주장은 보류해야 한다."
        )

    return {
        "trial_count": len(trials),
        "metrics": metrics,
        "api_usage": {
            "actual_generation_calls_expected_max": len(trials) * 2,
            "total_tokens": total_tokens,
            "llm_latency_ms": {
                key: {
                    "p50": percentile(vals, 0.50),
                    "p95": percentile(vals, 0.95),
                    "mean": round(statistics.mean(vals), 3) if vals else 0.0,
                }
                for key, vals in llm_latencies.items()
            },
        },
        "error_count": len(errors),
        "errors": errors,
        "recommended_claim": claim,
    }


def transcript_block(trial: dict[str, Any]) -> list[str]:
    s1 = trial["turn1"]["single_rag"]
    m1 = trial["turn1"]["multi_agent"]
    m2 = trial["turn2"]["multi_agent_native"]
    s2 = trial["turn2"]["single_rag_forced_reentry"]

    lines = [
        f"## {trial['case_id']} — {trial['topic']} (Repeat {trial['repeat']})",
        "",
        f"### 고객 Turn 1",
        "",
        f"> {trial['first_query']}",
        "",
        "### Single RAG",
        "",
        f"- 상태: `{s1.get('status')}`",
        f"- awaiting_customer_input: `{s1.get('awaiting_customer_input')}`",
        f"- Retrieval: `{s1.get('retrieval_outcome')}`",
        "",
        f"> {s1.get('message', '[실행 오류]')}",
        "",
    ]
    if s1.get("followup_questions"):
        lines += ["질문 데이터는 생성되어 있었음:"] + [
            f"- {q}" for q in s1["followup_questions"]
        ] + [""]
    lines += [
        "**Native Runtime 결과:** "
        + (
            "다음 고객 턴을 기다리는 상태"
            if trial["native_continuation_eligible"]["single_rag"]
            else "FALLBACK 종료 — 자동 대화 continuation 상태가 아님"
        ),
        "",
        "### Multi-Agent",
        "",
        f"- 상태: `{m1.get('status')}`",
        f"- awaiting_customer_input: `{m1.get('awaiting_customer_input')}`",
        f"- Handoff: `{' → '.join(m1.get('handoffs') or [])}`",
        "",
        f"> {m1.get('message', '[실행 오류]')}",
        "",
    ]
    if m1.get("followup_questions"):
        lines += ["고객에게 이어지는 질문:"] + [
            f"- {q}" for q in m1["followup_questions"]
        ] + [""]

    lines += [
        "### 고객 Turn 2",
        "",
        f"> {trial['second_customer_answer']}",
        "",
        "### Multi-Agent — Native continuation",
        "",
    ]
    if m2.get("skipped"):
        lines += [f"- SKIPPED: `{m2.get('skip_reason')}`", ""]
    else:
        lines += [
            f"- 상태: `{m2.get('status')}`",
            f"- Evidence: `{', '.join(x for x in m2.get('evidence_chunk_ids', []) if x)}`",
            "",
            f"> {m2.get('message', '[실행 오류]')}",
            "",
        ]

    lines += [
        "### Single RAG — Forced re-entry diagnostic",
        "",
        "> 아래 결과는 Single이 스스로 continuation 상태를 만든 것이 아니라, "
        "실험 스크립트가 동일한 고객 답변을 강제로 다시 넣어 재호출한 결과입니다.",
        "",
        f"- 상태: `{s2.get('status')}`",
        f"- Evidence: `{', '.join(x for x in s2.get('evidence_chunk_ids', []) if x)}`",
        "",
        f"> {s2.get('message', '[실행 오류]')}",
        "",
        "---",
        "",
    ]
    return lines


def write_outputs(
    trials: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    sha: str,
    model_name: str,
    repeats: int,
    scenario_count: int,
    elapsed: float,
    completed: bool,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": (
            "E05_Q2_CONVERSATION_COMPLETE"
            if completed
            else "E05_Q2_CONVERSATION_ABORTED"
        ),
        "result_label": "QUALITATIVE_PLUS_REPEATED_DIAGNOSTIC",
        "git_sha": sha,
        "original_e05_sha": ORIGINAL_E05_SHA,
        "same_sha_as_original_e05": sha == ORIGINAL_E05_SHA,
        "model": model_name,
        "scenario_count": scenario_count,
        "repeats": repeats,
        "retrieval_design": (
            "SCRIPTED_FAULT_ISOLATION: Turn1=NO_MATCH, Turn2=actual processed JAC104 manual excerpt. "
            "Not a live vector-retrieval benchmark."
        ),
        "experiment_total_seconds": round(elapsed, 3),
        **summary,
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "raw.jsonl").open("w", encoding="utf-8") as f:
        for trial in trials:
            f.write(json.dumps(trial, ensure_ascii=False) + "\n")

    conversation_lines = [
        "# E05-Q2 Conversation Transcripts",
        "",
        f"- Git SHA: `{sha}`",
        f"- Model: `{model_name}`",
        "- Turn1 Retrieval: 의도적 NO MATCH",
        "- Turn2 Evidence: repo에 저장된 JAC104 공식 매뉴얼 processed text의 관련 구간",
        "- 주의: Single Turn2는 **Forced re-entry diagnostic**, Multi Turn2는 **Native continuation**",
        "",
    ]
    # 발표용으로 Repeat 1만 모두 싣고, 나머지는 raw.jsonl에 보존.
    for trial in trials:
        if trial["repeat"] == 1:
            conversation_lines += transcript_block(trial)
    (OUT_DIR / "conversations.md").write_text(
        "\n".join(conversation_lines),
        encoding="utf-8",
    )

    m = summary["metrics"]
    report_claim = (
        summary["recommended_claim"]
        if completed
        else "실험이 중단되어 비교 Claim을 확정하지 않습니다. summary.json의 errors/error_chain을 확인하세요."
    )
    report_lines = [
        "# E05-Q2 — 검색 실패 후 2턴 대화 복구 실험",
        "",
        f"- Git SHA: `{sha}`",
        f"- Model: `{model_name}`",
        f"- Scenarios: `{scenario_count}`",
        f"- Repeats: `{repeats}`",
        f"- Trials: `{len(trials)}`",
        "",
        "## 설계",
        "",
        "동일한 1턴 고객 문의에 대해 Single RAG와 Multi-Agent 모두 Retrieval NO MATCH를 받습니다.",
        "그 후 Multi-Agent가 CUSTOMER_INPUT_PENDING을 만들면 고객의 2턴 답변을 넣어 재진입합니다.",
        "Single은 FALLBACK 이후에도 **외부에서 강제로 재호출하면 답할 능력이 있는지** 별도 진단합니다.",
        "",
        "따라서 이 실험은 Multi를 유리하게 보이도록 Single의 생성 능력을 제거하지 않습니다.",
        "",
        "## 주요 결과",
        "",
        f"- Single Turn1 FALLBACK rate: **{m['single_turn1_fallback_rate']:.1%}**",
        f"- Multi Turn1 CUSTOMER_INPUT_PENDING rate: **{m['multi_turn1_customer_input_pending_rate']:.1%}**",
        f"- Multi Feedback Handoff rate: **{m['multi_turn1_feedback_handoff_rate']:.1%}**",
        f"- Native continuation eligibility — Single: **{m['native_continuation_eligibility_single']:.1%}**",
        f"- Native continuation eligibility — Multi: **{m['native_continuation_eligibility_multi']:.1%}**",
        f"- Multi native Turn2 success: **{m['multi_native_turn2_success_rate']:.1%}**",
        f"- Single forced re-entry Turn2 success: **{m['single_forced_reentry_turn2_success_rate']:.1%}**",
        "",
        "## 해석",
        "",
        report_claim,
        "",
        "## Claim 제한",
        "",
        "- Turn1/Turn2 Retrieval은 실제 Vector Search 성능 비교가 아니라 의도적으로 통제한 Fault-Isolation입니다.",
        "- Turn2 Evidence 본문은 repo의 processed 공식 JAC104 매뉴얼에서 읽습니다.",
        "- Single forced re-entry는 제품 Runtime의 자연스러운 continuation이 아니라 실험자가 강제로 재호출한 진단입니다.",
        "- 이 결과로 'Multi-Agent가 일반적으로 더 정확하다'고 주장하면 안 됩니다.",
        "",
        "상세 실제 답변은 `conversations.md`, 모든 반복 원본은 `raw.jsonl`을 확인하세요.",
        "",
    ]
    (OUT_DIR / "report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E05-Q2: Single RAG vs Multi-Agent 2-turn conversation recovery"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=1600,
        help="Grounded extractive Guidance 출력 한도. 실제 매뉴얼 Evidence 원문 복사를 위해 기본 1600.",
    )
    args = parser.parse_args()

    if args.repeats < 1:
        raise SystemExit("--repeats는 1 이상이어야 합니다.")
    if not 1 <= args.limit <= len(SCENARIOS):
        raise SystemExit(f"--limit는 1~{len(SCENARIOS)} 범위여야 합니다.")
    if not 100 <= args.max_output_tokens <= 2000:
        raise SystemExit("--max-output-tokens는 100~2000 범위여야 합니다.")

    load_backend_env()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            f"OPENAI_API_KEY를 찾지 못했습니다. 확인 경로: {ENV_PATH}"
        )

    pages = load_manual_pages()
    for required_page in {37, 38}:
        if required_page not in pages:
            raise RuntimeError(f"매뉴얼 page {required_page}가 processed corpus에 없습니다.")

    llm = E05Q2OpenAIClient(
        api_key=api_key,
        model_name=args.model,
        base_url=os.getenv("OPENAI_BASE_URL", OpenAIResponsesLLMClient.DEFAULT_BASE_URL),
        max_output_tokens=args.max_output_tokens,
    )

    selected = SCENARIOS[: args.limit]
    sha = git_sha()
    trials: list[dict[str, Any]] = []
    total = len(selected) * args.repeats
    done = 0
    started = time.perf_counter()

    print("=" * 92)
    print("E05-Q2 | 2-turn Conversation Recovery")
    print(f"Git SHA     : {sha}")
    print(f"Model       : {args.model}")
    print("LLM adapter : E05Q2 integer-index strict schema (same for Single/Multi)")
    print(f"Scenarios   : {len(selected)}")
    print(f"Repeats     : {args.repeats}")
    print(f"Trials      : {total}")
    print(f"Max tokens  : {args.max_output_tokens}")
    print("Retrieval   : Turn1 scripted NO_MATCH / Turn2 short official manual child-like excerpt")
    print("API key     : loaded (value hidden)")
    print("=" * 92)

    consecutive_api_errors = 0
    for repeat in range(1, args.repeats + 1):
        for scenario in selected:
            done += 1
            trial = run_trial(
                scenario,
                repeat=repeat,
                llm_client=llm,
                pages=pages,
            )
            trials.append(trial)

            s1 = trial["turn1"]["single_rag"]
            m1 = trial["turn1"]["multi_agent"]
            m2 = trial["turn2"]["multi_agent_native"]
            s2 = trial["turn2"]["single_rag_forced_reentry"]

            rows_for_error = [m2, s2]
            api_errors = sum(1 for x in rows_for_error if x.get("error"))
            consecutive_api_errors = consecutive_api_errors + 1 if api_errors == len(rows_for_error) else 0

            print(
                f"[{done:02d}/{total}] {scenario.case_id} r{repeat} | "
                f"S1={s1.get('status')} pending={s1.get('awaiting_customer_input')} | "
                f"M1={m1.get('status')} pending={m1.get('awaiting_customer_input')} "
                f"feedback={has_feedback_handoff(m1)} | "
                f"M2={m2.get('status', m2.get('skip_reason'))} | "
                f"S2-forced={s2.get('status', s2.get('error'))}"
            )

            if api_errors:
                for label, row in (
                    ("MULTI_T2_NATIVE", m2),
                    ("SINGLE_T2_FORCED", s2),
                ):
                    if not row.get("error"):
                        continue
                    print(f"  [ERROR DETAIL] {label}")
                    for depth, item in enumerate(row.get("error_chain", [])):
                        print(f"    {depth}: {item['type']}: {item['message']}")

            if consecutive_api_errors >= 2:
                print("\n[FAIL-FAST] 연속 2개 Trial에서 두 Turn2 생성 경로가 모두 실패했습니다.")
                print("공통 LLM/Generation/Validation 경계 문제로 보고 남은 호출을 중단합니다.")
                break
        if consecutive_api_errors >= 2:
            break

    elapsed = time.perf_counter() - started
    summary = summarize(trials)
    completed = len(trials) == total and summary["error_count"] == 0
    write_outputs(
        trials,
        summary,
        sha=sha,
        model_name=args.model,
        repeats=args.repeats,
        scenario_count=len(selected),
        elapsed=elapsed,
        completed=completed,
    )

    final_status = (
        "E05_Q2_CONVERSATION_COMPLETE"
        if completed
        else "E05_Q2_CONVERSATION_ABORTED"
    )
    print("\n" + "=" * 92)
    print("E05-Q2 SUMMARY")
    print("=" * 92)
    print(json.dumps(
        {
            "status": final_status,
            "git_sha": sha,
            "trial_count": len(trials),
            "metrics": summary["metrics"],
            "error_count": summary["error_count"],
            "recommended_claim": (
                summary["recommended_claim"]
                if completed
                else "실험 중단: Claim 확정 보류"
            ),
            "output_dir": str(OUT_DIR.relative_to(ROOT)).replace("\\", "/"),
            "experiment_total_seconds": round(elapsed, 3),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
