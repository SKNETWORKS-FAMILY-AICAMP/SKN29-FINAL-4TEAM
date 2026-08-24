"""JSONL 기반 Neo4j Lineage QA를 실행하고 정제 증거 묶음을 생성한다."""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from ai.app.experiments.neo4j_evidence_lineage import (
    LAB_LOOPBACK_PROFILE,
    QA_EPHEMERAL_LOOPBACK_PROFILE,
    REPOSITORY_ROOT,
    Neo4jEvidenceLineageError,
    Neo4jHttpQueryClient,
    Neo4jQaTargetIdentity,
    build_evidence_lineage_graph,
    build_visual_query_presets,
    canonical_json_sha256,
    cleanup_graph_run,
    load_graph_into_neo4j,
    render_lineage_svg,
    render_visual_query_bundle,
    verify_graph_in_neo4j,
)


DEFAULT_NEO4J_IMAGE = "neo4j:2026.07.1"
OFFICIAL_DOCKER_REFERENCE = (
    "https://neo4j.com/docs/operations-manual/current/docker/introduction/"
)
OFFICIAL_QUERY_API_REFERENCE = "https://neo4j.com/docs/query-api/current/query/"
IMAGE_DIGEST_PATTERN = re.compile(r"sha256:[A-Fa-f0-9]{64}")


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_identity() -> dict[str, Any]:
    local_branch = _git_output("branch", "--show-current")
    git_sha = _git_output("rev-parse", "HEAD")
    worktree_status = _git_output(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    ci_expected_sha = os.environ.get("GITHUB_SHA")
    ci_head_ref = os.environ.get("GITHUB_HEAD_REF")
    ci_ref_name = os.environ.get("GITHUB_REF_NAME")
    return {
        "branch": local_branch or ci_head_ref or ci_ref_name or "DETACHED",
        "checkout_mode": "BRANCH" if local_branch else "DETACHED",
        "git_sha": git_sha,
        "git_dirty": bool(worktree_status),
        "worktree_status_sha256": sha256(
            worktree_status.encode("utf-8")
        ).hexdigest().upper(),
        "ci_expected_sha": ci_expected_sha,
        "ci_sha_matches_head": (
            git_sha == ci_expected_sha if ci_expected_sha is not None else None
        ),
        "ci_head_ref": ci_head_ref,
        "ci_ref_name": ci_ref_name,
    }


def _git_provenance(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    head_stable = before["git_sha"] == after["git_sha"]
    worktree_stable = (
        before["worktree_status_sha256"]
        == after["worktree_status_sha256"]
    )
    ci_sha_matches = before["ci_sha_matches_head"] is not False and after[
        "ci_sha_matches_head"
    ] is not False
    return {
        "status": (
            "PASS" if head_stable and worktree_stable and ci_sha_matches else "FAIL"
        ),
        "head_stable": head_stable,
        "worktree_status_stable": worktree_stable,
        "ci_sha_matches_head": ci_sha_matches,
        "clean_head": not bool(after["git_dirty"]),
    }


def _validated_generated_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Neo4jEvidenceLineageError(
            "generated-at은 timezone이 포함된 ISO-8601이어야 합니다."
        ) from exc
    if parsed.tzinfo is None:
        raise Neo4jEvidenceLineageError(
            "generated-at은 timezone이 포함된 ISO-8601이어야 합니다."
        )
    return parsed.isoformat()


def _validated_image_digest(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise Neo4jEvidenceLineageError(
                "QA Profile에는 Infra가 확인한 Neo4j Repo Digest가 필요합니다."
            )
        return None
    if IMAGE_DIGEST_PATTERN.fullmatch(value) is None:
        raise Neo4jEvidenceLineageError(
            "Neo4j 이미지 Digest는 sha256 형식이어야 합니다."
        )
    return value.casefold()


def _resolve_output_dir(value: str) -> Path:
    runtime_root = (REPOSITORY_ROOT / ".runtime").resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = REPOSITORY_ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(runtime_root)
    except ValueError as exc:
        raise Neo4jEvidenceLineageError(
            "Neo4j QA 출력은 저장소 .runtime 아래만 허용합니다."
        ) from exc
    return candidate


def _write_text_exclusive(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
    except FileExistsError as exc:
        raise Neo4jEvidenceLineageError(
            "같은 Neo4j QA 증거 파일이 이미 있어 덮어쓰지 않습니다."
        ) from exc


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    _write_text_exclusive(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _relative(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value:
        raise Neo4jEvidenceLineageError(
            "Neo4j QA 실행에 필요한 Secret 또는 대상 식별자가 없습니다."
        )
    return value


def _target_identity(
    *,
    profile: str,
    run_id: str,
    image_digest: str | None,
) -> Neo4jQaTargetIdentity | None:
    if profile == LAB_LOOPBACK_PROFILE:
        return None
    if profile != QA_EPHEMERAL_LOOPBACK_PROFILE or image_digest is None:
        raise Neo4jEvidenceLineageError("지원하지 않는 Neo4j 실행 Profile입니다.")
    return Neo4jQaTargetIdentity(
        target_id=_required_environment("NEO4J_QA_TARGET_ID"),
        run_id=run_id,
        nonce_sha256=_required_environment("NEO4J_QA_TARGET_NONCE_SHA256"),
        database="neo4j",
        image_digest=image_digest,
    )


def _client(
    *,
    endpoint: str,
    profile: str,
) -> Neo4jHttpQueryClient:
    if profile == LAB_LOOPBACK_PROFILE:
        return Neo4jHttpQueryClient(endpoint, profile=profile)
    if profile != QA_EPHEMERAL_LOOPBACK_PROFILE:
        raise Neo4jEvidenceLineageError("지원하지 않는 Neo4j 실행 Profile입니다.")
    return Neo4jHttpQueryClient(
        endpoint,
        profile=profile,
        username=_required_environment("NEO4J_QA_USERNAME"),
        password=_required_environment("NEO4J_QA_PASSWORD"),
    )


def _write_artifact_integrity(
    *,
    output_dir: Path,
    artifact_paths: list[Path],
    run_id: str,
) -> tuple[Path, Path]:
    artifact_manifest_path = output_dir / "artifact_manifest.json"
    checksum_path = output_dir / "checksums.sha256"
    artifact_manifest = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "algorithm": "SHA-256",
        "artifacts": [
            {
                "path": _relative(path),
                "file_sha256": _file_sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in artifact_paths
        ],
        "excluded_from_durable_upload": ["graph_projection.json"],
    }
    _write_json_exclusive(artifact_manifest_path, artifact_manifest)
    checksum_paths = [*artifact_paths, artifact_manifest_path]
    checksum_lines = [
        f"{_file_sha256(path)}  {path.name}" for path in checksum_paths
    ]
    _write_text_exclusive(checksum_path, "\n".join(checksum_lines) + "\n")
    return artifact_manifest_path, checksum_path


def run_lab(
    *,
    output_dir: str,
    generated_at: str,
    endpoint: str | None,
    run_id: str,
    profile: str = LAB_LOOPBACK_PROFILE,
    neo4j_image: str = DEFAULT_NEO4J_IMAGE,
    neo4j_image_digest: str | None = None,
) -> tuple[int, dict[str, Any]]:
    evidence_generated_at = _validated_generated_at(generated_at)
    resolved_output = _resolve_output_dir(output_dir)
    digest = _validated_image_digest(
        neo4j_image_digest,
        required=profile == QA_EPHEMERAL_LOOPBACK_PROFILE,
    )
    graph = build_evidence_lineage_graph()
    projection_hash = canonical_json_sha256(graph.projection_payload())
    visual_query_presets = build_visual_query_presets(graph)
    visual_query_bundle = render_visual_query_bundle(
        visual_query_presets,
        run_id=run_id,
    )
    source_before = _git_identity()

    projection_manifest_path = resolved_output / "projection_manifest.json"
    browser_query_path = resolved_output / "neo4j_browser_visual_query.cypher"
    visual_query_catalog_path = resolved_output / "visual_query_catalog.json"
    visual_query_catalog = {
        "schema_version": "2.0.0",
        "scope": "JSONL_BASED_LINEAGE_QA",
        "run_id": run_id,
        "profile": profile,
        "production_runtime_connected": False,
        "rds_connected": False,
        "query_count": len(visual_query_presets),
        "queries": [preset.manifest_row() for preset in visual_query_presets],
    }
    projection_manifest = {
        "schema_version": "2.0.0",
        "status": "JSONL_PROJECTION_READY",
        "scope": "JSONL_BASED_LINEAGE_QA",
        "run_id": run_id,
        "generated_at": evidence_generated_at,
        "source": source_before,
        "profile": profile,
        "input_source": "REPOSITORY_JSONL_ONLY",
        "rds_connected": False,
        "production_runtime_connected": False,
        "public_runtime_activation": "HOLD",
        "official_metrics_allowed": False,
        "neo4j_image": {
            "tag": neo4j_image,
            "infra_supplied_repo_digest": digest,
            "digest_collection_owner": "INFRA_JOB",
        },
        "neo4j_docker_reference": OFFICIAL_DOCKER_REFERENCE,
        "neo4j_query_api_reference": OFFICIAL_QUERY_API_REFERENCE,
        "input_files": graph.input_files,
        "node_counts": graph.node_counts(),
        "relationship_counts": graph.relationship_counts(),
        "projection_sha256": projection_hash,
        "data_policy": {
            "source_text_included": False,
            "vectors_included": False,
            "prompts_included": False,
            "scores_included": False,
            "customer_data_included": False,
        },
        "durable_artifact_policy": {
            "graph_projection_json": "EXCLUDED",
            "canonical_hashes_and_counts_only": True,
        },
    }
    _write_json_exclusive(projection_manifest_path, projection_manifest)
    _write_text_exclusive(browser_query_path, visual_query_bundle)
    _write_json_exclusive(visual_query_catalog_path, visual_query_catalog)

    if endpoint is None:
        result = {
            "result": "NOT_RUN",
            "reason": "NEO4J_ENDPOINT_NOT_PROVIDED",
            "projection_manifest": _relative(projection_manifest_path),
        }
        return 2, result

    target_identity = _target_identity(
        profile=profile,
        run_id=run_id,
        image_digest=digest,
    )
    client = _client(endpoint=endpoint, profile=profile)
    target_verification = None
    cleanup_result: dict[str, Any] | None = None
    try:
        target_verification = load_graph_into_neo4j(
            graph,
            client,
            profile=profile,
            run_id=run_id,
            target_identity=target_identity,
        )
        database_result = verify_graph_in_neo4j(
            graph,
            client,
            run_id=run_id,
        )
    finally:
        try:
            if target_verification is not None:
                cleanup_result = cleanup_graph_run(
                    client,
                    verification=target_verification,
                    target_identity=target_identity,
                )
        finally:
            client.close()

    if cleanup_result is None:
        raise Neo4jEvidenceLineageError("Neo4j QA Graph 정리 증거가 없습니다.")
    source_after = _git_identity()
    git_provenance = _git_provenance(source_before, source_after)
    database_validation = database_result["database_validation"]
    application_validation = (
        "PASS"
        if database_validation == "PASS" and cleanup_result["status"] == "PASS"
        else "FAIL"
    )
    if application_validation == "FAIL" or git_provenance["status"] == "FAIL":
        result_status = "FAIL"
        submission_status = "BLOCKED_BY_APPLICATION_OR_GIT_VALIDATION"
        exit_code = 1
    elif profile == QA_EPHEMERAL_LOOPBACK_PROFILE:
        result_status = "PARTIAL"
        submission_status = (
            "HOLD_PENDING_CLEAN_COMMIT_AND_INFRA_FINALIZATION"
            if source_after["git_dirty"]
            else "HOLD_PENDING_INFRA_FINALIZATION"
        )
        exit_code = 2
    elif source_after["git_dirty"]:
        result_status = "PARTIAL"
        submission_status = "HOLD_PENDING_CLEAN_COMMIT_RERUN"
        exit_code = 2
    else:
        result_status = "PASS"
        submission_status = "LAB_PASS_NOT_DEPLOYMENT_EVIDENCE"
        exit_code = 0
    pm_approval_status = submission_status

    svg_path = resolved_output / "neo4j_evidence_lineage_visual.svg"
    evidence_path = resolved_output / "neo4j_lab_evidence.json"
    cleanup_path = resolved_output / "cleanup_evidence.json"
    run_manifest_path = resolved_output / "run_manifest.json"
    svg = render_lineage_svg(database_result)
    _write_text_exclusive(svg_path, svg)
    _write_json_exclusive(cleanup_path, cleanup_result)
    execution_reference = {
        "ci_run_id": os.environ.get("GITHUB_RUN_ID"),
        "ci_job": os.environ.get("GITHUB_JOB"),
        "local_execution": os.environ.get("GITHUB_RUN_ID") is None,
    }
    report = {
        "schema_version": "2.0.0",
        "result": result_status,
        "scope": "JSONL_BASED_LINEAGE_QA",
        "run_id": run_id,
        "generated_at": evidence_generated_at,
        "source": {
            "before": source_before,
            "after": source_after,
            "validation": git_provenance,
        },
        "profile": profile,
        "application_validation": application_validation,
        "submission_status": submission_status,
        "execution_reference": execution_reference,
        "input_source": "REPOSITORY_JSONL_ONLY",
        "rds_connected": False,
        "rds_lineage_validation": "NOT_RUN_SEPARATE_FUTURE_GATE",
        "production_runtime_connected": False,
        "public_runtime_activation": "HOLD",
        "official_metrics_allowed": False,
        "pm_approval_status": pm_approval_status,
        "neo4j_image": {
            "tag": neo4j_image,
            "infra_supplied_repo_digest": digest,
            "digest_collection_owner": "INFRA_JOB",
        },
        "target_preflight": {
            "status": "PASS",
            "profile": target_verification.profile,
            "database": target_verification.database,
            "marker_validated": target_verification.marker_validated,
            "unexpected_node_count": target_verification.unexpected_node_count,
            "relationship_count": target_verification.relationship_count,
        },
        "projection_manifest": _relative(projection_manifest_path),
        "projection_sha256": projection_hash,
        "database": database_result,
        "graph_cleanup": {
            **cleanup_result,
            "evidence_path": _relative(cleanup_path),
        },
        "visual_artifact": {
            "path": _relative(svg_path),
            "file_sha256": _file_sha256(svg_path),
            "contains_source_text": False,
        },
        "visual_queries": {
            "bundle_path": _relative(browser_query_path),
            "catalog_path": _relative(visual_query_catalog_path),
            "query_count": len(visual_query_presets),
            "catalog_canonical_payload_sha256": canonical_json_sha256(
                visual_query_catalog
            ),
            "catalog_file_sha256": _file_sha256(visual_query_catalog_path),
        },
        "trigger_scope": {
            "included": [
                "JSONL_INPUT_CHANGE",
                "PROJECTION_OR_QUERY_CHANGE",
                "NEO4J_QA_CONFIG_CHANGE",
                "MANUAL_RELEASE_CANDIDATE_RUN",
            ],
            "excluded": ["RDS_LINEAGE_VIEW_CHANGE"],
        },
        "owner_boundaries": {
            "production_retrieval": "UNCHANGED_PGVECTOR",
            "pipeline_router": "NOT_CONNECTED",
            "backend_rds": "NOT_CONNECTED",
            "harness_hitl_handoff": "NOT_CONNECTED",
            "container_cleanup_and_digest": "INFRA_JOB_OWNED",
        },
    }
    report["integrity"] = {
        "algorithm": "SHA-256",
        "canonical_payload_sha256": canonical_json_sha256(report),
    }
    _write_json_exclusive(evidence_path, report)

    run_manifest = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "result": result_status,
        "scope": "JSONL_BASED_LINEAGE_QA",
        "profile": profile,
        "application_validation": application_validation,
        "submission_status": submission_status,
        "source": {
            "before": source_before,
            "after": source_after,
            "validation": git_provenance,
        },
        "execution_reference": execution_reference,
        "artifacts": {
            "evidence": _relative(evidence_path),
            "visual": _relative(svg_path),
            "visual_query_catalog": _relative(visual_query_catalog_path),
            "visual_query_bundle": _relative(browser_query_path),
            "projection_manifest": _relative(projection_manifest_path),
            "graph_cleanup": _relative(cleanup_path),
        },
        "infra_completion_required": [
            "CI_RUN_LOG_OR_RUN_ID",
            "IMAGE_REPO_DIGEST_COLLECTION",
            "CONTAINER_AND_VOLUME_ZERO_AFTER_ALWAYS_CLEANUP",
            "INFRA_CLEANUP_EVIDENCE",
            "EXTERNAL_SUBMISSION_MANIFEST_AND_CHECKSUMS",
        ],
    }
    _write_json_exclusive(run_manifest_path, run_manifest)
    artifact_paths = [
        run_manifest_path,
        projection_manifest_path,
        evidence_path,
        svg_path,
        visual_query_catalog_path,
        browser_query_path,
        cleanup_path,
    ]
    artifact_manifest_path, checksum_path = _write_artifact_integrity(
        output_dir=resolved_output,
        artifact_paths=artifact_paths,
        run_id=run_id,
    )
    return exit_code, {
        "result": result_status,
        "application_validation": application_validation,
        "submission_status": submission_status,
        "database_validation": database_validation,
        "graph_cleanup": cleanup_result["status"],
        "pm_approval_status": pm_approval_status,
        "evidence_path": _relative(evidence_path),
        "visual_path": _relative(svg_path),
        "artifact_manifest_path": _relative(artifact_manifest_path),
        "checksums_path": _relative(checksum_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JSONL 기반 Neo4j Evidence Lineage QA를 실행합니다."
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--profile",
        choices=[LAB_LOOPBACK_PROFILE, QA_EPHEMERAL_LOOPBACK_PROFILE],
        default=LAB_LOOPBACK_PROFILE,
    )
    parser.add_argument(
        "--endpoint",
        help="전용 일회성 Neo4j Container의 Loopback Query API Root",
    )
    parser.add_argument("--neo4j-image", default=DEFAULT_NEO4J_IMAGE)
    parser.add_argument(
        "--neo4j-image-digest",
        help="Infra Job이 실제 Container 이미지에서 확인한 Repo Digest",
    )
    args = parser.parse_args()
    try:
        exit_code, result = run_lab(
            output_dir=args.output_dir,
            generated_at=args.generated_at,
            endpoint=args.endpoint,
            run_id=args.run_id,
            profile=args.profile,
            neo4j_image=args.neo4j_image,
            neo4j_image_digest=args.neo4j_image_digest,
        )
    except Neo4jEvidenceLineageError as exc:
        print(
            json.dumps(
                {"result": "FAIL", "message": str(exc)},
                ensure_ascii=True,
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {"result": "FAIL", "message": "Neo4j QA 실행에 실패했습니다."},
                ensure_ascii=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
