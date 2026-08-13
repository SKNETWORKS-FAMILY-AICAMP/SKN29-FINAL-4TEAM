"""Fail-closed importer for the seven approved Backend-AI evidence rows."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from django.core.management.base import CommandError
from django.utils.dateparse import parse_datetime

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


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACKAGE_MANIFEST = (
    REPOSITORY_ROOT
    / "data"
    / "config"
    / "evidence"
    / "backend_ai_canonical_import_v1.json"
)
FIXED_PACKAGE_STATUS = "BACKEND_AI_G1B_IMPORT_PACKAGE_FIXED"
APPROVED_EMBEDDING_FIXTURE_STATUS = (
    "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT"
)
APPROVED_CANONICAL_STATUS = "TEXT_AND_VISUAL_VERIFIED"
EXPECTED_CHUNK_COUNT = 7
OFFICIAL_SOURCE_PATH_ENV = "BACKEND_AI_OFFICIAL_SOURCE_PATH"
EXPECTED_SOURCE_SHA256 = (
    "0c6b94af53f23211f5fe542cb7712109e4a769a6f42ed758da7792fc62e44b2c"
)
FIXED_USAGE_TERMS_URL = (
    "https://www.skmagic.com/introduce/terms/termsService?tabId=tabStieTerms"
)
FIXED_LICENSE_NOTE = (
    "공식 원문 재배포 권한은 확인되지 않았다. 원본은 승인된 내부 "
    "QA·RAG 검증에만 사용하며 Git, 공개 API, 화면 및 로그에 원문 전체를 "
    "노출하지 않는다. 외부 공개 또는 재배포 전 권리자의 약관이나 허가를 "
    "별도로 확인한다."
)
FIXED_OBJECT_URI = (
    "object://official-sources/mvp/"
    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00/"
    f"{EXPECTED_SOURCE_SHA256}.pdf"
)


@dataclass(frozen=True, slots=True)
class CanonicalImportPackage:
    """Validated file package ready for one atomic DB transaction."""

    manifest: dict[str, Any]
    inventory: dict[str, str]
    pages: dict[int, dict[str, Any]]
    chunks: list[dict[str, Any]]
    identity: dict[str, Any]
    index: dict[str, Any]
    embeddings: dict[str, dict[str, Any]]
    embedding_fixture_sha256: str
    source_file_sha256: str


@dataclass(slots=True)
class CanonicalImportResult:
    """Created/unchanged counters returned to the management command."""

    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    unchanged: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, *, was_created: bool) -> None:
        target = self.created if was_created else self.unchanged
        target[key] = target.get(key, 0) + 1

    def summary(self) -> str:
        keys = (
            "products",
            "batches",
            "documents",
            "pages",
            "scopes",
            "chunks",
            "embeddings",
        )
        created = ",".join(f"{key}:{self.created.get(key, 0)}" for key in keys)
        updated = ",".join(f"{key}:{self.updated.get(key, 0)}" for key in keys)
        unchanged = ",".join(
            f"{key}:{self.unchanged.get(key, 0)}" for key in keys
        )
        return (
            f"created=[{created}] updated=[{updated}] "
            f"unchanged=[{unchanged}]"
        )


class CanonicalEvidenceImporter:
    """Validate immutable inputs and persist their official DB lineage."""

    def load_package(
        self,
        *,
        manifest_path: Path,
        embedding_fixture_path: Path,
        embedding_fixture_sha256: str,
        runtime_environment: Mapping[str, str] | None = None,
    ) -> CanonicalImportPackage:
        manifest = self._load_json(manifest_path)
        if manifest.get("schema_version") != "1.0.0":
            raise CommandError("Canonical import schema version is unsupported.")
        if manifest.get("status") != FIXED_PACKAGE_STATUS:
            raise CommandError("Canonical import package status is not fixed.")

        source = self._require_mapping(manifest, "source")
        self._validate_source_metadata(source)
        inventory_path = self._verified_repository_file(
            source.get("inventory_path"), source.get("inventory_sha256")
        )
        pages_path = self._verified_repository_file(
            source.get("manual_pages_path"),
            source.get("manual_pages_sha256"),
        )
        chunks_path = self._verified_repository_file(
            source.get("rag_chunks_path"), source.get("rag_chunks_sha256")
        )
        identity_meta = self._require_mapping(manifest, "identity")
        identity_path = self._verified_repository_file(
            identity_meta.get("path"), identity_meta.get("sha256")
        )
        index_meta = self._require_mapping(manifest, "index")
        index_path = self._verified_repository_file(
            index_meta.get("path"), index_meta.get("sha256")
        )

        inventory = self._load_inventory(
            inventory_path,
            inventory_id=str(source.get("inventory_id") or ""),
        )
        all_pages = self._load_jsonl(pages_path)
        chunks = self._load_jsonl(chunks_path)
        identity = self._load_json(identity_path)
        index = self._load_json(index_path)
        fixture_path = embedding_fixture_path.resolve()
        fixture_digest = self._file_digest(fixture_path)
        if fixture_digest != self._lower_hash(embedding_fixture_sha256):
            raise CommandError("Embedding fixture SHA-256 does not match.")
        fixture = self._load_json(fixture_path)

        reviewed_page_numbers = source.get("reviewed_page_numbers")
        if reviewed_page_numbers != [37, 38, 39]:
            raise CommandError("The approved reviewed-page set must be [37, 38, 39].")
        selected_pages = {
            int(row.get("page")): row
            for row in all_pages
            if row.get("page") in reviewed_page_numbers
        }
        if sorted(selected_pages) != reviewed_page_numbers:
            raise CommandError("The three approved manual pages are missing.")

        self._validate_inventory(manifest=manifest, inventory=inventory)
        source_path = self._runtime_source_path(
            runtime_environment if runtime_environment is not None else os.environ
        )
        self._verify_official_source_file(
            source_path,
            expected_sha256=self._lower_hash(inventory.get("sha256")),
            expected_size=self._positive_int(
                inventory.get("file_size_bytes"),
                label="Source inventory file_size_bytes",
            ),
        )
        self._validate_canonical_inputs(
            manifest=manifest,
            pages=selected_pages,
            chunks=chunks,
            identity=identity,
            index=index,
        )
        embeddings = self._validate_embedding_fixture(
            fixture=fixture,
            manifest=manifest,
            chunks=chunks,
        )
        return CanonicalImportPackage(
            manifest=manifest,
            inventory=inventory,
            pages=selected_pages,
            chunks=chunks,
            identity=identity,
            index=index,
            embeddings=embeddings,
            embedding_fixture_sha256=fixture_digest,
            source_file_sha256=self._lower_hash(inventory.get("sha256")),
        )

    def persist(
        self,
        *,
        package: CanonicalImportPackage,
        verifier: User,
    ) -> CanonicalImportResult:
        result = CanonicalImportResult()
        manifest = package.manifest
        source = manifest["source"]
        product_meta = manifest["product"]
        reviewed_at = self._parse_required_datetime(
            package.inventory.get("verified_at"),
            label="source inventory verified_at",
        )
        embedded_at = self._parse_required_datetime(
            package.index.get("indexed_at"),
            label="index indexed_at",
        )

        product, created = self._get_or_create_exact(
            ProductModel,
            lookup={"model_code": product_meta["model_code"]},
            expected={
                "model_name": product_meta["model_name"],
                "generation_code": product_meta["generation_code"],
                "manufacturer": product_meta["manufacturer"],
                "is_supported_mvp": True,
                "is_active": True,
            },
            defaults={"features": {}},
            label="approved product model",
        )
        result.add("products", was_created=created)

        package_digest = self._canonical_digest(manifest)
        batch, created = self._get_or_create_exact(
            IngestionBatch,
            lookup={"batch_no": manifest["batch_no"]},
            expected={
                "dataset_scope_code": IngestionBatch.DatasetScope.MVP,
                "source_type_code": IngestionBatch.SourceType.LOCAL_FILE,
                "status_code": IngestionBatch.Status.SUCCEEDED,
                "idempotency_key": f"backend-ai-evidence:{package_digest}",
                "correlation_id": uuid5(
                    NAMESPACE_URL,
                    f"waterbridge:{manifest['package_id']}",
                ),
                "started_by_id": verifier.pk,
                "started_at": reviewed_at,
                "completed_at": reviewed_at,
                "total_count": EXPECTED_CHUNK_COUNT,
                "success_count": EXPECTED_CHUNK_COUNT,
                "failure_count": 0,
                "pipeline_version": manifest["pipeline_version"],
                "log_uri": (
                    "repository://data/config/evidence/"
                    "backend_ai_canonical_import_v1.json"
                ),
                "error_summary": None,
            },
            label="canonical ingestion batch",
        )
        result.add("batches", was_created=created)

        document, created = self._get_or_create_exact(
            SourceDocument,
            lookup={"document_code": source["document_code"]},
            expected={
                "ingestion_batch_id": batch.pk,
                "dataset_scope_code": SourceDocument.DatasetScope.MVP,
                "supersedes_document_id": None,
                "title": source["document_title"],
                "source_org": source["source_org"],
                "document_type_code": source["document_type_code"],
                "official_source_url": source["official_source_url"],
                "usage_terms_url": source["usage_terms_url"],
                "license_note": source["license_note"],
                "original_file_uri": source["original_file_uri"],
                "file_name": PurePosixPath(
                    urlsplit(source["original_file_uri"]).path
                ).name,
                "mime_type": "application/pdf",
                "file_size_bytes": int(package.inventory["file_size_bytes"]),
                "sha256_hash": package.inventory["sha256"].lower(),
                "revision_label": package.inventory["version"],
                "published_on": None,
                "collected_at": reviewed_at,
                "collected_by_id": verifier.pk,
                "status_code": "APPROVED",
                "parser_version": "pdfplumber_text",
                "deleted_at": None,
                "deleted_by_id": None,
            },
            label="approved source document",
        )
        result.add("documents", was_created=created)

        pages: dict[int, DocumentPage] = {}
        for page_no in sorted(package.pages):
            row = package.pages[page_no]
            page, created = self._get_or_create_exact(
                DocumentPage,
                lookup={"document": document, "page_no": page_no},
                expected={
                    "extracted_text": row["text"],
                    "text_sha256": row["text_sha256"].lower(),
                    "parse_status_code": "PARSED",
                    "review_status_code": "APPROVED",
                    "is_rag_eligible": True,
                    "exclusion_reason": None,
                    "reviewer_id": verifier.pk,
                    "reviewed_at": reviewed_at,
                },
                label=f"approved document page {page_no}",
            )
            pages[page_no] = page
            result.add("pages", was_created=created)

        scope, created = self._get_or_create_exact(
            DocumentModelScope,
            lookup={"document": document, "product_model": product},
            expected={
                "applicable_from": None,
                "applicable_to": None,
                "applicability_note": (
                    "Exact approved MVP scope for WPUJAC104DWH generation D."
                ),
                "is_verified": True,
                "verified_by_id": verifier.pk,
                "verified_at": reviewed_at,
            },
            label="approved document model scope",
        )
        result.add("scopes", was_created=created)
        del scope

        chunk_positions: dict[int, int] = {}
        for row in package.chunks:
            primary_page_no = int(row["page_start"])
            chunk_positions[primary_page_no] = (
                chunk_positions.get(primary_page_no, 0) + 1
            )
            metadata = {
                "canonical_chunk_id": row["chunk_id"],
                "evidence_id": row["evidence_id"],
                "page_refs": row["page_refs"],
                "evidence_summary": row["evidence_summary"],
                "safe_actions": row["safe_actions"],
                "escalation_conditions": row["escalation_conditions"],
                "prohibited_actions": row["prohibited_actions"],
                "risk_level": row["risk_level"],
                "use_guidance": row["use_guidance"],
                "requires_consultation": row["requires_consultation"],
                "verification_status": row["verification_status"],
            }
            chunk_hash = sha256(row["chunk_text"].encode("utf-8")).hexdigest()
            chunk, created = self._get_or_create_exact(
                DocumentChunk,
                lookup={"chunk_text_sha256": chunk_hash},
                expected={
                    "page_id": pages[primary_page_no].pk,
                    "chunk_no": chunk_positions[primary_page_no],
                    "chunk_type_code": "PARAGRAPH",
                    "section_path": row["section_title"],
                    "chunk_text": row["chunk_text"],
                    "start_offset": None,
                    "end_offset": None,
                    "token_count": None,
                    "tokenizer_name": None,
                    "tokenizer_version": None,
                    "symptom_tags": [row["symptom_category"]],
                    "metadata": metadata,
                    "chunking_version": "rag_verified_sample/1.0.0",
                    "is_active": True,
                },
                label=f"approved chunk {row['chunk_id']}",
            )
            result.add("chunks", was_created=created)

            fixture_row = package.embeddings[row["chunk_id"]]
            embedding, created = self._get_or_create_exact(
                ChunkEmbedding,
                lookup={
                    "chunk": chunk,
                    "embedding_model": package.index["model_name"],
                    "embedding_model_version": package.index["model_revision"],
                },
                expected={
                    "embedding_dimension": 1024,
                    "source_text_sha256": chunk_hash,
                    "embedded_at": embedded_at,
                    "is_active": True,
                },
                defaults={"embedding": fixture_row["embedding"]},
                label=f"approved embedding {row['chunk_id']}",
            )
            if not created and not self._vectors_equal(
                embedding.embedding,
                fixture_row["embedding"],
            ):
                raise CommandError(
                    f"approved embedding {row['chunk_id']}: existing vector differs."
                )
            result.add("embeddings", was_created=created)
        return result

    def _validate_inventory(
        self,
        *,
        manifest: dict[str, Any],
        inventory: dict[str, str],
    ) -> None:
        source = manifest["source"]
        product = manifest["product"]
        expected = {
            "source_type": "official_manual",
            "exact_sales_code": product["model_code"],
            "version": "REV.00",
            "page_count": "44",
            "sha256": EXPECTED_SOURCE_SHA256.upper(),
            "scope_role": "mvp",
            "verification_status": "LOCAL_FILE_AND_VISUAL_VERIFIED",
            "deletion_scope": "external_backup_preserved",
        }
        for key, expected_value in expected.items():
            if inventory.get(key) != expected_value:
                raise CommandError(f"Source inventory {key} does not match.")
        source_url = self._required_trimmed(
            inventory.get("source_url"),
            label="Source inventory source_url",
        )
        official_source_url = self._required_trimmed(
            source.get("official_source_url"),
            label="Source official_source_url",
        )
        parsed_source_url = urlsplit(source_url)
        if parsed_source_url.scheme != "https" or not parsed_source_url.netloc:
            raise CommandError("Source inventory source_url must be HTTPS.")
        if source_url != official_source_url:
            raise CommandError("Approved source landing URL does not match inventory.")
        if official_source_url == source["usage_terms_url"]:
            raise CommandError("Source landing URL and usage terms URL must differ.")

    def _validate_canonical_inputs(
        self,
        *,
        manifest: dict[str, Any],
        pages: dict[int, dict[str, Any]],
        chunks: list[dict[str, Any]],
        identity: dict[str, Any],
        index: dict[str, Any],
    ) -> None:
        index_meta = manifest["index"]
        for key in (
            "model_name",
            "model_revision",
            "dimension",
            "index_version",
            "index_type",
            "chunk_count",
            "chunk_set_sha256",
        ):
            if index.get(key) != index_meta.get(key):
                raise CommandError(f"Index manifest {key} does not match package.")
        if len(chunks) != EXPECTED_CHUNK_COUNT:
            raise CommandError("RAG source must contain exactly seven chunks.")
        if identity.get("schema_version") != "1.0.0":
            raise CommandError("Canonical identity schema is unsupported.")
        if identity.get("chunk_set_sha256") != index["chunk_set_sha256"]:
            raise CommandError("Canonical identity chunk-set hash differs.")
        identity_rows = identity.get("chunks")
        if not isinstance(identity_rows, list) or len(identity_rows) != 7:
            raise CommandError("Canonical identity must contain seven chunks.")
        identity_by_id = {row.get("chunk_id"): row for row in identity_rows}
        if len(identity_by_id) != 7:
            raise CommandError("Canonical identity chunk IDs must be unique.")

        document_code = manifest["source"]["document_code"]
        product = manifest["product"]
        source_hash = EXPECTED_SOURCE_SHA256.upper()
        seen_ids: set[str] = set()
        for row in chunks:
            chunk_id = row.get("chunk_id")
            if not isinstance(chunk_id, str) or chunk_id in seen_ids:
                raise CommandError("RAG chunk IDs must be non-empty and unique.")
            seen_ids.add(chunk_id)
            calculated_hash = sha256(row["chunk_text"].encode("utf-8")).hexdigest()
            canonical = identity_by_id.get(chunk_id)
            if canonical is None:
                raise CommandError(f"{chunk_id}: canonical identity is missing.")
            expected_pairs = (
                (row.get("document_id"), document_code),
                (row.get("exact_sales_code"), product["model_code"]),
                (row.get("product_generation"), product["generation_code"]),
                (row.get("verification_status"), APPROVED_CANONICAL_STATUS),
                (row.get("source_file_sha256"), source_hash),
                (canonical.get("chunk_text_sha256"), calculated_hash),
                (canonical.get("page_refs"), row.get("page_refs")),
                (canonical.get("model_code"), product["model_code"]),
            )
            if any(actual != expected for actual, expected in expected_pairs):
                raise CommandError(f"{chunk_id}: approved canonical metadata differs.")
            if not set(row["page_refs"]).issubset(pages):
                raise CommandError(f"{chunk_id}: approved source page is unavailable.")
        if seen_ids != set(identity_by_id):
            raise CommandError("RAG and canonical identity chunk sets differ.")
        for page_no, page in pages.items():
            page_text_hash = sha256(page["text"].encode("utf-8")).hexdigest()
            if page_text_hash != str(page["text_sha256"]).lower():
                raise CommandError(f"Page {page_no}: extracted text SHA-256 differs.")
            if page.get("source_file_sha256") != source_hash:
                raise CommandError(f"Page {page_no}: source file SHA-256 differs.")

    def _validate_embedding_fixture(
        self,
        *,
        fixture: dict[str, Any],
        manifest: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        index = manifest["index"]
        expected = {
            "schema_version": "1.0.0",
            "status": APPROVED_EMBEDDING_FIXTURE_STATUS,
            "model_name": index["model_name"],
            "model_revision": index["model_revision"],
            "dimension": index["dimension"],
            "index_version": index["index_version"],
            "chunk_set_sha256": index["chunk_set_sha256"],
        }
        for key, expected_value in expected.items():
            if fixture.get(key) != expected_value:
                raise CommandError(f"Embedding fixture {key} does not match.")
        rows = fixture.get("rows")
        if not isinstance(rows, list) or len(rows) != EXPECTED_CHUNK_COUNT:
            raise CommandError("Embedding fixture must contain exactly seven rows.")
        by_id = {row.get("chunk_id"): row for row in rows}
        if len(by_id) != EXPECTED_CHUNK_COUNT:
            raise CommandError("Embedding fixture chunk IDs must be unique.")
        expected_ids = {row["chunk_id"] for row in chunks}
        if set(by_id) != expected_ids:
            raise CommandError("Embedding fixture chunk set does not match.")
        chunks_by_id = {row["chunk_id"]: row for row in chunks}
        for chunk_id, row in by_id.items():
            expected_hash = sha256(
                chunks_by_id[chunk_id]["chunk_text"].encode("utf-8")
            ).hexdigest()
            if row.get("chunk_text_sha256") != expected_hash:
                raise CommandError(f"{chunk_id}: embedding source hash differs.")
            vector = row.get("embedding")
            if not isinstance(vector, list) or len(vector) != 1024:
                raise CommandError(
                    f"{chunk_id}: embedding must contain exactly 1024 values."
                )
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in vector
            ):
                raise CommandError(f"{chunk_id}: embedding contains invalid values.")
        return by_id

    @staticmethod
    def _get_or_create_exact(
        model,
        *,
        lookup: dict[str, Any],
        expected: dict[str, Any],
        label: str,
        defaults: dict[str, Any] | None = None,
    ):
        instance = model.objects.select_for_update().filter(**lookup).first()
        if instance is None:
            values = {**lookup, **(defaults or {}), **expected}
            instance = model(**values)
            instance.full_clean()
            instance.save(force_insert=True)
            return instance, True
        for key, expected_value in expected.items():
            actual = getattr(instance, key)
            if actual != expected_value:
                raise CommandError(f"{label}: existing {key} differs.")
        return instance, False

    @staticmethod
    def _vectors_equal(actual, expected: list[float]) -> bool:
        actual_values = list(actual)
        return len(actual_values) == len(expected) and all(
            math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-6)
            for left, right in zip(actual_values, expected, strict=True)
        )

    @staticmethod
    def _parse_required_datetime(value: Any, *, label: str):
        parsed = parse_datetime(str(value or ""))
        if parsed is None:
            raise CommandError(f"{label} must be an ISO-8601 timestamp.")
        return parsed

    @staticmethod
    def _require_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise CommandError(f"Canonical import {key} must be an object.")
        return value

    def _validate_source_metadata(self, source: dict[str, Any]) -> None:
        usage_terms_url = self._required_trimmed(
            source.get("usage_terms_url"),
            label="Source usage_terms_url",
        )
        license_note = self._required_trimmed(
            source.get("license_note"),
            label="Source license_note",
        )
        original_file_uri = self._required_trimmed(
            source.get("original_file_uri"),
            label="Source original_file_uri",
        )

        if usage_terms_url != FIXED_USAGE_TERMS_URL:
            raise CommandError("Source usage_terms_url is not the fixed HTTPS URL.")
        terms = urlsplit(usage_terms_url)
        if (
            terms.scheme != "https"
            or terms.netloc != "www.skmagic.com"
        ):
            raise CommandError("Source usage_terms_url is not the fixed HTTPS URL.")
        if license_note != FIXED_LICENSE_NOTE:
            raise CommandError("Source license_note is not the fixed restriction note.")

        if original_file_uri != FIXED_OBJECT_URI:
            raise CommandError("Source original_file_uri is not the fixed object key.")
        object_uri = urlsplit(original_file_uri)
        if (
            object_uri.scheme != "object"
            or object_uri.netloc != "official-sources"
        ):
            raise CommandError("Source original_file_uri is not the fixed object key.")

    @staticmethod
    def _required_trimmed(value: Any, *, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise CommandError(f"{label} must be non-empty.")
        if value != value.strip():
            raise CommandError(f"{label} must not contain surrounding whitespace.")
        return value

    @staticmethod
    def _positive_int(value: Any, *, label: str) -> int:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{label} must be a positive integer.") from exc
        if parsed <= 0:
            raise CommandError(f"{label} must be a positive integer.")
        return parsed

    @staticmethod
    def _runtime_source_path(environment: Mapping[str, str]) -> Path:
        raw_path = environment.get(OFFICIAL_SOURCE_PATH_ENV)
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CommandError(
                f"{OFFICIAL_SOURCE_PATH_ENV} must be injected into the process."
            )
        path = Path(raw_path)
        if not path.is_absolute():
            raise CommandError("Official source runtime path must be absolute.")
        return path

    @staticmethod
    def _verify_official_source_file(
        path: Path,
        *,
        expected_sha256: str,
        expected_size: int,
    ) -> None:
        try:
            if not path.is_file():
                raise OSError
            if path.stat().st_size != expected_size:
                raise CommandError("Official source file size does not match.")
            digest = sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        except CommandError:
            raise
        except OSError:
            raise CommandError("Official source file is unavailable.") from None
        if digest.hexdigest() != expected_sha256:
            raise CommandError("Official source file SHA-256 does not match.")

    @staticmethod
    def _load_inventory(path: Path, *, inventory_id: str) -> dict[str, str]:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            matches = [
                row
                for row in csv.DictReader(stream)
                if row.get("data_id") == inventory_id
            ]
        if len(matches) != 1:
            raise CommandError("Source inventory must contain exactly one approved row.")
        return matches[0]

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        try:
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot load JSONL input: {path}") from exc
        if not rows or any(not isinstance(row, dict) for row in rows):
            raise CommandError(f"JSONL input must contain objects: {path}")
        return rows

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot load JSON input: {path}") from exc
        if not isinstance(payload, dict):
            raise CommandError(f"JSON root must be an object: {path}")
        return payload

    def _verified_repository_file(self, raw_path: Any, raw_hash: Any) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CommandError("Canonical package path must be non-empty.")
        path = (REPOSITORY_ROOT / raw_path).resolve()
        try:
            path.relative_to(REPOSITORY_ROOT)
        except ValueError as exc:
            raise CommandError("Canonical package path escapes the repository.") from exc
        if self._file_digest(path) != self._lower_hash(raw_hash):
            raise CommandError(f"Canonical source file SHA-256 differs: {raw_path}")
        return path

    @staticmethod
    def _file_digest(path: Path) -> str:
        try:
            return sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise CommandError(f"Cannot read package file: {path}") from exc

    @staticmethod
    def _canonical_digest(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _lower_hash(value: Any) -> str:
        if not isinstance(value, str) or len(value) != 64:
            raise CommandError("SHA-256 values must contain 64 hexadecimal characters.")
        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise CommandError("SHA-256 values must contain hexadecimal characters only.")
        return normalized
