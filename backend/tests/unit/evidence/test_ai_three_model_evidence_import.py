"""Three-model Backend evidence importer and Crosswalk regression tests."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import pytest
from django.core.management.base import CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.evidence.management.commands.sync_ai_canonical_crosswalk import (
    Command as SyncCommand,
)
from apps.evidence.models import (
    AIChunkCrosswalk,
    AIChunkCrosswalkPage,
    ChunkEmbedding,
    DocumentChunk,
    DocumentModelScope,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)
from apps.evidence.services.canonical_evidence_importer import (
    CanonicalEvidenceImporter,
)
from apps.evidence.services.three_model_evidence_importer import (
    DOCUMENT_CONFIG,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    EXPECTED_MODEL_COUNTS,
    INDEX_VERSION,
    SOURCE_PATH,
    ThreeModelEvidenceImporter,
)
from apps.products.models import ProductModel


pytestmark = pytest.mark.django_db
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = REPOSITORY_ROOT / ".runtime" / "backend-ai" / "three-model-import-tests"


def _operator() -> User:
    return User.objects.create_user(
        username="DEMO-OPERATOR-3MODEL",
        password=None,
        full_name="합성 3모델 검증자",
        role_code=User.Role.OPERATOR,
        employee_no="DEMO-EMP-3MODEL",
        is_active=True,
        is_synthetic=True,
    )


def _products() -> None:
    values = (
        ("WPUJAC104DWH", "WPU-JAC104 (D)", "D", True),
        ("WPUIAC425SNW", "WPU-IAC425", "IAC425", False),
        ("WPUIAC606SNW", "WPU-IAC606", "IAC606", False),
    )
    for model_code, model_name, generation, supported in values:
        ProductModel.objects.create(
            model_code=model_code,
            model_name=model_name,
            generation_code=generation,
            manufacturer="SK매직",
            is_active=True,
            is_supported_mvp=supported,
        )


def _source_rows():
    return sorted(
        [
            json.loads(line)
            for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ],
        key=lambda row: row["child_id"],
    )


def _chunk_set_hash(rows) -> str:
    payload = [
        {
            "chunk_id": row["child_id"],
            "source_hash": row["source_file_sha256"],
            "content": row["child_text"],
        }
        for row in rows
    ]
    return sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()


def _write_inputs():
    rows = _source_rows()
    chunk_set_hash = _chunk_set_hash(rows)
    identity = {
        "schema_version": "1.0.0",
        "status": "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING",
        "index_version": INDEX_VERSION,
        "chunk_count": 53,
        "model_chunk_counts": EXPECTED_MODEL_COUNTS,
        "chunk_set_sha256": chunk_set_hash,
        "chunks": [
            {
                "chunk_id": row["child_id"],
                "document_id": row["document_id"],
                "page_refs": row["page_refs"],
                "model_code": row["exact_sales_code"],
                "product_generation": row["product_generation"],
                "verification_status": row["verification_status"],
                "source_file_sha256": row["source_file_sha256"],
                "chunk_text_sha256": row["child_text_sha256"],
            }
            for row in rows
        ],
    }
    index = {
        "model_name": EMBEDDING_MODEL,
        "model_revision": EMBEDDING_REVISION,
        "dimension": EMBEDDING_DIMENSION,
        "index_type": "exact_search",
        "index_version": INDEX_VERSION,
        "chunk_count": 53,
        "chunk_set_sha256": chunk_set_hash,
        "document_hashes": {
            row["document_id"]: row["source_file_sha256"] for row in rows
        },
        "indexed_at": "2026-08-19T00:00:00Z",
    }
    fixture = {
        "schema_version": "1.0.0",
        "status": "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT",
        "model_name": EMBEDDING_MODEL,
        "model_revision": EMBEDDING_REVISION,
        "dimension": EMBEDDING_DIMENSION,
        "embedding_dtype": "FLOAT32",
        "index_version": INDEX_VERSION,
        "chunk_set_sha256": chunk_set_hash,
        "rows": [
            {
                "chunk_id": row["child_id"],
                "chunk_text_sha256": row["child_text_sha256"].lower(),
                "embedding": [float(number + 1) / 1000.0] * EMBEDDING_DIMENSION,
            }
            for number, row in enumerate(rows)
        ],
    }
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    identity_path = RUNTIME_ROOT / "identity.json"
    index_path = RUNTIME_ROOT / "index.json"
    fixture_path = RUNTIME_ROOT / "fixture.json"
    identity_path.write_text(json.dumps(identity, ensure_ascii=False), encoding="utf-8")
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    fixture_path.write_bytes(
        json.dumps(
            fixture,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return (
        identity_path,
        sha256(identity_path.read_bytes()).hexdigest(),
        index_path,
        sha256(index_path.read_bytes()).hexdigest(),
        fixture_path,
        sha256(fixture_path.read_bytes()).hexdigest(),
    )


@pytest.fixture
def package(monkeypatch):
    monkeypatch.setattr(
        CanonicalEvidenceImporter,
        "_verify_official_source_file",
        staticmethod(lambda path, *, expected_sha256, expected_size: None),
    )
    environment = {
        str(config["source_path_env"]): str(
            (RUNTIME_ROOT / f"{config['model_code']}.pdf").resolve()
        )
        for config in DOCUMENT_CONFIG.values()
    }
    inputs = _write_inputs()
    return ThreeModelEvidenceImporter().load_package(
        identity_path=inputs[0],
        identity_sha256=inputs[1],
        index_path=inputs[2],
        index_sha256=inputs[3],
        embedding_fixture_path=inputs[4],
        embedding_fixture_sha256=inputs[5],
        runtime_environment=environment,
    )


def _counts():
    return {
        "batches": IngestionBatch.objects.count(),
        "documents": SourceDocument.objects.count(),
        "pages": DocumentPage.objects.count(),
        "scopes": DocumentModelScope.objects.count(),
        "chunks": DocumentChunk.objects.count(),
        "embeddings": ChunkEmbedding.objects.count(),
    }


def test_load_package_validates_exact_three_model_distribution(package):
    assert len(package.chunks) == 53
    assert Counter(row["exact_sales_code"] for row in package.chunks) == Counter(
        EXPECTED_MODEL_COUNTS
    )
    assert {document_id: sorted(pages) for document_id, pages in package.pages.items()} == {
        "MAN-SKMAGIC-WPU-IAC425-REV02": [5, 43, 44, 45, 46],
        "MAN-SKMAGIC-WPU-IAC606-REV00": [5, 40, 41, 42, 43],
        "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00": [5, 7, 37, 38, 39],
    }


def test_index_manifest_rejects_document_hash_value_drift(package):
    index = dict(package.index)
    index["document_hashes"] = dict(index["document_hashes"])
    index["document_hashes"]["MAN-SKMAGIC-WPU-IAC425-REV02"] = "0" * 64

    with pytest.raises(CommandError, match="document hash values differ"):
        ThreeModelEvidenceImporter()._validate_index(
            index=index,
            identity=package.identity,
        )


def test_apply_replay_and_crosswalk_preserve_new_model_support_hold(package):
    operator = _operator()
    _products()
    importer = ThreeModelEvidenceImporter()

    first = importer.persist(package=package, verifier=operator)

    assert first.created == {
        "batches": 3,
        "documents": 3,
        "pages": 15,
        "scopes": 3,
        "chunks": 53,
        "embeddings": 53,
    }
    assert _counts() == first.created
    assert set(
        ProductModel.objects.filter(is_supported_mvp=False).values_list(
            "model_code", flat=True
        )
    ) == {"WPUIAC425SNW", "WPUIAC606SNW"}

    replay = importer.persist(package=package, verifier=operator)

    assert replay.created == {}
    assert replay.unchanged == {
        "documents": 3,
        "pages": 15,
        "scopes": 3,
        "chunks": 53,
        "embeddings": 53,
    }
    assert _counts() == first.created

    sync = SyncCommand()
    plan = sync._build_plan(identity=package.identity, index=package.index)
    with transaction.atomic():
        applied = sync._apply_plan(
            plan=plan,
            identity=package.identity,
            index=package.index,
            manifest_digest=package.identity_sha256,
            verifier=operator,
        )
    assert applied == {"created": 53, "updated": 0, "unchanged": 0}
    assert AIChunkCrosswalk.objects.filter(is_active=True).count() == 53
    assert AIChunkCrosswalkPage.objects.filter(
        crosswalk__is_active=True
    ).count() == 53

    with transaction.atomic():
        replay_crosswalk = sync._apply_plan(
            plan=plan,
            identity=package.identity,
            index=package.index,
            manifest_digest=package.identity_sha256,
            verifier=operator,
        )
    assert replay_crosswalk == {"created": 0, "updated": 0, "unchanged": 53}


def test_replay_accepts_existing_approved_pages_from_another_reviewer(package):
    first_reviewer = _operator()
    second_reviewer = User.objects.create_user(
        username="DEMO-OPERATOR-3MODEL-2",
        password=None,
        full_name="합성 3모델 재검증자",
        role_code=User.Role.OPERATOR,
        employee_no="DEMO-EMP-3MODEL-2",
        is_active=True,
        is_synthetic=True,
    )
    _products()
    importer = ThreeModelEvidenceImporter()
    importer.persist(package=package, verifier=first_reviewer)

    replay = importer.persist(package=package, verifier=second_reviewer)

    assert replay.created == {}
    assert replay.unchanged["pages"] == 15
    assert set(DocumentPage.objects.values_list("reviewer_id", flat=True)) == {
        first_reviewer.pk
    }


def test_late_embedding_failure_rolls_back_entire_import(monkeypatch, package):
    operator = _operator()
    _products()
    original_save = ChunkEmbedding.save
    calls = 0

    def fail_on_last(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 53:
            raise RuntimeError("forced 53-row failure")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(ChunkEmbedding, "save", fail_on_last)
    with pytest.raises(RuntimeError, match="forced 53-row failure"):
        with transaction.atomic():
            ThreeModelEvidenceImporter().persist(package=package, verifier=operator)

    assert _counts() == {
        "batches": 0,
        "documents": 0,
        "pages": 0,
        "scopes": 0,
        "chunks": 0,
        "embeddings": 0,
    }
    assert ProductModel.objects.count() == 3
