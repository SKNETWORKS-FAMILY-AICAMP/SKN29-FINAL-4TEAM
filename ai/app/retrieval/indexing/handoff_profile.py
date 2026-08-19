"""Data Owner가 인계한 RAG Consumer Profile 해석기."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RagHandoffProfile:
    """AI 인덱싱·평가에서 사용하는 RAG 인계 프로필의 안전한 Projection."""

    name: str
    readiness: str
    contract_dependency: str
    ingest_role: str
    ingest_path: Path
    evaluation_path: Path | None
    evidence_groups_path: Path | None
    supported_products_path: Path | None
    handoff_manifest_path: Path | None
    required_pre_score_filter: str | None
    expected_counts: dict[str, int]

    @property
    def candidate_only(self) -> bool:
        return self.ingest_role == "INGEST_CANDIDATE"


def _repository_root(repository_root: Path | None = None) -> Path:
    return repository_root or Path(__file__).resolve().parents[4]


def _safe_data_path(data_root: Path, relative_path: str) -> Path:
    candidate = (data_root / relative_path).resolve()
    if not candidate.is_relative_to(data_root.resolve()):
        raise ValueError("RAG 인계 Profile 경로가 data 디렉토리를 벗어났습니다.")
    if not candidate.is_file():
        raise FileNotFoundError(f"RAG 인계 파일이 없습니다: {candidate}")
    return candidate


def load_rag_handoff_profile(
    profile_name: str,
    *,
    repository_root: Path | None = None,
) -> RagHandoffProfile:
    """`consumer_profiles.json`에서 AI가 소비할 RAG 프로필을 로드한다."""

    root = _repository_root(repository_root)
    data_root = root / "data"
    definitions_path = data_root / "config" / "handoff" / "consumer_profiles.json"
    definitions = json.loads(definitions_path.read_text(encoding="utf-8"))
    try:
        raw_profile = definitions["profiles"][profile_name]
    except KeyError as exc:
        raise ValueError(f"알 수 없는 RAG 인계 Profile입니다: {profile_name}") from exc

    items = raw_profile.get("items", [])
    ingest_items = [
        item for item in items if item.get("role") in {"INGEST", "INGEST_CANDIDATE"}
    ]
    if len(ingest_items) != 1:
        raise ValueError("RAG 인계 Profile에는 적재 입력이 정확히 하나여야 합니다.")

    def item_path(role: str, *, suffix: str | None = None) -> Path | None:
        matches = [
            item
            for item in items
            if item.get("role") == role
            and (suffix is None or item.get("path", "").endswith(suffix))
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError(f"RAG 인계 Profile의 {role} 항목이 중복됐습니다.")
        return _safe_data_path(data_root, matches[0]["path"])

    selection = raw_profile.get("selection", {})
    required_filter = selection.get("required_pre_score_filter")
    if profile_name == "rag-expansion" and required_filter != "exact_sales_code":
        raise ValueError("rag-expansion은 exact_sales_code 선필터가 필요합니다.")

    ingest_item = ingest_items[0]
    return RagHandoffProfile(
        name=profile_name,
        readiness=raw_profile["readiness"],
        contract_dependency=raw_profile["contract_dependency"],
        ingest_role=ingest_item["role"],
        ingest_path=_safe_data_path(data_root, ingest_item["path"]),
        evaluation_path=item_path("EVALUATION_CONTRACT"),
        evidence_groups_path=item_path(
            "REFERENCE",
            suffix="rag_evidence_groups_3model_v1.jsonl",
        ),
        supported_products_path=item_path(
            "REFERENCE",
            suffix="supported_products.json",
        ),
        handoff_manifest_path=item_path("MANIFEST"),
        required_pre_score_filter=required_filter,
        expected_counts={
            key: int(value)
            for key, value in selection.get("expected_counts", {}).items()
        },
    )
