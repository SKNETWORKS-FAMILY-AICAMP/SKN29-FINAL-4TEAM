"""Allowlisted RAG Runtime profile selection and contract tests."""

from datetime import datetime, timezone

import pytest

from ai.app.retrieval import RetrievalConfigurationError
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.runtime_profile import (
    load_runtime_retrieval_policy,
    resolve_rag_runtime_profile,
    validate_runtime_manifest,
)


def _manifest(*, three_model: bool) -> IndexManifest:
    return IndexManifest(
        model_name="BAAI/bge-m3",
        model_revision="5617a9f61b028005a4858fdac845db406aefb181",
        dimension=1024,
        index_type="exact_search",
        index_version="2.0.0" if three_model else "1.0.0",
        chunk_count=53 if three_model else 7,
        chunk_set_sha256=(
            "5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304"
            if three_model
            else "175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958"
        ),
        document_hashes=(
            {
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00": "a" * 64,
                "MAN-SKMAGIC-WPU-IAC425-REV02": "b" * 64,
                "MAN-SKMAGIC-WPU-IAC606-REV00": "c" * 64,
            }
            if three_model
            else {"MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00": "a" * 64}
        ),
        indexed_at=datetime.now(timezone.utc),
    )


def test_runtime_profile_defaults_to_public_mvp(monkeypatch):
    monkeypatch.delenv("AI_RAG_RUNTIME_PROFILE", raising=False)

    profile = resolve_rag_runtime_profile()
    policy = load_runtime_retrieval_policy(profile)

    assert profile.name == "mvp"
    assert profile.activation_scope == "PUBLIC_MVP"
    assert profile.manifest_relative_path == "ai/configs/index_manifest.json"
    assert policy.answerability_gate["supported_model_codes"] == ["WPUJAC104DWH"]
    validate_runtime_manifest(profile, _manifest(three_model=False))


def test_three_model_profile_is_explicit_integration_only(monkeypatch):
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")

    profile = resolve_rag_runtime_profile()
    policy = load_runtime_retrieval_policy(profile)

    assert profile.activation_scope == "INTEGRATION_VERIFICATION_ONLY"
    assert profile.manifest_relative_path == "ai/configs/index_manifest_3model.json"
    assert set(policy.answerability_gate["supported_model_codes"]) == {
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    }
    assert set(policy.metadata_filters["target_models"]) == set(
        profile.approved_model_codes
    )
    validate_runtime_manifest(profile, _manifest(three_model=True))


@pytest.mark.parametrize(
    "value",
    ["../index_manifest.json", "C:/temp/manifest.json", "three_model", "public"],
)
def test_runtime_profile_rejects_arbitrary_path_or_unapproved_alias(value):
    with pytest.raises(RetrievalConfigurationError, match="허용 Profile"):
        resolve_rag_runtime_profile(value)


def test_three_model_profile_rejects_legacy_manifest():
    profile = resolve_rag_runtime_profile("three_model_integration")

    with pytest.raises(RetrievalConfigurationError, match="Manifest와 일치하지"):
        validate_runtime_manifest(profile, _manifest(three_model=False))
