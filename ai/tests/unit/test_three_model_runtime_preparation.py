"""3모델 Canonical Identity·검색 정책 준비 계약 테스트."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest
import yaml

from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.orchestration.stages.retrieval_stage import execute_retrieval_stage
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.retrieval.runtime_profile import resolve_rag_runtime_profile
from ai.app.schemas import TraceContext
from ai.scripts.export_three_model_canonical_identity import (
    BACKEND_HANDOFF_PATH,
    EXPECTED_MODEL_COUNTS,
    IDENTITY_PATH,
    IDENTITY_SCHEMA_PATH,
    INDEX_MANIFEST_SCHEMA_PATH,
    INDEX_TARGET_PATH,
    build_identity,
    build_index_target,
    load_source_rows,
)
from ai.scripts.generate_three_model_index_manifest import (
    build_manifest,
    validate_confirmed_counts,
)
from ai.scripts import verify_three_model_readonly_runtime as readonly_verifier
from ai.scripts.verify_three_model_readonly_runtime import (
    EXPECTED_TABLE,
    _integration_product_filter,
    _load_identity_and_manifest,
    _required_environment,
)


def test_three_model_identity_artifacts_match_canonical_handoff() -> None:
    rows = load_source_rows()
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    index_target = json.loads(INDEX_TARGET_PATH.read_text(encoding="utf-8"))

    assert identity == build_identity(rows)
    assert index_target == build_index_target(rows)
    assert identity["chunk_count"] == 53
    assert identity["model_chunk_counts"] == EXPECTED_MODEL_COUNTS
    assert Counter(item["model_code"] for item in identity["chunks"]) == Counter(
        EXPECTED_MODEL_COUNTS
    )
    assert [item["chunk_id"] for item in identity["chunks"]] == sorted(
        item["chunk_id"] for item in identity["chunks"]
    )
    assert index_target["status"] == "PREPARED_NOT_INDEXED"
    assert index_target["ai_access"] == "SELECT_ONLY"
    assert index_target["required_pre_score_filter"] == "exact_sales_code"
    assert index_target["cross_model_fallback"] is False


def test_three_model_identity_and_handoff_hashes_match_schemas() -> None:
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    identity_schema = json.loads(IDENTITY_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(
        identity_schema,
        format_checker=FormatChecker(),
    ).validate(identity)

    handoff = json.loads(BACKEND_HANDOFF_PATH.read_text(encoding="utf-8"))
    identity_contract = handoff["canonical_identity"]
    assert identity_contract["file_bytes_sha256"] == sha256(
        IDENTITY_PATH.read_bytes()
    ).hexdigest().upper()
    assert identity_contract["schema_sha256"] == sha256(
        IDENTITY_SCHEMA_PATH.read_bytes()
    ).hexdigest().upper()
    assert handoff["evaluation_contract"]["total"] == 50
    assert handoff["evaluation_contract"]["positive"] == 43
    assert handoff["evaluation_contract"]["negative"] == 7
    assert handoff["crosswalk_validation"]["required_counts"] == {
        "canonical_ids": 53,
        "active_chunks": 53,
        "active_embeddings": 53,
        "active_crosswalks": 53,
        "readonly_view_rows": 53,
        "readonly_view_model_counts": EXPECTED_MODEL_COUNTS,
    }


def test_three_model_index_manifest_contract_and_confirmed_counts() -> None:
    manifest = build_manifest(indexed_at="2026-08-19T12:34:56Z")
    schema = json.loads(INDEX_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(manifest)
    assert manifest["chunk_count"] == 53
    assert manifest["chunk_set_sha256"] == json.loads(
        IDENTITY_PATH.read_text(encoding="utf-8")
    )["chunk_set_sha256"]
    assert manifest["indexed_at"] == "2026-08-19T12:34:56Z"

    validate_confirmed_counts(total=53, jac104=15, iac425=19, iac606=19)
    with pytest.raises(ValueError, match="15/19/19"):
        validate_confirmed_counts(total=53, jac104=16, iac425=18, iac606=19)


def test_three_model_identity_rejects_text_hash_drift(tmp_path: Path) -> None:
    rows = load_source_rows()
    rows[0]["child_text"] = f"{rows[0]['child_text']} 변경"
    drifted_source = tmp_path / "drifted.jsonl"
    drifted_source.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="child_text_sha256 does not match"):
        load_source_rows(drifted_source)


def test_three_model_policy_is_integration_only_and_default_remains_jac104() -> None:
    policy = yaml.safe_load(
        Path("ai/configs/retrieval_policy.yaml").read_text(encoding="utf-8")
    )
    prepared = policy["prepared_runtime_profiles"]["three_model"]

    assert policy["answerability_capability_gate"]["supported_model_codes"] == [
        "WPUJAC104DWH"
    ]
    assert prepared["activation_status"] == "INTEGRATION_VERIFICATION_ONLY"
    assert prepared["public_runtime_activation"] == "HOLD"
    assert prepared["supported_model_codes"] == list(EXPECTED_MODEL_COUNTS)
    assert prepared["supported_generations"] == ["D", "IAC425", "IAC606"]
    assert prepared["cross_model_fallback"] is False


@pytest.mark.parametrize(
    ("model_code", "generation"),
    [
        ("WPUIAC425SNW", "IAC425"),
        ("WPUIAC606SNW", "IAC606"),
    ],
)
def test_retrieval_stage_preserves_backend_model_code_and_resolves_generation(
    model_code: str,
    generation: str,
) -> None:
    observed = []

    class RecordingSearchService:
        def search(self, query, *, cancellation_token=None):
            observed.append(query)
            return []

    ctx = PipelineContext(
        trace_context=TraceContext(
            inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b490",
            correlation_id="018f2f9b-7c30-7981-b541-1a987c88e490",
            ai_request_id=f"ai-req-model-preserve-{model_code}",
            state_version=1,
        ),
        raw_symptom="제품 조작 방법을 확인하고 싶습니다.",
        model_code=model_code,
    )

    execute_retrieval_stage(ctx, RecordingSearchService())

    assert len(observed) == 1
    assert observed[0].model_code == model_code
    assert observed[0].product_generation == generation


def test_prepared_product_filter_accepts_only_exact_three_model_scope() -> None:
    policy = yaml.safe_load(
        Path("ai/configs/retrieval_policy.yaml").read_text(encoding="utf-8")
    )["prepared_runtime_profiles"]["three_model"]["metadata_filters"]
    product_filter = ProductFilter(
        allowed_generations=policy["allowed_generations"],
        target_models=policy["target_models"],
        excluded_models=policy["excluded_models"],
    )

    def chunk(model_code: str, generation: str) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=f"RAG-{model_code}-TEST",
            document_title="공식 문서",
            manual_model=model_code,
            model_code=model_code,
            product_generation=generation,
            content="검증용 근거",
            similarity_score=0.9,
            verification_status="official_verified",
            allowed_use=True,
        )

    iac425 = chunk("WPUIAC425SNW", "IAC425")
    iac606 = chunk("WPUIAC606SNW", "IAC606")
    wrong_model = chunk("WPUIAC999ZZZ", "IAC999")

    assert product_filter.is_valid_chunk(iac425, "WPUIAC425SNW") is True
    assert product_filter.is_valid_chunk(iac606, "WPUIAC606SNW") is True
    assert product_filter.is_valid_chunk(iac606, "WPUIAC425SNW") is False
    assert product_filter.is_valid_chunk(wrong_model, "WPUIAC999ZZZ") is False


def test_readonly_runtime_verifier_requires_official_view_and_loads_candidate_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_VECTOR_TABLE_NAME", raising=False)
    with pytest.raises(RuntimeError, match="AI_VECTOR_TABLE_NAME"):
        _required_environment("AI_VECTOR_TABLE_NAME")

    assert EXPECTED_TABLE == "backend_ai_rag_chunks_v1"
    runtime_profile = resolve_rag_runtime_profile("three_model_integration")
    assert _integration_product_filter(runtime_profile).target_models == set(
        EXPECTED_MODEL_COUNTS
    )
    identity, manifest = _load_identity_and_manifest(runtime_profile)
    assert manifest.chunk_count == identity["chunk_count"] == 53
    assert manifest.chunk_set_sha256.upper() == identity["chunk_set_sha256"]
    assert manifest.index_version == identity["index_version"] == "2.0.0"


def test_readonly_runtime_verifier_does_not_print_connection_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail() -> None:
        raise RuntimeError("SENSITIVE_CONNECTION_DETAIL_SENTINEL")

    monkeypatch.setattr(readonly_verifier, "_verify_runtime", fail)

    assert readonly_verifier.main() == 1
    output = capsys.readouterr().out
    assert "SENSITIVE_CONNECTION_DETAIL_SENTINEL" not in output
    assert "THREE_MODEL_READONLY_RUNTIME_REQUIREMENTS_NOT_MET" in output
