"""Validate AI and cleanup evidence and build the external submission manifest."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
REQUIRED_AI_ARTIFACTS = {
    "run_manifest.json",
    "projection_manifest.json",
    "neo4j_lab_evidence.json",
    "neo4j_evidence_lineage_visual.svg",
    "visual_query_catalog.json",
    "neo4j_browser_visual_query.cypher",
    "cleanup_evidence.json",
}


class FinalizationError(RuntimeError):
    """The evidence bundle cannot be promoted to a completed submission."""


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FinalizationError(f"Invalid evidence JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise FinalizationError(f"Evidence must be a JSON object: {path.name}")
    return value


def finalize(
    *,
    artifact_dir: Path,
    run_id: str,
    git_sha: str,
    image_digest: str,
    ci_run_id: str,
    ci_run_url: str,
) -> tuple[Path, Path]:
    artifact_dir = artifact_dir.resolve()
    if ROOT.resolve() not in artifact_dir.parents:
        raise FinalizationError("Artifact directory must stay inside the repository.")
    if SHA_PATTERN.fullmatch(git_sha) is None:
        raise FinalizationError("Git SHA is invalid.")
    if DIGEST_PATTERN.fullmatch(image_digest) is None:
        raise FinalizationError("Image digest is invalid.")

    cleanup_path = artifact_dir / "infra_cleanup_evidence.json"
    cleanup = _load_object(cleanup_path)
    expected_cleanup = {
        "status": "PASS",
        "run_id": run_id,
        "git_sha": git_sha,
        "image_repo_digest": image_digest,
        "container_count": 0,
        "anonymous_volume_count": 0,
    }
    for key, expected in expected_cleanup.items():
        if cleanup.get(key) != expected:
            raise FinalizationError(f"Infra cleanup evidence mismatch: {key}")

    ai_manifest_path = artifact_dir / "artifact_manifest.json"
    ai_manifest = _load_object(ai_manifest_path)
    if ai_manifest.get("run_id") != run_id:
        raise FinalizationError("AI artifact manifest run ID mismatch.")
    artifacts = ai_manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise FinalizationError("AI artifact manifest has no artifact list.")
    verified: list[dict[str, Any]] = []
    names: set[str] = set()
    for row in artifacts:
        if not isinstance(row, dict):
            raise FinalizationError("AI artifact manifest row is invalid.")
        relative = row.get("path")
        expected_hash = row.get("file_sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise FinalizationError("AI artifact path or checksum is invalid.")
        path = (ROOT / relative).resolve()
        if artifact_dir not in path.parents or not path.is_file():
            raise FinalizationError("AI artifact escaped or is missing.")
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise FinalizationError(f"AI artifact checksum mismatch: {path.name}")
        names.add(path.name)
        verified.append({"name": path.name, "file_sha256": actual_hash})
    if names != REQUIRED_AI_ARTIFACTS:
        raise FinalizationError("AI durable artifact set is incomplete or unexpected.")
    if (artifact_dir / "graph_projection.json").exists():
        raise FinalizationError("Raw graph projection must not be uploaded.")

    evidence = _load_object(artifact_dir / "neo4j_lab_evidence.json")
    run_manifest = _load_object(artifact_dir / "run_manifest.json")
    for document, label in ((evidence, "AI evidence"), (run_manifest, "run manifest")):
        if document.get("run_id") != run_id:
            raise FinalizationError(f"{label} run ID mismatch.")
        if document.get("application_validation") != "PASS":
            raise FinalizationError(f"{label} did not pass application validation.")
        if document.get("submission_status") != "HOLD_PENDING_INFRA_FINALIZATION":
            raise FinalizationError(f"{label} is not ready for Infra finalization.")
        source = document.get("source")
        if not isinstance(source, dict):
            raise FinalizationError(f"{label} has no Git provenance.")
        after = source.get("after")
        validation = source.get("validation")
        if (
            not isinstance(after, dict)
            or after.get("git_sha") != git_sha
            or after.get("git_dirty") is not False
            or not isinstance(validation, dict)
            or validation.get("status") != "PASS"
        ):
            raise FinalizationError(f"{label} Git provenance did not pass on the target SHA.")
    graph_cleanup = evidence.get("graph_cleanup")
    if not isinstance(graph_cleanup, dict) or graph_cleanup.get("status") != "PASS":
        raise FinalizationError("Application graph cleanup did not pass.")

    submission = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "scope": "JSONL_BASED_LINEAGE_QA",
        "run_id": run_id,
        "git_sha": git_sha,
        "ci_run_id": ci_run_id,
        "ci_run_url": ci_run_url,
        "image_repo_digest": image_digest,
        "container_count_after_cleanup": 0,
        "anonymous_volume_count_after_cleanup": 0,
        "ai_artifact_manifest_sha256": _sha256(ai_manifest_path),
        "infra_cleanup_evidence_sha256": _sha256(cleanup_path),
        "artifacts": sorted(verified, key=lambda row: row["name"]),
    }
    submission_path = artifact_dir / "submission_manifest.json"
    checksums_path = artifact_dir / "submission_checksums.sha256"
    if submission_path.exists() or checksums_path.exists():
        raise FinalizationError("Submission evidence already exists.")
    submission_path.write_text(
        json.dumps(submission, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checksum_rows = [
        f"{_sha256(submission_path)}  {submission_path.name}",
        f"{_sha256(cleanup_path)}  {cleanup_path.name}",
        f"{_sha256(ai_manifest_path)}  {ai_manifest_path.name}",
    ]
    checksums_path.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8", newline="\n")
    return submission_path, checksums_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--ci-run-id", required=True)
    parser.add_argument("--ci-run-url", required=True)
    args = parser.parse_args()
    try:
        submission, checksums = finalize(
            artifact_dir=args.artifact_dir,
            run_id=args.run_id,
            git_sha=args.git_sha.casefold(),
            image_digest=args.image_digest.casefold(),
            ci_run_id=args.ci_run_id,
            ci_run_url=args.ci_run_url,
        )
    except FinalizationError as exc:
        print(json.dumps({"status": "FAIL", "message": str(exc)}))
        return 1
    print(json.dumps({"status": "PASS", "submission": submission.name, "checksums": checksums.name}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
