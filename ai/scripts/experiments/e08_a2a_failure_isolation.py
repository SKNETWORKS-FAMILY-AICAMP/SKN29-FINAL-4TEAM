from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.integrations.a2a.client import (
    A2ASafetyFailureKind,
    SdkA2ASafetyTransport,
    WaterBridgeA2ASafetyClient,
)
from ai.app.integrations.a2a.safety_adapter import (
    SafetyA2AAdapter,
    SafetyA2ARequest,
    SafetyA2AResponse,
)
from ai.app.safety.risk_classifier import RiskClassifier

OUT = ROOT / "ai/experiment_results/e08"
SERVER_LOG = OUT / "a2a_server.log"

INQUIRY_ID = UUID("11111111-1111-4111-8111-111111111111")
CORRELATION_ID = UUID("22222222-2222-4222-8222-222222222222")
MODEL_CODE = "WPUJAC104DWH"
PRODUCT_FAMILY = "DIRECT_WATER_PURIFIER"
RAW_TEXT = "정수기 냉수가 미지근합니다."
SELECTED_SYMPTOMS = ["COLD_WATER_TEMPERATURE"]


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


def request() -> SafetyA2ARequest:
    return SafetyA2ARequest(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        raw_text=RAW_TEXT,
        selected_symptoms=SELECTED_SYMPTOMS,
        model_code=MODEL_CODE,
        product_family=PRODUCT_FAMILY,
        supported_functions=["COLD_WATER"],
    )


class CountingRiskClassifier:
    """실제 RiskClassifier를 감싸 Local fallback 호출 횟수를 센다."""

    def __init__(self) -> None:
        self.inner = RiskClassifier()
        self.calls = 0

    def classify(
        self,
        raw_text: str,
        selected_symptoms: list[str] | None = None,
    ):
        self.calls += 1
        return self.inner.classify(
            raw_text=raw_text,
            selected_symptoms=selected_symptoms,
        )


def local_adapter_with_counter():
    classifier = CountingRiskClassifier()
    adapter = SafetyA2AAdapter(classifier=classifier)
    return adapter, classifier


def dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def recursive_contains(value: Any, needle: str) -> bool:
    return needle.lower() in json.dumps(
        value,
        ensure_ascii=False,
    ).lower()


def start_a2a_server(port: int) -> tuple[subprocess.Popen, Any]:
    OUT.mkdir(parents=True, exist_ok=True)

    # create_app(public_base_url=...)를 사용해 Agent Card가 실제 동적 포트의
    # JSON-RPC endpoint를 광고하게 한다.
    bootstrap = (
        "from ai.app.integrations.a2a.server import create_app;"
        "import uvicorn;"
        f"app=create_app(public_base_url='http://127.0.0.1:{port}');"
        f"uvicorn.run(app,host='127.0.0.1',port={port},log_level='warning')"
    )

    log_handle = SERVER_LOG.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-c", bootstrap],
        cwd=ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, log_handle


def server_log_tail(lines: int = 80) -> str:
    if not SERVER_LOG.exists():
        return ""
    content = SERVER_LOG.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()
    return "\n".join(content[-lines:])


def wait_until_ready(
    proc: subprocess.Popen,
    base_url: str,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                "A2A Safety Agent가 준비되기 전에 종료되었습니다.\n"
                + server_log_tail()
            )
        try:
            health = httpx.get(
                f"{base_url}/health",
                timeout=0.5,
            )
            card = httpx.get(
                f"{base_url}/.well-known/agent-card.json",
                timeout=0.5,
            )
            if health.status_code == 200 and card.status_code == 200:
                return {
                    "health": health.json(),
                    "agent_card": card.json(),
                }
        except Exception as exc:
            last_error = repr(exc)

        time.sleep(0.1)

    raise RuntimeError(
        "A2A Safety Agent readiness timeout. "
        f"last_error={last_error}\n"
        + server_log_tail()
    )


def stop_server(proc: subprocess.Popen, log_handle: Any) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    try:
        log_handle.flush()
    finally:
        log_handle.close()


def wait_until_down(
    base_url: str,
    timeout_seconds: float = 5.0,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            httpx.get(
                f"{base_url}/health",
                timeout=0.25,
            )
        except Exception:
            return True
        time.sleep(0.1)
    return False


async def assess(client: WaterBridgeA2ASafetyClient):
    return await client.assess(request())


def case_remote_success(base_url: str, readiness: dict[str, Any]) -> dict[str, Any]:
    adapter, counter = local_adapter_with_counter()

    transport = SdkA2ASafetyTransport(
        agent_url=base_url,
        timeout_seconds=3.0,
    )
    client = WaterBridgeA2ASafetyClient(
        remote_transport=transport,
        local_adapter=adapter,
        timeout_seconds=3.0,
    )

    started = time.perf_counter()
    result = asyncio.run(assess(client))
    elapsed_ms = round(
        (time.perf_counter() - started) * 1000,
        3,
    )

    # 같은 입력을 Local RiskClassifier에 직접 넣어 A2A 경계가
    # Safety 의미를 바꾸지 않았는지 비교한다.
    direct_local = RiskClassifier().classify(
        raw_text=RAW_TEXT,
        selected_symptoms=SELECTED_SYMPTOMS,
    )

    card = readiness["agent_card"]

    checks = {
        "health_ok": (
            readiness["health"].get("status") == "ok"
        ),
        "agent_card_reachable": bool(card),
        "agent_card_exposes_jsonrpc": recursive_contains(
            card,
            "JSONRPC",
        ),
        "agent_card_exposes_a2a_endpoint": recursive_contains(
            card,
            "/a2a",
        ),
        "remote_result_used": (
            result.used_local_fallback is False
        ),
        "failure_kind_none": result.failure_kind is None,
        "local_fallback_not_called": counter.calls == 0,
        "inquiry_identity_preserved": (
            result.response.inquiry_id == INQUIRY_ID
        ),
        "correlation_identity_preserved": (
            result.response.correlation_id == CORRELATION_ID
        ),
        "model_identity_preserved": (
            result.response.model_code == MODEL_CODE
        ),
        "product_family_preserved": (
            result.response.product_family
            == PRODUCT_FAMILY
        ),
        "remote_local_safety_semantics_equal": (
            dump(result.response.assessment)
            == dump(direct_local)
        ),
    }

    return {
        "case_id": "REMOTE_SUCCESS",
        "mode": "REAL_A2A_SERVER_PROCESS",
        "remote_server": base_url,
        "elapsed_ms": elapsed_ms,
        "used_local_fallback": result.used_local_fallback,
        "failure_kind": (
            result.failure_kind.value
            if result.failure_kind
            else None
        ),
        "local_classifier_calls": counter.calls,
        "response": dump(result.response),
        "direct_local_assessment": dump(direct_local),
        "checks": checks,
        "pass": all(checks.values()),
    }


def case_agent_down(base_url: str, server_is_down: bool) -> dict[str, Any]:
    adapter, counter = local_adapter_with_counter()

    transport = SdkA2ASafetyTransport(
        agent_url=base_url,
        timeout_seconds=1.0,
    )
    client = WaterBridgeA2ASafetyClient(
        remote_transport=transport,
        local_adapter=adapter,
        timeout_seconds=1.0,
    )

    started = time.perf_counter()
    raised = None
    result = None
    try:
        result = asyncio.run(assess(client))
    except Exception as exc:
        raised = f"{type(exc).__name__}: {exc}"

    elapsed_ms = round(
        (time.perf_counter() - started) * 1000,
        3,
    )

    checks = {
        "server_confirmed_down": server_is_down,
        "main_runtime_exception_not_propagated": raised is None,
        "result_available": result is not None,
        "local_fallback_used": bool(
            result and result.used_local_fallback
        ),
        # 실제 프로세스 종료 시 SDK의 Agent Card/연결 시도가
        # outer timeout budget을 소진하면 TIMEOUT으로 관측될 수 있고,
        # 즉시 connection error가 전파되면 UNAVAILABLE로 분류될 수 있다.
        # 둘 다 "Remote Agent 장애가 Local fallback으로 격리됨"이라는
        # E08-B의 성공 조건을 만족한다.
        "failure_kind_is_remote_failure": bool(
            result
            and result.failure_kind in {
                A2ASafetyFailureKind.UNAVAILABLE,
                A2ASafetyFailureKind.TIMEOUT,
            }
        ),
        "local_classifier_called_once": counter.calls == 1,
        "original_model_preserved": bool(
            result
            and result.response.model_code == MODEL_CODE
        ),
        "safety_result_available": bool(
            result and result.response.assessment is not None
        ),
    }

    return {
        "case_id": "AGENT_DOWN",
        "mode": "REAL_A2A_SERVER_PROCESS_TERMINATED",
        "remote_server": base_url,
        "elapsed_ms": elapsed_ms,
        "exception_propagated": raised,
        "used_local_fallback": (
            result.used_local_fallback
            if result
            else None
        ),
        "failure_kind": (
            result.failure_kind.value
            if result and result.failure_kind
            else None
        ),
        "failure_taxonomy_note": (
            "실제 Agent 프로세스 종료는 A2A SDK/Agent Card discovery의 "
            "동작과 timeout budget에 따라 TIMEOUT 또는 UNAVAILABLE로 "
            "관측될 수 있다. E08-B는 둘 중 하나를 Remote 장애로 인정한다."
        ),
        "local_classifier_calls": counter.calls,
        "response": (
            dump(result.response)
            if result
            else None
        ),
        "checks": checks,
        "pass": all(checks.values()),
    }


class WrongIdentityRemote:
    """통신은 성공했지만 다른 제품 Context를 반환하는 Fault Injection."""

    async def execute(
        self,
        req: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        # 실제 Local Adapter로 assessment를 생성하되,
        # model_code만 다른 제품으로 오염시킨다.
        actual = SafetyA2AAdapter().execute(req)
        return SafetyA2AResponse(
            inquiry_id=actual.inquiry_id,
            correlation_id=actual.correlation_id,
            model_code="WPUIAC606SNW",
            product_family=actual.product_family,
            assessment=actual.assessment,
        )


def case_invalid_identity() -> dict[str, Any]:
    adapter, counter = local_adapter_with_counter()

    client = WaterBridgeA2ASafetyClient(
        remote_transport=WrongIdentityRemote(),
        local_adapter=adapter,
        timeout_seconds=1.0,
    )

    result = asyncio.run(assess(client))

    checks = {
        "remote_response_rejected": (
            result.used_local_fallback is True
        ),
        "failure_kind_invalid_response": (
            result.failure_kind
            == A2ASafetyFailureKind.INVALID_RESPONSE
        ),
        "local_classifier_called_once": counter.calls == 1,
        "wrong_remote_model_not_released": (
            result.response.model_code == MODEL_CODE
        ),
        "inquiry_identity_preserved": (
            result.response.inquiry_id == INQUIRY_ID
        ),
        "safety_result_available": (
            result.response.assessment is not None
        ),
    }

    return {
        "case_id": "INVALID_IDENTITY",
        "mode": "CONTROLLED_FAULT_INJECTION",
        "injected_remote_model": "WPUIAC606SNW",
        "expected_model": MODEL_CODE,
        "used_local_fallback": result.used_local_fallback,
        "failure_kind": result.failure_kind.value,
        "local_classifier_calls": counter.calls,
        "final_response": dump(result.response),
        "checks": checks,
        "pass": all(checks.values()),
    }


class SlowRemote:
    """A2A Remote가 Client timeout보다 늦게 응답하는 Fault Injection."""

    async def execute(
        self,
        req: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        await asyncio.sleep(0.25)
        return SafetyA2AAdapter().execute(req)


def case_timeout() -> dict[str, Any]:
    adapter, counter = local_adapter_with_counter()

    client = WaterBridgeA2ASafetyClient(
        remote_transport=SlowRemote(),
        local_adapter=adapter,
        timeout_seconds=0.03,
    )

    started = time.perf_counter()
    result = asyncio.run(assess(client))
    elapsed_ms = round(
        (time.perf_counter() - started) * 1000,
        3,
    )

    checks = {
        "local_fallback_used": (
            result.used_local_fallback is True
        ),
        "failure_kind_timeout": (
            result.failure_kind
            == A2ASafetyFailureKind.TIMEOUT
        ),
        "local_classifier_called_once": counter.calls == 1,
        "original_model_preserved": (
            result.response.model_code == MODEL_CODE
        ),
        "safety_result_available": (
            result.response.assessment is not None
        ),
    }

    return {
        "case_id": "TIMEOUT",
        "mode": "CONTROLLED_FAULT_INJECTION",
        "configured_timeout_seconds": 0.03,
        "injected_remote_delay_seconds": 0.25,
        "elapsed_ms": elapsed_ms,
        "used_local_fallback": result.used_local_fallback,
        "failure_kind": result.failure_kind.value,
        "local_classifier_calls": counter.calls,
        "final_response": dump(result.response),
        "checks": checks,
        "pass": all(checks.values()),
    }


def print_case(case: dict[str, Any]) -> None:
    print("\n" + "=" * 88)
    print(f"[{case['case_id']}] PASS={case['pass']}")
    print(json.dumps(
        case,
        ensure_ascii=False,
        indent=2,
    ))


def main() -> None:
    experiment_started = time.perf_counter()
    sha = git_sha()
    OUT.mkdir(parents=True, exist_ok=True)

    port = reserve_free_port()
    base_url = f"http://127.0.0.1:{port}"

    server_proc = None
    log_handle = None
    cases: list[dict[str, Any]] = []

    try:
        print("\n[E08] 실제 Safety A2A Agent 프로세스를 기동합니다.")
        print(f"Agent Base URL: {base_url}")

        server_proc, log_handle = start_a2a_server(port)
        readiness = wait_until_ready(
            server_proc,
            base_url,
        )

        print("[E08-A] Agent Card + JSON-RPC 실제 통신을 확인합니다...")
        cases.append(
            case_remote_success(
                base_url,
                readiness,
            )
        )

        print("[E08-B] Safety A2A Agent 프로세스를 실제 종료합니다...")
        stop_server(
            server_proc,
            log_handle,
        )
        server_proc = None
        log_handle = None

        server_is_down = wait_until_down(base_url)

        print("[E08-B] 종료된 Agent에 다시 요청해 장애 격리를 확인합니다...")
        cases.append(
            case_agent_down(
                base_url,
                server_is_down,
            )
        )

        print("[E08-C] 잘못된 Product Identity 응답을 주입합니다...")
        cases.append(case_invalid_identity())

        print("[E08-D] Timeout Fault를 주입합니다...")
        cases.append(case_timeout())

    finally:
        if server_proc is not None and log_handle is not None:
            stop_server(
                server_proc,
                log_handle,
            )

    passed = sum(1 for case in cases if case["pass"])
    total = len(cases)

    summary = {
        "status": (
            "E08_COMPLETE"
            if passed == 4 and total == 4
            else "E08_FAILED"
        ),
        "experiment_id": "E08",
        "title": "A2A Agent Failure Isolation",
        "result_label": "INTEGRATION_PRESENTATION_EVIDENCE",
        "git_sha": sha,
        "executed_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "a2a_agent_process": "REAL_SEPARATE_UVICORN_PROCESS",
        "a2a_protocol_path": (
            "Agent Card discovery + A2A SDK JSON-RPC"
        ),
        "real_process_cases": [
            "REMOTE_SUCCESS",
            "AGENT_DOWN",
        ],
        "controlled_fault_cases": [
            "INVALID_IDENTITY",
            "TIMEOUT",
        ],
        "cases_passed": passed,
        "cases_total": total,
        "all_cases_passed": passed == 4 and total == 4,
        "cases": cases,
        "experiment_total_seconds": round(
            time.perf_counter() - experiment_started,
            3,
        ),
        "claim": (
            "Safety 역할을 별도 A2A Agent로 분리한 상태에서 정상 통신을 "
            "확인했고, Agent 종료·Timeout·잘못된 Product Context가 "
            "발생해도 장애를 Local Safety fallback으로 격리했다."
        ),
        "claim_boundary": (
            "A2A 자체가 자동으로 장애 복원력을 제공한다는 의미가 아니다. "
            "A2A는 Agent 분리/통신 계약이며, 장애 격리는 "
            "WaterBridgeA2ASafetyClient의 검증 및 Local fallback 정책으로 구현했다."
        ),
    }

    (OUT / "summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    by_id = {
        case["case_id"]: case
        for case in cases
    }

    report = [
        "# E08 — A2A Agent Failure Isolation",
        "",
        f"- Git SHA: `{sha}`",
        f"- 결과: **{passed}/{total} PASS**",
        "- E08-A/B: 실제 별도 Safety A2A Server Process 사용",
        "- E08-C/D: 통제된 Fault Injection",
        "",
        "## 실험 질문",
        "",
        "> Safety 역할을 별도 A2A Agent로 분리해도 정상 동작하며, "
        "해당 Agent에 장애 또는 잘못된 응답이 발생했을 때 "
        "Main Runtime의 Safety 판단까지 함께 실패하지 않는가?",
        "",
        "## 실험 구조",
        "",
        "```text",
        "Main Runtime",
        "  ↓",
        "WaterBridgeA2ASafetyClient",
        "  ↓",
        "Agent Card Discovery",
        "  ↓",
        "A2A SDK / JSON-RPC",
        "  ↓",
        "Separate Safety Agent Process",
        "  ↓",
        "SafetyA2AAdapter",
        "  ↓",
        "RiskClassifier",
        "",
        "Remote Failure / Invalid Contract",
        "  ↓",
        "Local Safety Fallback",
        "```",
        "",
        "## 결과 요약",
        "",
        "| Case | 방식 | Remote 상태 | 최종 처리 | 결과 |",
        "|---|---|---|---|---:|",
        f"| REMOTE_SUCCESS | 실제 프로세스 | 정상 | Remote Safety 사용 | {'PASS' if by_id.get('REMOTE_SUCCESS', {}).get('pass') else 'FAIL'} |",
        f"| AGENT_DOWN | 실제 프로세스 종료 | TIMEOUT 또는 UNAVAILABLE | Local Safety fallback | {'PASS' if by_id.get('AGENT_DOWN', {}).get('pass') else 'FAIL'} |",
        f"| INVALID_IDENTITY | Fault Injection | INVALID_RESPONSE | Remote 폐기 + Local fallback | {'PASS' if by_id.get('INVALID_IDENTITY', {}).get('pass') else 'FAIL'} |",
        f"| TIMEOUT | Fault Injection | TIMEOUT | Local Safety fallback | {'PASS' if by_id.get('TIMEOUT', {}).get('pass') else 'FAIL'} |",
        "",
        "## 핵심 해석",
        "",
        summary["claim"],
        "",
        "특히 `AGENT_DOWN`은 Safety Agent를 실제 별도 프로세스로 실행한 뒤 "
        "프로세스를 종료하고 동일 Client 경계를 다시 호출하여 확인한다.",
        "",
        "## 주장 범위",
        "",
        summary["claim_boundary"],
        "",
        "따라서 발표에서는 **'A2A 덕분에 장애 복원이 자동으로 됐다'**가 아니라 "
        "**'A2A로 역할을 독립 Agent로 분리했고, 그 경계의 장애 전파 위험을 "
        "Local fallback으로 격리했다'**고 설명한다.",
        "",
        "## 발표용 문장",
        "",
        "> Safety Agent를 A2A Protocol 기반 독립 Agent로 분리했습니다. "
        "실제 Agent Card Discovery와 JSON-RPC 통신을 확인했으며, "
        "Agent 프로세스를 종료하거나 별도 Timeout·잘못된 Product Context를 "
        "발생시켜도 Remote 장애가 Main Runtime으로 전파되지 않고 "
        "기존 Local Safety로 전환되는 것을 확인했습니다.",
        "",
    ]

    for case in cases:
        report += [
            f"## {case['case_id']}",
            "",
            "```json",
            json.dumps(
                case,
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
        ]

    (OUT / "report.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    for case in cases:
        print_case(case)

    print("\n" + "=" * 88)
    print("[E08] FINAL")
    print(json.dumps(
        {
            "status": summary["status"],
            "git_sha": sha,
            "cases_passed": f"{passed}/{total}",
            "real_process_cases": summary[
                "real_process_cases"
            ],
            "controlled_fault_cases": summary[
                "controlled_fault_cases"
            ],
            "output_dir": (
                "ai/experiment_results/"
                "e08"
            ),
            "server_log": (
                "ai/experiment_results/"
                "e08/"
                "a2a_server.log"
            ),
            "experiment_total_seconds": summary[
                "experiment_total_seconds"
            ],
        },
        ensure_ascii=False,
        indent=2,
    ))

    if summary["status"] != "E08_COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
