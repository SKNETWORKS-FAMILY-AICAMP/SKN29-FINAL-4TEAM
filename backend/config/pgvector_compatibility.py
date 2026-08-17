"""Backend가 검증한 PostgreSQL pgvector 서버 호환 정책."""

from __future__ import annotations


PREFERRED_PGVECTOR_VERSION = "0.8.6"
SUPPORTED_PGVECTOR_VERSIONS = (
    "0.8.2",
    PREFERRED_PGVECTOR_VERSION,
)


def is_supported_pgvector_version(version: object) -> bool:
    """명시적으로 검증한 서버 Extension 버전만 허용한다."""

    return isinstance(version, str) and version in SUPPORTED_PGVECTOR_VERSIONS
