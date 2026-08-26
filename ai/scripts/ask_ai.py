"""실행 중인 AI 분석 서버에 증상 문장을 보내고 전체 응답을 출력한다."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_MODEL_CODE = "WPUJAC104DWH"


class AiClientError(RuntimeError):
    """AI 서버에 요청을 보내거나 응답을 읽지 못했다."""


def build_payload(
    question: str,
    *,
    model_code: str = DEFAULT_MODEL_CODE,
    selected_symptoms: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    """공개 Analyze 계약에 맞는 요청과 Correlation ID를 만든다."""

    normalized_question = question.strip()
    if not normalized_question:
        raise AiClientError("AI에 보낼 문장을 입력해 주세요.")

    correlation_id = str(uuid4())
    payload = {
        "inquiry_id": str(uuid4()),
        "correlation_id": correlation_id,
        "ai_request_id": f"ai-manual-{uuid4()}",
        "state_version": 1,
        "raw_symptom": normalized_question,
        "model_code": model_code,
        "selected_symptoms": selected_symptoms or [],
        "previous_answers": [],
    }
    return payload, correlation_id


def ask_ai(
    question: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    mode: str = "local",
    model_code: str = DEFAULT_MODEL_CODE,
    selected_symptoms: list[str] | None = None,
    timeout_seconds: float = 35.0,
) -> tuple[int, dict[str, Any]]:
    """AI Analyze API를 호출하고 HTTP 상태와 전체 JSON Body를 반환한다."""

    payload, correlation_id = build_payload(
        question,
        model_code=model_code,
        selected_symptoms=selected_symptoms,
    )
    request = Request(
        f"{base_url.rstrip('/')}/api/v1/ai/analyze?mode={mode}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-Correlation-ID": correlation_id,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = response.status
            raw_body = response.read()
    except HTTPError as exc:
        status = exc.code
        raw_body = exc.read()
    except (URLError, TimeoutError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else str(exc)
        raise AiClientError(f"AI 서버에 연결할 수 없습니다: {reason}") from exc

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AiClientError(
            f"AI 서버가 JSON이 아닌 응답을 반환했습니다. HTTP {status}"
        ) from exc
    if not isinstance(body, dict):
        raise AiClientError(f"AI 응답의 Root가 객체가 아닙니다. HTTP {status}")
    return status, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "question",
        nargs="?",
        help="AI에 보낼 고객 증상 문장. 생략하면 실행 후 직접 입력합니다.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--mode", choices=("mock", "local"), default="local")
    parser.add_argument("--model-code", default=DEFAULT_MODEL_CODE)
    parser.add_argument(
        "--selected-symptom",
        action="append",
        default=[],
        help="선택 증상. 여러 개면 옵션을 반복해서 사용합니다.",
    )
    parser.add_argument("--timeout", type=float, default=35.0)
    args = parser.parse_args()

    question = args.question
    if question is None:
        try:
            question = input("AI에 보낼 증상 문장: ")
        except EOFError:
            question = ""

    try:
        status, body = ask_ai(
            question,
            base_url=args.base_url,
            mode=args.mode,
            model_code=args.model_code,
            selected_symptoms=args.selected_symptom,
            timeout_seconds=args.timeout,
        )
    except AiClientError as exc:
        print(
            json.dumps(
                {"client_error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    print(f"HTTP {status}")
    print(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
