"""Neo4j Evidence Lineage 독립 LAB을 실행하고 정제 증거를 생성한다."""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from ai.app.experiments.neo4j_evidence_lineage import (
    REPOSITORY_ROOT,
    VISUAL_BROWSER_QUERY,
    Neo4jEvidenceLineageError,
    Neo4jHttpQueryClient,
    build_evidence_lineage_graph,
    canonical_json_sha256,
    load_graph_into_neo4j,
    render_lineage_svg,
    verify_graph_in_neo4j,
)


DEFAULT_NEO4J_IMAGE = "neo4j:2026.07.1"
OFFICIAL_DOCKER_REFERENCE = (
    "https://neo4j.com/docs/operations-manual/current/docker/introduction/"
)
OFFICIAL_QUERY_API_REFERENCE = "https://neo4j.com/docs/query-api/current/query/"


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
    return {
        "branch": _git_output("branch", "--show-current") or "DETACHED",
        "git_sha": _git_output("rev-parse", "HEAD"),
        "git_dirty": bool(_git_output("status", "--porcelain")),
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
            "Neo4j LAB 출력은 저장소 .runtime 아래만 허용합니다."
        ) from exc
    return candidate


def _write_text_exclusive(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
    except FileExistsError as exc:
        raise Neo4jEvidenceLineageError(
            "같은 Neo4j LAB 증거 파일이 이미 있어 덮어쓰지 않습니다."
        ) from exc


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    _write_text_exclusive(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _relative(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def run_lab(
    *,
    output_dir: str,
    generated_at: str,
    endpoint: str | None,
    neo4j_image: str = DEFAULT_NEO4J_IMAGE,
) -> tuple[int, dict[str, Any]]:
    evidence_generated_at = _validated_generated_at(generated_at)
    resolved_output = _resolve_output_dir(output_dir)
    graph = build_evidence_lineage_graph()
    projection = graph.projection_payload()
    projection_hash = canonical_json_sha256(projection)
    source = _git_identity()

    projection_path = resolved_output / "graph_projection.json"
    manifest_path = resolved_output / "projection_manifest.json"
    browser_query_path = resolved_output / "neo4j_browser_visual_query.cypher"
    projection_manifest = {
        "schema_version": "1.0.0",
        "status": "LAB_PROJECTION_READY",
        "scope": "LAB_ONLY",
        "generated_at": evidence_generated_at,
        "source": source,
        "production_runtime_connected": False,
        "public_runtime_activation": "HOLD",
        "official_metrics_allowed": False,
        "neo4j_image": neo4j_image,
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
        "artifacts": {
            "projection": _relative(projection_path),
            "browser_visual_query": _relative(browser_query_path),
        },
    }
    _write_json_exclusive(projection_path, projection)
    _write_json_exclusive(manifest_path, projection_manifest)
    _write_text_exclusive(browser_query_path, VISUAL_BROWSER_QUERY + ";\n")

    if endpoint is None:
        result = {
            "result": "NOT_RUN",
            "reason": "NEO4J_ENDPOINT_NOT_PROVIDED",
            "projection_manifest": _relative(manifest_path),
        }
        return 2, result

    client = Neo4jHttpQueryClient(endpoint)
    try:
        load_graph_into_neo4j(graph, client)
        database_result = verify_graph_in_neo4j(graph, client)
    finally:
        client.close()

    database_validation = database_result["database_validation"]
    if database_validation == "FAIL":
        result_status = "FAIL"
        pm_approval_status = "BLOCKED_BY_GRAPH_VALIDATION"
        exit_code = 1
    elif source["git_dirty"]:
        result_status = "PARTIAL"
        pm_approval_status = "HOLD_PENDING_CLEAN_COMMIT_RERUN"
        exit_code = 2
    else:
        result_status = "PASS"
        pm_approval_status = "READY_FOR_PM_REVIEW"
        exit_code = 0

    svg_path = resolved_output / "neo4j_evidence_lineage_visual.svg"
    evidence_path = resolved_output / "neo4j_lab_evidence.json"
    svg = render_lineage_svg(database_result)
    _write_text_exclusive(svg_path, svg)
    report = {
        "schema_version": "1.0.0",
        "result": result_status,
        "scope": "LAB_ONLY",
        "generated_at": evidence_generated_at,
        "source": source,
        "production_runtime_connected": False,
        "public_runtime_activation": "HOLD",
        "official_metrics_allowed": False,
        "pm_approval_status": pm_approval_status,
        "neo4j_image": neo4j_image,
        "projection_manifest": _relative(manifest_path),
        "projection_sha256": projection_hash,
        "database": database_result,
        "visual_artifact": {
            "path": _relative(svg_path),
            "file_sha256": sha256(svg.encode("utf-8")).hexdigest().upper(),
            "contains_source_text": False,
        },
        "owner_boundaries": {
            "production_retrieval": "UNCHANGED_PGVECTOR",
            "pipeline_router": "NOT_CONNECTED",
            "backend_rds": "NOT_CONNECTED",
            "harness_hitl_handoff": "NOT_CONNECTED",
        },
    }
    report["integrity"] = {
        "algorithm": "SHA-256",
        "canonical_payload_sha256": canonical_json_sha256(report),
    }
    _write_json_exclusive(evidence_path, report)
    return exit_code, {
        "result": result_status,
        "database_validation": database_validation,
        "pm_approval_status": pm_approval_status,
        "evidence_path": _relative(evidence_path),
        "visual_path": _relative(svg_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Neo4j Evidence Lineage 독립 LAB을 실행합니다."
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument(
        "--endpoint",
        help="인증을 끈 Loopback Neo4j Query API Root",
    )
    parser.add_argument("--neo4j-image", default=DEFAULT_NEO4J_IMAGE)
    args = parser.parse_args()
    try:
        exit_code, result = run_lab(
            output_dir=args.output_dir,
            generated_at=args.generated_at,
            endpoint=args.endpoint,
            neo4j_image=args.neo4j_image,
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
                {"result": "FAIL", "message": "Neo4j LAB 실행에 실패했습니다."},
                ensure_ascii=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
