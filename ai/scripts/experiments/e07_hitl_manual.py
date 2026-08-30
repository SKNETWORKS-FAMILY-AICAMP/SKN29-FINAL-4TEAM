from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.orchestration.agents import ConsultationContextSynthesisAgent
from ai.app.orchestration.harness import (
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
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

OUT = ROOT / "ai/experiment_results/e07/manual"

MODEL = "WPUJAC104DWH"
STATE_VERSION = 7
CHUNK_ID = "E07-MANUAL-JAC104-EVIDENCE-001"


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


def proposed_guidance() -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=(
            "요청하신 기능은 현재 자동 안내 범위를 벗어나므로 "
            "제품 사양을 추가 확인해 주세요."
        ),
        restricted_functions=[],
        next_actions=["제품 사양 확인"],
    )


def make_ctx() -> SimpleNamespace:
    inquiry_id = uuid5(
        NAMESPACE_URL,
        "waterbridge-e07-manual:inquiry",
    )
    correlation_id = uuid5(
        NAMESPACE_URL,
        "waterbridge-e07-manual:correlation",
    )

    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            ai_request_id="e07-manual-human-review",
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
        usage_guidance=proposed_guidance(),
        awaiting_customer_input=False,
        retry_count=0,
        retrieval_outcome=None,
    )


class CountingHarnessRunner(HarnessRunner):
    """Resume에서 Harness verification이 다시 실행되는지 확인."""

    def __init__(self) -> None:
        super().__init__(
            context_synthesis_agent=ConsultationContextSynthesisAgent(
                llm_client=None
            )
        )
        self.harness_run_calls = 0

    def run(self, *args: Any, **kwargs: Any):
        self.harness_run_calls += 1
        return super().run(*args, **kwargs)


def dump_guidance(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return value.model_dump(mode="json")


def issue_codes(harness: Any) -> list[str]:
    return [
        item.code.value
        for item in harness.verification.issues
    ]


def checkpoint_request(
    runner: CountingHarnessRunner,
    interrupted: Any,
) -> dict[str, Any]:
    snapshot = runner.hitl_workflow.graph.get_state(
        interrupted.checkpoint.langgraph_config()
    )
    values = getattr(snapshot, "values", {}) or {}
    if not isinstance(values, dict):
        return {}
    request = values.get("request") or {}
    return request if isinstance(request, dict) else {}


def print_header(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def print_review_screen(
    *,
    ctx: SimpleNamespace,
    runtime: Any,
) -> None:
    review = runtime.human_review
    payload = review.interrupt_payload or {}

    print_header("[E07-B] 실제 Human Review 대기 상태")
    print()
    print("AI Workflow가 LangGraph interrupt에서 중단되었습니다.")
    print("지금부터 아래 내용을 직접 확인한 뒤 사람이 결정을 입력해야 합니다.")
    print()
    print(f"상태              : {review.status.value}")
    print(f"Thread ID         : {review.checkpoint.thread_id}")
    print(f"Inquiry ID        : {ctx.trace_context.inquiry_id}")
    print(f"State Version     : {review.checkpoint.state_version}")
    print(f"고객 제품          : {MODEL}")
    print(f"고객 요청          : {ctx.raw_symptom}")
    print(f"지원 기능          : {', '.join(sorted(product().supported_functions))}")
    print("요청 기능          : ice")
    print(f"Harness Decision  : {runtime.harness.decision.value}")
    print(f"Harness Issues    : {', '.join(issue_codes(runtime.harness))}")
    print(f"Evidence IDs      : {payload.get('evidence_chunk_ids')}")
    print()
    print("[AI 제안 Guidance]")
    print(ctx.usage_guidance.message)
    print()
    print("※ 실제 상담사 검토를 흉내 내는 실험입니다.")
    print("※ 전화번호/이메일 등 개인정보는 입력하지 마세요.")
    print()


def ask_decision() -> HumanReviewDecision:
    while True:
        print("사람의 결정을 선택하세요.")
        print("  1. APPROVE  - AI 제안을 그대로 승인")
        print("  2. MODIFY   - 사람이 안내 문구를 수정")
        print("  3. REJECT   - AI 제안을 거절")
        raw = input("\n선택 > ").strip().lower()

        mapping = {
            "1": HumanReviewDecision.APPROVE,
            "approve": HumanReviewDecision.APPROVE,
            "a": HumanReviewDecision.APPROVE,
            "2": HumanReviewDecision.MODIFY,
            "modify": HumanReviewDecision.MODIFY,
            "m": HumanReviewDecision.MODIFY,
            "3": HumanReviewDecision.REJECT,
            "reject": HumanReviewDecision.REJECT,
            "r": HumanReviewDecision.REJECT,
        }
        if raw in mapping:
            return mapping[raw]

        print("\n[입력 오류] 1/2/3 또는 approve/modify/reject 중 하나를 입력하세요.\n")


def ask_nonempty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("[입력 오류] 빈 문자열은 입력할 수 없습니다.")


def build_resume(
    decision: HumanReviewDecision,
) -> tuple[HumanReviewResume, dict[str, Any]]:
    if decision == HumanReviewDecision.MODIFY:
        print()
        print("[사람이 수정할 최종 Guidance]")
        message = ask_nonempty("수정 안내 문장 > ")
        next_action = ask_nonempty("다음 조치 문장 > ")
        note = input("검토 메모(선택) > ").strip() or None

        modified = UsageGuidance(
            guidance_status=UsageGuidanceStatus.NORMAL,
            message=message,
            restricted_functions=[],
            next_actions=[next_action],
        )

        return (
            HumanReviewResume(
                decision=decision,
                state_version=STATE_VERSION,
                modified_guidance=modified,
                reviewer_note=note,
            ),
            {
                "decision": decision.value,
                "modified_guidance": dump_guidance(modified),
                "reviewer_note": note,
            },
        )

    if decision == HumanReviewDecision.APPROVE:
        note = input("\n승인 메모(선택) > ").strip() or None
        return (
            HumanReviewResume(
                decision=decision,
                state_version=STATE_VERSION,
                reviewer_note=note,
            ),
            {
                "decision": decision.value,
                "modified_guidance": None,
                "reviewer_note": note,
            },
        )

    note = input("\n거절 사유 메모(선택) > ").strip() or None
    return (
        HumanReviewResume(
            decision=decision,
            state_version=STATE_VERSION,
            reviewer_note=note,
        ),
        {
            "decision": decision.value,
            "modified_guidance": None,
            "reviewer_note": note,
        },
    )


def main() -> None:
    started = time.perf_counter()
    sha = git_sha()

    runner = CountingHarnessRunner()
    ctx = make_ctx()

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

    interrupted = runtime.human_review
    harness_calls_before_resume = runner.harness_run_calls

    print_review_screen(
        ctx=ctx,
        runtime=runtime,
    )

    wait_started = time.perf_counter()
    decision = ask_decision()
    response, human_input = build_resume(decision)
    human_wait_seconds = round(time.perf_counter() - wait_started, 3)

    print()
    print("[사람 입력 수신 완료]")
    print(f"Decision: {decision.value}")
    print("동일 LangGraph Checkpoint에서 Resume합니다...")

    resolution = runner.resume_human_review(
        ctx=ctx,
        product=product(),
        interrupted=interrupted,
        response=response,
    )

    checkpoint_data = checkpoint_request(
        runner,
        interrupted,
    )

    outcome = resolution.review.outcome
    handoff = resolution.handoff

    preserved = {
        "same_thread_id": (
            resolution.review.checkpoint.thread_id
            == interrupted.checkpoint.thread_id
        ),
        "inquiry_id_preserved": (
            str(checkpoint_data.get("inquiry_id"))
            == str(ctx.trace_context.inquiry_id)
        ),
        "ai_request_id_preserved": (
            checkpoint_data.get("ai_request_id")
            == ctx.trace_context.ai_request_id
        ),
        "model_code_preserved": (
            checkpoint_data.get("model_code") == MODEL
        ),
        "state_version_preserved": (
            checkpoint_data.get("state_version") == STATE_VERSION
        ),
        "evidence_ids_preserved": (
            checkpoint_data.get("evidence_chunk_ids")
            == [CHUNK_ID]
        ),
        "no_harness_reverification_on_resume": (
            runner.harness_run_calls
            == harness_calls_before_resume
        ),
    }

    if decision == HumanReviewDecision.APPROVE:
        behavior_checks = {
            "completed": (
                resolution.review.status
                == HumanReviewStatus.COMPLETED
            ),
            "approved": bool(
                outcome and outcome.approved
            ),
            "original_guidance_released": (
                dump_guidance(resolution.guidance)
                == dump_guidance(ctx.usage_guidance)
            ),
            "handoff_absent": handoff is None,
        }
    elif decision == HumanReviewDecision.MODIFY:
        behavior_checks = {
            "completed": (
                resolution.review.status
                == HumanReviewStatus.COMPLETED
            ),
            "approved": bool(
                outcome and outcome.approved
            ),
            "human_modified_guidance_released": (
                dump_guidance(resolution.guidance)
                == human_input["modified_guidance"]
            ),
            "original_guidance_not_released": (
                dump_guidance(resolution.guidance)
                != dump_guidance(ctx.usage_guidance)
            ),
            "handoff_absent": handoff is None,
        }
    else:
        behavior_checks = {
            "completed": (
                resolution.review.status
                == HumanReviewStatus.COMPLETED
            ),
            "rejected": bool(
                outcome and not outcome.approved
            ),
            "guidance_release_blocked": (
                resolution.guidance is None
            ),
            "handoff_created": handoff is not None,
            "handoff_reason_is_human_review_rejected": (
                getattr(handoff, "escalation_reason", None)
                == "HUMAN_REVIEW_REJECTED"
            ),
        }

    checks = {
        **preserved,
        **behavior_checks,
    }
    passed = all(checks.values())

    result = {
        "status": (
            "E07_MANUAL_COMPLETE"
            if passed
            else "E07_MANUAL_FAILED"
        ),
        "experiment_id": "E07-B",
        "title": "Interactive Human-in-the-Loop Resume",
        "result_label": "MANUAL_HUMAN_INTERACTION_EVIDENCE",
        "git_sha": sha,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "SAME_PROCESS_INTERACTIVE_HUMAN_REVIEW",
        "checkpointer_type": type(
            runner.hitl_workflow.checkpointer
        ).__name__,
        "human_input_source": "INTERACTIVE_TERMINAL_INPUT",
        "human_wait_seconds": human_wait_seconds,
        "before": {
            "customer_request": ctx.raw_symptom,
            "model_code": MODEL,
            "requested_function": "ice",
            "supported_functions": sorted(
                product().supported_functions
            ),
            "harness_decision": runtime.harness.decision.value,
            "harness_issues": issue_codes(runtime.harness),
            "hitl_status": interrupted.status.value,
            "thread_id": interrupted.checkpoint.thread_id,
            "state_version": interrupted.checkpoint.state_version,
            "evidence_chunk_ids": (
                interrupted.interrupt_payload or {}
            ).get("evidence_chunk_ids"),
            "proposed_guidance": dump_guidance(
                ctx.usage_guidance
            ),
            "harness_run_calls": harness_calls_before_resume,
        },
        "human_input": human_input,
        "after": {
            "review_status": resolution.review.status.value,
            "thread_id": resolution.review.checkpoint.thread_id,
            "approved": (
                outcome.approved
                if outcome is not None
                else None
            ),
            "final_guidance": dump_guidance(
                resolution.guidance
            ),
            "handoff_present": handoff is not None,
            "handoff_reason": getattr(
                handoff,
                "escalation_reason",
                None,
            ),
            "harness_run_calls": runner.harness_run_calls,
        },
        "checks": checks,
        "pass": passed,
        "experiment_total_seconds": round(
            time.perf_counter() - started,
            3,
        ),
        "claim_boundary": (
            "실제 사람이 터미널에서 Human Review 결정을 입력한 "
            "same-process HITL 실험이다. Browser UI E2E 및 "
            "process restart durability는 본 실험 범위가 아니다."
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report = [
        "# E07-B — Interactive Human-in-the-Loop Resume",
        "",
        f"- Git SHA: `{sha}`",
        f"- Result: `{'PASS' if passed else 'FAIL'}`",
        f"- Human Input Source: `INTERACTIVE_TERMINAL_INPUT`",
        f"- Checkpointer: `{result['checkpointer_type']}`",
        f"- Human Wait Time: `{human_wait_seconds}s`",
        "",
        "## BEFORE — AI가 사람 검토를 기다리는 상태",
        "",
        "```json",
        json.dumps(
            result["before"],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 실제 사람 입력",
        "",
        "```json",
        json.dumps(
            result["human_input"],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## AFTER — 동일 Checkpoint에서 Resume한 결과",
        "",
        "```json",
        json.dumps(
            result["after"],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 검증 항목",
        "",
        "```json",
        json.dumps(
            result["checks"],
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 해석",
        "",
        "> AI가 자동 판단 범위를 벗어난 요청에서 Human Review 상태로 "
        "중단되었고, 실제 사람이 터미널에서 결정을 입력한 뒤 "
        "동일 LangGraph Thread와 Context를 유지한 채 Resume되었다.",
        "",
        "## 범위 제한",
        "",
        result["claim_boundary"],
        "",
    ]

    (OUT / "report.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print_header("[E07-B] Human Review Resume 결과")
    print(json.dumps(
        {
            "status": result["status"],
            "human_decision": human_input["decision"],
            "human_wait_seconds": human_wait_seconds,
            "same_thread_id": checks["same_thread_id"],
            "inquiry_id_preserved": checks["inquiry_id_preserved"],
            "evidence_ids_preserved": checks["evidence_ids_preserved"],
            "no_harness_reverification_on_resume": checks[
                "no_harness_reverification_on_resume"
            ],
            "final_guidance": result["after"]["final_guidance"],
            "handoff_present": result["after"]["handoff_present"],
            "handoff_reason": result["after"]["handoff_reason"],
            "pass": passed,
            "output_dir": "ai/experiment_results/e07/manual",
        },
        ensure_ascii=False,
        indent=2,
    ))

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
