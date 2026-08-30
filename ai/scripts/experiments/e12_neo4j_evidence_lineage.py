"""E12 — Neo4j Evidence Lineage / Knowledge Relationship Validation.

Purpose
-------
Validate that the repository JSONL evidence lineage can be projected into an
actual disposable Neo4j database without identity/relationship drift, and that
relationship-integrity faults are detected.

This experiment does NOT use Neo4j for retrieval or GraphRAG.  It validates
evidence lineage metadata only.

Execution outline
-----------------
1. Pin execution to the current committed Git HEAD in a temporary clean
   detached worktree.
2. Start an authenticated disposable Neo4j container bound only to
   127.0.0.1 on an ephemeral port.
3. Create the repository-defined QA target marker.
4. Run two controlled fault cases against the actual Neo4j Query API:
   - E12-03A: orphan EvidenceChunk by removing MEMBER_OF.
   - E12-03B: cross-model lineage by replacing HAS_PARENT_PAGE with a
              ParentPage from another model while preserving edge count.
5. Run the repository's official Neo4j lineage runner for the clean baseline.
6. Remove the exact container and anonymous volumes.
7. Copy only sanitized evidence to:
      ai/experiment_results/e12_neo4j_evidence_lineage/<run_id>/

Expected final status
---------------------
E12_COMPLETE means:
- baseline application/database validation PASS,
- canonical node/relationship snapshot match,
- normal orphan/cross-model/cross-namespace counts are zero,
- all visual queries PASS,
- both fault injections are detected,
- application graph cleanup PASS,
- disposable Docker container/volumes are removed.

The repository official QA runner intentionally reports PARTIAL /
HOLD_PENDING_INFRA_FINALIZATION in qa_ephemeral_loopback profile.  That status
is preserved in the E12 summary and is NOT promoted to deployment evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_ROOT = (
    REPO_ROOT
    / "ai"
    / "experiment_results"
    / "e12_neo4j_evidence_lineage"
)

DEFAULT_NEO4J_IMAGE = "neo4j:2026.07.1"
QA_PROFILE = "qa_ephemeral_loopback"

REQUIRED_SOURCE_PATHS = (
    "ai/app/experiments/neo4j_evidence_lineage.py",
    "ai/scripts/run_neo4j_evidence_lineage_lab.py",
    "scripts/deployment/prepare_neo4j_lineage_qa.py",
    "data/processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl",
    "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl",
    "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl",
)

SAFE_BASELINE_ARTIFACTS = (
    "run_manifest.json",
    "projection_manifest.json",
    "neo4j_lab_evidence.json",
    "neo4j_evidence_lineage_visual.svg",
    "visual_query_catalog.json",
    "neo4j_browser_visual_query.cypher",
    "cleanup_evidence.json",
    "artifact_manifest.json",
    "checksums.sha256",
)

IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LOOPBACK_PORT_RE = re.compile(r"^127\.0\.0\.1:(\d+)$")


class ExperimentBlocked(RuntimeError):
    """Environment or committed-source precondition prevents execution."""


class ExperimentFailed(RuntimeError):
    """The experiment executed but a required validation failed."""


def _run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float = 120.0,
    check: bool = True,
    secret_command: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ExperimentBlocked(
            f"Required executable is unavailable: {args[0]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ExperimentBlocked(
            f"Command timed out after {timeout:.0f}s."
        ) from exc

    if check and result.returncode != 0:
        if secret_command:
            detail = "Secret-bearing command failed."
        else:
            detail = (result.stderr or result.stdout).strip()[-3000:]
        raise ExperimentBlocked(
            f"Command failed with exit={result.returncode}. {detail}"
        )
    return result


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    return _run(
        ["git", *args],
        cwd=cwd,
        timeout=30.0,
    ).stdout.strip()


def _current_head() -> str:
    sha = _git("rev-parse", "HEAD")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ExperimentBlocked("Current Git HEAD is invalid.")
    return sha


def _source_exists_at_head(path: str, sha: str) -> bool:
    result = _run(
        ["git", "cat-file", "-e", f"{sha}:{path}"],
        cwd=REPO_ROOT,
        timeout=30.0,
        check=False,
    )
    return result.returncode == 0


def _assert_required_sources(sha: str) -> None:
    missing = [
        path
        for path in REQUIRED_SOURCE_PATHS
        if not _source_exists_at_head(path, sha)
    ]
    if missing:
        raise ExperimentBlocked(
            "Committed HEAD does not contain required E12 sources: "
            + ", ".join(missing)
        )


def _make_run_id(sha: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    nonce = secrets.token_hex(4)
    return f"e12-{stamp}-{sha[:8]}-{nonce}"


def _make_clean_worktree(sha: str) -> tuple[Path, Path]:
    parent = Path(tempfile.mkdtemp(prefix="waterbridge-e12-"))
    worktree = parent / "repo"

    print(
        "[E12] Clean detached worktree 생성 중 "
        "(Windows에서는 수 분 걸릴 수 있습니다)"
    )

    try:
        result = _run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(worktree),
                sha,
            ],
            cwd=REPO_ROOT,
            timeout=300.0,
            check=False,
        )
    except ExperimentBlocked:
        # A timed-out `git worktree add` may leave a partially-created
        # directory or registration behind. Attempt only a targeted cleanup
        # for this experiment path; do not touch unrelated worktrees.
        _run(
            [
                "git",
                "worktree",
                "remove",
                "--force",
                str(worktree),
            ],
            cwd=REPO_ROOT,
            timeout=60.0,
            check=False,
        )
        shutil.rmtree(parent, ignore_errors=True)
        raise

    if result.returncode != 0:
        _run(
            [
                "git",
                "worktree",
                "remove",
                "--force",
                str(worktree),
            ],
            cwd=REPO_ROOT,
            timeout=60.0,
            check=False,
        )
        shutil.rmtree(parent, ignore_errors=True)
        raise ExperimentBlocked(
            "Could not create a temporary clean detached worktree."
        )

    if _git("status", "--porcelain=v1", cwd=worktree):
        _remove_worktree(parent, worktree)
        raise ExperimentBlocked(
            "Temporary detached worktree is unexpectedly dirty."
        )

    return parent, worktree


def _remove_worktree(parent: Path, worktree: Path) -> None:
    try:
        _run(
            [
                "git",
                "worktree",
                "remove",
                "--force",
                str(worktree),
            ],
            cwd=REPO_ROOT,
            timeout=60.0,
            check=False,
        )
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _docker_server_version() -> str:
    result = _run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        cwd=REPO_ROOT,
        timeout=30.0,
        check=False,
    )
    version = result.stdout.strip()
    if result.returncode != 0 or not version:
        raise ExperimentBlocked(
            "Docker daemon is unavailable. Start Docker Desktop/Engine first."
        )
    return version


def _docker_pull_and_digest(image: str) -> tuple[str, str]:
    print(f"[E12] Neo4j image 확인/다운로드: {image}")
    result = _run(
        ["docker", "pull", image],
        cwd=REPO_ROOT,
        timeout=600.0,
        check=False,
    )
    if result.returncode != 0:
        raise ExperimentBlocked(
            "Neo4j Docker image pull failed."
        )

    inspect = _run(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            "{{index .RepoDigests 0}}",
        ],
        cwd=REPO_ROOT,
        timeout=30.0,
    ).stdout.strip()

    if "@" not in inspect:
        raise ExperimentBlocked(
            "Neo4j RepoDigest could not be resolved."
        )
    digest = inspect.rsplit("@", 1)[1].casefold()
    if IMAGE_DIGEST_RE.fullmatch(digest) is None:
        raise ExperimentBlocked(
            "Neo4j RepoDigest is missing or invalid."
        )
    return inspect, digest


def _start_container(
    *,
    image_reference: str,
    container_name: str,
    run_id: str,
    username: str,
    password: str,
) -> str:
    result = _run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            container_name,
            "--label",
            f"waterbridge.neo4j.qa.run_id={run_id}",
            "--publish",
            "127.0.0.1::7474",
            "--env",
            f"NEO4J_AUTH={username}/{password}",
            image_reference,
        ],
        cwd=REPO_ROOT,
        timeout=60.0,
        check=False,
        secret_command=True,
    )
    if result.returncode != 0:
        raise ExperimentBlocked(
            "Authenticated disposable Neo4j container failed to start."
        )

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        port_result = _run(
            [
                "docker",
                "port",
                container_name,
                "7474/tcp",
            ],
            cwd=REPO_ROOT,
            timeout=10.0,
            check=False,
        )
        for line in port_result.stdout.splitlines():
            match = LOOPBACK_PORT_RE.fullmatch(line.strip())
            if match:
                return f"http://127.0.0.1:{match.group(1)}"
        time.sleep(0.5)

    raise ExperimentBlocked(
        "Neo4j Query API was not bound to an ephemeral loopback port."
    )


def _container_volume_names(container_name: str) -> list[str]:
    result = _run(
        ["docker", "inspect", container_name],
        cwd=REPO_ROOT,
        timeout=20.0,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list) or len(payload) != 1:
        return []
    mounts = payload[0].get("Mounts", [])
    names: list[str] = []
    if isinstance(mounts, list):
        for mount in mounts:
            if (
                isinstance(mount, dict)
                and mount.get("Type") == "volume"
                and isinstance(mount.get("Name"), str)
                and mount["Name"]
            ):
                names.append(mount["Name"])
    return sorted(set(names))


def _cleanup_container(
    *,
    container_name: str,
    run_id: str,
    volume_names: list[str],
) -> dict[str, Any]:
    _run(
        [
            "docker",
            "rm",
            "--force",
            "--volumes",
            container_name,
        ],
        cwd=REPO_ROOT,
        timeout=30.0,
        check=False,
    )

    for name in volume_names:
        _run(
            ["docker", "volume", "rm", "--force", name],
            cwd=REPO_ROOT,
            timeout=20.0,
            check=False,
        )

    containers = _run(
        [
            "docker",
            "ps",
            "--all",
            "--quiet",
            "--filter",
            f"label=waterbridge.neo4j.qa.run_id={run_id}",
        ],
        cwd=REPO_ROOT,
        timeout=20.0,
        check=False,
    )
    container_ids = [
        line.strip()
        for line in containers.stdout.splitlines()
        if line.strip()
    ]

    remaining_volumes = 0
    for name in volume_names:
        inspect = _run(
            ["docker", "volume", "inspect", name],
            cwd=REPO_ROOT,
            timeout=10.0,
            check=False,
        )
        if inspect.returncode == 0:
            remaining_volumes += 1

    status = (
        "PASS"
        if not container_ids and remaining_volumes == 0
        else "FAIL"
    )
    return {
        "status": status,
        "run_id": run_id,
        "container_count": len(container_ids),
        "anonymous_volume_count": remaining_volumes,
        "tracked_volume_count": len(volume_names),
    }


def _parse_json_output(
    text: str,
    *,
    label: str,
) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ExperimentFailed(
        f"{label} did not emit a JSON object."
    )


FAULT_DRIVER_SOURCE = r"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from ai.app.experiments.neo4j_evidence_lineage import (
    QA_EPHEMERAL_LOOPBACK_PROFILE,
    QA_NODE_LABEL,
    Neo4jHttpQueryClient,
    Neo4jQaTargetIdentity,
    build_evidence_lineage_graph,
    cleanup_graph_run,
    load_graph_into_neo4j,
    verify_graph_in_neo4j,
)


def count_relationships(
    client: Neo4jHttpQueryClient,
    run_id: str,
) -> int:
    rows = client.query(
        f"MATCH (:{QA_NODE_LABEL} {{qa_run_id: $run_id}})"
        "-[rel]->"
        f"(:{QA_NODE_LABEL} {{qa_run_id: $run_id}}) "
        "WHERE rel.qa_run_id = $run_id "
        "RETURN count(rel) AS count",
        {"run_id": run_id},
    )
    return int(rows[0]["count"])


def target_identity(run_id: str) -> Neo4jQaTargetIdentity:
    return Neo4jQaTargetIdentity(
        target_id=os.environ["NEO4J_QA_TARGET_ID"],
        run_id=run_id,
        nonce_sha256=os.environ[
            "NEO4J_QA_TARGET_NONCE_SHA256"
        ],
        database="neo4j",
        image_digest=os.environ[
            "NEO4J_QA_IMAGE_DIGEST"
        ],
    )


def client() -> Neo4jHttpQueryClient:
    return Neo4jHttpQueryClient(
        os.environ["NEO4J_QA_ENDPOINT"],
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        username=os.environ["NEO4J_QA_USERNAME"],
        password=os.environ["NEO4J_QA_PASSWORD"],
    )


def orphan_case() -> dict[str, Any]:
    run_id = os.environ["NEO4J_QA_RUN_ID"]
    graph = build_evidence_lineage_graph()
    identity = target_identity(run_id)
    neo = client()
    verification = None
    cleanup = None
    try:
        verification = load_graph_into_neo4j(
            graph,
            neo,
            profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
            run_id=run_id,
            target_identity=identity,
        )
        baseline = verify_graph_in_neo4j(
            graph,
            neo,
            run_id=run_id,
        )
        if baseline["database_validation"] != "PASS":
            raise RuntimeError(
                "orphan baseline validation failed"
            )

        edge = next(
            item
            for item in graph.edges
            if item.relationship == "MEMBER_OF"
        )
        before = count_relationships(neo, run_id)
        deleted = neo.query(
            f"MATCH (source:{QA_NODE_LABEL}:EvidenceChunk "
            "{qa_run_id: $run_id, id: $source_id})"
            "-[rel:MEMBER_OF {qa_run_id: $run_id}]->"
            f"(target:{QA_NODE_LABEL}:EvidenceGroup "
            "{qa_run_id: $run_id, id: $target_id}) "
            "DELETE rel RETURN count(rel) AS deleted",
            {
                "run_id": run_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
            },
        )[0]["deleted"]
        after = count_relationships(neo, run_id)

        corrupted = verify_graph_in_neo4j(
            graph,
            neo,
            run_id=run_id,
        )
        detected = (
            deleted == 1
            and after == before - 1
            and corrupted["database_validation"] == "FAIL"
            and corrupted["orphan_chunk_count"] >= 1
            and "ORPHAN_CHUNK_PRESENT"
            in corrupted["issues"]
        )
        return {
            "case_id": "E12-03A",
            "name": "ORPHAN_CHUNK_RELATIONSHIP",
            "baseline_database_validation":
                baseline["database_validation"],
            "fault_mutation_count": int(deleted),
            "relationship_count_before": before,
            "relationship_count_after": after,
            "corrupted_database_validation":
                corrupted["database_validation"],
            "orphan_chunk_count":
                corrupted["orphan_chunk_count"],
            "issues": corrupted["issues"],
            "detected": detected,
        }
    finally:
        try:
            if verification is not None:
                cleanup = cleanup_graph_run(
                    neo,
                    verification=verification,
                    target_identity=identity,
                )
        finally:
            neo.close()
        if cleanup is not None and cleanup["status"] != "PASS":
            raise RuntimeError(
                "orphan fault cleanup failed"
            )


def cross_model_case() -> dict[str, Any]:
    run_id = os.environ["NEO4J_QA_RUN_ID"]
    graph = build_evidence_lineage_graph()
    identity = target_identity(run_id)
    neo = client()
    verification = None
    cleanup = None
    try:
        verification = load_graph_into_neo4j(
            graph,
            neo,
            profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
            run_id=run_id,
            target_identity=identity,
        )
        baseline = verify_graph_in_neo4j(
            graph,
            neo,
            run_id=run_id,
        )
        if baseline["database_validation"] != "PASS":
            raise RuntimeError(
                "cross-model baseline validation failed"
            )

        nodes = {
            (node.label, node.node_id): node
            for node in graph.nodes
        }
        edge = next(
            item
            for item in graph.edges
            if item.relationship == "HAS_PARENT_PAGE"
        )
        source = nodes[
            (edge.source_label, edge.source_id)
        ]
        source_model = str(
            source.properties["model_code"]
        )
        wrong_parent = next(
            node
            for node in graph.nodes
            if node.label == "ParentPage"
            and str(node.properties["model_code"])
            != source_model
        )

        before = count_relationships(neo, run_id)
        mutated = neo.query(
            f"MATCH (source:{QA_NODE_LABEL}:Document "
            "{qa_run_id: $run_id, id: $source_id})"
            "-[old:HAS_PARENT_PAGE {qa_run_id: $run_id}]->"
            f"(:{QA_NODE_LABEL}:ParentPage "
            "{qa_run_id: $run_id, id: $target_id}) "
            "DELETE old WITH source "
            f"MATCH (wrong:{QA_NODE_LABEL}:ParentPage "
            "{qa_run_id: $run_id, id: $wrong_target_id}) "
            "CREATE "
            "(source)-[replacement:HAS_PARENT_PAGE]->(wrong) "
            "SET replacement.qa_run_id = $run_id "
            "RETURN count(replacement) AS mutated",
            {
                "run_id": run_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "wrong_target_id": wrong_parent.node_id,
            },
        )[0]["mutated"]
        after = count_relationships(neo, run_id)

        corrupted = verify_graph_in_neo4j(
            graph,
            neo,
            run_id=run_id,
        )
        detected = (
            mutated == 1
            and before == after
            and corrupted["database_validation"] == "FAIL"
            and corrupted["cross_model_path_count"] >= 1
            and "CROSS_MODEL_PATH_PRESENT"
            in corrupted["issues"]
            and "RELATIONSHIP_IDENTITY_SET_MISMATCH"
            in corrupted["issues"]
            and "GRAPH_SNAPSHOT_SHA256_MISMATCH"
            in corrupted["issues"]
        )
        return {
            "case_id": "E12-03B",
            "name": "CROSS_MODEL_RELATIONSHIP",
            "baseline_database_validation":
                baseline["database_validation"],
            "source_model_code": source_model,
            "wrong_parent_model_code": str(
                wrong_parent.properties["model_code"]
            ),
            "fault_mutation_count": int(mutated),
            "relationship_count_before": before,
            "relationship_count_after": after,
            "same_relationship_count": before == after,
            "corrupted_database_validation":
                corrupted["database_validation"],
            "cross_model_path_count":
                corrupted["cross_model_path_count"],
            "issues": corrupted["issues"],
            "detected": detected,
        }
    finally:
        try:
            if verification is not None:
                cleanup = cleanup_graph_run(
                    neo,
                    verification=verification,
                    target_identity=identity,
                )
        finally:
            neo.close()
        if cleanup is not None and cleanup["status"] != "PASS":
            raise RuntimeError(
                "cross-model fault cleanup failed"
            )


def main() -> int:
    try:
        cases = [
            orphan_case(),
            cross_model_case(),
        ]
        payload = {
            "status": (
                "PASS"
                if all(case["detected"] for case in cases)
                else "FAIL"
            ),
            "cases": cases,
        }
    except Exception as exc:
        payload = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _prepare_target(
    *,
    worktree: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    script = (
        worktree
        / "scripts"
        / "deployment"
        / "prepare_neo4j_lineage_qa.py"
    )
    result = _run(
        [
            sys.executable,
            str(script),
            "--timeout-seconds",
            "90",
        ],
        cwd=worktree,
        env=env,
        timeout=120.0,
        check=False,
    )
    payload = _parse_json_output(
        result.stdout,
        label="Neo4j target preparation",
    )
    if (
        result.returncode != 0
        or payload.get("status") != "PASS"
        or payload.get("marker_count") != 1
    ):
        raise ExperimentFailed(
            "Disposable Neo4j target marker preparation failed."
        )
    return payload


def _run_fault_injections(
    *,
    worktree: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    runtime_dir = worktree / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    driver = runtime_dir / "e12_fault_injection_driver.py"
    driver.write_text(
        FAULT_DRIVER_SOURCE,
        encoding="utf-8",
        newline="\n",
    )

    fault_env = env.copy()
    fault_env["PYTHONPATH"] = str(worktree)

    try:
        result = _run(
            [sys.executable, str(driver)],
            cwd=worktree,
            env=fault_env,
            timeout=180.0,
            check=False,
        )
    finally:
        driver.unlink(missing_ok=True)

    payload = _parse_json_output(
        result.stdout,
        label="E12 fault injection",
    )
    if (
        result.returncode != 0
        or payload.get("status") != "PASS"
    ):
        raise ExperimentFailed(
            "Controlled Neo4j fault injection did not pass."
        )

    cases = payload.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 2
        or not all(
            isinstance(case, dict)
            and case.get("detected") is True
            for case in cases
        )
    ):
        raise ExperimentFailed(
            "Fault injection result contract is invalid."
        )
    return payload


def _run_official_baseline(
    *,
    worktree: Path,
    env: dict[str, str],
    run_id: str,
    endpoint: str,
    image: str,
    image_digest: str,
) -> tuple[dict[str, Any], Path]:
    # The fault driver is removed before this call, so the detached source
    # worktree remains clean. The official runner itself writes only .runtime.
    status_before = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        cwd=worktree,
    )
    if status_before:
        raise ExperimentFailed(
            "Clean detached worktree became dirty before baseline run."
        )

    output_dir = (
        worktree
        / ".runtime"
        / "e12_neo4j_lineage"
        / run_id
    )
    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    result = _run(
        [
            sys.executable,
            "-m",
            "ai.scripts.run_neo4j_evidence_lineage_lab",
            "--output-dir",
            str(output_dir),
            "--generated-at",
            generated_at,
            "--run-id",
            run_id,
            "--profile",
            QA_PROFILE,
            "--endpoint",
            endpoint,
            "--neo4j-image",
            image,
            "--neo4j-image-digest",
            image_digest,
        ],
        cwd=worktree,
        env=env,
        timeout=240.0,
        check=False,
    )

    payload = _parse_json_output(
        result.stdout,
        label="Official Neo4j lineage runner",
    )

    # qa_ephemeral_loopback intentionally exits 2 before Infra finalization.
    if result.returncode != 2:
        raise ExperimentFailed(
            "Official Neo4j runner did not return the expected "
            "qa_ephemeral pre-finalization exit code 2."
        )
    if (
        payload.get("result") != "PARTIAL"
        or payload.get("application_validation") != "PASS"
        or payload.get("database_validation") != "PASS"
        or payload.get("graph_cleanup") != "PASS"
        or payload.get("submission_status")
        != "HOLD_PENDING_INFRA_FINALIZATION"
    ):
        raise ExperimentFailed(
            "Official Neo4j baseline application validation did not pass."
        )
    return payload, output_dir


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ExperimentFailed(
            f"Cannot read JSON artifact: {path.name}"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentFailed(
            f"JSON artifact is not an object: {path.name}"
        )
    return value


def _copy_baseline_artifacts(
    source_dir: Path,
    destination: Path,
) -> None:
    baseline_dir = destination / "baseline"
    baseline_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    for name in SAFE_BASELINE_ARTIFACTS:
        source = source_dir / name
        if not source.is_file():
            raise ExperimentFailed(
                f"Official baseline artifact is missing: {name}"
            )
        shutil.copy2(
            source,
            baseline_dir / name,
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest().upper()


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_baseline_evidence(
    *,
    evidence: dict[str, Any],
    projection: dict[str, Any],
) -> dict[str, Any]:
    database = evidence.get("database")
    if not isinstance(database, dict):
        raise ExperimentFailed(
            "Baseline evidence has no database validation."
        )

    graph_identity = database.get(
        "graph_identity_validation"
    )
    visual_validation = database.get(
        "visual_query_validation"
    )
    data_policy = projection.get(
        "data_policy"
    )
    input_files = projection.get(
        "input_files"
    )

    if not isinstance(graph_identity, dict):
        raise ExperimentFailed(
            "Graph identity validation is missing."
        )
    if not isinstance(visual_validation, dict):
        raise ExperimentFailed(
            "Visual query validation is missing."
        )
    if not isinstance(data_policy, dict):
        raise ExperimentFailed(
            "Projection data policy is missing."
        )
    if not isinstance(input_files, dict):
        raise ExperimentFailed(
            "Projection input file manifest is missing."
        )

    nodes = graph_identity.get("nodes")
    relationships = graph_identity.get(
        "relationships"
    )
    snapshot = graph_identity.get(
        "snapshot"
    )
    if not all(
        isinstance(value, dict)
        for value in (
            nodes,
            relationships,
            snapshot,
        )
    ):
        raise ExperimentFailed(
            "Canonical graph identity details are incomplete."
        )

    input_counts = {
        key: (
            int(input_files[key]["row_count"])
            if key in input_files
            and isinstance(input_files[key], dict)
            and isinstance(
                input_files[key].get("row_count"),
                int,
            )
            else None
        )
        for key in (
            "parents",
            "children",
            "evidence_groups",
        )
    }

    policy_flags = {
        key: data_policy.get(key)
        for key in (
            "source_text_included",
            "vectors_included",
            "prompts_included",
            "scores_included",
            "customer_data_included",
        )
    }

    checks = {
        "input_contract_15_53_43":
            input_counts
            == {
                "parents": 15,
                "children": 53,
                "evidence_groups": 43,
            },
        "database_validation":
            database.get("database_validation") == "PASS",
        "node_snapshot_match":
            nodes.get("match") is True,
        "relationship_snapshot_match":
            relationships.get("match") is True,
        "full_snapshot_match":
            snapshot.get("match") is True,
        "orphan_chunk_zero":
            database.get("orphan_chunk_count") == 0,
        "cross_model_path_zero":
            database.get("cross_model_path_count") == 0,
        "cross_namespace_zero":
            database.get(
                "cross_namespace_relationship_count"
            )
            == 0,
        "visual_queries_pass":
            visual_validation.get("status") == "PASS",
        "issues_empty":
            database.get("issues") == [],
        "metadata_only_projection":
            all(value is False for value in policy_flags.values()),
    }

    return {
        "checks": checks,
        "input_counts": input_counts,
        "node_counts": database.get(
            "node_counts",
            {},
        ),
        "relationship_counts": database.get(
            "relationship_counts",
            {},
        ),
        "visual_query_validation": visual_validation,
        "neo4j": database.get("neo4j", {}),
        "data_policy": policy_flags,
        "graph_identity_validation": graph_identity,
    }


def _write_report(
    *,
    path: Path,
    summary: dict[str, Any],
) -> None:
    baseline = summary["baseline"]
    faults = summary["fault_injection"]
    cleanup = summary["infra_cleanup"]
    lines = [
        "# E12 — Neo4j Evidence Lineage / Knowledge Relationship Validation",
        "",
        f"- Status: **{summary['status']}**",
        f"- Git SHA: `{summary['git_sha']}`",
        f"- Run ID: `{summary['run_id']}`",
        f"- Neo4j image digest: `{summary['neo4j_image_digest']}`",
        "- Scope: `JSONL_BASED_LINEAGE_QA`",
        "- Production retrieval: **UNCHANGED_PGVECTOR**",
        "- Production runtime connected: **False**",
        "- GraphRAG claim: **Not applicable / not claimed**",
        "",
        "## E12-01 Projection Fidelity",
        "",
        (
            "- Input contract: "
            f"{baseline['input_counts']['parents']} Parent / "
            f"{baseline['input_counts']['children']} Child / "
            f"{baseline['input_counts']['evidence_groups']} Evidence Group"
        ),
        (
            "- Canonical node snapshot match: "
            f"`{baseline['checks']['node_snapshot_match']}`"
        ),
        (
            "- Canonical relationship snapshot match: "
            f"`{baseline['checks']['relationship_snapshot_match']}`"
        ),
        (
            "- Full graph snapshot match: "
            f"`{baseline['checks']['full_snapshot_match']}`"
        ),
        "",
        "## E12-02 Lineage Traversal / Visual Query Validation",
        "",
        (
            "- Visual query validation: "
            f"`{baseline['visual_query_validation'].get('status')}`"
        ),
        (
            "- Visual query count: "
            f"`{baseline['visual_query_validation'].get('query_count')}`"
        ),
        (
            "- Normal orphan chunk count: "
            f"`{baseline['checks']['orphan_chunk_zero'] and 0}`"
        ),
        (
            "- Normal cross-model path count: "
            f"`{baseline['checks']['cross_model_path_zero'] and 0}`"
        ),
        "",
        "## E12-03 Controlled Fault Injection",
        "",
    ]
    for case in faults["cases"]:
        lines.extend(
            [
                f"### {case['case_id']} — {case['name']}",
                "",
                f"- Detected: `{case['detected']}`",
                (
                    "- Corrupted DB validation: "
                    f"`{case['corrupted_database_validation']}`"
                ),
                (
                    "- Relationship count before/after: "
                    f"`{case['relationship_count_before']} / "
                    f"{case['relationship_count_after']}`"
                ),
                (
                    "- Detector issues: "
                    + ", ".join(
                        f"`{issue}`"
                        for issue in case["issues"]
                    )
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## E12-04 Isolation / Cleanup",
            "",
            (
                "- Application graph cleanup: "
                f"`{summary['official_runner']['graph_cleanup']}`"
            ),
            (
                "- Disposable container count after cleanup: "
                f"`{cleanup['container_count']}`"
            ),
            (
                "- Anonymous volume count after cleanup: "
                f"`{cleanup['anonymous_volume_count']}`"
            ),
            "",
            "## Claim Boundary",
            "",
            (
                "Neo4j는 RAG 검색 엔진이나 GraphRAG로 사용하지 않았다. "
                "Repository JSONL에서 검증된 Evidence 관계 Metadata만 "
                "일회성 Neo4j QA Graph로 투영하여 Product → Document → "
                "ParentPage → EvidenceChunk → EvidenceGroup → Topic 계보와 "
                "관계 정합성을 검증했다."
            ),
            "",
            (
                "공식 qa_ephemeral runner의 `PARTIAL / "
                "HOLD_PENDING_INFRA_FINALIZATION` 상태는 그대로 보존한다. "
                "E12_COMPLETE는 로컬 일회성 실험 검증 완료를 뜻하며 "
                "Production Deployment 증거를 뜻하지 않는다."
            ),
            "",
            "## Presentation-ready Result",
            "",
            (
                "pgvector가 검색할 근거를 담당하는 동안, Neo4j에는 "
                "근거 본문·Embedding·Prompt를 저장하지 않고 관계 Metadata만 "
                "투영했다. 원본 JSONL과 실제 Neo4j의 Node·Relationship "
                "Snapshot이 일치했고, Orphan Chunk와 Cross-model 관계를 "
                "의도적으로 주입했을 때 정합성 검증이 이를 탐지했다."
            ),
            "",
        ]
    )
    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )


def _write_blocked_or_failed(
    *,
    result_dir: Path,
    status: str,
    git_sha: str | None,
    run_id: str | None,
    error: Exception,
) -> None:
    result_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    payload = {
        "status": status,
        "git_sha": git_sha,
        "run_id": run_id,
        "error_type": type(error).__name__,
        "message": str(error),
        "result_interpretation": (
            "NOT_A_VALID_E12_RESULT"
        ),
    }
    _write_json(
        result_dir / "summary.json",
        payload,
    )
    (result_dir / "report.md").write_text(
        "# E12 Neo4j Experiment\n\n"
        f"- Status: **{status}**\n"
        f"- Error type: `{type(error).__name__}`\n"
        f"- Message: {error}\n\n"
        "이 실행은 유효한 E12 실험 결과로 사용하지 않는다.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    print(
        "=== E12: Neo4j Evidence Lineage / "
        "Knowledge Relationship Validation ==="
    )

    git_sha: str | None = None
    run_id: str | None = None
    result_dir: Path | None = None
    worktree_parent: Path | None = None
    worktree: Path | None = None
    container_name: str | None = None
    volume_names: list[str] = []
    infra_cleanup: dict[str, Any] | None = None
    image_digest: str | None = None

    try:
        git_sha = _current_head()
        run_id = _make_run_id(git_sha)
        result_dir = RESULT_ROOT / run_id
        result_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        print(f"[E12] git_sha={git_sha}")
        print(f"[E12] run_id={run_id}")
        print(
            "[E12] scope=JSONL Evidence Lineage QA "
            "(not retrieval / not GraphRAG)"
        )

        _assert_required_sources(git_sha)

        docker_version = _docker_server_version()
        print(
            f"[E12] Docker daemon: {docker_version}"
        )

        worktree_parent, worktree = (
            _make_clean_worktree(git_sha)
        )
        print(
            "[E12] Source execution: "
            "temporary clean detached worktree"
        )

        image_reference, image_digest = (
            _docker_pull_and_digest(
                DEFAULT_NEO4J_IMAGE
            )
        )
        print(
            f"[E12] Neo4j RepoDigest: {image_digest}"
        )

        username = "neo4j"
        password = secrets.token_urlsafe(36)
        raw_nonce = secrets.token_urlsafe(36)
        nonce_sha256 = hashlib.sha256(
            raw_nonce.encode("utf-8")
        ).hexdigest()

        container_name = (
            f"waterbridge-{run_id}"
        )[:120]

        endpoint = _start_container(
            image_reference=image_reference,
            container_name=container_name,
            run_id=run_id,
            username=username,
            password=password,
        )
        parsed_endpoint = urlparse(endpoint)
        print(
            "[E12] Disposable Neo4j Query API: "
            f"{parsed_endpoint.scheme}://"
            f"{parsed_endpoint.hostname}:"
            f"{parsed_endpoint.port}"
        )

        volume_names = _container_volume_names(
            container_name
        )

        env = os.environ.copy()
        env.update(
            {
                "NEO4J_QA_USERNAME": username,
                "NEO4J_QA_PASSWORD": password,
                "NEO4J_QA_RUN_ID": run_id,
                "NEO4J_QA_TARGET_ID": container_name,
                "NEO4J_QA_TARGET_NONCE_SHA256":
                    nonce_sha256,
                "NEO4J_QA_IMAGE_DIGEST":
                    image_digest,
                "NEO4J_QA_ENDPOINT": endpoint,
            }
        )

        print(
            "[E12] QA target marker 준비/검증"
        )
        target = _prepare_target(
            worktree=worktree,
            env=env,
        )
        print(
            "[E12] Target marker: PASS "
            f"(marker_count={target['marker_count']})"
        )

        print(
            "[E12] E12-03 Controlled Fault Injection"
        )
        fault_results = _run_fault_injections(
            worktree=worktree,
            env=env,
        )
        for case in fault_results["cases"]:
            print(
                f"  - {case['case_id']} "
                f"{case['name']}: "
                f"{'PASS' if case['detected'] else 'FAIL'}"
            )

        print(
            "[E12] E12-01/E12-02 공식 Baseline "
            "Projection + Actual Neo4j Validation"
        )
        official_result, baseline_dir = (
            _run_official_baseline(
                worktree=worktree,
                env=env,
                run_id=run_id,
                endpoint=endpoint,
                image=DEFAULT_NEO4J_IMAGE,
                image_digest=image_digest,
            )
        )
        print(
            "[E12] Official application validation: "
            f"{official_result['application_validation']}"
        )
        print(
            "[E12] Official database validation: "
            f"{official_result['database_validation']}"
        )
        print(
            "[E12] Official graph cleanup: "
            f"{official_result['graph_cleanup']}"
        )

        evidence = _load_json(
            baseline_dir
            / "neo4j_lab_evidence.json"
        )
        projection = _load_json(
            baseline_dir
            / "projection_manifest.json"
        )
        baseline = _validate_baseline_evidence(
            evidence=evidence,
            projection=projection,
        )

        if not all(
            baseline["checks"].values()
        ):
            raise ExperimentFailed(
                "One or more baseline E12 checks failed: "
                + json.dumps(
                    baseline["checks"],
                    ensure_ascii=False,
                )
            )

        _copy_baseline_artifacts(
            baseline_dir,
            result_dir,
        )
        _write_json(
            result_dir
            / "fault_injection_results.json",
            fault_results,
        )

        # Secrets are no longer needed after all DB queries.
        env.pop("NEO4J_QA_PASSWORD", None)
        password = ""
        raw_nonce = ""

        print(
            "[E12] E12-04 Disposable Container Cleanup"
        )
        infra_cleanup = _cleanup_container(
            container_name=container_name,
            run_id=run_id,
            volume_names=volume_names,
        )
        container_name = None
        _write_json(
            result_dir
            / "infra_cleanup_evidence.json",
            {
                **infra_cleanup,
                "git_sha": git_sha,
                "image_repo_digest":
                    image_digest,
            },
        )
        print(
            "[E12] Infra cleanup: "
            f"{infra_cleanup['status']} "
            f"(containers="
            f"{infra_cleanup['container_count']}, "
            f"volumes="
            f"{infra_cleanup['anonymous_volume_count']})"
        )

        if infra_cleanup["status"] != "PASS":
            raise ExperimentFailed(
                "Disposable Neo4j container/volume cleanup failed."
            )

        fault_pass = all(
            case.get("detected") is True
            for case in fault_results["cases"]
        )
        official_pass = (
            official_result.get(
                "application_validation"
            )
            == "PASS"
            and official_result.get(
                "database_validation"
            )
            == "PASS"
            and official_result.get(
                "graph_cleanup"
            )
            == "PASS"
        )

        status = (
            "E12_COMPLETE"
            if (
                fault_pass
                and official_pass
                and all(
                    baseline["checks"].values()
                )
                and infra_cleanup["status"]
                == "PASS"
            )
            else "E12_FAILED"
        )

        summary = {
            "status": status,
            "git_sha": git_sha,
            "run_id": run_id,
            "scope":
                "JSONL_BASED_LINEAGE_QA",
            "execution":
                "LOCAL_DISPOSABLE_AUTHENTICATED_NEO4J",
            "source_execution":
                "TEMP_CLEAN_DETACHED_WORKTREE_AT_HEAD",
            "docker_server_version":
                docker_version,
            "neo4j_image":
                DEFAULT_NEO4J_IMAGE,
            "neo4j_image_digest":
                image_digest,
            "production_retrieval":
                "UNCHANGED_PGVECTOR",
            "production_runtime_connected":
                False,
            "rds_connected":
                False,
            "graphrag_implemented":
                False,
            "baseline": baseline,
            "fault_injection":
                fault_results,
            "official_runner":
                official_result,
            "infra_cleanup":
                infra_cleanup,
            "result_interpretation": (
                "E12 experimental validation only; "
                "not production deployment evidence"
            ),
            "presentation_claim": (
                "Neo4j에는 RAG 원문이나 Embedding을 저장하지 않고 "
                "Evidence 관계 Metadata만 투영했다. 원본 JSONL과 "
                "실제 Neo4j Graph의 Node·Relationship Snapshot이 "
                "일치했고, Orphan Chunk와 Cross-model 관계를 "
                "의도적으로 주입했을 때 정합성 검증이 이를 탐지했다."
            ),
        }
        _write_json(
            result_dir / "summary.json",
            summary,
        )
        _write_report(
            path=result_dir / "report.md",
            summary=summary,
        )

        artifact_rows: list[dict[str, Any]] = []
        for path in sorted(
            p
            for p in result_dir.rglob("*")
            if p.is_file()
            and p.name
            not in {
                "artifact_checksums.json",
            }
        ):
            artifact_rows.append(
                {
                    "path":
                        path.relative_to(
                            result_dir
                        ).as_posix(),
                    "sha256": _sha256(path),
                    "size_bytes":
                        path.stat().st_size,
                }
            )
        _write_json(
            result_dir
            / "artifact_checksums.json",
            {
                "algorithm": "SHA-256",
                "run_id": run_id,
                "artifacts": artifact_rows,
            },
        )

        print()
        print("=" * 88)
        print("[E12] FINAL")
        print(
            json.dumps(
                {
                    "status": status,
                    "git_sha": git_sha,
                    "run_id": run_id,
                    "input_counts":
                        baseline["input_counts"],
                    "node_snapshot_match":
                        baseline["checks"][
                            "node_snapshot_match"
                        ],
                    "relationship_snapshot_match":
                        baseline["checks"][
                            "relationship_snapshot_match"
                        ],
                    "visual_queries":
                        baseline[
                            "visual_query_validation"
                        ].get("status"),
                    "fault_cases_passed":
                        f"{sum(case['detected'] for case in fault_results['cases'])}/2",
                    "normal_orphan_chunk_count": 0,
                    "normal_cross_model_path_count": 0,
                    "graph_cleanup":
                        official_result[
                            "graph_cleanup"
                        ],
                    "infra_cleanup":
                        infra_cleanup["status"],
                    "official_submission_status":
                        official_result[
                            "submission_status"
                        ],
                    "output_dir":
                        result_dir.relative_to(
                            REPO_ROOT
                        ).as_posix(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return 0 if status == "E12_COMPLETE" else 1

    except ExperimentBlocked as exc:
        if result_dir is None:
            fallback = (
                RESULT_ROOT
                / "environment_blocked"
            )
        else:
            fallback = result_dir
        _write_blocked_or_failed(
            result_dir=fallback,
            status="E12_ENVIRONMENT_BLOCKED",
            git_sha=git_sha,
            run_id=run_id,
            error=exc,
        )
        print()
        print("=" * 88)
        print("[E12] E12_ENVIRONMENT_BLOCKED")
        print(str(exc))
        return 2

    except Exception as exc:
        if result_dir is None:
            fallback = RESULT_ROOT / "failed"
        else:
            fallback = result_dir
        _write_blocked_or_failed(
            result_dir=fallback,
            status="E12_FAILED",
            git_sha=git_sha,
            run_id=run_id,
            error=exc,
        )
        print()
        print("=" * 88)
        print("[E12] E12_FAILED")
        print(
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    finally:
        # Best-effort cleanup. Never leave a secret-bearing disposable
        # container running after a Python exception.
        if container_name is not None:
            try:
                cleanup = _cleanup_container(
                    container_name=container_name,
                    run_id=run_id or "unknown",
                    volume_names=volume_names,
                )
                if (
                    result_dir is not None
                    and infra_cleanup is None
                ):
                    _write_json(
                        result_dir
                        / "infra_cleanup_evidence.json",
                        {
                            **cleanup,
                            "git_sha": git_sha,
                            "image_repo_digest":
                                image_digest,
                            "cleanup_trigger":
                                "FINALLY_AFTER_NON_SUCCESS",
                        },
                    )
            except Exception:
                pass

        if (
            worktree_parent is not None
            and worktree is not None
        ):
            _remove_worktree(
                worktree_parent,
                worktree,
            )


if __name__ == "__main__":
    raise SystemExit(main())
