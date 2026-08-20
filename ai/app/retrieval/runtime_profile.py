"""Allowlisted RAG Runtime profile and Manifest selection."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml

from .indexing.index_manifest import IndexManifest
from .runtime import RetrievalConfigurationError


RUNTIME_PROFILE_ENV = "AI_RAG_RUNTIME_PROFILE"
DEFAULT_RUNTIME_PROFILE = "mvp"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RETRIEVAL_POLICY_PATH = REPOSITORY_ROOT / "ai/configs/retrieval_policy.yaml"


@dataclass(frozen=True, slots=True)
class RagRuntimeProfile:
    """One allowlisted combination of Manifest, policy, and product scope."""

    name: str
    manifest_relative_path: str
    policy_profile: str | None
    approved_model_codes: frozenset[str]
    expected_index_version: str
    expected_chunk_count: int
    expected_chunk_set_sha256: str
    expected_document_ids: frozenset[str]
    activation_scope: str

    @property
    def manifest_path(self) -> Path:
        path = (REPOSITORY_ROOT / self.manifest_relative_path).resolve()
        try:
            path.relative_to(REPOSITORY_ROOT.resolve())
        except ValueError as exc:  # pragma: no cover - constants are defensive data.
            raise RetrievalConfigurationError(
                "RAG Runtime Manifest 경로가 저장소 범위를 벗어났습니다."
            ) from exc
        return path


@dataclass(frozen=True, slots=True)
class RuntimeRetrievalPolicy:
    """Resolved search policy that must match the selected Runtime profile."""

    metadata_filters: dict[str, list[str]]
    answerability_gate: dict[str, Any]


_PROFILES = {
    "mvp": RagRuntimeProfile(
        name="mvp",
        manifest_relative_path="ai/configs/index_manifest.json",
        policy_profile=None,
        approved_model_codes=frozenset({"WPUJAC104DWH"}),
        expected_index_version="1.0.0",
        expected_chunk_count=7,
        expected_chunk_set_sha256=(
            "175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958"
        ),
        expected_document_ids=frozenset(
            {"MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"}
        ),
        activation_scope="PUBLIC_MVP",
    ),
    "three_model_integration": RagRuntimeProfile(
        name="three_model_integration",
        manifest_relative_path="ai/configs/index_manifest_3model.json",
        policy_profile="three_model",
        approved_model_codes=frozenset(
            {"WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"}
        ),
        expected_index_version="2.0.0",
        expected_chunk_count=53,
        expected_chunk_set_sha256=(
            "5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304"
        ),
        expected_document_ids=frozenset(
            {
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00",
                "MAN-SKMAGIC-WPU-IAC425-REV02",
                "MAN-SKMAGIC-WPU-IAC606-REV00",
            }
        ),
        activation_scope="INTEGRATION_VERIFICATION_ONLY",
    ),
}


def resolve_rag_runtime_profile(value: str | None = None) -> RagRuntimeProfile:
    """Resolve only a named profile; arbitrary Manifest paths are never accepted."""

    configured = value if value is not None else os.getenv(RUNTIME_PROFILE_ENV)
    profile_name = (configured or DEFAULT_RUNTIME_PROFILE).strip().casefold()
    profile = _PROFILES.get(profile_name)
    if profile is None:
        allowed = ", ".join(sorted(_PROFILES))
        raise RetrievalConfigurationError(
            f"{RUNTIME_PROFILE_ENV}은 다음 허용 Profile 중 하나여야 합니다: {allowed}"
        )
    return profile


def load_runtime_retrieval_policy(
    profile: RagRuntimeProfile,
) -> RuntimeRetrievalPolicy:
    """Load the policy section paired with an allowlisted Runtime profile."""

    try:
        config = yaml.safe_load(RETRIEVAL_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RetrievalConfigurationError("RAG 검색 정책을 읽지 못했습니다.") from exc
    if not isinstance(config, dict):
        raise RetrievalConfigurationError("RAG 검색 정책의 Root 형식이 올바르지 않습니다.")

    metadata = config.get("metadata_filters")
    answerability = config.get("answerability_capability_gate")
    if not isinstance(metadata, dict) or not isinstance(answerability, dict):
        raise RetrievalConfigurationError("활성 RAG 검색 정책이 완전하지 않습니다.")

    if profile.policy_profile is not None:
        prepared_profiles = config.get("prepared_runtime_profiles")
        prepared = (
            prepared_profiles.get(profile.policy_profile)
            if isinstance(prepared_profiles, dict)
            else None
        )
        if not isinstance(prepared, dict):
            raise RetrievalConfigurationError("선택한 RAG 통합검증 정책이 없습니다.")
        if prepared.get("activation_status") != "INTEGRATION_VERIFICATION_ONLY":
            raise RetrievalConfigurationError(
                "3모델 정책이 통합검증 전용 상태로 승인되지 않았습니다."
            )
        if prepared.get("public_runtime_activation") != "HOLD":
            raise RetrievalConfigurationError(
                "3모델 Public Runtime HOLD 계약이 유지되지 않았습니다."
            )
        prepared_metadata = prepared.get("metadata_filters")
        if not isinstance(prepared_metadata, dict):
            raise RetrievalConfigurationError("3모델 Metadata 검색 정책이 없습니다.")
        metadata = prepared_metadata
        answerability = deepcopy(answerability)
        answerability["supported_model_codes"] = prepared.get(
            "supported_model_codes", []
        )
        answerability["supported_generations"] = prepared.get(
            "supported_generations", []
        )

    resolved_models = frozenset(answerability.get("supported_model_codes", []))
    target_models = frozenset(metadata.get("target_models", []))
    if resolved_models != profile.approved_model_codes:
        raise RetrievalConfigurationError(
            "선택한 RAG Profile과 Answerability 제품 범위가 다릅니다."
        )
    target_scope_valid = (
        target_models == profile.approved_model_codes
        if profile.policy_profile is not None
        else profile.approved_model_codes.issubset(target_models)
    )
    if not target_scope_valid:
        raise RetrievalConfigurationError(
            "선택한 RAG Profile과 Metadata 제품 범위가 다릅니다."
        )

    return RuntimeRetrievalPolicy(
        metadata_filters={
            "allowed_generations": list(metadata.get("allowed_generations", [])),
            "excluded_models": list(metadata.get("excluded_models", [])),
            "target_models": list(metadata.get("target_models", [])),
        },
        answerability_gate=deepcopy(answerability),
    )


def validate_runtime_manifest(
    profile: RagRuntimeProfile,
    manifest: IndexManifest,
) -> None:
    """Fail closed when a selected Manifest does not match its profile contract."""

    valid = all(
        (
            manifest.model_name == "BAAI/bge-m3",
            manifest.model_revision
            == "5617a9f61b028005a4858fdac845db406aefb181",
            manifest.dimension == 1024,
            manifest.index_type == "exact_search",
            manifest.index_version == profile.expected_index_version,
            manifest.chunk_count == profile.expected_chunk_count,
            manifest.chunk_set_sha256.casefold()
            == profile.expected_chunk_set_sha256.casefold(),
            frozenset(manifest.document_hashes) == profile.expected_document_ids,
        )
    )
    if not valid:
        raise RetrievalConfigurationError(
            "선택한 RAG Runtime Profile이 Index Manifest와 일치하지 않습니다."
        )


__all__ = [
    "DEFAULT_RUNTIME_PROFILE",
    "RUNTIME_PROFILE_ENV",
    "RagRuntimeProfile",
    "RuntimeRetrievalPolicy",
    "load_runtime_retrieval_policy",
    "resolve_rag_runtime_profile",
    "validate_runtime_manifest",
]
