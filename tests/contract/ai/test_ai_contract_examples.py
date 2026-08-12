"""Backend와 AI 사이의 공개 예시를 저장소 루트에서 독립 검증한다."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = REPO_ROOT / "contracts" / "ai"

SUCCESS_EXAMPLES = [
    (
        "examples/symptom-analysis/general-guidance.json",
        "requests/SymptomAnalysisRequest.schema.json",
        "responses/SymptomAnalysisResponse.schema.json",
    ),
    (
        "examples/symptom-analysis/danger-detected.json",
        "requests/SymptomAnalysisRequest.schema.json",
        "responses/SymptomAnalysisResponse.schema.json",
    ),
    (
        "examples/symptom-analysis/no-evidence.json",
        "requests/SymptomAnalysisRequest.schema.json",
        "responses/SymptomAnalysisResponse.schema.json",
    ),
    (
        "examples/consultation-summary/summary-example.json",
        "requests/ConsultationSummaryRequest.schema.json",
        "responses/ConsultationSummaryResponse.schema.json",
    ),
    (
        "examples/technician-report/report-example.json",
        "requests/TechnicianReportRequest.schema.json",
        "responses/TechnicianReportResponse.schema.json",
    ),
]

ERROR_EXAMPLES = [
    "examples/symptom-analysis/validation-failed.json",
    "examples/fallback/vector-not-configured-error.json",
    "examples/fallback/retrieval-failed-error.json",
    "examples/fallback/timeout-error.json",
]

TRACE_FIELDS = ("inquiry_id", "correlation_id", "ai_request_id", "state_version")
PRIVATE_ERROR_KEYS = {
    "dsn",
    "evidence_text",
    "prompt",
    "raw_symptom",
    "stack_trace",
    "token",
    "traceback",
    "vector_content",
}


def _load(relative_path: str) -> dict[str, Any]:
    return json.loads((CONTRACT_ROOT / relative_path).read_text(encoding="utf-8"))


def _schema_document(schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$id"] = schema_path.resolve().as_uri()
    return schema


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    registry = Registry()
    for schema_path in sorted(CONTRACT_ROOT.rglob("*.schema.json")):
        schema = _schema_document(schema_path)
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def _validator(relative_path: str) -> Draft202012Validator:
    schema_path = CONTRACT_ROOT / relative_path
    schema = _schema_document(schema_path)
    return Draft202012Validator(
        schema,
        registry=_schema_registry(),
        format_checker=FormatChecker(),
    )


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _keys(item)}
    return set()


@pytest.mark.parametrize(("example_path", "request_schema", "response_schema"), SUCCESS_EXAMPLES)
def test_success_examples_match_request_and_response_schemas(
    example_path: str,
    request_schema: str,
    response_schema: str,
) -> None:
    document = _load(example_path)

    _validator(request_schema).validate(document["request"])
    _validator(response_schema).validate(document["response"])


@pytest.mark.parametrize("example_path", ERROR_EXAMPLES)
def test_error_examples_match_public_error_schema(example_path: str) -> None:
    document = _load(example_path)

    _validator("common/AIErrorResponse.schema.json").validate(document["error_response"])
    if example_path.endswith("validation-failed.json"):
        with pytest.raises(ValidationError):
            _validator("requests/SymptomAnalysisRequest.schema.json").validate(document["request"])
    else:
        _validator("requests/SymptomAnalysisRequest.schema.json").validate(document["request"])


@pytest.mark.parametrize(
    "example_path",
    [path for path, _, _ in SUCCESS_EXAMPLES] + ERROR_EXAMPLES,
)
def test_examples_echo_trace_and_state_fields(example_path: str) -> None:
    document = _load(example_path)
    result = document.get("response", document.get("error_response"))

    assert result is not None
    for field in TRACE_FIELDS:
        assert result[field] == document["request"][field]


@pytest.mark.parametrize("example_path", ERROR_EXAMPLES)
def test_error_examples_do_not_expose_private_request_or_runtime_fields(example_path: str) -> None:
    document = _load(example_path)
    response = document["error_response"]
    serialized_response = json.dumps(response, ensure_ascii=False)
    raw_symptom = document["request"].get("raw_symptom")

    assert _keys(response).isdisjoint(PRIVATE_ERROR_KEYS)
    if raw_symptom:
        assert raw_symptom not in serialized_response


def test_standalone_fallback_matches_response_contract_and_stays_ungrounded() -> None:
    response = _load("examples/fallback/fallback-response.json")

    _validator("responses/SymptomAnalysisResponse.schema.json").validate(response)
    assert response["status"] == "FALLBACK"
    assert response["usage_guidance"]["guidance_status"] == "PENDING_CONSULTATION"
    assert response["evidence_references"] == []
