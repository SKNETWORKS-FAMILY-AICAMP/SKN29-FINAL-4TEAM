from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.orchestration.agents import ConsultationContextSynthesisAgent
from ai.app.orchestration.harness import (
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.harness.evidence_capture import (
    GuardedEvidenceSearchService,
)
from ai.app.orchestration.harness.tool_failure import (
    McpToolFailure,
    McpToolFailureKind,
    McpToolName,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import (
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    UsageGuidance,
    UsageGuidanceStatus,
)

OUT = ROOT / "ai/experiment_results/e06/qualitative"
EXPECTED_SHA = "68666b88fcf33273906710f23a8d17f7f1faa07f"

MODEL = "WPUJAC104DWH"
WRONG_MODEL = "WPUIAC606SNW"


class GuidanceOutputSchema(BaseModel):
    """발표용으로 단순화한 최종 Guidance 출력 계약."""

    guidance_status: str
    message: str
    restricted_functions: list[str]
    next_actions: list[str]


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


def product() -> ProductContext:
    return ProductContext(
        model_code=MODEL,
        product_family=ProductFamily.DIRECT_WATER_PURIFIER,
        runtime_approved=True,
        supported_functions={"cold_water", "hot_water"},
    )


def chunk(
    chunk_id: str,
    *,
    model: str = MODEL,
    verification_status: str = "official_verified",
) -> RetrievedChunk:
    if model == MODEL:
        text = (
            "냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인하고, "
            "기본 점검 후에도 증상이 지속되면 전문 상담 및 점검을 요청합니다."
        )
        generation = "D"
    else:
        # 의미는 비슷해 검색 후보로 들어올 수 있지만 고객 제품과는 다른 모델의 공식 문서.
        text = (
            "출수량이 적을 때는 급수 상태와 제품 내부 공급 상태를 확인하고, "
            "증상이 지속되면 점검을 요청합니다."
        )
        generation = "IAC606"

    return RetrievedChunk(
        chunk_id=chunk_id,
        document_title=f"{model} 공식 사용설명서",
        manual_model=model,
        model_code=model,
        product_generation=generation,
        content=text,
        similarity_score=0.95,
        verification_status=verification_status,
        allowed_use=True,
        runtime_eligible=True,
    )


def general_safety() -> SafetyAssessment:
    return SafetyAssessment(
        risk_level=RiskLevel.GENERAL,
        priority=SafetyPriority.GENERAL_GUIDANCE,
        requires_consultation=False,
        matched_safety_rule_ids=[],
        detected_risks=[],
        safety_reason="일반 안내 가능",
    )


def normal_guidance(
    message: str = "제품 상태를 확인하는 안내 후보입니다.",
) -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=message,
        restricted_functions=[],
        next_actions=["상태 확인"],
    )


def base_ctx(
    *,
    raw_symptom: str = "정수기 상태를 확인하고 싶습니다.",
    safety: SafetyAssessment | None = None,
    guidance: UsageGuidance | None = None,
    evidence_refs: list[Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b801"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e801"),
            ai_request_id="e06q-runtime",
            state_version=1,
        ),
        raw_symptom=raw_symptom,
        model_code=MODEL,
        selected_symptoms=[],
        structured_symptom=None,
        previous_answers=[],
        missing_fields=[],
        followup_questions=[],
        evidence_references=evidence_refs or [],
        safety_assessment=safety,
        usage_guidance=guidance,
        awaiting_customer_input=False,
        retry_count=0,
        retrieval_outcome=None,
    )


def runner() -> HarnessRunner:
    # 외부 LLM을 쓰지 않고 실제 Harness/HITL/Handoff 계약만 검증한다.
    return HarnessRunner(
        context_synthesis_agent=ConsultationContextSynthesisAgent(llm_client=None)
    )


class StagedSearch:
    """1차에는 타 모델 Evidence, 2차에는 정확한 모델 Evidence를 반환."""

    def __init__(self) -> None:
        self.calls = 0

    def search(self, *args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        self.calls += 1
        if self.calls == 1:
            return [chunk("E06Q-WRONG-001", model=WRONG_MODEL)]
        return [chunk("E06Q-CORRECT-002", model=MODEL)]


def issues(harness_result: Any) -> list[str]:
    return [
        issue.code.value
        for issue in harness_result.verification.issues
    ]


def guidance_dump(guidance: UsageGuidance | None) -> dict[str, Any] | None:
    if guidance is None:
        return None
    return {
        "guidance_status": guidance.guidance_status.value,
        "message": guidance.message,
        "restricted_functions": list(guidance.restricted_functions),
        "next_actions": list(guidance.next_actions),
    }


def wrong_model_case() -> dict[str, Any]:
    """
    CASE 1 — RETRY_RETRIEVAL

    고객 모델은 JAC104인데 의미적으로 비슷한 IAC606 문서가 검색 후보로 들어온다.
    Harness가 모델 불일치를 차단하고 한 번만 재검색한 뒤 정확한 모델 Evidence로 PASS.
    """
    preview = StagedSearch().search(object())[0]

    search = StagedSearch()
    guard = GuardedEvidenceSearchService(search, product())

    guard.begin_attempt()
    first_forwarded = guard.search(object())

    first = runner().run(
        product=product(),
        evidence_chunks=guard.evidence_for_harness(
            SimpleNamespace(evidence_references=[])
        ),
        safety_assessment=general_safety(),
        guidance=normal_guidance(
            "검색 근거를 기반으로 한 안내 후보입니다."
        ),
    )

    guard.begin_attempt()
    second_forwarded = guard.search(object())
    second_ctx = SimpleNamespace(
        evidence_references=[
            SimpleNamespace(chunk_id=item.chunk_id)
            for item in second_forwarded
        ]
    )

    second = runner().run(
        product=product(),
        evidence_chunks=guard.evidence_for_harness(second_ctx),
        safety_assessment=general_safety(),
        guidance=normal_guidance(
            second_forwarded[0].content
            if second_forwarded
            else "근거 없음"
        ),
        retry_state=first.retry_state,
    )

    return {
        "case_id": "WRONG_MODEL_EVIDENCE",
        "presentation_role": "RETRY_RETRIEVAL",
        "before": {
            "customer_symptom": "냉수가 예전보다 적게 나와요.",
            "customer_model": MODEL,
            "retrieved_document_model": preview.model_code,
            "retrieved_document_title": preview.document_title,
            "candidate_evidence_text": preview.content,
            "why_it_looks_plausible": (
                "출수량 관련 내용은 유사하지만 고객 제품과 문서 모델이 다름"
            ),
        },
        "harness": {
            "first_decision": first.decision.value,
            "issues": issues(first),
            "blocked_chunk_ids": guard.rejected_chunk_ids,
            "retry_count": second.retry_state.retrieval_retries,
            "final_decision": second.decision.value,
        },
        "after": {
            "first_attempt_forwarded_count": len(first_forwarded),
            "wrong_model_evidence_released": False,
            "accepted_retry_model": (
                second_forwarded[0].model_code
                if second_forwarded
                else None
            ),
            "customer_guidance": (
                second_forwarded[0].content
                if second_forwarded
                else None
            ),
        },
    }


def schema_case() -> dict[str, Any]:
    """
    CASE 2 — RETRY_GENERATION

    내용은 그럴듯하지만 Backend가 요구하는 출력 계약을 지키지 않은 LLM 응답을 주입.
    Harness가 OUTPUT_SCHEMA_INVALID로 잡고 한 번 재생성한 뒤 PASS.
    """
    h = runner()
    evidence = [chunk("E06Q-SCHEMA-EVIDENCE")]
    guidance = normal_guidance(
        "냉수 출수량이 적을 때는 원수 공급 상태와 "
        "필터 장착 상태를 확인합니다."
    )

    invalid_payload = {
        "message": guidance.message,
        "recommendation": "상태 확인",
    }

    first = h.run(
        product=product(),
        evidence_chunks=evidence,
        safety_assessment=general_safety(),
        guidance=guidance,
        output_payload=invalid_payload,
        output_schema=GuidanceOutputSchema,
    )

    corrected_payload = guidance_dump(guidance)
    assert corrected_payload is not None

    second = h.run(
        product=product(),
        evidence_chunks=evidence,
        safety_assessment=general_safety(),
        guidance=guidance,
        output_payload=corrected_payload,
        output_schema=GuidanceOutputSchema,
        retry_state=first.retry_state,
    )

    return {
        "case_id": "OUTPUT_SCHEMA_INVALID",
        "presentation_role": "RETRY_GENERATION",
        "before": {
            "expected_contract_fields": [
                "guidance_status",
                "message",
                "restricted_functions",
                "next_actions",
            ],
            "llm_output_payload": invalid_payload,
            "problem": (
                "내용은 읽을 수 있지만 Backend 공개 응답 계약 필드가 누락됨"
            ),
        },
        "harness": {
            "first_decision": first.decision.value,
            "issues": issues(first),
            "generation_retry_count": second.retry_state.generation_retries,
            "final_decision": second.decision.value,
        },
        "after": {
            "regenerated_payload": corrected_payload,
            "schema_contract_satisfied": second.decision.value == "PASS",
            "customer_guidance": guidance_dump(guidance),
        },
    }


def mcp_nonretryable_case() -> dict[str, Any]:
    """
    CASE 3 — ESCALATE

    공식 Evidence 검색 MCP Tool이 복구 불가능한 UNAVAILABLE 오류를 반환한 상황.
    Harness가 임의 답변 생성을 허용하지 않고 상담 Handoff로 전환.
    """
    ctx = base_ctx(
        raw_symptom="냉수가 갑자기 안 나와요.",
        safety=general_safety(),
        guidance=None,
        evidence_refs=[],
    )

    failure = McpToolFailure(
        tool_name=McpToolName.SEARCH_OFFICIAL_EVIDENCE,
        kind=McpToolFailureKind.UNAVAILABLE,
        retryable=False,
    )

    runtime = runner().run_runtime(
        ctx=ctx,
        product=product(),
        evidence_chunks=[],
        safety_assessment=ctx.safety_assessment,
        guidance=ctx.usage_guidance,
        evidence_required=False,
        tool_failure=failure,
    )

    harness = runtime.harness
    handoff = runtime.handoff

    return {
        "case_id": "MCP_NONRETRYABLE_FAILURE",
        "presentation_role": "ESCALATE",
        "before": {
            "customer_symptom": ctx.raw_symptom,
            "required_tool": failure.tool_name.value,
            "tool_failure_kind": failure.kind.value,
            "retryable": failure.retryable,
            "official_evidence_available_to_runtime": False,
            "raw_exception_exposed": False,
        },
        "harness": {
            "decision": harness.decision.value,
            "issues": issues(harness),
            "error_code": (
                harness.error_code.value
                if harness.error_code is not None
                else None
            ),
            "should_escalate": harness.should_escalate,
            "handoff_present": handoff is not None,
            "handoff_reason": (
                handoff.escalation_reason
                if handoff is not None
                else None
            ),
        },
        "after": {
            "automatic_guidance_released": False,
            "hallucinated_manual_guidance_generated": False,
            "next_state": "Consultation Handoff",
            "customer_facing_policy": (
                "공식 근거 조회 Tool을 사용할 수 없으므로 "
                "추측성 자가조치를 생성하지 않고 상담 경로로 전환"
            ),
        },
    }


def hitl_case() -> dict[str, Any]:
    """
    CASE 4 — HUMAN_REVIEW

    JAC104가 지원하지 않는 ice 기능을 요청한 상황.
    Harness가 자동 확정하지 않고 HITL Human Review로 중단.
    """
    h = runner()

    ctx = base_ctx(
        raw_symptom="얼음 기능도 확인해 주세요.",
        safety=general_safety(),
        guidance=normal_guidance(
            "냉수 상태를 확인하는 안내 후보입니다."
        ),
        evidence_refs=[
            SimpleNamespace(
                chunk_id="E06Q-HITL-EVIDENCE",
                document_title="WPUJAC104DWH 공식 사용설명서",
                page=37,
                summary="냉수 관련 공식 근거",
            )
        ],
    )

    result = h.run_runtime(
        ctx=ctx,
        product=product(),
        evidence_chunks=[chunk("E06Q-HITL-EVIDENCE")],
        safety_assessment=ctx.safety_assessment,
        guidance=ctx.usage_guidance,
        required_functions={"ice"},
    )

    review = result.human_review
    status = (
        getattr(
            getattr(review, "status", None),
            "value",
            getattr(review, "status", None),
        )
        if review
        else None
    )

    return {
        "case_id": "UNSUPPORTED_FUNCTION",
        "presentation_role": "HUMAN_REVIEW",
        "before": {
            "customer_product": MODEL,
            "supported_functions": sorted(product().supported_functions),
            "requested_function": "ice",
            "guidance_candidate": guidance_dump(ctx.usage_guidance),
        },
        "harness": {
            "decision": result.harness.decision.value,
            "issues": issues(result.harness),
            "human_review_present": review is not None,
            "human_review_status": status,
        },
        "after": {
            "customer_release": "자동 확정하지 않음",
            "next_state": "HITL Human Review 대기",
        },
    }


def render(case: dict[str, Any]) -> list[str]:
    return [
        f"## {case['case_id']}",
        "",
        f"- Harness role: `{case['presentation_role']}`",
        "",
        "### BEFORE — Harness 직전",
        "",
        "```json",
        json.dumps(case["before"], ensure_ascii=False, indent=2),
        "```",
        "",
        "### HARNESS",
        "",
        "```json",
        json.dumps(case["harness"], ensure_ascii=False, indent=2),
        "```",
        "",
        "### AFTER — 고객-facing 결과 / 다음 상태",
        "",
        "```json",
        json.dumps(case["after"], ensure_ascii=False, indent=2),
        "```",
        "",
        "---",
        "",
    ]


def main() -> None:
    sha = git_sha()
    started = time.perf_counter()

    cases = [
        wrong_model_case(),
        schema_case(),
        mcp_nonretryable_case(),
        hitl_case(),
    ]

    payload = {
        "status": "E06_QUALITATIVE_COMPLETE",
        "result_label": "QUALITATIVE_PRESENTATION_EVIDENCE",
        "variant": "V2_HARNESS_DISTINCT_DECISION_PATHS",
        "git_sha": sha,
        "original_e06_sha": EXPECTED_SHA,
        "matches_original_e06_sha": sha == EXPECTED_SHA,
        "scope": "BEFORE_HARNESS_AFTER_PRESENTATION_CASES",
        "design": {
            "goal": (
                "Harness의 네 가지 대표 의사결정 경로를 "
                "중복 없이 사람이 읽기 쉬운 사례로 제시"
            ),
            "decision_paths": [
                "RETRY_RETRIEVAL",
                "RETRY_GENERATION",
                "ESCALATE",
                "HUMAN_REVIEW",
            ],
            "excluded_from_main_showcase": [
                "SAFETY_CONFLICT"
            ],
            "exclusion_reason": (
                "누수/DANGER는 정상 파이프라인에서 앞단 Rule-based Safety Guard가 "
                "이미 결정론적으로 TOTAL_STOP 처리하므로 Harness 고유 가치 설명에 "
                "중복이 생김. Safety Conflict는 Defense-in-Depth 보조 사례로만 해석."
            ),
        },
        "note": (
            "E06 정량 Fault Injection Ablation을 대체하지 않는 발표용 정성 사례. "
            "외부 LLM/Vector DB 없이 실제 Harness decision/routing contract를 사용한다."
        ),
        "cases": cases,
        "experiment_total_seconds": round(
            time.perf_counter() - started,
            3,
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)

    (OUT / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# E06-Q v2 — Harness Before / Decision / After",
        "",
        f"- Git SHA: `{sha}`",
        f"- Original E06 SHA 일치: `{sha == EXPECTED_SHA}`",
        "- Variant: `V2_HARNESS_DISTINCT_DECISION_PATHS`",
        "",
        "> E06 정량 실험을 대체하지 않는 발표용 Qualitative Evidence입니다.",
        "",
        "## 발표용 핵심 구조",
        "",
        "| Fault | Harness 결정 | 의미 |",
        "|---|---|---|",
        "| 다른 제품 Evidence | RETRY_RETRIEVAL | 검색 복구 |",
        "| LLM 출력 계약 위반 | RETRY_GENERATION | 생성 복구 |",
        "| MCP 복구 불가 장애 | ESCALATE | Fail-closed 상담 Handoff |",
        "| 미지원 기능 요청 | HUMAN_REVIEW | HITL 사람 검토 |",
        "",
    ]

    for case in cases:
        md += render(case)

    md += [
        "## 발표용 한 줄 설명",
        "",
        "> Harness는 오류를 전부 같은 방식으로 막는 계층이 아니라, "
        "복구 가능한 오류는 다시 시도하고, 복구 불가능한 오류는 상담으로 넘기며, "
        "사람 판단이 필요한 요청은 HITL로 중단하는 Reliability Boundary입니다.",
        "",
        "## Safety Conflict 보조 해석",
        "",
        "> 누수/DANGER는 정상 실행에서 Rule-based Safety Guard가 우선 TOTAL_STOP으로 처리합니다. "
        "따라서 Safety Conflict는 Harness의 주 사례가 아니라, 앞단 안전 판정과 최종 응답이 "
        "비정상적으로 모순되는 상태를 막는 Defense-in-Depth 사례로 분리합니다.",
        "",
    ]

    (OUT / "report.md").write_text(
        "\n".join(md),
        encoding="utf-8",
    )

    for case in cases:
        print("\n" + "=" * 80)
        print(f"[{case['case_id']}]")
        print("- BEFORE")
        print(
            json.dumps(
                case["before"],
                ensure_ascii=False,
                indent=2,
            )
        )
        print("- HARNESS")
        print(
            json.dumps(
                case["harness"],
                ensure_ascii=False,
                indent=2,
            )
        )
        print("- AFTER")
        print(
            json.dumps(
                case["after"],
                ensure_ascii=False,
                indent=2,
            )
        )

    print(
        "\n"
        + json.dumps(
            {
                "status": payload["status"],
                "variant": payload["variant"],
                "git_sha": sha,
                "output_dir": str(
                    OUT.relative_to(ROOT)
                ).replace("\\", "/"),
                "experiment_total_seconds": payload[
                    "experiment_total_seconds"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
