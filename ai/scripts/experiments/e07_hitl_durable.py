from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.orchestration.agents import ConsultationContextSynthesisAgent
from ai.app.orchestration.harness import HarnessRunner, ProductContext, ProductFamily
from ai.app.orchestration.hitl import (
    HumanReviewDecision,
    HumanReviewResume,
    HumanReviewStatus,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import (
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    UsageGuidance,
    UsageGuidanceStatus,
)

OUT = ROOT / "ai/experiment_results/e07_hitl_durable"
MODEL = "WPUJAC104DWH"
STATE_VERSION = 7
CHUNK_ID = "E07-JAC104-EVIDENCE-001"


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


def evidence() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=CHUNK_ID,
        document_title=f"{MODEL} 공식 사용설명서",
        manual_model=MODEL,
        model_code=MODEL,
        product_generation="D",
        content=(
            "해당 제품은 냉수 및 온수 사용 안내 범위에 해당하며, "
            "제품 사양에 없는 기능은 추가 확인이 필요합니다."
        ),
        similarity_score=0.96,
        verification_status="official_verified",
        allowed_use=True,
        runtime_eligible=True,
    )


def safety() -> SafetyAssessment:
    return SafetyAssessment(
        risk_level=RiskLevel.GENERAL,
        priority=SafetyPriority.GENERAL_GUIDANCE,
        requires_consultation=False,
        matched_safety_rule_ids=[],
        detected_risks=[],
        safety_reason="일반 안내 가능",
    )


def original_guidance() -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=(
            "요청하신 기능은 현재 자동 안내 범위를 벗어나므로 "
            "제품 사양을 추가 확인해 주세요."
        ),
        restricted_functions=[],
        next_actions=["제품 사양 확인"],
    )


def human_modified_guidance() -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=(
            "상담사가 제품 사양을 확인한 뒤 "
            "얼음 기능 지원 여부를 안내합니다."
        ),
        restricted_functions=[],
        next_actions=["상담사 사양 확인"],
    )


def make_ctx(case_id: str) -> SimpleNamespace:
    inquiry_id = uuid5(NAMESPACE_URL, f"waterbridge-e07:{case_id}:inquiry")
    correlation_id = uuid5(NAMESPACE_URL, f"waterbridge-e07:{case_id}:correlation")
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            ai_request_id=f"e07-{case_id.lower()}-request",
            state_version=STATE_VERSION,
        ),
        raw_symptom="얼음 기능도 사용할 수 있는지 확인해 주세요.",
        model_code=MODEL,
        selected_symptoms=[],
        structured_symptom=None,
        previous_answers=[],
        missing_fields=[],
        followup_questions=[],
        evidence_references=[
            SimpleNamespace(
                chunk_id=CHUNK_ID,
                document_title=f"{MODEL} 공식 사용설명서",
                page=37,
                summary="제품 기능 범위 확인용 공식 근거",
            )
        ],
        safety_assessment=safety(),
        usage_guidance=original_guidance(),
        awaiting_customer_input=False,
        retry_count=0,
        retrieval_outcome=None,
    )


class CountingHarnessRunner(HarnessRunner):
    """Resume 시 Harness verification 재실행 여부를 동적으로 센다."""

    def __init__(self) -> None:
        super().__init__(
            context_synthesis_agent=ConsultationContextSynthesisAgent(llm_client=None)
        )
        self.harness_run_calls = 0

    def run(self, *args: Any, **kwargs: Any):
        self.harness_run_calls += 1
        return super().run(*args, **kwargs)


def dump_guidance(value: Any) -> dict[str, Any] | None:
    return value.model_dump(mode="json") if value is not None else None


def issue_codes(harness: Any) -> list[str]:
    return [item.code.value for item in harness.verification.issues]


def state_values(runner: CountingHarnessRunner, interrupted: Any) -> dict[str, Any]:
    snapshot = runner.hitl_workflow.graph.get_state(
        interrupted.checkpoint.langgraph_config()
    )
    values = getattr(snapshot, "values", {}) or {}
    return values if isinstance(values, dict) else {}


def context_checks(
    runner: CountingHarnessRunner,
    ctx: SimpleNamespace,
    interrupted: Any,
) -> dict[str, bool]:
    payload = interrupted.interrupt_payload or {}
    request = state_values(runner, interrupted).get("request") or {}
    return {
        "interrupt_inquiry_preserved": (
            str(payload.get("inquiry_id")) == str(ctx.trace_context.inquiry_id)
        ),
        "checkpoint_inquiry_preserved": (
            str(request.get("inquiry_id")) == str(ctx.trace_context.inquiry_id)
        ),
        "ai_request_id_preserved": (
            request.get("ai_request_id") == ctx.trace_context.ai_request_id
        ),
        "model_code_preserved": request.get("model_code") == MODEL,
        "state_version_preserved": request.get("state_version") == STATE_VERSION,
        "evidence_ids_preserved": request.get("evidence_chunk_ids") == [CHUNK_ID],
    }


def start_review(case_id: str):
    runner = CountingHarnessRunner()
    ctx = make_ctx(case_id)
    runtime = runner.run_runtime(
        ctx=ctx,
        product=product(),
        evidence_chunks=[evidence()],
        safety_assessment=ctx.safety_assessment,
        guidance=ctx.usage_guidance,
        required_functions={"ice"},
    )
    assert runtime.harness.decision.value == "HUMAN_REVIEW"
    assert "UNSUPPORTED_FUNCTION" in issue_codes(runtime.harness)
    assert runtime.human_review is not None
    assert runtime.human_review.status == HumanReviewStatus.WAITING_FOR_REVIEW
    return runner, ctx, runtime


def before_payload(runner: CountingHarnessRunner, ctx: SimpleNamespace, runtime: Any):
    review = runtime.human_review
    return {
        "customer_request": ctx.raw_symptom,
        "product_model": MODEL,
        "supported_functions": sorted(product().supported_functions),
        "requested_function": "ice",
        "harness_decision": runtime.harness.decision.value,
        "harness_issues": issue_codes(runtime.harness),
        "hitl_status": review.status.value,
        "thread_id": review.checkpoint.thread_id,
        "state_version": review.checkpoint.state_version,
        "evidence_chunk_ids": review.interrupt_payload["evidence_chunk_ids"],
        "harness_run_calls": runner.harness_run_calls,
    }


def run_approve():
    runner, ctx, runtime = start_review("APPROVE")
    review = runtime.human_review
    before = before_payload(runner, ctx, runtime)
    calls_before = runner.harness_run_calls

    result = runner.resume_human_review(
        ctx=ctx,
        product=product(),
        interrupted=review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.APPROVE,
            state_version=STATE_VERSION,
            reviewer_note="제안 안내 승인",
        ),
    )

    checks = {
        "completed": result.review.status == HumanReviewStatus.COMPLETED,
        "approved": bool(result.review.outcome and result.review.outcome.approved),
        "same_thread_id": (
            result.review.checkpoint.thread_id == review.checkpoint.thread_id
        ),
        "original_guidance_preserved": (
            dump_guidance(result.guidance) == dump_guidance(ctx.usage_guidance)
        ),
        "no_harness_reverification_on_resume": (
            runner.harness_run_calls == calls_before
        ),
        **context_checks(runner, ctx, review),
    }

    return {
        "case_id": "APPROVE",
        "before": before,
        "after": {
            "status": result.review.status.value,
            "final_guidance": dump_guidance(result.guidance),
            "handoff_present": result.handoff is not None,
            "harness_run_calls": runner.harness_run_calls,
        },
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_modify():
    runner, ctx, runtime = start_review("MODIFY")
    review = runtime.human_review
    before = before_payload(runner, ctx, runtime)
    calls_before = runner.harness_run_calls
    modified = human_modified_guidance()

    result = runner.resume_human_review(
        ctx=ctx,
        product=product(),
        interrupted=review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.MODIFY,
            state_version=STATE_VERSION,
            modified_guidance=modified,
            reviewer_note="제품 사양 확인 표현으로 수정",
        ),
    )

    checks = {
        "completed": result.review.status == HumanReviewStatus.COMPLETED,
        "approved": bool(result.review.outcome and result.review.outcome.approved),
        "same_thread_id": (
            result.review.checkpoint.thread_id == review.checkpoint.thread_id
        ),
        "human_modified_guidance_applied": (
            dump_guidance(result.guidance) == dump_guidance(modified)
        ),
        "original_guidance_not_released": (
            dump_guidance(result.guidance) != dump_guidance(ctx.usage_guidance)
        ),
        "no_harness_reverification_on_resume": (
            runner.harness_run_calls == calls_before
        ),
        **context_checks(runner, ctx, review),
    }

    return {
        "case_id": "MODIFY",
        "before": before,
        "after": {
            "status": result.review.status.value,
            "final_guidance": dump_guidance(result.guidance),
            "reviewer_note": (
                result.review.outcome.reviewer_note
                if result.review.outcome else None
            ),
            "handoff_present": result.handoff is not None,
            "harness_run_calls": runner.harness_run_calls,
        },
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_reject():
    runner, ctx, runtime = start_review("REJECT")
    review = runtime.human_review
    before = before_payload(runner, ctx, runtime)
    calls_before = runner.harness_run_calls

    result = runner.resume_human_review(
        ctx=ctx,
        product=product(),
        interrupted=review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.REJECT,
            state_version=STATE_VERSION,
            reviewer_note="자동 안내 승인 불가",
        ),
    )
    handoff = result.handoff

    checks = {
        "completed": result.review.status == HumanReviewStatus.COMPLETED,
        "rejected": bool(result.review.outcome and not result.review.outcome.approved),
        "same_thread_id": (
            result.review.checkpoint.thread_id == review.checkpoint.thread_id
        ),
        "guidance_release_blocked": result.guidance is None,
        "handoff_created": handoff is not None,
        "handoff_reason_is_human_review_rejected": (
            getattr(handoff, "escalation_reason", None) == "HUMAN_REVIEW_REJECTED"
        ),
        "no_harness_reverification_on_resume": (
            runner.harness_run_calls == calls_before
        ),
        **context_checks(runner, ctx, review),
    }

    return {
        "case_id": "REJECT",
        "before": before,
        "after": {
            "status": result.review.status.value,
            "final_guidance": None,
            "handoff_present": handoff is not None,
            "handoff_reason": getattr(handoff, "escalation_reason", None),
            "harness_run_calls": runner.harness_run_calls,
        },
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_stale_version():
    runner, ctx, runtime = start_review("STALE_STATE_VERSION")
    review = runtime.human_review
    before = before_payload(runner, ctx, runtime)
    calls_before = runner.harness_run_calls

    error_type = None
    error_message = None
    try:
        runner.resume_human_review(
            ctx=ctx,
            product=product(),
            interrupted=review,
            response=HumanReviewResume(
                decision=HumanReviewDecision.APPROVE,
                state_version=STATE_VERSION + 1,
                reviewer_note="불일치 버전 승인",
            ),
        )
    except ValueError as exc:
        error_type = type(exc).__name__
        error_message = str(exc)

    # 현재 LangGraph HITL 계약에서는 stale resume이 resolve_review 단계에서
    # fail-closed 된 뒤 같은 checkpoint에 두 번째 Command(resume=...)를 넣어
    # 이전 잘못된 payload를 덮어쓰는 동작을 보장하지 않는다.
    # 따라서 이 실험의 목적은 "stale human decision이 차단되는가"로 한정한다.
    # 정상 state_version의 Resume 가능성은 별도 APPROVE case가 검증한다.
    preserved = context_checks(runner, ctx, review)

    checks = {
        "stale_version_blocked": error_type == "ValueError",
        "state_version_error_reported": (
            error_message is not None and "state_version" in error_message
        ),
        "no_harness_reverification_on_failed_resume": (
            runner.harness_run_calls == calls_before
        ),
        **preserved,
    }

    return {
        "case_id": "STALE_STATE_VERSION",
        "before": before,
        "stale_attempt": {
            "checkpoint_state_version": STATE_VERSION,
            "submitted_state_version": STATE_VERSION + 1,
            "blocked": error_type == "ValueError",
            "error_type": error_type,
            "error_message": error_message,
        },
        "after": {
            "automatic_guidance_released": False,
            "resume_result": "BLOCKED_FAIL_CLOSED",
            "same_checkpoint_retry_claimed": False,
            "normal_resume_is_verified_by": "APPROVE case",
            "harness_run_calls": runner.harness_run_calls,
        },
        "checks": checks,
        "pass": all(checks.values()),
    }


def main():
    started = time.perf_counter()
    sha = git_sha()
    cases = [run_approve(), run_modify(), run_reject(), run_stale_version()]
    passed = sum(case["pass"] for case in cases)

    probe = CountingHarnessRunner()
    checkpointer_type = type(probe.hitl_workflow.checkpointer).__name__

    summary = {
        "status": "E07_COMPLETE" if passed == len(cases) else "E07_FAILED",
        "experiment_id": "E07",
        "title": "HITL + LangGraph Checkpointed Resume",
        "result_label": "QUALITATIVE_RUNTIME_EVIDENCE",
        "git_sha": sha,
        "scope": "SAME_PROCESS_CHECKPOINTED_INTERRUPT_RESUME",
        "checkpointer_type": checkpointer_type,
        "persistent_process_restart_durability_claimed": False,
        "state_version_semantics": "PRESERVE_AND_MATCH_CHECKPOINT_VERSION",
        "cases_passed": passed,
        "cases_total": len(cases),
        "cases": cases,
        "experiment_total_seconds": round(time.perf_counter() - started, 3),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# E07 — HITL + LangGraph Checkpointed Resume",
        "",
        f"- Git SHA: `{sha}`",
        f"- Checkpointer: `{checkpointer_type}`",
        f"- 결과: **{passed}/{len(cases)} PASS**",
        "",
        "## 목적",
        "",
        "사람 검토가 필요한 요청을 LangGraph interrupt에서 중단하고, "
        "동일 Checkpoint/Thread의 Context를 보존한 채 "
        "APPROVE/MODIFY/REJECT로 Resume할 수 있는지 검증한다.",
        "",
        "## 핵심 결과",
        "",
        "| Case | 기대 결과 | PASS |",
        "|---|---|---|",
        f"| APPROVE | 기존 Guidance 보존 | {cases[0]['pass']} |",
        f"| MODIFY | 사람 수정 Guidance 반영 | {cases[1]['pass']} |",
        f"| REJECT | 자동 Release 차단 + Handoff | {cases[2]['pass']} |",
        f"| STALE_STATE_VERSION | 불일치 버전 Fail-closed 차단 | {cases[3]['pass']} |",
        "",
        "## 해석 범위",
        "",
        "- 현재 `InMemorySaver`이면 같은 AI 프로세스 안의 interrupt/resume만 주장한다.",
        "- 프로세스 재시작 후 Persistent Durability는 본 실험 범위가 아니다.",
        "- 현재 HITL 계약의 `state_version`은 증가시키는 값이 아니라 "
        "checkpoint 요청과 동일해야 하는 consistency key다.",
        "- Resume 시 Harness verification 재호출 여부는 동적 call counter로 확인한다.",
        "- Retrieval/Generation 전체 E2E 재실행 여부는 E07의 독립 측정 대상이 아니다.",
        "",
        "## 발표용 문장",
        "",
        "> 사람 판단이 필요한 요청은 LangGraph Checkpoint에서 중단하고, "
        "검토 후 동일 Thread와 Context를 유지한 채 Resume했습니다. "
        "승인·수정·거절을 각각 다른 후속 처리로 연결하고, "
        "불일치 State Version의 검토 응답은 Fail-closed로 차단했습니다.",
        "",
    ]

    for case in cases:
        md += [
            f"## {case['case_id']}",
            "",
            f"- PASS: `{case['pass']}`",
            "",
            "### BEFORE",
            "```json",
            json.dumps(case["before"], ensure_ascii=False, indent=2),
            "```",
        ]
        if "stale_attempt" in case:
            md += [
                "### STALE ATTEMPT",
                "```json",
                json.dumps(case["stale_attempt"], ensure_ascii=False, indent=2),
                "```",
            ]
        md += [
            "### AFTER",
            "```json",
            json.dumps(case["after"], ensure_ascii=False, indent=2),
            "```",
            "### CHECKS",
            "```json",
            json.dumps(case["checks"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]

    (OUT / "report.md").write_text("\n".join(md), encoding="utf-8")

    for case in cases:
        print("\n" + "=" * 80)
        print(f"[{case['case_id']}] PASS={case['pass']}")
        print(json.dumps(case, ensure_ascii=False, indent=2))

    print("\n" + json.dumps({
        "status": summary["status"],
        "git_sha": sha,
        "checkpointer_type": checkpointer_type,
        "scope": summary["scope"],
        "cases_passed": f"{passed}/{len(cases)}",
        "output_dir": "ai/experiment_results/e07_hitl_durable",
        "experiment_total_seconds": summary["experiment_total_seconds"],
    }, ensure_ascii=False, indent=2))

    if passed != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
