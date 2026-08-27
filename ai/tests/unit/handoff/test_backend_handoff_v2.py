"""Parity and privacy tests for the external Consultation Handoff 2.0 DTO."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from ai.app.orchestration.handoff import (
    ConsultationHandoffResult,
    ConsultationHandoffV2Request,
    HandoffContextSynthesis,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "ai"
SCHEMA_PATH = CONTRACT_ROOT / "handoff" / "ConsultationHandoffRequest.schema.json"
EXAMPLE_ROOT = CONTRACT_ROOT / "examples" / "handoff"
V2_EXAMPLE_NAMES = (
    "v2-succeeded-request.json",
    "v2-fallback-request.json",
    "v2-null-context-request.json",
    "v2-human-review-rejected-request.json",
)
PRIVATE_EXTERNAL_KEYS = {
    "latency_ms",
    "model_name",
    "prompt_version",
    "provider_called",
    "should_use_deterministic_handoff",
    "source_ids",
    "tokens_used",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _example(name: str) -> dict[str, Any]:
    return _load(EXAMPLE_ROOT / name)


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key for item in value.values() for key in _nested_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _nested_keys(item)}
    return set()


def _with_source_ids(
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
    def inflate_list(field_name: str, prefix: str) -> list[dict[str, Any]]:
        return [
            _with_source_ids(item, prefix=prefix, index=index)
            for index, item in enumerate(brief[field_name], start=1)
        ]

    return {
        "safety_constraints": inflate_list("safety_constraints", "safety"),
        "issue_summary": _with_source_ids(
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


def _internal_from_example(name: str) -> ConsultationHandoffResult:
    payload = _example(name)
    context = payload["context_synthesis"]
    internal_context = None
    if context is not None:
        internal_context = HandoffContextSynthesis(
            status=context["status"],
            routing_reason=payload["routing_reason"],
            brief=_inflate_external_brief(context["brief"]),
            fallback_reason=context["fallback_reason"],
            should_use_deterministic_handoff=context["status"] == "FALLBACK",
            provider_called=context["status"] == "SUCCEEDED",
            model_name=(
                "internal-provider-model"
                if context["status"] == "SUCCEEDED"
                else None
            ),
            prompt_version="consultation_summary/v1",
            tokens_used=10 if context["status"] == "SUCCEEDED" else None,
            latency_ms=25.0,
        )

    internal_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"schema_version", "context_synthesis"}
    }
    internal_payload["context_synthesis"] = internal_context
    return ConsultationHandoffResult.model_validate(internal_payload)


@pytest.mark.parametrize("example_name", V2_EXAMPLE_NAMES)
def test_mapper_matches_frozen_v2_examples_exactly(example_name: str) -> None:
    expected = _example(example_name)

    mapped = ConsultationHandoffV2Request.from_internal(
        _internal_from_example(example_name)
    ).model_dump(mode="json")

    assert mapped == expected
    validator = Draft202012Validator(
        _load(SCHEMA_PATH),
        format_checker=FormatChecker(),
    )
    validator.validate(mapped)
    assert _nested_keys(mapped).isdisjoint(PRIVATE_EXTERNAL_KEYS)


def test_unexpected_context_mapping_failure_preserves_base_route() -> None:
    source = _internal_from_example("v2-succeeded-request.json")
    source.context_synthesis = HandoffContextSynthesis(
        status="SUCCEEDED",
        routing_reason="HARNESS_ESCALATE",
        brief={"unexpected": "invalid internal brief"},
        fallback_reason=None,
        should_use_deterministic_handoff=False,
        provider_called=True,
        model_name="internal-provider-model",
        prompt_version="consultation_summary/v1",
        tokens_used=10,
        latency_ms=25.0,
    )

    mapped = ConsultationHandoffV2Request.from_internal(source)

    assert mapped.state_version == source.state_version
    assert mapped.routing_reason == "HARNESS_ESCALATE"
    assert mapped.context_synthesis is None


def test_base_identity_and_route_fail_before_transport() -> None:
    source = _internal_from_example("v2-null-context-request.json")
    missing_state = source.model_copy(update={"state_version": None})
    pre_send = source.model_copy(
        update={"routing_reason": "PRE_SEND_HUMAN_REVIEW"}
    )

    with pytest.raises(ValueError, match="state_version"):
        ConsultationHandoffV2Request.from_internal(missing_state)
    with pytest.raises(ValueError):
        ConsultationHandoffV2Request.from_internal(pre_send)


def test_evidence_binding_mismatch_is_not_silently_removed() -> None:
    source = _internal_from_example("v2-succeeded-request.json")
    mismatched = source.model_copy(update={"source_chunk_ids": []})

    with pytest.raises(ValueError, match="source_chunk_ids"):
        ConsultationHandoffV2Request.from_internal(mismatched)


def test_nested_context_evidence_must_be_top_level_subset() -> None:
    source = _internal_from_example("v2-succeeded-request.json")
    context = deepcopy(source.context_synthesis)
    context.brief["evidence_based_findings"][0]["source_chunk_ids"] = [
        "unapproved-chunk"
    ]
    source.context_synthesis = context

    with pytest.raises(ValueError, match="부분집합"):
        ConsultationHandoffV2Request.from_internal(source)
