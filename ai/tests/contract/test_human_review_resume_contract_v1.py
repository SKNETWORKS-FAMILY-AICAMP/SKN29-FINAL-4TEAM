"""Protected HumanReview Resume v1 JSON Schema and Pydantic parity."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError
from referencing import Registry, Resource

from ai.app.interfaces.http.human_review_resume_models import (
    HumanReviewResumeApiRequest,
    HumanReviewResumeApiResponse,
)
from ai.tests.unit.test_human_review_resume_routes import _payload


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "ai"
REQUEST_PATH = "internal/HumanReviewResumeRequest.schema.json"
RESPONSE_PATH = "internal/HumanReviewResumeResponse.schema.json"


def _validator(relative_path: str) -> Draft202012Validator:
    registry = Registry()
    for path in sorted(CONTRACT_ROOT.rglob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema["$id"] = path.resolve().as_uri()
        registry = registry.with_resource(
            schema["$id"],
            Resource.from_contents(schema),
        )
    path = (CONTRACT_ROOT / relative_path).resolve()
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["$id"] = path.as_uri()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )


def _request_with_official_evidence() -> dict:
    request = _payload()
    request["analysis_result"]["evidence_references"] = [
        {
            "document_title": "JAC104 공식 가이드",
            "document_version": "v1",
            "page": 10,
            "page_refs": [10],
            "chunk_id": "RAG-JAC104-CONTEXT-001",
            "official_url": "https://example.invalid/jac104",
            "summary": "합성 공식 근거",
            "similarity_score": 0.9,
            "verification_status": "official_verified",
        }
    ]
    return request


def test_request_schema_matches_pydantic_and_requires_official_evidence():
    request = _request_with_official_evidence()

    _validator(REQUEST_PATH).validate(request)
    parsed = HumanReviewResumeApiRequest.model_validate(request)

    assert parsed.decision == "REJECT"
    assert parsed.analysis_result.evidence_references[0].chunk_id == (
        "RAG-JAC104-CONTEXT-001"
    )

    team_only = deepcopy(request)
    team_only["analysis_result"]["evidence_references"][0][
        "verification_status"
    ] = "team_verified"
    with pytest.raises(JsonSchemaValidationError):
        _validator(REQUEST_PATH).validate(team_only)
    with pytest.raises(PydanticValidationError):
        HumanReviewResumeApiRequest.model_validate(team_only)


def test_response_schema_matches_sanitized_pydantic_receipt():
    request = _request_with_official_evidence()
    response = {
        "contract_version": "1.0.0",
        "backend_review_id": request["backend_review_id"],
        "inquiry_id": request["analysis_result"]["inquiry_id"],
        "ai_request_id": request["analysis_result"]["ai_request_id"],
        "source_inquiry_state_version": request[
            "source_inquiry_state_version"
        ],
        "review_state_version": request["review_state_version"],
        "status": "RESUMED",
        "routing_reason": "FAIL_CLOSED_CONSULTATION",
        "escalation_reason": "HUMAN_REVIEW_REJECTED",
        "context_agent_calls": 1,
        "provider_calls": 1,
        "context_synthesis_status": "SUCCEEDED",
        "fallback_reason": None,
        "handoff_created": True,
        "handoff_delivery_scheduled": False,
        "idempotent_replay": False,
    }

    _validator(RESPONSE_PATH).validate(response)
    assert (
        HumanReviewResumeApiResponse.model_validate(response)
        .model_dump(mode="json")
        == response
    )

    invalid = {**response, "provider_calls": 0}
    with pytest.raises(JsonSchemaValidationError):
        _validator(RESPONSE_PATH).validate(invalid)
    with pytest.raises(PydanticValidationError):
        HumanReviewResumeApiResponse.model_validate(invalid)
