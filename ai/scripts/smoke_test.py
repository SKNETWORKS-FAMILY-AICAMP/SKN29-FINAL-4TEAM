"""실행 중인 AI 서비스의 Health와 Analyze 계약을 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88f001"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88f002"
AI_REQUEST_ID = "ai-smoke-20260810-001"


class SmokeFailure(RuntimeError):
    """Smoke 검증 실패."""


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


def run_smoke(base_url: str, mode: str, expected_analysis_status: int) -> dict[str, Any]:
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

    return {
        "health": "PASS",
        "analysis": "PASS",
        "mode": mode,
        "analysis_http_status": analysis_status,
        "correlation_trace": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--mode", choices=("mock", "local"), default="mock")
    parser.add_argument("--expected-analysis-status", type=int, default=200)
    args = parser.parse_args()
    try:
        result = run_smoke(args.base_url, args.mode, args.expected_analysis_status)
    except SmokeFailure as exc:
        print(json.dumps({"result": "FAIL", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"result": "PASS", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
