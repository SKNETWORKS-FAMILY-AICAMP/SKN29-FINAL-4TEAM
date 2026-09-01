"""Internal analysis + consultation-cause Envelope v1 contract tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError
from referencing import Registry, Resource

from ai.app.schemas import (
    AnalysisConsultationEnvelope,
    canonical_payload_sha256,
)
from ai.app.schemas.consultation_cause_ledger import (
    ConsultationCauseLedgerBuildError,
    build_analysis_consultation_envelope,
    resolve_execution_commit_sha,
)
from ai.app.schemas.pipeline import SymptomAnalysisResult


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "ai"
ENVELOPE_SCHEMA_PATH = "internal/AnalysisConsultationEnvelope.schema.json"
LEDGER_SCHEMA_PATH = "internal/ConsultationCauseLedger.schema.json"
PUBLIC_RESPONSE_SCHEMA_PATH = "responses/SymptomAnalysisResponse.schema.json"
EXAMPLE_PATH = "examples/internal/analysis-consultation-envelope-refrigerant.json"


def _load(relative_path: str) -> dict:
    return json.loads((CONTRACT_ROOT / relative_path).read_text(encoding="utf-8"))


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
    return Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )


def test_internal_envelope_example_matches_schema_and_pydantic() -> None:
    response = _load(EXAMPLE_PATH)["response"]

    _validator(ENVELOPE_SCHEMA_PATH).validate(response)
    model = AnalysisConsultationEnvelope.model_validate(response)

    assert model.model_dump(mode="json") == response
    assert model.contract_version == "1.0.0"
    assert model.analysis_result.model_code == "WPUJAC104DWH"
    assert model.consultation_cause_ledger.contract_version == "1.0.0"


def test_public_analysis_contract_remains_4_0_0_without_ledger_fields() -> None:
    schema = _load(PUBLIC_RESPONSE_SCHEMA_PATH)

    assert schema["x-contract-version"] == "4.0.0"
    assert "consultation_cause_ledger" not in schema["properties"]
    assert "analysis_result" not in schema["properties"]


def test_envelope_rejects_identifier_or_result_hash_mismatch() -> None:
    response = _load(EXAMPLE_PATH)["response"]
    identifier_mismatch = deepcopy(response)
    identifier_mismatch["consultation_cause_ledger"]["model_code"] = "WPUIAC425SNW"
    identifier_mismatch["consultation_cause_ledger"]["ledger_sha256"] = (
        canonical_payload_sha256(
            identifier_mismatch["consultation_cause_ledger"],
            excluded_key="ledger_sha256",
        )
    )
    hash_mismatch = deepcopy(response)
    hash_mismatch["consultation_cause_ledger"]["analysis_result_sha256"] = "f" * 64
    hash_mismatch["consultation_cause_ledger"]["ledger_sha256"] = (
        canonical_payload_sha256(
            hash_mismatch["consultation_cause_ledger"],
            excluded_key="ledger_sha256",
        )
    )

    with pytest.raises(PydanticValidationError, match="식별자"):
        AnalysisConsultationEnvelope.model_validate(identifier_mismatch)
    with pytest.raises(PydanticValidationError, match="analysis_result_sha256"):
        AnalysisConsultationEnvelope.model_validate(hash_mismatch)


def test_ledger_hash_and_analysis_hash_are_canonical() -> None:
    response = _load(EXAMPLE_PATH)["response"]
    ledger = response["consultation_cause_ledger"]

    assert ledger["analysis_result_sha256"] == canonical_payload_sha256(
        response["analysis_result"]
    )
    assert ledger["ledger_sha256"] == canonical_payload_sha256(
        ledger,
        excluded_key="ledger_sha256",
    )


def test_schema_and_pydantic_reject_private_or_evaluation_only_evidence() -> None:
    response = _load(EXAMPLE_PATH)["response"]
    private = deepcopy(response)
    private["consultation_cause_ledger"]["causes"][0]["raw_symptom"] = "금지"

    with pytest.raises(JsonSchemaValidationError):
        _validator(ENVELOPE_SCHEMA_PATH).validate(private)

    evaluation_only = deepcopy(response)
    evaluation_only["consultation_cause_ledger"]["causes"][0]["evidence_refs"] = [
        {
            "chunk_id": "CHILD-001",
            "document_id": "MANUAL-001",
            "model_code": "WPUJAC104DWH",
            "index_version": "2.0.0",
            "chunk_set_sha256": "a" * 64,
            "source_file_sha256": "b" * 64,
            "content_sha256": "c" * 64,
            "scenario_id": "REF-JAC104-D-004",
        }
    ]
    with pytest.raises(JsonSchemaValidationError):
        _validator(LEDGER_SCHEMA_PATH).validate(
            evaluation_only["consultation_cause_ledger"]
        )
    with pytest.raises(PydanticValidationError, match=r"REF-\*"):
        AnalysisConsultationEnvelope.model_validate(evaluation_only)


def test_schema_and_pydantic_reject_lock_downgrade_or_unproved_resolution() -> None:
    response = _load(EXAMPLE_PATH)["response"]
    lock_downgrade = deepcopy(response)
    lock_downgrade["consultation_cause_ledger"]["causes"][0][
        "lock_class"
    ] = "NON_SAFETY_RESOLVABLE"

    with pytest.raises(JsonSchemaValidationError):
        _validator(LEDGER_SCHEMA_PATH).validate(
            lock_downgrade["consultation_cause_ledger"]
        )
    with pytest.raises(PydanticValidationError, match="잠금 분류"):
        AnalysisConsultationEnvelope.model_validate(lock_downgrade)

    unproved_resolution = deepcopy(response)
    cause = unproved_resolution["consultation_cause_ledger"]["causes"][0]
    cause["cause_code"] = "HARNESS_SCOPE_EXCEEDED"
    cause["origin"] = "HARNESS"
    cause["lock_class"] = "NON_SAFETY_RESOLVABLE"
    cause["status"] = "RESOLUTION_PROPOSED"
    cause["matched_safety_rule_ids"] = []

    with pytest.raises(JsonSchemaValidationError):
        _validator(LEDGER_SCHEMA_PATH).validate(
            unproved_resolution["consultation_cause_ledger"]
        )
    with pytest.raises(PydanticValidationError, match="검증 Evidence"):
        AnalysisConsultationEnvelope.model_validate(unproved_resolution)


def test_runtime_builder_is_deterministic_and_hashes_nested_public_result() -> None:
    response = _load(EXAMPLE_PATH)["response"]
    analysis = SymptomAnalysisResult.model_validate(
        response["analysis_result"]
    )

    first = build_analysis_consultation_envelope(
        analysis,
        runtime_name="single_rag",
        execution_commit_sha="a" * 40,
    )
    replay = build_analysis_consultation_envelope(
        analysis,
        runtime_name="single_rag",
        execution_commit_sha="a" * 40,
    )

    first_payload = first.model_dump(mode="json")
    replay_payload = replay.model_dump(mode="json")
    ledger = first_payload["consultation_cause_ledger"]
    assert first_payload == replay_payload
    assert ledger["analysis_result_sha256"] == canonical_payload_sha256(
        first_payload["analysis_result"]
    )
    assert ledger["ledger_sha256"] == canonical_payload_sha256(
        ledger,
        excluded_key="ledger_sha256",
    )
    assert {cause["cause_code"] for cause in ledger["causes"]} == {
        "DANGER_ASSESSMENT",
        "EXPLICIT_SAFETY_RULE",
    }


def test_runtime_builder_rejects_explicit_invalid_release_identity() -> None:
    with pytest.raises(
        ConsultationCauseLedgerBuildError,
        match="EXECUTION_COMMIT_SHA_INVALID",
    ):
        resolve_execution_commit_sha("not-a-release-sha")


def test_runtime_builder_uses_codes_not_customer_or_llm_free_text() -> None:
    response = _load(EXAMPLE_PATH)["response"]
    analysis_payload = deepcopy(response["analysis_result"])
    sentinel = "customer-and-llm-free-text-must-not-enter-ledger"
    analysis_payload["structured_symptom"]["occurrence_condition"] = sentinel
    analysis_payload["safety_assessment"]["safety_reason"] = sentinel
    analysis = SymptomAnalysisResult.model_validate(analysis_payload)

    envelope = build_analysis_consultation_envelope(
        analysis,
        runtime_name="single_rag",
        execution_commit_sha="b" * 40,
    )
    ledger_json = json.dumps(
        envelope.consultation_cause_ledger.model_dump(mode="json"),
        ensure_ascii=False,
    )

    assert sentinel not in ledger_json
    assert "DETERMINISTIC_DANGER_ASSESSMENT" in ledger_json
    assert "APPROVED_SAFETY_RULE_MATCH" in ledger_json


def test_runtime_builder_does_not_lock_non_consultation_caution_rule() -> None:
    response = _load(
        "examples/symptom-analysis/caution-pre-send-human-review.json"
    )["response"]
    analysis = SymptomAnalysisResult.model_validate(response)

    envelope = build_analysis_consultation_envelope(
        analysis,
        runtime_name="single_rag",
        execution_commit_sha="c" * 40,
    )

    assert analysis.safety_assessment.matched_safety_rule_ids == [
        "SAFETY-TEMP-ABNORMAL-001"
    ]
    assert analysis.safety_assessment.requires_consultation is False
    assert envelope.consultation_cause_ledger.causes == []


def test_runtime_builder_maps_harness_codes_without_free_text() -> None:
    response = _load(
        "examples/symptom-analysis/no-evidence.json"
    )["response"]
    analysis = SymptomAnalysisResult.model_validate(response)

    envelope = build_analysis_consultation_envelope(
        analysis,
        runtime_name="multi_agent",
        harness_issue_codes=(
            "NO_EVIDENCE",
            "UNSUPPORTED_FUNCTION",
            "PRODUCT_FAMILY_MISMATCH",
        ),
        execution_commit_sha="d" * 40,
    )
    causes = envelope.consultation_cause_ledger.causes

    assert {cause.cause_code.value for cause in causes} == {
        "FAIL_CLOSED_AI_RESULT",
        "HARNESS_UNSUPPORTED_FUNCTION",
        "HARNESS_SCOPE_EXCEEDED",
    }
    assert {cause.origin.value for cause in causes} == {
        "AI_RUNTIME",
        "HARNESS",
    }
    assert all(not cause.evidence_refs for cause in causes)


def test_runtime_builder_fails_closed_for_unverified_public_evidence() -> None:
    general = _load(
        "examples/symptom-analysis/general-guidance.json"
    )["response"]
    general["evidence_references"][0][
        "verification_status"
    ] = "team_verified"
    analysis = SymptomAnalysisResult.model_validate(general)

    with pytest.raises(
        ConsultationCauseLedgerBuildError,
        match="UNVERIFIED_EVIDENCE_NOT_ALLOWED",
    ):
        build_analysis_consultation_envelope(
            analysis,
            runtime_name="single_rag",
            execution_commit_sha="e" * 40,
        )
