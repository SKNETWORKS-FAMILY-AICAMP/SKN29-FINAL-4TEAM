"""공식 53건 적재 확인 후 3모델 Index Manifest를 생성한다."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from ai.scripts.export_three_model_canonical_identity import (
    EXPECTED_MODEL_COUNTS,
    INDEX_TARGET_PATH,
    REPOSITORY_ROOT,
    build_index_target,
    load_source_rows,
)


DEFAULT_OUTPUT_PATH = REPOSITORY_ROOT / "ai/configs/index_manifest_3model.json"
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "ai/configs/schemas/ThreeModelIndexManifest.schema.json"
)


def _load_json_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return payload


def _normalized_utc_timestamp(value: str) -> str:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("--indexed-at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("--indexed-at must include the UTC offset")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_confirmed_counts(
    *,
    total: int,
    jac104: int,
    iac425: int,
    iac606: int,
) -> None:
    actual = {
        "WPUJAC104DWH": jac104,
        "WPUIAC425SNW": iac425,
        "WPUIAC606SNW": iac606,
    }
    if total != sum(actual.values()) or actual != EXPECTED_MODEL_COUNTS:
        raise ValueError(
            "Confirmed Backend embedding counts must be 53 and 15/19/19"
        )


def build_manifest(*, indexed_at: str) -> dict[str, object]:
    expected_target = build_index_target(load_source_rows())
    stored_target = _load_json_object(INDEX_TARGET_PATH)
    if stored_target != expected_target:
        raise RuntimeError("The three-model index target is stale")
    manifest = {
        "model_name": expected_target["model_name"],
        "model_revision": expected_target["model_revision"],
        "dimension": expected_target["dimension"],
        "index_type": expected_target["index_type"],
        "index_version": expected_target["index_version"],
        "chunk_count": expected_target["expected_chunk_count"],
        "chunk_set_sha256": expected_target["expected_chunk_set_sha256"],
        "document_hashes": expected_target["document_hashes"],
        "indexed_at": _normalized_utc_timestamp(indexed_at),
    }
    schema = _load_json_object(SCHEMA_PATH)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(manifest)
    return manifest


def _serialized(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indexed-at", required=True)
    parser.add_argument("--confirmed-total", type=int, required=True)
    parser.add_argument("--confirmed-jac104", type=int, required=True)
    parser.add_argument("--confirmed-iac425", type=int, required=True)
    parser.add_argument("--confirmed-iac606", type=int, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    validate_confirmed_counts(
        total=args.confirmed_total,
        jac104=args.confirmed_jac104,
        iac425=args.confirmed_iac425,
        iac606=args.confirmed_iac606,
    )
    output = args.output.resolve()
    if output != DEFAULT_OUTPUT_PATH.resolve():
        raise RuntimeError("The official manifest output path is fixed")
    serialized = _serialized(build_manifest(indexed_at=args.indexed_at))
    output.write_bytes(serialized)
    print(
        json.dumps(
            {
                "status": "INDEX_MANIFEST_READY_FOR_CROSSWALK",
                "path": output.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": sha256(serialized).hexdigest().upper(),
                "chunk_count": 53,
                "model_chunk_counts": EXPECTED_MODEL_COUNTS,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
