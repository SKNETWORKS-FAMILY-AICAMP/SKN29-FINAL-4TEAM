"""E09 - MCP Tool Contract & Failure Handling experiment.

Goal
----
Verify that WaterBridge MCP:
1) preserves business results across the real stdio MCP boundary,
2) rejects invalid Tool input,
3) normalizes timeout / unavailable failures,
4) fails closed on identity or response mismatch,
5) does not expose injected raw sensitive error details.

Run from repository root:

    python ai/scripts/experiments/e09_mcp_contract_failure.py

Optional:

    python ai/scripts/experiments/e09_mcp_contract_failure.py --output ai/results/e09_mcp_contract_failure.json

The experiment intentionally uses a policy-blocked model for the real
search_official_evidence stdio call, so E09-01/E09-02 do not require pgvector.
Fault scenarios E09-03~05 use injected MCP clients and do not require Backend.
"""

from __future__ import annotations

from pathlib import Path
import sys

# Allow direct execution from repository root:
#   python ai/scripts/experiments/e09_mcp_contract_failure.py
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import asyncio
import json
import platform
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from uuid import UUID

from ai.app.integrations.backend import BackendContextFailureKind
from ai.app.integrations.mcp.client import WaterBridgeMCPClient
from ai.app.integrations.mcp.context_service import (
    McpBackendContextError,
    McpBackendContextService,
)
from ai.app.integrations.mcp.server import search_official_evidence


EXPERIMENT_ID = "E09"
EXPERIMENT_NAME = "MCP Tool Contract & Failure Handling"

POLICY_BLOCK_MODEL = "WPUIAC425SNW"
POLICY_BLOCK_QUERY = "얼음이 나오지 않아요"

EXPECTED_MODEL_CODE = "WPUJAC104DWH"
WRONG_MODEL_CODE = "WPUIAC606SNW"

INQUIRY_ID = UUID("11111111-1111-4111-8111-111111111111")
CORRELATION_ID = UUID("22222222-2222-4222-8222-222222222222")
SUBSCRIPTION_ID = UUID("33333333-3333-4333-8333-333333333333")
PRODUCT_MODEL_ID = UUID("44444444-4444-4444-8444-444444444444")
STATE_VERSION = 7

SECRET_MARKER = "E09_SECRET_MARKER_DO_NOT_EXPOSE"


@dataclass(slots=True)
class ScenarioResult:
    scenario_id: str
    scenario: str
    expected: str
    actual: str
    latency_ms: float
    retryable: bool | None
    contract_valid: bool
    invalid_data_released: bool
    sensitive_detail_leaked: bool
    passed: bool
    notes: str = ""


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _structured_content(result: Any) -> Any:
    payload = getattr(result, "structured_content", None)
    if payload is None:
        payload = getattr(result, "structuredContent", None)
    return payload


def _is_error(result: Any) -> bool:
    return bool(
        getattr(result, "isError", False)
        or getattr(result, "is_error", False)
    )


def _fake_mcp_result(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        isError=False,
        is_error=False,
        structured_content=payload,
        structuredContent=payload,
        content=[],
    )


def _product_context_payload(model_code: str) -> dict[str, Any]:
    return {
        "subscription_id": str(SUBSCRIPTION_ID),
        "subscription_status_code": "ACTIVE",
        "management_type_code": "CARE",
        "product_model_id": str(PRODUCT_MODEL_ID),
        "model_code": model_code,
        "model_name": "WaterBridge E09 Fixture",
        "product_family": "DIRECT_WATER_PURIFIER",
        "generation_code": "E09",
        "manufacturer": "SK magic",
        "features": {
            "model_family": "E09_FIXTURE",
            "water_modes": ["cold_water", "hot_water"],
            "supported_functions": ["cold_water", "hot_water"],
        },
    }


def _lookup_product_payload(*, model_code: str = EXPECTED_MODEL_CODE) -> dict[str, Any]:
    return {
        "success": True,
        "inquiry_id": str(INQUIRY_ID),
        "correlation_id": str(CORRELATION_ID),
        "product_context": _product_context_payload(model_code),
        "failure_kind": None,
        "retryable": False,
    }


def _inquiry_context_payload() -> dict[str, Any]:
    return {
        "success": True,
        "inquiry_id": str(INQUIRY_ID),
        "correlation_id": str(CORRELATION_ID),
        "inquiry_code": "INQ-E09-001",
        "status_code": "AI_PROCESSING",
        "state_version": STATE_VERSION,
        "inquiry_context": {
            "customer_query": "냉수가 나오지 않아요.",
            "symptom_type": "NO_COLD_WATER",
            "selected_symptoms": ["NO_COLD_WATER"],
            "previous_answers": [],
        },
        "failure_kind": None,
        "retryable": False,
    }


async def _real_mcp_call(tool_name: str, arguments: dict[str, Any]) -> Any:
    async with WaterBridgeMCPClient() as client:
        return await client.call_tool(tool_name, arguments)


def scenario_01_normal_stdio_call() -> ScenarioResult:
    """Real Python -> MCP client -> stdio -> separate MCP server process."""
    started = time.perf_counter()

    direct = search_official_evidence(
        customer_query=POLICY_BLOCK_QUERY,
        model_code=POLICY_BLOCK_MODEL,
        symptom_type=None,
        previous_answers=[],
    ).model_dump(mode="json")

    result = asyncio.run(
        _real_mcp_call(
            "search_official_evidence",
            {
                "customer_query": POLICY_BLOCK_QUERY,
                "model_code": POLICY_BLOCK_MODEL,
                "symptom_type": None,
                "previous_answers": [],
            },
        )
    )
    payload = _structured_content(result)
    latency_ms = (time.perf_counter() - started) * 1000

    parity = isinstance(payload, dict) and payload == direct
    policy_blocked = (
        isinstance(payload, dict)
        and payload.get("policy_blocked") is True
        and payload.get("policy_execution_path") == "POLICY_BLOCK_UNSUPPORTED_MODEL"
        and payload.get("applied_rule_id") == "GATE-MODEL-001"
        and payload.get("vector_search_executed") is False
        and payload.get("evidence_found") is False
    )
    passed = (not _is_error(result)) and parity and policy_blocked

    return ScenarioResult(
        scenario_id="E09-01",
        scenario="NORMAL_STDIO_CALL",
        expected="Structured output + direct/MCP parity",
        actual="STRUCTURED_PARITY" if passed else "MCP_RESULT_MISMATCH_OR_ERROR",
        latency_ms=latency_ms,
        retryable=None,
        contract_valid=parity,
        invalid_data_released=False,
        sensitive_detail_leaked=False,
        passed=passed,
        notes="Actual MCP stdio subprocess path; policy-blocked before pgvector.",
    )


def scenario_02_invalid_input() -> ScenarioResult:
    """Actual MCP tool schema must reject a missing required argument."""
    started = time.perf_counter()
    exception: BaseException | None = None
    result: Any = None

    try:
        result = asyncio.run(
            _real_mcp_call(
                "search_official_evidence",
                {
                    "customer_query": "냉수가 나오지 않아요.",
                    # model_code intentionally omitted
                    "symptom_type": None,
                    "previous_answers": [],
                },
            )
        )
    except BaseException as exc:
        exception = exc

    latency_ms = (time.perf_counter() - started) * 1000
    rejected = exception is not None or (result is not None and _is_error(result))
    payload = _structured_content(result) if result is not None else None

    invalid_data_released = bool(
        isinstance(payload, dict) and payload.get("evidence_found") is True
    )
    leaked = SECRET_MARKER in (str(exception) if exception is not None else "")
    passed = rejected and not invalid_data_released and not leaked

    return ScenarioResult(
        scenario_id="E09-02",
        scenario="INVALID_INPUT",
        expected="MCP input contract rejection",
        actual="INPUT_CONTRACT_REJECTED" if rejected else "INVALID_INPUT_ACCEPTED",
        latency_ms=latency_ms,
        retryable=False,
        contract_valid=rejected,
        invalid_data_released=invalid_data_released,
        sensitive_detail_leaked=leaked,
        passed=passed,
        notes="Required model_code omitted intentionally.",
    )


class _TimeoutClient:
    async def __aenter__(self) -> "_TimeoutClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        await asyncio.sleep(0.25)
        raise TimeoutError(f"{SECRET_MARKER}: raw timeout detail")


class _UnavailableClient:
    async def __aenter__(self) -> "_UnavailableClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        raise ConnectionError(
            f"{SECRET_MARKER}: backend=http://private-internal-host"
        )


class _InvalidResponseClient:
    async def __aenter__(self) -> "_InvalidResponseClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if tool_name == "lookup_product_context":
            return _fake_mcp_result(
                _lookup_product_payload(model_code=WRONG_MODEL_CODE)
            )
        if tool_name == "get_inquiry_context":
            return _fake_mcp_result(_inquiry_context_payload())
        raise AssertionError(f"Unexpected tool: {tool_name}")


def _run_context_failure_scenario(
    *,
    scenario_id: str,
    scenario: str,
    factory: Callable[[], Any],
    timeout_seconds: float,
    expected_kind: BackendContextFailureKind,
    expected_retryable: bool,
    expected: str,
    notes: str,
) -> ScenarioResult:
    started = time.perf_counter()
    error: McpBackendContextError | None = None
    unexpected: BaseException | None = None

    service = McpBackendContextService(
        client_factory=factory,
        timeout_seconds=timeout_seconds,
    )

    try:
        service.resolve(
            inquiry_id=INQUIRY_ID,
            correlation_id=CORRELATION_ID,
            expected_state_version=STATE_VERSION,
            expected_model_code=EXPECTED_MODEL_CODE,
        )
    except McpBackendContextError as exc:
        error = exc
    except BaseException as exc:
        unexpected = exc

    latency_ms = (time.perf_counter() - started) * 1000

    kind_match = error is not None and error.kind == expected_kind
    retry_match = error is not None and error.retryable is expected_retryable

    exposed_text = (
        str(error)
        if error is not None
        else str(unexpected)
        if unexpected is not None
        else ""
    )
    leaked = SECRET_MARKER in exposed_text or "private-internal-host" in exposed_text

    # If resolve() did not raise, invalid/mismatched context escaped the guard.
    invalid_data_released = error is None

    passed = (
        unexpected is None
        and kind_match
        and retry_match
        and not invalid_data_released
        and not leaked
    )

    return ScenarioResult(
        scenario_id=scenario_id,
        scenario=scenario,
        expected=expected,
        actual=error.kind.value if error is not None else "NO_NORMALIZED_ERROR",
        latency_ms=latency_ms,
        retryable=error.retryable if error is not None else None,
        contract_valid=kind_match and retry_match,
        invalid_data_released=invalid_data_released,
        sensitive_detail_leaked=leaked,
        passed=passed,
        notes=notes,
    )


def scenario_03_timeout() -> ScenarioResult:
    return _run_context_failure_scenario(
        scenario_id="E09-03",
        scenario="TIMEOUT",
        factory=_TimeoutClient,
        timeout_seconds=0.10,
        expected_kind=BackendContextFailureKind.TIMEOUT,
        expected_retryable=True,
        expected="TIMEOUT / retryable=true",
        notes="Injected client sleeps 0.25s while MCP context timeout is 0.10s.",
    )


def scenario_04_unavailable() -> ScenarioResult:
    return _run_context_failure_scenario(
        scenario_id="E09-04",
        scenario="UNAVAILABLE",
        factory=_UnavailableClient,
        timeout_seconds=1.0,
        expected_kind=BackendContextFailureKind.UNAVAILABLE,
        expected_retryable=True,
        expected="UNAVAILABLE / retryable=true",
        notes="Injected ConnectionError contains a secret marker and private URL.",
    )


def scenario_05_invalid_response() -> ScenarioResult:
    return _run_context_failure_scenario(
        scenario_id="E09-05",
        scenario="INVALID_RESPONSE",
        factory=_InvalidResponseClient,
        timeout_seconds=1.0,
        expected_kind=BackendContextFailureKind.INVALID_RESPONSE,
        expected_retryable=False,
        expected="INVALID_RESPONSE / retryable=false / fail-closed",
        notes=f"Requested {EXPECTED_MODEL_CODE}, injected {WRONG_MODEL_CODE}.",
    )


def _print_result(result: ScenarioResult) -> None:
    mark = "PASS" if result.passed else "FAIL"
    print(
        f"[{result.scenario_id}] {result.scenario:<20} "
        f"{mark:<4}  "
        f"actual={result.actual:<24} "
        f"latency={result.latency_ms:8.2f} ms"
    )


def _write_json(output_path: Path, results: list[ScenarioResult]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_name": EXPERIMENT_NAME,
        "git_sha": _git_sha(),
        "python": platform.python_version(),
        "scenario_count": len(results),
        "pass_count": sum(item.passed for item in results),
        "all_passed": all(item.passed for item in results),
        "metrics": {
            "contract_match_count": sum(item.contract_valid for item in results),
            "invalid_data_release_count": sum(
                item.invalid_data_released for item in results
            ),
            "sensitive_detail_leak_count": sum(
                item.sensitive_detail_leaked for item in results
            ),
        },
        "results": [asdict(item) for item in results],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"{EXPERIMENT_ID} - {EXPERIMENT_NAME}"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ai/experiment_results/e09_mcp_contract_failure/summary.json"),
        help="JSON result output path (default: ai/experiment_results/e09_mcp_contract_failure/summary.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    scenarios = [
        scenario_01_normal_stdio_call,
        scenario_02_invalid_input,
        scenario_03_timeout,
        scenario_04_unavailable,
        scenario_05_invalid_response,
    ]

    print(f"=== {EXPERIMENT_ID}: {EXPERIMENT_NAME} ===")
    print(f"git_sha={_git_sha() or 'UNKNOWN'}")
    print()

    results: list[ScenarioResult] = []

    for index, scenario in enumerate(scenarios, start=1):
        try:
            result = scenario()
        except BaseException as exc:
            result = ScenarioResult(
                scenario_id=f"E09-{index:02d}",
                scenario=scenario.__name__.removeprefix("scenario_").upper(),
                expected="Scenario-specific contract",
                actual=f"EXPERIMENT_ERROR:{type(exc).__name__}",
                latency_ms=0.0,
                retryable=None,
                contract_valid=False,
                invalid_data_released=False,
                sensitive_detail_leaked=SECRET_MARKER in str(exc),
                passed=False,
                notes="Scenario runner raised unexpectedly; inspect traceback locally.",
            )
        results.append(result)
        _print_result(result)

    _write_json(args.output, results)

    passed = sum(item.passed for item in results)
    total = len(results)

    print()
    print(f"TOTAL: {passed}/{total} PASS")
    print(
        "Invalid Data Release: "
        f"{sum(item.invalid_data_released for item in results)}"
    )
    print(
        "Sensitive Detail Leak: "
        f"{sum(item.sensitive_detail_leaked for item in results)}"
    )
    print(f"Result JSON: {args.output}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
