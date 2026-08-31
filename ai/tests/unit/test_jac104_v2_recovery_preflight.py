"""Readonly identity and Provider-free recovery CLI regressions; no real DB."""

from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import psycopg
import pytest

from ai.app.common.protected_database import ProtectedDatabaseOperationError
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.runtime import RetrievalConfigurationError
from ai.app.retrieval.runtime_profile import (
    JAC104_V2_RECOVERY_PROFILE,
    resolve_rag_runtime_profile,
)
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.retrieval.verification.index_readiness import (
    IndexReadinessError,
    ReadonlyIndexRow,
    validate_readonly_index,
)
from ai.scripts import verify_jac104_v2_recovery as gate


@pytest.fixture
def index():
    profile = resolve_rag_runtime_profile(JAC104_V2_RECOVERY_PROFILE)
    manifest = IndexManifest.load_manifest(str(profile.manifest_path))
    identity = json.loads(gate.IDENTITY_PATH.read_text(encoding="utf-8"))
    chunks = {chunk.chunk_id: chunk for chunk in
              ChunkLoader.from_handoff_profile("rag-expansion").load_verified_chunks()}
    rows = []
    for item in identity["chunks"]:
        chunk = chunks[item["chunk_id"]].model_copy(update={
            "runtime_eligible": True,
            "record_type": None,
            "topic_code": None,
            "safe_actions": [],
            "embedding_model": manifest.model_name,
            "embedding_model_revision": manifest.model_revision,
            "index_version": manifest.index_version,
            "chunk_set_sha256": manifest.chunk_set_sha256.lower(),
            "similarity_score": 0.9,
        })
        chunks[chunk.chunk_id] = chunk
        metadata = chunk.model_dump(exclude={"content", "similarity_score", "chunk_id",
                                             "record_type", "topic_code", "runtime_eligible"})
        rows.append(ReadonlyIndexRow(
            chunk_id=chunk.chunk_id, model_code=chunk.model_code,
            product_generation=chunk.product_generation,
            verification_status=chunk.verification_status, allowed_use=chunk.allowed_use,
            dimension=1024, content_sha256=item["chunk_text_sha256"].lower(), metadata=metadata,
        ))
    return SimpleNamespace(profile=profile, manifest=manifest, identity=identity,
                           rows=rows, chunks=chunks)


def _validate(index, *, rows=None, identity=None):
    return validate_readonly_index(index.profile, index.manifest,
                                   index.identity if identity is None else identity,
                                   index.rows if rows is None else rows)


def test_full_53_row_identity_is_separate_from_15_row_public_scope(index):
    report = _validate(index)
    assert report["index_row_count"] == 53
    assert report["model_row_counts"] == {"WPUJAC104DWH": 15,
                                          "WPUIAC425SNW": 19, "WPUIAC606SNW": 19}
    assert report["approved_model_codes"] == ["WPUJAC104DWH"]
    assert report["approved_model_row_count"] == 15


@pytest.mark.parametrize("kind", ["empty", "missing", "extra", "duplicate", "unknown"])
def test_row_count_alone_never_establishes_canonical_identity(index, kind):
    rows = list(index.rows)
    if kind == "empty":
        rows = []
    elif kind == "missing":
        rows.pop()
    elif kind == "extra":
        rows.append(rows[0])
    elif kind == "duplicate":
        rows[0] = rows[1]
    else:
        rows[0] = replace(rows[0], chunk_id="UNKNOWN-CHILD")
    with pytest.raises(IndexReadinessError):
        _validate(index, rows=rows)


@pytest.mark.parametrize("field,value", [
    ("dimension", 512), ("model_code", "WPUJAC104DWH"),
    ("product_generation", "S"), ("allowed_use", False),
    ("verification_status", "unverified"), ("content_sha256", "0" * 64),
])
def test_wrong_db_columns_fail_closed(index, field, value):
    rows = [replace(index.rows[0], **{field: value}), *index.rows[1:]]
    with pytest.raises(IndexReadinessError):
        _validate(index, rows=rows)


@pytest.mark.parametrize("field,value", [
    ("index_version", "1.0.0"), ("chunk_set_sha256", "0" * 64),
    ("chunk_set_sha256", "not-a-hash"), ("source_hash", "0" * 64),
    ("embedding_model", "other-model"), ("embedding_model_revision", "wrong-revision"),
    ("model_code", "WPUJAC104DWH"), ("product_generation", "S"),
    ("document_id", "OTHER-DOCUMENT"), ("page_refs", [999]),
    ("verification_status", "unverified"), ("allowed_use", False),
    ("runtime_eligible", False), ("runtime_eligible", "true"),
    ("record_type", "PARENT"), ("record_type", "SOURCE_PAGE"),
    ("retrieval_role", "CONTEXT_ONLY"), ("retrieval_role", None),
    ("evidence_group_id", ""), ("source_variant_id", None), ("parent_id", " "),
])
def test_mixed_or_invalid_metadata_fail_closed(index, field, value):
    metadata = {**index.rows[0].metadata, field: value}
    rows = [replace(index.rows[0], metadata=metadata), *index.rows[1:]]
    with pytest.raises(IndexReadinessError):
        _validate(index, rows=rows)


def test_default_mvp_cannot_pass_against_the_v2_view(index):
    with pytest.raises(RetrievalConfigurationError):
        validate_readonly_index(resolve_rag_runtime_profile("mvp"), index.manifest,
                                index.identity, index.rows)


def test_canonical_source_identity_cannot_be_silently_changed(index):
    identity = {**index.identity, "chunk_set_sha256": "0" * 64}
    with pytest.raises(IndexReadinessError, match="CANONICAL_MANIFEST_MISMATCH"):
        _validate(index, identity=identity)


def test_duplicate_canonical_definitions_are_rejected(index):
    identity = {**index.identity, "chunks": [index.identity["chunks"][1],
                                            *index.identity["chunks"][1:]]}
    with pytest.raises(IndexReadinessError, match="CANONICAL_IDENTITY_INVALID"):
        _validate(index, identity=identity)


@pytest.mark.parametrize("readonly", ["on", "off"])
def test_database_inspection_is_bounded_readonly_and_never_fetches_source_text(
    monkeypatch, index, readonly,
):
    statements = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            assert connection.read_only is True
            statements.append((sql, params))

        def fetchone(self):
            return {"default_transaction_read_only": readonly}

        def fetchall(self):
            return [asdict(row) for row in index.rows]

    class Connection:
        read_only = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self, **kwargs):
            return Cursor()

    connection = Connection()
    monkeypatch.setattr(gate.psycopg, "connect", lambda *args, **kwargs: connection)
    if readonly == "off":
        with pytest.raises(IndexReadinessError, match="READONLY_ROLE_CONFIGURATION_REQUIRED"):
            gate._read_index_rows("unused", maximum_rows=54)
        assert len(statements) == 2
        return
    assert gate._read_index_rows("unused", maximum_rows=54) == index.rows
    assert len(statements) == 3
    sql, params = statements[-1]
    assert "FROM backend_ai_rag_chunks_v1" in sql
    assert "sha256(convert_to(content, 'UTF8'))" in sql
    assert "LIMIT %s" in sql
    assert params == (54,)
    assert "content" not in asdict(index.rows[0])


def test_database_driver_exception_is_sanitized_without_an_exception_context(monkeypatch):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError("PROTECTED_CONNECTION_STRING")

    monkeypatch.setattr(gate.psycopg, "connect", fail)
    with pytest.raises(ProtectedDatabaseOperationError) as caught:
        gate._read_index_rows("unused", maximum_rows=54)
    assert "PROTECTED_CONNECTION_STRING" not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.fixture
def cli(monkeypatch, index):
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", JAC104_V2_RECOVERY_PROFILE)
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", gate.EXPECTED_TABLE)
    monkeypatch.setenv("AI_VECTOR_DSN", "PROTECTED_CONNECTION_STRING")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", index.manifest.model_revision)
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "direct")
    db_calls = []

    def read_rows(*args, **kwargs):
        db_calls.append("readonly")
        return index.rows

    class Embedding:
        model_name = index.manifest.model_name
        model_revision = index.manifest.model_revision
        dimension = 1024
        calls = 0
        warmup_calls = 0
        query = ""

        def warmup(self):
            self.warmup_calls += 1

        def embed_query(self, text):
            self.calls += 1
            self.query = text
            return [0.0] * self.dimension

    class Store:
        def search(self, vector, *, model_code, product_generation, top_k):
            assert model_code == "WPUJAC104DWH"
            if "미지근" in embedding.query:
                key = "CHILD-WPUJAC104DWH-P037-COLD-NORMAL-001"
            elif "냄새" in embedding.query:
                key = "CHILD-WPUJAC104DWH-P038-TASTE-ODOR-001"
            else:
                key = "CHILD-WPUJAC104DWH-P038-LOW-FLOW-001"
            return [index.chunks[key]]

    embedding = Embedding()
    service = VectorSearchService(embedding, Store(), index_manifest=index.manifest)
    monkeypatch.setattr(gate, "_read_index_rows", read_rows)
    monkeypatch.setattr(gate.PipelineRouter, "_configured_search_service", lambda: service)
    return SimpleNamespace(index=index, embedding=embedding, service=service, db_calls=db_calls)


def test_cli_reports_retrieval_only_not_public_activation(cli, capsys):
    assert gate.main() == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["status"] == "PASS"
    assert report["gate_scope"] == "JAC104_RETRIEVAL_ONLY"
    assert report["index_row_count"] == 53
    assert report["approved_model_row_count"] == 15
    assert report["blocked_product_count"] == 2
    assert len(report["retrieval_probes"]) == 3
    assert report["guidance_provider_calls"] == report["backend_writes"] == 0
    assert report["schema_ddl_executed"] is False
    assert report["three_model_public_activation"] == "HOLD"
    assert report["operation_activation"] == "HOLD_PENDING_QA_AND_RELEASE_APPROVAL"
    assert cli.embedding.calls == 3
    assert cli.embedding.warmup_calls == 1
    assert "PROTECTED_CONNECTION_STRING" not in output.out + output.err
    for row in cli.index.rows:
        assert cli.index.chunks[row.chunk_id].content not in output.out


@pytest.mark.parametrize("name,value", [
    ("AI_RAG_RUNTIME_PROFILE", None), ("AI_RAG_RUNTIME_PROFILE", "mvp"),
    ("AI_RAG_RUNTIME_PROFILE", "three_model_integration"),
    ("AI_RAG_RUNTIME_PROFILE", "unknown"),
    ("AI_VECTOR_TABLE_NAME", "other_view"), ("AI_VECTOR_DSN", ""),
    ("AI_EMBEDDING_REVISION", "wrong-revision"), ("AI_RETRIEVAL_TRANSPORT", "mcp"),
])
def test_cli_invalid_environment_stops_before_db_and_embedding(cli, monkeypatch, capsys, name, value):
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    assert gate.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "BLOCKED"
    assert report["operation_activation"] == "HOLD"
    assert cli.db_calls == []
    assert cli.embedding.calls == cli.embedding.warmup_calls == 0


def test_cli_view_mismatch_stops_before_embedding(cli, capsys):
    cli.index.rows[0] = replace(cli.index.rows[0], dimension=512)
    assert gate.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == "READONLY_INDEX_IDENTITY"
    assert report["reason_code"] == "VIEW_INDEX_IDENTITY_MISMATCH"
    assert cli.embedding.calls == cli.embedding.warmup_calls == 0


def test_cli_requires_semantically_matching_evidence_not_just_any_hit(cli, monkeypatch, capsys):
    unrelated = cli.index.chunks["CHILD-WPUJAC104DWH-P037-NOISE-001"]
    monkeypatch.setattr(cli.service.vector_store, "search", lambda *args, **kwargs: [unrelated])
    assert gate.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["reason_code"] == "JAC104_RETRIEVAL_PROBE_FAILED"


def test_cli_never_prints_unexpected_exception_messages(cli, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise RuntimeError("PROTECTED_CONNECTION_STRING protected-source-text")

    monkeypatch.setattr(gate, "_read_index_rows", fail)
    assert gate.main() == 1
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["reason_code"] == "JAC104_RECOVERY_REQUIREMENTS_NOT_MET"
    assert "PROTECTED_CONNECTION_STRING" not in output.out + output.err
    assert "protected-source-text" not in output.out + output.err
