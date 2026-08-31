"""Provider-free JAC104 recovery preflight; never enables public operation.

Run in an approved one-off process using the candidate image and its protected
readonly environment. No expansion dataset, Git checkout, DDL or DB write is
required. CI/startup integration remains owned by the deployment/runtime owners.
"""

from __future__ import annotations

import json
import os
import platform
from typing import Any

import psycopg
from psycopg.rows import dict_row

from ai.app.common.protected_database import run_protected_database_operation
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.runtime_profile import (
    JAC104_V2_RECOVERY_PROFILE,
    REPOSITORY_ROOT,
    load_runtime_retrieval_policy,
    resolve_rag_runtime_profile,
    validate_runtime_manifest,
)
from ai.app.retrieval.verification.index_readiness import (
    IndexReadinessError,
    ReadonlyIndexRow,
    validate_readonly_index,
)


EXPECTED_TABLE = "backend_ai_rag_chunks_v1"
MODEL_CODE = "WPUJAC104DWH"
IDENTITY_PATH = REPOSITORY_ROOT / "ai/configs/canonical_evidence_identity_3model.json"
PROBES = (
    ("COLD_TEMPERATURE", "냉수가 안 차갑고 미지근합니다", frozenset({
        "CHILD-WPUJAC104DWH-P037-COLD-NORMAL-001",
        "CHILD-WPUJAC104DWH-P037-COLD-FAULT-001",
    })),
    ("LOW_FLOW", "정수기 물이 졸졸 나와요.", frozenset({
        "CHILD-WPUJAC104DWH-P038-LOW-FLOW-001",
    })),
    ("TASTE_ODOR", "정수기 물에서 불쾌한 맛과 냄새가 납니다.", frozenset({
        "CHILD-WPUJAC104DWH-P038-TASTE-ODOR-001",
    })),
)


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise IndexReadinessError("REQUIRED_ENVIRONMENT_MISSING")
    return value


def _read_index_rows(dsn: str, *, maximum_rows: int) -> list[ReadonlyIndexRow]:
    def read_rows():
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            connection.read_only = True
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                cursor.execute("SHOW default_transaction_read_only")
                if cursor.fetchone() != {"default_transaction_read_only": "on"}:
                    raise IndexReadinessError("READONLY_ROLE_CONFIGURATION_REQUIRED")
                cursor.execute(
                    """
                    SELECT chunk_id, model_code, product_generation,
                           verification_status, allowed_use, metadata,
                           vector_dims(embedding) AS dimension,
                           encode(sha256(convert_to(content, 'UTF8')), 'hex')
                               AS content_sha256
                    FROM backend_ai_rag_chunks_v1
                    ORDER BY chunk_id
                    LIMIT %s
                    """,
                    (maximum_rows,),
                )
                return cursor.fetchall()

    rows = run_protected_database_operation(
        read_rows,
        public_message="RAG readonly index inspection failed.",
    )
    return [ReadonlyIndexRow(**row) for row in rows]


def _verify_search(manifest: IndexManifest, identity: dict[str, Any]) -> dict[str, Any]:
    # Use the existing production factory; do not create a separate search policy.
    service = PipelineRouter._configured_search_service()
    if service is None or service.index_manifest != manifest:
        raise IndexReadinessError("CONFIGURED_SEARCH_SERVICE_MISMATCH")
    canonical_ids = {item["chunk_id"] for item in identity["chunks"]}
    for model_code, generation in (("WPUIAC425SNW", "IAC425"),
                                   ("WPUIAC606SNW", "IAC606")):
        query = RetrievalQuery(
            query_text=PROBES[0][1], model_code=model_code,
            product_generation=generation,
        )
        if service.execution_path(query) != "POLICY_BLOCK_UNSUPPORTED_MODEL":
            raise IndexReadinessError("UNAPPROVED_PRODUCT_NOT_BLOCKED")
        if service.search(query):
            raise IndexReadinessError("UNAPPROVED_PRODUCT_NOT_BLOCKED")

    service.embedding_client.warmup()
    results = []
    for probe_id, text, required_ids in PROBES:
        query = RetrievalQuery(query_text=text, model_code=MODEL_CODE,
                               product_generation="D", top_k=5)
        if service.execution_path(query) != "PGVECTOR_QUERY":
            raise IndexReadinessError("JAC104_QUERY_POLICY_BLOCKED")
        chunks = service.search(query)
        ids = {chunk.chunk_id for chunk in chunks}
        if not (
            1 <= len(chunks) <= 5
            and ids.issubset(canonical_ids)
            and ids.intersection(required_ids)
            and all(chunk.model_code == MODEL_CODE
                    and service._is_valid_result(chunk, MODEL_CODE) for chunk in chunks)
        ):
            raise IndexReadinessError("JAC104_RETRIEVAL_PROBE_FAILED")
        results.append({"probe_id": probe_id, "hit_count": len(chunks),
                        "expected_evidence_hit": True, "chunk_ids": sorted(ids)})
    return {"retrieval_probes": results, "blocked_product_count": 2}


def main() -> int:
    stage = "ENVIRONMENT"
    try:
        if platform.python_version() != "3.13.13":
            raise IndexReadinessError("PYTHON_VERSION_MISMATCH")
        profile = resolve_rag_runtime_profile(_required_environment("AI_RAG_RUNTIME_PROFILE"))
        if profile.name != JAC104_V2_RECOVERY_PROFILE:
            raise IndexReadinessError("JAC104_RECOVERY_PROFILE_REQUIRED")
        if _required_environment("AI_VECTOR_TABLE_NAME") != EXPECTED_TABLE:
            raise IndexReadinessError("APPROVED_READONLY_VIEW_REQUIRED")
        # An in-process direct probe is not evidence for an MCP deployment.
        if os.getenv("AI_RETRIEVAL_TRANSPORT", "direct").strip().lower() != "direct":
            raise IndexReadinessError("DIRECT_RETRIEVAL_TRANSPORT_REQUIRED")
        dsn = _required_environment("AI_VECTOR_DSN")
        revision = _required_environment("AI_EMBEDDING_REVISION")

        stage = "PROFILE_MANIFEST"
        manifest = IndexManifest.load_manifest(str(profile.manifest_path))
        if manifest is None:
            raise IndexReadinessError("INDEX_MANIFEST_MISSING")
        validate_runtime_manifest(profile, manifest)
        load_runtime_retrieval_policy(profile)
        if revision != manifest.model_revision:
            raise IndexReadinessError("EMBEDDING_REVISION_MISMATCH")
        identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))

        stage = "READONLY_INDEX_IDENTITY"
        rows = _read_index_rows(dsn, maximum_rows=manifest.chunk_count + 1)
        index = validate_readonly_index(profile, manifest, identity, rows)
        stage = "RETRIEVAL_PROBES"
        retrieval = _verify_search(manifest, identity)
    except Exception as exc:
        print(json.dumps({
            "status": "BLOCKED", "stage": stage,
            "reason_code": (exc.reason_code if isinstance(exc, IndexReadinessError)
                            else "JAC104_RECOVERY_REQUIREMENTS_NOT_MET"),
            "operation_activation": "HOLD",
        }))
        return 1

    print(json.dumps({
        "status": "PASS", "gate_scope": "JAC104_RETRIEVAL_ONLY",
        "runtime_profile": profile.name, "activation_scope": profile.activation_scope,
        "python_version": platform.python_version(),
        **index, **retrieval,
        "guidance_provider_calls": 0, "backend_writes": 0,
        "schema_ddl_executed": False,
        "three_model_public_activation": "HOLD",
        "operation_activation": "HOLD_PENDING_QA_AND_RELEASE_APPROVAL",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
