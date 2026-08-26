"""AI Contract 4.0의 JSON Schema와 Pydantic 공개 경계를 함께 검증한다."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError
from referencing import Registry, Resource

from ai.app.interfaces.http.request_models import SymptomAnalysisApiRequest
from ai.app.schemas.pipeline import SymptomAnalysisResult


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "ai"
REQUEST_SCHEMA_PATH = "requests/SymptomAnalysisRequest.schema.json"
RESPONSE_SCHEMA_PATH = "responses/SymptomAnalysisResponse.schema.json"
EXAMPLE_PATHS = (
    "examples/symptom-analysis/general-guidance.json",
    "examples/symptom-analysis/caution-pre-send-human-review.json",
    "examples/symptom-analysis/danger-detected.json",
    "examples/symptom-analysis/no-evidence.json",
    "examples/symptom-analysis/runtime-product-not-approved.json",
)
TRACE_FIELDS = ("inquiry_id", "correlation_id", "ai_request_id", "state_version")
PRIVATE_RESPONSE_KEYS = {
    "dsn",
    "embedding",
    "prompt",
    "raw_symptom",
    "stack_trace",
    "token",
    "traceback",
    "vector",
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


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for item in value.values() for key in _nested_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _nested_keys(item)}
    return set()


@pytest.mark.parametrize("example_path", EXAMPLE_PATHS)
def test_examples_match_json_schema_and_pydantic_contract(example_path: str) -> None:
    document = _load(example_path)

    _validator(REQUEST_SCHEMA_PATH).validate(document["request"])
    _validator(RESPONSE_SCHEMA_PATH).validate(document["response"])
    request = SymptomAnalysisApiRequest.model_validate(document["request"])
    response = SymptomAnalysisResult.model_validate(document["response"])

    assert request.model_dump(mode="json", exclude_unset=True) == document["request"]
    assert response.model_dump(mode="json", exclude_unset=True) == document["response"]
    for field in TRACE_FIELDS:
        assert document["response"][field] == document["request"][field]
    assert document["response"]["model_code"] == document["request"]["model_code"]


def test_contract_documents_are_version_4_0_0_and_draft_2020_12() -> None:
    for relative_path in (REQUEST_SCHEMA_PATH, RESPONSE_SCHEMA_PATH):
        schema = _load(relative_path)

        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["x-contract-version"] == "4.0.0"


@pytest.mark.parametrize(
    ("example_path", "fallback_reason_code"),
    (
        ("examples/symptom-analysis/general-guidance.json", "NO_EVIDENCE"),
        ("examples/symptom-analysis/no-evidence.json", None),
    ),
)
def test_status_and_fallback_reason_invariant_is_rejected_by_both_contracts(
    example_path: str,
    fallback_reason_code: str | None,
) -> None:
    payload = _load(example_path)["response"]
    payload["fallback_reason_code"] = fallback_reason_code

    with pytest.raises(JsonSchemaValidationError):
        _validator(RESPONSE_SCHEMA_PATH).validate(payload)
    with pytest.raises(PydanticValidationError):
        SymptomAnalysisResult.model_validate(payload)


@pytest.mark.parametrize(
    ("example_path", "expected"),
    (
        (
            "examples/symptom-analysis/danger-detected.json",
            {
                "status": "SUCCEEDED",
                "risk_level": "danger",
                "guidance_status": "TOTAL_STOP",
                "requires_consultation": True,
                "evidence_count": 0,
                "fallback_reason_code": None,
            },
        ),
        (
            "examples/symptom-analysis/no-evidence.json",
            {
                "status": "FALLBACK",
                "risk_level": "caution",
                "guidance_status": "PENDING_CONSULTATION",
                "requires_consultation": True,
                "evidence_count": 0,
                "fallback_reason_code": "NO_EVIDENCE",
            },
        ),
        (
            "examples/symptom-analysis/runtime-product-not-approved.json",
            {
                "status": "FALLBACK",
                "risk_level": "caution",
                "guidance_status": "PENDING_CONSULTATION",
                "requires_consultation": True,
                "evidence_count": 0,
                "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
            },
        ),
    ),
)
def test_approved_public_safety_and_fallback_behavior(
    example_path: str,
    expected: dict[str, object],
) -> None:
    response = _load(example_path)["response"]

    actual = {
        "status": response["status"],
        "risk_level": response["safety_assessment"]["risk_level"],
        "guidance_status": response["usage_guidance"]["guidance_status"],
        "requires_consultation": response["safety_assessment"][
            "requires_consultation"
        ],
        "evidence_count": len(response["evidence_references"]),
        "fallback_reason_code": response["fallback_reason_code"],
    }

    assert actual == expected
    if actual["risk_level"] == "danger":
        assert response["safety_assessment"]["matched_safety_rule_ids"]


@pytest.mark.parametrize("example_path", EXAMPLE_PATHS)
def test_public_response_does_not_expose_private_runtime_fields(
    example_path: str,
) -> None:
    response = _load(example_path)["response"]
    schema = _load(RESPONSE_SCHEMA_PATH)

    assert set(response) == set(schema["properties"])
    assert _nested_keys(response).isdisjoint(PRIVATE_RESPONSE_KEYS)
