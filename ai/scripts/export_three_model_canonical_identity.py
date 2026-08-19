"""3모델 RAG Child의 Canonical Identity와 공식 Index 기대값을 생성한다."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import unicodedata


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "rag"
    / "expansion"
    / "rag_child_chunks_3model_v1.jsonl"
)
EVIDENCE_GROUPS_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "evidence"
    / "rag_evidence_groups_3model_v1.jsonl"
)
IDENTITY_PATH = (
    REPOSITORY_ROOT / "ai" / "configs" / "canonical_evidence_identity_3model.json"
)
INDEX_TARGET_PATH = (
    REPOSITORY_ROOT / "ai" / "configs" / "three_model_index_target.json"
)

EXPECTED_MODEL_COUNTS = {
    "WPUJAC104DWH": 15,
    "WPUIAC425SNW": 19,
    "WPUIAC606SNW": 19,
}
INDEX_VERSION = "2.0.0"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
REQUIRED_FIELDS = {
    "child_id",
    "record_type",
    "retrieval_role",
    "child_text",
    "child_text_sha256",
    "exact_sales_code",
    "product_generation",
    "document_id",
    "page_refs",
    "source_file_sha256",
    "verification_status",
    "allowed_use",
}


def _relative(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def _validated_sha256(value: object, *, field: str, chunk_id: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{chunk_id}: {field} must be a SHA-256 string")
    normalized = value.upper()
    if len(normalized) != 64 or any(
        character not in "0123456789ABCDEF" for character in normalized
    ):
        raise ValueError(f"{chunk_id}: {field} must contain 64 hexadecimal characters")
    return normalized


def _assert_nfc(value: object, *, field: str, chunk_id: str) -> None:
    if not isinstance(value, str) or not unicodedata.is_normalized("NFC", value):
        raise ValueError(f"{chunk_id}: {field} must already be NFC normalized")


def load_source_rows(path: Path = SOURCE_PATH) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = REQUIRED_FIELDS.difference(row)
        if missing:
            raise ValueError(f"line {line_number}: missing fields {sorted(missing)}")
        chunk_id = str(row["child_id"])
        if row["record_type"] != "child" or row["retrieval_role"] != "SEARCH_CANDIDATE":
            raise ValueError(f"{chunk_id}: only search Child rows are canonical inputs")
        if row["verification_status"] != "TEXT_AND_VISUAL_VERIFIED":
            raise ValueError(f"{chunk_id}: source verification is incomplete")
        if row["allowed_use"] != "RAG_HANDOFF_ONLY":
            raise ValueError(f"{chunk_id}: unexpected handoff usage policy")
        if (
            not isinstance(row["page_refs"], list)
            or not row["page_refs"]
            or any(
                isinstance(page, bool) or not isinstance(page, int) or page < 1
                for page in row["page_refs"]
            )
        ):
            raise ValueError(f"{chunk_id}: page_refs must not be empty")
        for field in (
            "child_id",
            "child_text",
            "exact_sales_code",
            "product_generation",
            "document_id",
        ):
            _assert_nfc(row[field], field=field, chunk_id=chunk_id)
        child_text_hash = _validated_sha256(
            row["child_text_sha256"],
            field="child_text_sha256",
            chunk_id=chunk_id,
        )
        actual_child_text_hash = sha256(
            str(row["child_text"]).encode("utf-8")
        ).hexdigest().upper()
        if child_text_hash != actual_child_text_hash:
            raise ValueError(f"{chunk_id}: child_text_sha256 does not match child_text")
        _validated_sha256(row["source_file_sha256"], field="source_file_sha256", chunk_id=chunk_id)
        rows.append(row)

    chunk_ids = [str(row["child_id"]) for row in rows]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Canonical Child IDs must be unique")
    counts = Counter(str(row["exact_sales_code"]) for row in rows)
    if dict(counts) != EXPECTED_MODEL_COUNTS:
        raise ValueError(f"Unexpected model Child counts: {dict(counts)}")
    return rows


def chunk_set_sha256(rows: list[dict[str, object]]) -> str:
    canonical = [
        {
            "chunk_id": row["child_id"],
            "source_hash": str(row["source_file_sha256"]).upper(),
            "content": row["child_text"],
        }
        for row in sorted(rows, key=lambda item: str(item["child_id"]))
    ]
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest().upper()


def build_identity(rows: list[dict[str, object]]) -> dict[str, object]:
    chunk_set_hash = chunk_set_sha256(rows)
    chunks = [
        {
            "chunk_id": row["child_id"],
            "document_id": row["document_id"],
            "page_refs": row["page_refs"],
            "model_code": row["exact_sales_code"],
            "product_generation": row["product_generation"],
            "verification_status": row["verification_status"],
            "source_file_sha256": str(row["source_file_sha256"]).upper(),
            "chunk_text_sha256": str(row["child_text_sha256"]).upper(),
        }
        for row in sorted(rows, key=lambda item: str(item["child_id"]))
    ]
    return {
        "schema_version": "1.0.0",
        "status": "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING",
        "runtime_activation": "HOLD_PENDING_OFFICIAL_INDEX_AND_BACKEND_CROSSWALK",
        "source_dataset": _relative(SOURCE_PATH),
        "evidence_registry": _relative(EVIDENCE_GROUPS_PATH),
        "required_index_manifest": "ai/configs/index_manifest_3model.json",
        "index_version": INDEX_VERSION,
        "chunk_count": len(chunks),
        "model_chunk_counts": EXPECTED_MODEL_COUNTS,
        "chunk_set_sha256": chunk_set_hash,
        "identity_policy": {
            "ai_canonical_key": "chunk_id",
            "backend_target_key": "knowledge_document_chunk.public_id",
            "backend_mapping_owner": "Backend·Database",
            "ai_does_not_generate_backend_id": True,
            "required_match_fields": [
                "chunk_id",
                "document_id",
                "page_refs",
                "model_code",
                "product_generation",
                "verification_status",
                "source_file_sha256",
                "chunk_text_sha256",
            ],
        },
        "chunks": chunks,
    }


def build_index_target(rows: list[dict[str, object]]) -> dict[str, object]:
    document_hashes: dict[str, str] = {}
    for row in rows:
        document_id = str(row["document_id"])
        source_hash = str(row["source_file_sha256"]).upper()
        previous = document_hashes.setdefault(document_id, source_hash)
        if previous != source_hash:
            raise ValueError(f"{document_id}: source hash differs between Child rows")
    return {
        "schema_version": "1.0.0",
        "status": "PREPARED_NOT_INDEXED",
        "write_owner": "Backend·Database",
        "ai_access": "SELECT_ONLY",
        "readonly_view": "backend_ai_rag_chunks_v1",
        "source_dataset": _relative(SOURCE_PATH),
        "identity_manifest": _relative(IDENTITY_PATH),
        "actual_index_manifest": "ai/configs/index_manifest_3model.json",
        "model_name": EMBEDDING_MODEL,
        "model_revision": EMBEDDING_REVISION,
        "dimension": 1024,
        "index_type": "exact_search",
        "index_version": INDEX_VERSION,
        "expected_chunk_count": len(rows),
        "expected_model_chunk_counts": EXPECTED_MODEL_COUNTS,
        "expected_chunk_set_sha256": chunk_set_sha256(rows),
        "document_hashes": dict(sorted(document_hashes.items())),
        "required_pre_score_filter": "exact_sales_code",
        "cross_model_fallback": False,
        "runtime_activation": "HOLD_UNTIL_BACKEND_QA_AND_AI_READONLY_VERIFICATION_PASS",
    }


def _serialized(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3모델 Canonical Identity 준비")
    parser.add_argument(
        "--check",
        action="store_true",
        help="저장된 산출물이 Canonical 입력과 일치하는지만 확인",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rows = load_source_rows()
    outputs = {
        IDENTITY_PATH: build_identity(rows),
        INDEX_TARGET_PATH: build_index_target(rows),
    }
    if args.check:
        stale = [
            _relative(path)
            for path, payload in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != _serialized(payload)
        ]
        if stale:
            raise RuntimeError(f"Three-model canonical preparation is stale: {stale}")
        print(json.dumps({"status": "PASS", "stale": 0}, ensure_ascii=False))
        return

    for path, payload in outputs.items():
        path.write_text(_serialized(payload), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "PREPARED_NOT_ACTIVE",
                "chunk_count": len(rows),
                "model_chunk_counts": EXPECTED_MODEL_COUNTS,
                "chunk_set_sha256": chunk_set_sha256(rows),
                "outputs": [_relative(path) for path in outputs],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
