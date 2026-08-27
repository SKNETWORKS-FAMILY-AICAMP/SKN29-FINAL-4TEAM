"""Consultation Handoff v1/v2 JSON Schema와 AI 내부 Pydantic 경계를 검증한다."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from ai.app.generation.consultation_summary.context_models import (
    CounselorContextBrief,
)
from ai.app.orchestration.agents.context_synthesis_contracts import (
    ContextRoutingReason,
    ContextSynthesisFallbackReason,
    ContextSynthesisStatus,
)
from ai.app.orchestration.handoff import ConsultationHandoffResult
from ai.app.schemas.common import AiStage
from ai.app.schemas.pipeline import FallbackReasonCode


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "ai"
SCHEMA_PATH = CONTRACT_ROOT / "handoff" / "ConsultationHandoffRequest.schema.json"
EXAMPLE_ROOT = CONTRACT_ROOT / "examples" / "handoff"
EXAMPLE_NAMES = (
    "v1-request.json",
    "v2-succeeded-request.json",
    "v2-fallback-request.json",
    "v2-null-context-request.json",
    "v2-human-review-rejected-request.json",
)
V2_EXAMPLE_NAMES = tuple(name for name in EXAMPLE_NAMES if name.startswith("v2-"))
PRIVATE_EXTERNAL_KEYS = {
    "latency_ms",
    "model_name",
    "prompt_version",
    "provider_called",
    "raw_output_text",
    "should_use_deterministic_handoff",
    "source_ids",
    "stack_trace",
    "system_prompt",
    "tokens_used",
    "traceback",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return _load(SCHEMA_PATH)


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _example(name: str) -> dict[str, Any]:
    return _load(EXAMPLE_ROOT / name)


def _request_schema(
    schema: dict[str, Any],
    *,
    version: int,
) -> dict[str, Any]:
    return schema["$defs"][f"v{version}Request"]


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for item in value.values() for key in _nested_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _nested_keys(item)}
    return set()


def _inflate_statement(
    statement: dict[str, Any],
    *,
    prefix: str,
    index: int,
) -> dict[str, Any]:
    return {
        **statement,
        "source_ids": [f"{prefix}-{index:03d}"],
    }


def _inflate_external_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """외부에서 제거한 source_ids만 합성해 내부 Brief 타입을 검증한다."""

    def inflate_list(field_name: str, prefix: str) -> list[dict[str, Any]]:
        return [
            _inflate_statement(item, prefix=prefix, index=index)
            for index, item in enumerate(brief[field_name], start=1)
        ]

    return {
        "safety_constraints": inflate_list("safety_constraints", "safety"),
        "issue_summary": _inflate_statement(
            brief["issue_summary"],
            prefix="issue",
            index=1,
        ),
        "customer_reported_facts": inflate_list(
            "customer_reported_facts",
            "customer",
        ),
        "attempted_actions_and_outcomes": inflate_list(
            "attempted_actions_and_outcomes",
            "action",
        ),
        "unresolved_questions": inflate_list(
            "unresolved_questions",
            "unresolved",
        ),
        "evidence_based_findings": inflate_list(
            "evidence_based_findings",
            "evidence",
        ),
        "consultant_priority_checks": inflate_list(
            "consultant_priority_checks",
            "priority",
        ),
        "uncertainty_notes": inflate_list(
            "uncertainty_notes",
            "uncertainty",
        ),
    }


def test_schema_is_valid_draft_2020_12_handoff_contract_v2(
    schema: dict[str, Any],
) -> None:
    Draft202012Validator.check_schema(schema)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "ConsultationHandoffRequest.schema.json"
    assert schema["x-contract-version"] == "2.0.0"
    assert schema["oneOf"] == [
        {"$ref": "#/$defs/v1Request"},
        {"$ref": "#/$defs/v2Request"},
    ]
    assert _request_schema(schema, version=1)["additionalProperties"] is False
    assert _request_schema(schema, version=2)["additionalProperties"] is False


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_all_examples_match_json_schema(
    example_name: str,
    validator: Draft202012Validator,
) -> None:
    validator.validate(_example(example_name))


def test_v1_example_matches_current_internal_handoff_result() -> None:
    payload = _example("v1-request.json")

    internal = ConsultationHandoffResult.model_validate(payload)

    assert internal.model_dump(mode="json", exclude_none=True) == payload


def test_v1_and_v2_constraints_are_structurally_isolated(
    schema: dict[str, Any],
) -> None:
    v1 = _request_schema(schema, version=1)
    v2 = _request_schema(schema, version=2)
    v1_properties = v1["properties"]
    v2_properties = v2["properties"]

    assert set(v1["required"]) == {
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "model_code",
        "product_family",
        "customer_symptom_summary",
        "safety_level",
        "safety_requires_consultation",
        "escalation_reason",
    }
    assert {
        "questionnaire_answers",
        "self_help_actions",
        "evidence",
        "safety_notes",
        "consultant_priority_checks",
        "source_chunk_ids",
    }.isdisjoint(v1["required"])
    assert set(v2["required"]) == set(v2_properties)

    expected_v2_max_items = {
        "questionnaire_answers": 30,
        "self_help_actions": 20,
        "evidence": 10,
        "safety_notes": 20,
        "consultant_priority_checks": 30,
        "source_chunk_ids": 10,
    }
    for field_name, expected_max_items in expected_v2_max_items.items():
        assert "maxItems" not in v1_properties[field_name]
        assert v2_properties[field_name]["maxItems"] == expected_max_items

    assert "enum" not in v1_properties["safety_level"]
    assert v1_properties["safety_level"]["maxLength"] == 50
    assert set(v2_properties["safety_level"]["enum"]) == {
        "general",
        "caution",
        "danger",
        "unknown",
    }
    assert "page" not in schema["$defs"]["v1Evidence"]["required"]
    assert "page" in schema["$defs"]["v2Evidence"]["required"]


def test_v1_accepts_legacy_optional_defaults_and_open_safety_value(
    validator: Draft202012Validator,
) -> None:
    payload = _example("v1-request.json")
    for field_name in (
        "questionnaire_answers",
        "self_help_actions",
        "evidence",
        "safety_notes",
        "consultant_priority_checks",
        "source_chunk_ids",
    ):
        del payload[field_name]
    payload["safety_level"] = "legacy_review_required"

    validator.validate(payload)
    internal = ConsultationHandoffResult.model_validate(payload)

    assert internal.safety_level == "legacy_review_required"
    assert internal.questionnaire_answers == []
    assert internal.self_help_actions == []
    assert internal.evidence == []
    assert internal.safety_notes == []
    assert internal.consultant_priority_checks == []
    assert internal.source_chunk_ids == []


def test_v1_accepts_evidence_without_page(
    validator: Draft202012Validator,
) -> None:
    payload = _example("v1-request.json")
    payload["evidence"] = [
        {
            "chunk_id": "legacy-chunk-001",
            "document_title": "기존 상담 근거",
            "summary": "기존 Backend에서는 page가 없어도 허용됩니다.",
        }
    ]
    payload["source_chunk_ids"] = ["legacy-chunk-001"]

    validator.validate(payload)
    internal = ConsultationHandoffResult.model_validate(payload)

    assert internal.evidence[0].page is None


def test_v1_accepts_existing_unbounded_list_counts(
    validator: Draft202012Validator,
) -> None:
    payload = _example("v1-request.json")
    payload["questionnaire_answers"] = [
        {"field_name": f"field-{index}", "answer": f"answer-{index}"}
        for index in range(31)
    ]
    payload["self_help_actions"] = [f"action-{index}" for index in range(21)]
    payload["evidence"] = [
        {
            "chunk_id": f"legacy-chunk-{index:03d}",
            "document_title": f"기존 근거 {index}",
            "summary": f"기존 근거 요약 {index}",
        }
        for index in range(11)
    ]
    payload["safety_notes"] = [f"note-{index}" for index in range(21)]
    payload["consultant_priority_checks"] = [
        f"priority-{index}" for index in range(31)
    ]
    payload["source_chunk_ids"] = [
        item["chunk_id"] for item in payload["evidence"]
    ]

    validator.validate(payload)
    internal = ConsultationHandoffResult.model_validate(payload)

    assert len(internal.questionnaire_answers) == 31
    assert len(internal.self_help_actions) == 21
    assert len(internal.evidence) == 11
    assert len(internal.safety_notes) == 21
    assert len(internal.consultant_priority_checks) == 31
    assert len(internal.source_chunk_ids) == 11


def test_version_discriminator_does_not_reclassify_payloads(
    validator: Draft202012Validator,
) -> None:
    explicit_v1 = _example("v1-request.json")
    explicit_v1["schema_version"] = "1.0.0"
    validator.validate(explicit_v1)

    v1_labeled_as_v2 = deepcopy(explicit_v1)
    v1_labeled_as_v2["schema_version"] = "2.0.0"
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(v1_labeled_as_v2)

    v2_labeled_as_v1 = _example("v2-succeeded-request.json")
    v2_labeled_as_v1["schema_version"] = "1.0.0"
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(v2_labeled_as_v1)


@pytest.mark.parametrize("example_name", V2_EXAMPLE_NAMES)
def test_v2_base_handoff_fields_match_current_internal_result(
    example_name: str,
) -> None:
    payload = _example(example_name)
    base_payload = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "schema_version",
            "state_version",
            "routing_reason",
            "context_synthesis",
        }
    }

    internal = ConsultationHandoffResult.model_validate(base_payload)

    assert internal.model_dump(mode="json", exclude_none=True) == base_payload


def test_external_enums_match_agent_contracts(schema: dict[str, Any]) -> None:
    v2_properties = _request_schema(schema, version=2)["properties"]
    external_routes = set(v2_properties["routing_reason"]["enum"])
    internal_handoff_routes = {
        item.value
        for item in ContextRoutingReason
        if item != ContextRoutingReason.PRE_SEND_HUMAN_REVIEW
    }
    status_values = set(
        schema["$defs"]["contextSynthesis"]["properties"]["status"]["enum"]
    )
    fallback_values = set(
        schema["$defs"]["contextSynthesis"]["properties"]["fallback_reason"][
            "enum"
        ]
    )

    assert external_routes == internal_handoff_routes
    assert "PRE_SEND_HUMAN_REVIEW" not in external_routes
    assert status_values == {item.value for item in ContextSynthesisStatus}
    assert fallback_values - {None} == {
        item.value for item in ContextSynthesisFallbackReason
    }


def test_external_brief_fields_and_values_match_internal_pydantic_model(
    schema: dict[str, Any],
) -> None:
    external_fields = set(schema["$defs"]["contextBrief"]["properties"])

    assert external_fields == set(CounselorContextBrief.model_fields)
    for example_name in V2_EXAMPLE_NAMES:
        context = _example(example_name)["context_synthesis"]
        if context is None:
            continue
        CounselorContextBrief.model_validate(
            _inflate_external_brief(context["brief"])
        )


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_external_examples_exclude_private_agent_and_provider_fields(
    example_name: str,
) -> None:
    assert _nested_keys(_example(example_name)).isdisjoint(PRIVATE_EXTERNAL_KEYS)


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_example_evidence_bindings_follow_declared_runtime_invariants(
    example_name: str,
) -> None:
    payload = _example(example_name)
    top_level_ids = payload["source_chunk_ids"]

    assert top_level_ids == [item["chunk_id"] for item in payload["evidence"]]
    assert len(top_level_ids) == len(set(top_level_ids))

    context = payload.get("context_synthesis")
    if context is None:
        return
    nested_ids = {
        chunk_id
        for finding in context["brief"]["evidence_based_findings"]
        for chunk_id in finding["source_chunk_ids"]
    }
    assert nested_ids <= set(top_level_ids)


def test_harness_authority_crosswalk_uses_airun_fallback_not_http_error(
    schema: dict[str, Any],
) -> None:
    crosswalk = schema["x-authoritative-airun-crosswalk"]["HARNESS_ESCALATE"]
    pairs = {
        (item["fallback_reason_code"], item["failure_stage"])
        for item in crosswalk["allowed_pairs"]
    }

    assert crosswalk["source"] == "AIRun.validated_output_payload"
    assert crosswalk["source_fields"] == [
        "fallback_reason_code",
        "failure_stage",
    ]
    assert pairs == {
        ("MCP_TOOL_FAILURE", "VALIDATING"),
        ("OUTPUT_SCHEMA_INVALID", "VALIDATING"),
        ("UNSPECIFIED_FALLBACK", "VALIDATING"),
    }
    assert {reason for reason, _stage in pairs} <= {
        item.value for item in FallbackReasonCode
    }
    assert {stage for _reason, stage in pairs} <= {
        item.value for item in AiStage
    }


def test_human_review_rejection_crosswalk_is_exact(
    schema: dict[str, Any],
) -> None:
    crosswalk = schema["x-human-review-rejection-crosswalk"]

    assert crosswalk["required_values"] == {
        "HumanReview.status_code": "REJECTED",
        "HumanReview.decision_code": "REJECT",
        "request.routing_reason": "FAIL_CLOSED_CONSULTATION",
    }
    assert {
        (item["left"], item["right"])
        for item in crosswalk["identity_bindings"]
    } == {
        ("HumanReview.inquiry_id", "request.inquiry_id"),
        ("HumanReview.guidance.inquiry_id", "request.inquiry_id"),
        ("HumanReview.source_ai_request_id", "request.ai_request_id"),
        (
            "HumanReview.source_inquiry_state_version",
            "request.state_version",
        ),
    }
    assert crosswalk["automatic_inquiry_transition"] is False
    assert crosswalk["automatic_consultation_creation"] is False

    example = _example("v2-human-review-rejected-request.json")
    assert example["routing_reason"] == "FAIL_CLOSED_CONSULTATION"
    assert example["escalation_reason"] == "HUMAN_REVIEW_REJECTED"


def test_backend_error_retry_matrix_is_exact(schema: dict[str, Any]) -> None:
    retry = schema["x-backend-error-retry-policy"]

    assert retry["maximum_attempts"] == 2
    assert retry["retryable_error_codes"] == ["AI_HANDOFF_NOT_READY"]
    assert set(retry["non_retryable_error_codes"]) == {
        "AI_HANDOFF_STALE",
        "AI_HANDOFF_EVIDENCE_REJECTED",
        "DUPLICATE-EVENT-01",
        "VALIDATION_ERROR",
        "FORBIDDEN",
    }
    assert set(retry["retryable_http_statuses"]) == {429, 500, 502, 503, 504}
    assert set(retry["retryable_transport_failures"]) == {"NETWORK", "TIMEOUT"}
    assert retry["default_4xx_retryable"] is False
    assert retry["payload_mutation_after_rejection"] is False


def test_v2_rejects_constraints_that_remain_open_in_v1(
    validator: Draft202012Validator,
) -> None:
    invalid_documents: list[dict[str, Any]] = []
    base = _example("v2-succeeded-request.json")

    questionnaire_over_limit = deepcopy(base)
    questionnaire_over_limit["questionnaire_answers"] = [
        {"field_name": f"field-{index}", "answer": f"answer-{index}"}
        for index in range(31)
    ]
    invalid_documents.append(questionnaire_over_limit)

    actions_over_limit = deepcopy(base)
    actions_over_limit["self_help_actions"] = [
        f"action-{index}" for index in range(21)
    ]
    invalid_documents.append(actions_over_limit)

    evidence_over_limit = deepcopy(base)
    evidence_over_limit["evidence"] = [
        {
            "chunk_id": f"v2-chunk-{index:03d}",
            "document_title": f"v2 근거 {index}",
            "page": index + 1,
            "summary": f"v2 근거 요약 {index}",
        }
        for index in range(11)
    ]
    invalid_documents.append(evidence_over_limit)

    safety_notes_over_limit = deepcopy(base)
    safety_notes_over_limit["safety_notes"] = [
        f"note-{index}" for index in range(21)
    ]
    invalid_documents.append(safety_notes_over_limit)

    priority_checks_over_limit = deepcopy(base)
    priority_checks_over_limit["consultant_priority_checks"] = [
        f"priority-{index}" for index in range(31)
    ]
    invalid_documents.append(priority_checks_over_limit)

    source_ids_over_limit = deepcopy(base)
    source_ids_over_limit["source_chunk_ids"] = [
        f"v2-source-{index:03d}" for index in range(11)
    ]
    invalid_documents.append(source_ids_over_limit)

    open_safety_value = deepcopy(base)
    open_safety_value["safety_level"] = "legacy_review_required"
    invalid_documents.append(open_safety_value)

    missing_evidence_page = deepcopy(base)
    del missing_evidence_page["evidence"][0]["page"]
    invalid_documents.append(missing_evidence_page)

    for document in invalid_documents:
        with pytest.raises(JsonSchemaValidationError):
            validator.validate(document)


@pytest.mark.parametrize(
    "field_name",
    (
        "questionnaire_answers",
        "self_help_actions",
        "evidence",
        "safety_notes",
        "consultant_priority_checks",
        "source_chunk_ids",
    ),
)
def test_v2_requires_lists_that_remain_optional_in_v1(
    field_name: str,
    validator: Draft202012Validator,
) -> None:
    payload = _example("v2-succeeded-request.json")
    del payload[field_name]

    with pytest.raises(JsonSchemaValidationError):
        validator.validate(payload)


def test_schema_rejects_pre_send_and_invalid_status_fallback_combinations(
    validator: Draft202012Validator,
) -> None:
    invalid_documents: list[dict[str, Any]] = []

    pre_send = _example("v2-succeeded-request.json")
    pre_send["routing_reason"] = "PRE_SEND_HUMAN_REVIEW"
    invalid_documents.append(pre_send)

    succeeded_with_reason = _example("v2-succeeded-request.json")
    succeeded_with_reason["context_synthesis"]["fallback_reason"] = "CONFIGURATION"
    invalid_documents.append(succeeded_with_reason)

    danger_succeeded = _example("v2-fallback-request.json")
    danger_succeeded["context_synthesis"]["status"] = "SUCCEEDED"
    danger_succeeded["context_synthesis"]["fallback_reason"] = None
    invalid_documents.append(danger_succeeded)

    non_danger_bypass = _example("v2-succeeded-request.json")
    non_danger_bypass["context_synthesis"]["status"] = "FALLBACK"
    non_danger_bypass["context_synthesis"]["fallback_reason"] = "DANGER_BYPASS"
    invalid_documents.append(non_danger_bypass)

    v1_with_v2_field = _example("v1-request.json")
    v1_with_v2_field["state_version"] = 1
    invalid_documents.append(v1_with_v2_field)

    v2_without_state = _example("v2-null-context-request.json")
    del v2_without_state["state_version"]
    invalid_documents.append(v2_without_state)

    private_metadata = _example("v2-succeeded-request.json")
    private_metadata["context_synthesis"]["provider_called"] = True
    invalid_documents.append(private_metadata)

    internal_source_id = _example("v2-succeeded-request.json")
    internal_source_id["context_synthesis"]["brief"]["issue_summary"][
        "source_ids"
    ] = ["issue-001"]
    invalid_documents.append(internal_source_id)

    for document in invalid_documents:
        with pytest.raises(JsonSchemaValidationError):
            validator.validate(document)


def test_null_context_example_preserves_required_handoff_route() -> None:
    payload = deepcopy(_example("v2-null-context-request.json"))

    assert payload["routing_reason"] == "FAIL_CLOSED_CONSULTATION"
    assert payload["context_synthesis"] is None
    assert payload["escalation_reason"] == "NO_EVIDENCE"
