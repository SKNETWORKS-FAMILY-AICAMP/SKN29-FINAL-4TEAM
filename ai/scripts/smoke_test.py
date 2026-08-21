"""실행 중인 AI 서비스의 Health와 Analyze 계약을 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker, RefResolver


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88f001"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88f002"
AI_REQUEST_ID = "ai-smoke-20260810-001"


class SmokeFailure(RuntimeError):
    """Smoke 검증 실패."""


def _validate_analysis_contract(body: dict[str, Any]) -> None:
    """공개 SymptomAnalysisResponse 4.0.0 전체 Schema를 검증한다."""

    contract_root = Path(__file__).resolve().parents[2] / "contracts" / "ai"
    schema_path = contract_root / "responses" / "SymptomAnalysisResponse.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        resolver = RefResolver(
            base_uri=schema_path.resolve().as_uri(),
            referrer=schema,
        )
        errors = sorted(
            Draft202012Validator(
                schema,
                resolver=resolver,
                format_checker=FormatChecker(),
            ).iter_errors(body),
            key=lambda error: list(error.absolute_path),
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise SmokeFailure("AI 공개 계약 Schema를 읽을 수 없습니다.") from exc
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.absolute_path) or "$"
        raise SmokeFailure(
            f"Analyze 계약 4.0.0 검증 실패: path={location}, message={first.message}"
        )


def _json_request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], dict[str, str]]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["X-Correlation-ID"] = CORRELATION_ID
    request = Request(url, data=data, headers=headers, method=method)
    try:
        response = urlopen(request, timeout=35)
        status = response.status
        body = json.loads(response.read().decode("utf-8"))
        response_headers = dict(response.headers.items())
    except HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode("utf-8"))
        response_headers = dict(exc.headers.items())
    except (URLError, TimeoutError) as exc:
        raise SmokeFailure(f"AI 서비스에 연결할 수 없습니다: {exc.reason if isinstance(exc, URLError) else exc}") from exc
    return status, body, response_headers


def run_smoke(
    base_url: str,
    mode: str,
    expected_analysis_status: int,
    *,
    expected_result_status: str | None = None,
    expected_failure_stage: str | None = None,
    expected_evidence_id: str | None = None,
    minimum_evidence_count: int | None = None,
    require_verified_evidence: bool = False,
    expected_guidance_message: str | None = None,
) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    health_status, health_body, _ = _json_request(f"{base_url}/health")
    if health_status != 200 or health_body.get("status") != "ok":
        raise SmokeFailure(f"Health 검증 실패: HTTP {health_status}")

    payload = {
        "inquiry_id": INQUIRY_ID,
        "correlation_id": CORRELATION_ID,
        "ai_request_id": AI_REQUEST_ID,
        "state_version": 1,
        "raw_symptom": "냉수 출수량이 줄었습니다.",
        "model_code": "WPUJAC104DWH",
        "selected_symptoms": ["출수량 저하"],
        "previous_answers": [],
    }
    analysis_status, analysis_body, analysis_headers = _json_request(
        f"{base_url}/api/v1/ai/analyze?mode={mode}",
        method="POST",
        payload=payload,
    )
    if analysis_status != expected_analysis_status:
        raise SmokeFailure(
            f"Analyze HTTP 상태 불일치: expected={expected_analysis_status}, actual={analysis_status}"
        )
    if analysis_status == 200:
        _validate_analysis_contract(analysis_body)
    if analysis_body.get("inquiry_id") != INQUIRY_ID:
        raise SmokeFailure("Analyze Body inquiry_id Echo가 일치하지 않습니다.")
    if analysis_body.get("correlation_id") != CORRELATION_ID:
        raise SmokeFailure("Analyze Body correlation_id Echo가 일치하지 않습니다.")
    response_correlation = next(
        (value for key, value in analysis_headers.items() if key.lower() == "x-correlation-id"),
        None,
    )
    if response_correlation != CORRELATION_ID:
        raise SmokeFailure("Analyze Header correlation_id Echo가 일치하지 않습니다.")
    if analysis_body.get("ai_request_id") != AI_REQUEST_ID or analysis_body.get("state_version") != 1:
        raise SmokeFailure("Analyze 추적·멱등 필드 Echo가 일치하지 않습니다.")

    result_status = analysis_body.get("status")
    if expected_result_status is not None and result_status != expected_result_status:
        raise SmokeFailure(
            "Analyze 실행 상태 불일치: "
            f"expected={expected_result_status}, actual={result_status}"
        )

    usage_guidance = analysis_body.get("usage_guidance")
    actual_guidance_message = (
        usage_guidance.get("message") if isinstance(usage_guidance, dict) else None
    )
    if (
        expected_guidance_message is not None
        and actual_guidance_message != expected_guidance_message
    ):
        raise SmokeFailure(
            "Analyze LLM Guidance 문구 불일치: "
            f"expected={expected_guidance_message!r}, actual={actual_guidance_message!r}"
        )

    if expected_failure_stage is not None:
        normalized_expected_stage = (
            None if expected_failure_stage.upper() == "NONE" else expected_failure_stage
        )
        actual_failure_stage = analysis_body.get("failure_stage")
        if actual_failure_stage != normalized_expected_stage:
            raise SmokeFailure(
                "Analyze 실패 단계 불일치: "
                f"expected={normalized_expected_stage}, actual={actual_failure_stage}"
            )

    evidence_references = analysis_body.get("evidence_references")
    evidence_checks_requested = any(
        (
            expected_evidence_id is not None,
            minimum_evidence_count is not None,
            require_verified_evidence,
        )
    )
    if evidence_checks_requested and not isinstance(evidence_references, list):
        raise SmokeFailure("Analyze Evidence 목록이 없습니다.")
    evidence_references = (
        evidence_references if isinstance(evidence_references, list) else []
    )

    if minimum_evidence_count is not None:
        if minimum_evidence_count < 0:
            raise SmokeFailure("최소 Evidence 개수는 0 이상이어야 합니다.")
        if len(evidence_references) < minimum_evidence_count:
            raise SmokeFailure(
                "Analyze Evidence 개수 부족: "
                f"expected>={minimum_evidence_count}, actual={len(evidence_references)}"
            )
    if expected_evidence_id is not None and not any(
        isinstance(reference, dict)
        and reference.get("chunk_id") == expected_evidence_id
        for reference in evidence_references
    ):
        raise SmokeFailure(
            f"예상 Evidence chunk_id를 찾지 못했습니다: {expected_evidence_id}"
        )
    if require_verified_evidence:
        if not evidence_references:
            raise SmokeFailure("검증할 Evidence가 없습니다.")
        for reference in evidence_references:
            if not isinstance(reference, dict):
                raise SmokeFailure("Evidence 항목이 객체가 아닙니다.")
            if reference.get("verification_status") != "official_verified":
                raise SmokeFailure("Evidence 검증 상태가 승인 범위가 아닙니다.")
            official_url = reference.get("official_url")
            try:
                parsed_official_url = (
                    urlsplit(official_url) if isinstance(official_url, str) else None
                )
            except ValueError:
                parsed_official_url = None
            if (
                parsed_official_url is None
                or parsed_official_url.scheme != "https"
                or not parsed_official_url.hostname
                or parsed_official_url.username is not None
                or parsed_official_url.password is not None
            ):
                raise SmokeFailure("Evidence 공식 URL이 HTTPS가 아닙니다.")
            page = reference.get("page")
            page_refs = reference.get("page_refs")
            positive_page = isinstance(page, int) and not isinstance(page, bool) and page >= 1
            positive_page_refs = (
                isinstance(page_refs, list)
                and bool(page_refs)
                and all(
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and value >= 1
                    for value in page_refs
                )
            )
            if not positive_page and not positive_page_refs:
                raise SmokeFailure("Evidence 페이지 식별자가 유효하지 않습니다.")

    return {
        "health": "PASS",
        "analysis": "PASS",
        "mode": mode,
        "analysis_http_status": analysis_status,
        "analysis_result_status": result_status,
        "analysis_failure_stage": analysis_body.get("failure_stage"),
        "evidence_count": len(evidence_references),
        "guidance_message_match": (
            "PASS" if expected_guidance_message is not None else "NOT_CHECKED"
        ),
        "correlation_trace": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--mode", choices=("mock", "local"), default="mock")
    parser.add_argument("--expected-analysis-status", type=int, default=200)
    parser.add_argument(
        "--expected-result-status",
        choices=("SUCCEEDED", "FALLBACK"),
    )
    parser.add_argument(
        "--expected-failure-stage",
        help="기대 failure_stage. null을 기대하면 NONE을 사용합니다.",
    )
    parser.add_argument("--expected-evidence-id")
    parser.add_argument("--minimum-evidence-count", type=int)
    parser.add_argument("--require-verified-evidence", action="store_true")
    parser.add_argument(
        "--expected-guidance-message",
        help="이번 고정 입력에서 실제 LLM이 반환해야 하는 승인 Evidence 원문 문장.",
    )
    args = parser.parse_args()
    try:
        result = run_smoke(
            args.base_url,
            args.mode,
            args.expected_analysis_status,
            expected_result_status=args.expected_result_status,
            expected_failure_stage=args.expected_failure_stage,
            expected_evidence_id=args.expected_evidence_id,
            minimum_evidence_count=args.minimum_evidence_count,
            require_verified_evidence=args.require_verified_evidence,
            expected_guidance_message=args.expected_guidance_message,
        )
    except SmokeFailure as exc:
        print(json.dumps({"result": "FAIL", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"result": "PASS", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
