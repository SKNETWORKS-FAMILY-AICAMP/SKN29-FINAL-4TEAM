"""답변용 Child와 문맥·보존 레코드를 검색 단계에서 분리한다."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json

from ..models.retrieved_chunk import RetrievedChunk
from ..runtime import RetrievalConfigurationError
from ..runtime_profile import REPOSITORY_ROOT, resolve_rag_runtime_profile


@lru_cache(maxsize=1)
def _canonical_v2_children() -> dict[str, dict]:
    """Bundled identities, not a prefix heuristic or an expansion-data dependency."""

    profile = resolve_rag_runtime_profile("three_model_integration")
    path = REPOSITORY_ROOT / "ai/configs/canonical_evidence_identity_3model.json"
    try:
        identity = json.loads(path.read_text(encoding="utf-8"))
        children = {item["chunk_id"]: item for item in identity["chunks"]}
        valid = (
            identity["index_version"] == profile.expected_index_version
            and identity["chunk_set_sha256"].casefold()
            == profile.expected_chunk_set_sha256.casefold()
            and len(children) == len(identity["chunks"]) == profile.expected_chunk_count
        )
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise RetrievalConfigurationError("v2 Canonical Child 정체성을 확인하지 못했습니다.")
    return children


def _is_canonical_view_child(chunk: RetrievedChunk) -> bool:
    """Recover only an omitted type on an exact, content-verified v2 Child."""

    profile = resolve_rag_runtime_profile("three_model_integration")
    if (
        chunk.index_version != profile.expected_index_version
        or not isinstance(chunk.chunk_set_sha256, str)
        or chunk.chunk_set_sha256.casefold() != profile.expected_chunk_set_sha256.casefold()
    ):
        return False
    identity = _canonical_v2_children().get(chunk.chunk_id)
    if identity is None:
        return False
    return all((
        chunk.model_code == identity.get("model_code"),
        chunk.product_generation == identity.get("product_generation"),
        chunk.document_id == identity.get("document_id"),
        chunk.page_refs == identity.get("page_refs"),
        chunk.verification_status == "official_verified",
        chunk.allowed_use is True,
        chunk.runtime_eligible is True,
        identity.get("verification_status") == "TEXT_AND_VISUAL_VERIFIED",
        isinstance(chunk.source_hash, str)
        and chunk.source_hash.upper() == identity.get("source_file_sha256"),
        sha256(chunk.content.encode("utf-8")).hexdigest().upper()
        == identity.get("chunk_text_sha256"),
    ))


class SearchCandidateFilter:
    """직접 답변 후보인 Child만 허용한다.

    Public MVP 1.0.0의 기존 7개 레코드는 ``record_type``과
    ``retrieval_role`` 도입 전 적재됐으므로 두 필드가 모두 없는 경우에만
    Legacy 호환을 허용한다. 둘 중 하나라도 명시된 신규 데이터는
    ``CHILD + SEARCH_CANDIDATE``를 모두 충족해야 한다. 단, 공식 Backend View가
    record_type만 생략한 v2 행은 고정 Canonical Child의 제품·페이지·원문 Hash까지
    일치할 때만 호환한다. 명시된 Parent·보존 유형은 절대 덮어쓰지 않는다.
    """

    @staticmethod
    def is_valid_chunk(chunk: RetrievedChunk) -> bool:
        record_type = (
            chunk.record_type.strip().casefold()
            if isinstance(chunk.record_type, str)
            else None
        )
        retrieval_role = (
            chunk.retrieval_role.strip().upper()
            if isinstance(chunk.retrieval_role, str)
            else None
        )
        if record_type is None and retrieval_role is None:
            # v2 records must not fall through the pre-lineage MVP compatibility path.
            return chunk.index_version != "2.0.0"
        if record_type is None and retrieval_role == "SEARCH_CANDIDATE":
            return _is_canonical_view_child(chunk)
        return record_type == "child" and retrieval_role == "SEARCH_CANDIDATE"


__all__ = ["SearchCandidateFilter"]
