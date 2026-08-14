"""Official seven-row Backend evidence importer regression tests."""

from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.accounts.models import User
from apps.evidence.models import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentModelScope,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)
from apps.products.models import ProductModel
from apps.evidence.services.canonical_evidence_importer import (
    CanonicalEvidenceImporter,
    DEFAULT_PACKAGE_MANIFEST,
    FIXED_LICENSE_NOTE,
    FIXED_OBJECT_URI,
    FIXED_USAGE_TERMS_URL,
    OFFICIAL_SOURCE_PATH_ENV,
)


pytestmark = pytest.mark.django_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_FIXTURE_ROOT = (
    REPOSITORY_ROOT / "backend" / ".runtime" / "canonical-evidence-tests"
)
RAG_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "rag"
    / "mvp"
    / "rag_verified_sample.jsonl"
)
MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
CHUNK_SET_SHA256 = (
    "175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958"
)


@pytest.fixture
def approved_source_runtime(monkeypatch):
    """Provide a path without storing or printing the QA host's real path."""

    RUNTIME_FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    source_path = (RUNTIME_FIXTURE_ROOT / "approved-source.pdf").resolve()
    source_path.write_bytes(b"synthetic source; file verification has separate tests")
    monkeypatch.setenv(OFFICIAL_SOURCE_PATH_ENV, str(source_path))
    monkeypatch.setattr(
        CanonicalEvidenceImporter,
        "_verify_official_source_file",
        staticmethod(lambda path, *, expected_sha256, expected_size: None),
    )
    return source_path


def _operator() -> User:
    return User.objects.create_user(
        username="DEMO-OPERATOR-001",
        password=None,
        full_name="합성 운영자 001",
        role_code=User.Role.OPERATOR,
        employee_no="DEMO-EMP-OPS-001",
        is_active=True,
        is_synthetic=True,
    )


def _embedding_fixture(*, corrupt_dimension: bool = False):
    chunks = [
        json.loads(line)
        for line in RAG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    chunks.sort(key=lambda row: row["chunk_id"])
    dimension = 3 if corrupt_dimension else 1024
    payload = {
        "schema_version": "1.0.0",
        "status": "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT",
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "dimension": 1024,
        "embedding_dtype": "FLOAT32",
        "index_version": "1.0.0",
        "chunk_set_sha256": CHUNK_SET_SHA256,
        "rows": [
            {
                "chunk_id": chunk["chunk_id"],
                "chunk_text_sha256": sha256(
                    chunk["chunk_text"].encode("utf-8")
                ).hexdigest(),
                "embedding": [float(index + 1) / 1000.0] * dimension,
            }
            for index, chunk in enumerate(chunks)
        ],
    }
    RUNTIME_FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = "bad-dimension" if corrupt_dimension else "valid"
    fixture_path = RUNTIME_FIXTURE_ROOT / f"canonical-embedding-{suffix}.json"
    fixture_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return fixture_path, sha256(fixture_path.read_bytes()).hexdigest()


def _rewrite_fixture(fixture_path: Path, mutate, *, allow_nan: bool = False) -> str:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    mutate(payload)
    fixture_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=allow_nan,
        ),
        encoding="utf-8",
    )
    return sha256(fixture_path.read_bytes()).hexdigest()


def _run_import(
    fixture_path: Path,
    fixture_hash: str,
    *,
    apply: bool,
    stdout=None,
):
    arguments = [
        "--embedding-fixture",
        str(fixture_path),
        "--embedding-fixture-sha256",
        fixture_hash,
        "--verified-by",
        "DEMO-OPERATOR-001",
    ]
    if apply:
        arguments.append("--apply")
        if connection.vendor == "postgresql":
            arguments.extend(
                [
                    "--confirm-database",
                    connection.settings_dict["NAME"],
                ]
            )
    call_command("import_ai_canonical_evidence", *arguments, stdout=stdout)


def _counts() -> dict[str, int]:
    return {
        "batches": IngestionBatch.objects.count(),
        "documents": SourceDocument.objects.count(),
        "pages": DocumentPage.objects.count(),
        "scopes": DocumentModelScope.objects.count(),
        "chunks": DocumentChunk.objects.count(),
        "embeddings": ChunkEmbedding.objects.count(),
    }


def test_dry_run_validates_complete_package_without_persisting(
    approved_source_runtime,
):
    del approved_source_runtime
    attributes = (REPOSITORY_ROOT / ".gitattributes").read_text(
        encoding="utf-8"
    ).splitlines()
    canonical_paths = (
        "ai/configs/canonical_evidence_identity.json",
        "ai/configs/index_manifest.json",
    )
    for relative_path in canonical_paths:
        assert f"{relative_path} text eol=lf" in attributes
        assert b"\r" not in (REPOSITORY_ROOT / relative_path).read_bytes()

    _operator()
    fixture_path, fixture_hash = _embedding_fixture()
    fixture_before = fixture_path.read_bytes()

    _run_import(fixture_path, fixture_hash, apply=False)

    assert _counts() == {
        "batches": 0,
        "documents": 0,
        "pages": 0,
        "scopes": 0,
        "chunks": 0,
        "embeddings": 0,
    }
    assert ProductModel.objects.count() == 0
    assert fixture_path.read_bytes() == fixture_before


def test_apply_creates_exact_official_lineage_and_replay_is_noop(
    approved_source_runtime,
):
    del approved_source_runtime
    _operator()
    fixture_path, fixture_hash = _embedding_fixture()

    first_output = StringIO()
    _run_import(fixture_path, fixture_hash, apply=True, stdout=first_output)

    assert _counts() == {
        "batches": 1,
        "documents": 1,
        "pages": 3,
        "scopes": 1,
        "chunks": 7,
        "embeddings": 7,
    }
    product = ProductModel.objects.get(model_code="WPUJAC104DWH")
    assert product.generation_code == "D"
    assert product.is_supported_mvp is True
    document = SourceDocument.objects.get()
    assert document.document_code == (
        "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"
    )
    assert document.sha256_hash == (
        "0c6b94af53f23211f5fe542cb7712109e4a769a6f42ed758da7792fc62e44b2c"
    )
    assert document.usage_terms_url == FIXED_USAGE_TERMS_URL
    assert document.official_source_url != document.usage_terms_url
    assert document.license_note == FIXED_LICENSE_NOTE
    assert document.original_file_uri == FIXED_OBJECT_URI
    assert document.file_name == (
        "0c6b94af53f23211f5fe542cb7712109e4a769a6f42ed758da7792fc62e44b2c.pdf"
    )
    assert document.status_code == "APPROVED"
    assert document.dataset_scope_code == SourceDocument.DatasetScope.MVP
    assert document.ingestion_batch.status_code == IngestionBatch.Status.SUCCEEDED
    assert list(
        DocumentPage.objects.order_by("page_no").values_list(
            "page_no", flat=True
        )
    ) == [37, 38, 39]
    assert set(
        DocumentChunk.objects.values_list(
            "metadata__canonical_chunk_id", flat=True
        )
    ) == {
        json.loads(line)["chunk_id"]
        for line in RAG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert (
        DocumentChunk.objects.values("page__document_id").distinct().count()
        == 1
    )
    timestamps = {
        model.__name__: list(
            model.objects.order_by("pk").values_list(
                "pk", "created_at", "updated_at"
            )
        )
        for model in (
            IngestionBatch,
            SourceDocument,
            DocumentPage,
            DocumentModelScope,
            DocumentChunk,
            ChunkEmbedding,
        )
    }

    replay_output = StringIO()
    _run_import(fixture_path, fixture_hash, apply=True, stdout=replay_output)

    assert _counts() == {
        "batches": 1,
        "documents": 1,
        "pages": 3,
        "scopes": 1,
        "chunks": 7,
        "embeddings": 7,
    }
    assert timestamps == {
        model.__name__: list(
            model.objects.order_by("pk").values_list(
                "pk", "created_at", "updated_at"
            )
        )
        for model in (
            IngestionBatch,
            SourceDocument,
            DocumentPage,
            DocumentModelScope,
            DocumentChunk,
            ChunkEmbedding,
        )
    }
    assert "source_verified=true" in first_output.getvalue()
    assert "updated=[products:0" in first_output.getvalue()
    assert "created=[products:0,batches:0,documents:0" in replay_output.getvalue()
    assert "updated=[products:0" in replay_output.getvalue()
    assert "unchanged=[products:1,batches:1,documents:1" in replay_output.getvalue()


def test_invalid_embedding_fixture_fails_closed_without_writes(
    approved_source_runtime,
):
    del approved_source_runtime
    _operator()
    fixture_path, fixture_hash = _embedding_fixture(corrupt_dimension=True)

    with pytest.raises(CommandError, match="1024 values"):
        _run_import(fixture_path, fixture_hash, apply=True)

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("wrong_schema_version", "schema_version does not match"),
        ("wrong_status", "status does not match"),
        ("missing_dtype", "root fields do not match contract v1"),
        ("wrong_dtype", "embedding_dtype does not match"),
        ("wrong_order", "chunk_id ascending order"),
    ],
)
def test_embedding_fixture_contract_mismatch_fails_closed(
    approved_source_runtime,
    case,
    message,
):
    del approved_source_runtime
    _operator()
    fixture_path, _fixture_hash = _embedding_fixture()

    def mutate(payload):
        if case == "wrong_schema_version":
            payload["schema_version"] = "2.0.0"
        elif case == "wrong_status":
            payload["status"] = "READY"
        elif case == "missing_dtype":
            payload.pop("embedding_dtype")
        elif case == "wrong_dtype":
            payload["embedding_dtype"] = "FLOAT64"
        else:
            payload["rows"].reverse()

    fixture_hash = _rewrite_fixture(fixture_path, mutate)

    with pytest.raises(CommandError, match=message):
        _run_import(fixture_path, fixture_hash, apply=True)

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


@pytest.mark.parametrize("serialization", ["pretty", "trailing-newline"])
def test_embedding_fixture_rejects_noncanonical_json_bytes_without_writes(
    approved_source_runtime,
    serialization,
):
    del approved_source_runtime
    _operator()
    fixture_path, _fixture_hash = _embedding_fixture()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if serialization == "pretty":
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
    else:
        serialized = fixture_path.read_bytes() + b"\n"
    fixture_path.write_bytes(serialized)

    with pytest.raises(CommandError, match="canonical compact sorted UTF-8 JSON"):
        _run_import(
            fixture_path,
            sha256(serialized).hexdigest(),
            apply=False,
        )

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


@pytest.mark.parametrize("scope", ["root", "row"])
def test_embedding_fixture_rejects_extra_fields_without_writes(
    approved_source_runtime,
    scope,
):
    del approved_source_runtime
    _operator()
    fixture_path, _fixture_hash = _embedding_fixture()

    def mutate(payload):
        if scope == "root":
            payload["unexpected"] = "forbidden"
        else:
            payload["rows"][0]["unexpected"] = "forbidden"

    fixture_hash = _rewrite_fixture(fixture_path, mutate)

    with pytest.raises(CommandError, match="fields do not match contract v1"):
        _run_import(fixture_path, fixture_hash, apply=False)

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


@pytest.mark.parametrize(
    ("invalid_value", "message"),
    [
        (True, "contains invalid values"),
        ("0.1", "contains invalid values"),
        (float("nan"), "Cannot load canonical embedding fixture"),
        (float("inf"), "Cannot load canonical embedding fixture"),
    ],
)
def test_embedding_fixture_rejects_invalid_json_numbers(
    approved_source_runtime,
    invalid_value,
    message,
):
    del approved_source_runtime
    _operator()
    fixture_path, _fixture_hash = _embedding_fixture()

    def mutate(payload):
        payload["rows"][0]["embedding"][0] = invalid_value

    fixture_hash = _rewrite_fixture(fixture_path, mutate, allow_nan=True)

    with pytest.raises(CommandError, match=message):
        _run_import(fixture_path, fixture_hash, apply=True)

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


def test_embedding_fixture_rejects_non_nfc_source_without_mutation():
    fixture_path, _fixture_hash = _embedding_fixture()
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    manifest = json.loads(DEFAULT_PACKAGE_MANIFEST.read_text(encoding="utf-8"))
    chunks = [
        json.loads(line)
        for line in RAG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    chunks.sort(key=lambda row: row["chunk_id"])
    chunks[0] = {**chunks[0], "chunk_text": "e\u0301"}

    with pytest.raises(CommandError, match="already be NFC normalized"):
        CanonicalEvidenceImporter()._validate_embedding_fixture(
            fixture=fixture,
            manifest=manifest,
            chunks=chunks,
        )


def test_db_replay_vector_tolerance_is_one_e_minus_six():
    importer = CanonicalEvidenceImporter()

    assert importer._vectors_equal([0.0, 1.0], [0.0000005, 0.9999995]) is True
    assert importer._vectors_equal([0.0, 1.0], [0.0000011, 1.0]) is False


def test_late_persistence_failure_rolls_back_entire_package(
    monkeypatch,
    approved_source_runtime,
):
    del approved_source_runtime
    _operator()
    fixture_path, fixture_hash = _embedding_fixture()
    original_save = ChunkEmbedding.save
    calls = 0

    def fail_on_last_embedding(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 7:
            raise RuntimeError("forced late fixture failure")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(ChunkEmbedding, "save", fail_on_last_embedding)

    with pytest.raises(RuntimeError, match="forced late fixture failure"):
        _run_import(fixture_path, fixture_hash, apply=True)

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("usage_terms_url", None, "usage_terms_url must be non-empty"),
        ("usage_terms_url", "", "usage_terms_url must be non-empty"),
        ("usage_terms_url", "   ", "usage_terms_url must be non-empty"),
        ("license_note", None, "license_note must be non-empty"),
        ("license_note", "", "license_note must be non-empty"),
        ("license_note", "   ", "license_note must be non-empty"),
        ("original_file_uri", None, "original_file_uri must be non-empty"),
        ("original_file_uri", "", "original_file_uri must be non-empty"),
        ("original_file_uri", "   ", "original_file_uri must be non-empty"),
        (
            "usage_terms_url",
            "https://www.skmagic.com/customer/indexManual",
            "not the fixed HTTPS URL",
        ),
        (
            "usage_terms_url",
            "http://www.skmagic.com/introduce/terms/termsService?tabId=tabStieTerms",
            "not the fixed HTTPS URL",
        ),
        (
            "usage_terms_url",
            "https://user:password@www.skmagic.com/introduce/terms/termsService",
            "not the fixed HTTPS URL",
        ),
        (
            "original_file_uri",
            "C:\\Users\\qa\\Downloads\\manual.pdf",
            "not the fixed object key",
        ),
        (
            "original_file_uri",
            "object://other-source/mvp/manual.pdf",
            "not the fixed object key",
        ),
        (
            "original_file_uri",
            f"{FIXED_OBJECT_URI}?download=1",
            "not the fixed object key",
        ),
        (
            "original_file_uri",
            FIXED_OBJECT_URI.replace("/mvp/", "/mvp/../"),
            "not the fixed object key",
        ),
        (
            "original_file_uri",
            "https://example.com/manual.pdf",
            "not the fixed object key",
        ),
    ],
)
def test_source_metadata_is_fail_closed(key, value, message):
    source = {
        "usage_terms_url": FIXED_USAGE_TERMS_URL,
        "license_note": FIXED_LICENSE_NOTE,
        "original_file_uri": FIXED_OBJECT_URI,
    }
    source[key] = value

    with pytest.raises(CommandError, match=message):
        CanonicalEvidenceImporter()._validate_source_metadata(source)


def test_source_metadata_accepts_only_the_fixed_values():
    CanonicalEvidenceImporter()._validate_source_metadata(
        {
            "usage_terms_url": FIXED_USAGE_TERMS_URL,
            "license_note": FIXED_LICENSE_NOTE,
            "original_file_uri": FIXED_OBJECT_URI,
        }
    )


@pytest.mark.parametrize(
    "missing_key",
    ["usage_terms_url", "license_note", "original_file_uri"],
)
def test_source_metadata_rejects_missing_keys(missing_key):
    source = {
        "usage_terms_url": FIXED_USAGE_TERMS_URL,
        "license_note": FIXED_LICENSE_NOTE,
        "original_file_uri": FIXED_OBJECT_URI,
    }
    source.pop(missing_key)

    with pytest.raises(CommandError, match=f"{missing_key} must be non-empty"):
        CanonicalEvidenceImporter()._validate_source_metadata(source)


def test_runtime_source_path_requires_process_only_absolute_path():
    importer = CanonicalEvidenceImporter()
    with pytest.raises(CommandError, match=OFFICIAL_SOURCE_PATH_ENV):
        importer._runtime_source_path({})
    with pytest.raises(CommandError, match="must be absolute"):
        importer._runtime_source_path({OFFICIAL_SOURCE_PATH_ENV: "manual.pdf"})

    expected = (RUNTIME_FIXTURE_ROOT / "manual.pdf").resolve()
    assert importer._runtime_source_path(
        {OFFICIAL_SOURCE_PATH_ENV: str(expected)}
    ) == expected


def test_official_source_file_must_exist_and_match_size_and_hash():
    RUNTIME_FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    source_path = (RUNTIME_FIXTURE_ROOT / "secret-local-source.pdf").resolve()
    source_bytes = b"approved source bytes"
    source_path.write_bytes(source_bytes)
    source_stat_before = source_path.stat()
    importer = CanonicalEvidenceImporter()

    importer._verify_official_source_file(
        source_path,
        expected_sha256=sha256(source_bytes).hexdigest(),
        expected_size=len(source_bytes),
    )
    assert source_path.read_bytes() == source_bytes
    assert source_path.stat().st_mtime_ns == source_stat_before.st_mtime_ns

    with pytest.raises(CommandError, match="size does not match") as size_error:
        importer._verify_official_source_file(
            source_path,
            expected_sha256=sha256(source_bytes).hexdigest(),
            expected_size=len(source_bytes) + 1,
        )
    assert str(source_path) not in str(size_error.value)

    with pytest.raises(CommandError, match="SHA-256 does not match") as hash_error:
        importer._verify_official_source_file(
            source_path,
            expected_sha256="0" * 64,
            expected_size=len(source_bytes),
        )
    assert str(source_path) not in str(hash_error.value)

    missing_path = (RUNTIME_FIXTURE_ROOT / "missing-secret-source.pdf").resolve()
    with pytest.raises(CommandError, match="is unavailable") as missing_error:
        importer._verify_official_source_file(
            missing_path,
            expected_sha256="0" * 64,
            expected_size=1,
        )
    assert str(missing_path) not in str(missing_error.value)
    assert missing_error.value.__cause__ is None


def test_missing_runtime_source_fails_before_database_lookup(monkeypatch):
    fixture_path, fixture_hash = _embedding_fixture()
    monkeypatch.delenv(OFFICIAL_SOURCE_PATH_ENV, raising=False)

    with pytest.raises(CommandError, match=OFFICIAL_SOURCE_PATH_ENV):
        _run_import(fixture_path, fixture_hash, apply=False)

    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0


def test_runtime_source_hash_mismatch_fails_before_database_lookup(monkeypatch):
    fixture_path, fixture_hash = _embedding_fixture()
    source_path = (RUNTIME_FIXTURE_ROOT / "wrong-official-source.pdf").resolve()
    source_path.write_bytes(b"0" * 5_131_906)
    monkeypatch.setenv(OFFICIAL_SOURCE_PATH_ENV, str(source_path))

    def database_lookup_must_not_run(*args, **kwargs):
        raise AssertionError("database lookup ran before source verification")

    monkeypatch.setattr(User.objects, "get", database_lookup_must_not_run)
    with pytest.raises(CommandError, match="SHA-256 does not match") as error:
        _run_import(fixture_path, fixture_hash, apply=False)

    assert str(source_path) not in str(error.value)
    assert not any(_counts().values())
    assert ProductModel.objects.count() == 0
