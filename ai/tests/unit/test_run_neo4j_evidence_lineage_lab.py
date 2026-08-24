"""Neo4j QA runner의 제출 상태·Git 계보·Artifact 무결성 테스트."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai.app.experiments.neo4j_evidence_lineage import (
    LAB_LOOPBACK_PROFILE,
    QA_EPHEMERAL_LOOPBACK_PROFILE,
)
from ai.scripts import run_neo4j_evidence_lineage_lab as runner


IMAGE_DIGEST = "sha256:" + "a" * 64
RUN_ID = "runner-unit-001"


class _FakeClient:
    def close(self) -> None:
        return None


def _git_identity(*, dirty: bool = False) -> dict[str, Any]:
    return {
        "branch": "dongyoon",
        "checkout_mode": "BRANCH",
        "git_sha": "1" * 40,
        "git_dirty": dirty,
        "worktree_status_sha256": "2" * 64 if dirty else "0" * 64,
        "ci_expected_sha": None,
        "ci_sha_matches_head": None,
        "ci_head_ref": None,
        "ci_ref_name": None,
    }


def _database_report() -> dict[str, Any]:
    return {
        "database_validation": "PASS",
        "neo4j": {
            "name": "Neo4j Kernel",
            "version": "2026.07.1",
            "edition": "community",
            "database": "neo4j",
            "endpoint_class": "TEST_EXECUTOR",
        },
        "node_counts": {},
        "relationship_counts": {},
        "graph_identity_validation": {"status": "PASS"},
        "visual_summary": {"rows": [], "match": True, "row_count": 0},
        "visual_query_validation": {"status": "PASS", "query_count": 6},
        "issues": [],
    }


def _patch_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    dirty: bool = False,
) -> None:
    identity = _git_identity(dirty=dirty)
    monkeypatch.setattr(runner, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(runner, "_git_identity", lambda: dict(identity))
    monkeypatch.setattr(runner, "_client", lambda **_: _FakeClient())
    monkeypatch.setattr(
        runner,
        "load_graph_into_neo4j",
        lambda *_, profile, run_id, target_identity: SimpleNamespace(
            profile=profile,
            run_id=run_id,
            database="neo4j",
            marker_validated=target_identity is not None,
            unexpected_node_count=0,
            relationship_count=0,
        ),
    )
    monkeypatch.setattr(runner, "verify_graph_in_neo4j", lambda *_, **__: _database_report())
    monkeypatch.setattr(
        runner,
        "cleanup_graph_run",
        lambda *_, **__: {
            "status": "PASS",
            "scope": "QA_RUN_ONLY",
            "deleted_node_count": 142,
            "residual_node_count": 0,
            "residual_relationship_count": 0,
            "unexpected_node_count_excluding_target_marker": 0,
            "unexpected_relationship_count": 0,
            "target_marker_validation": "PASS",
            "container_cleanup": "NOT_RUN_INFRA_OWNED",
        },
    )
    monkeypatch.setattr(
        runner,
        "render_lineage_svg",
        lambda _: '<svg xmlns="http://www.w3.org/2000/svg"></svg>\n',
    )


def _set_qa_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_QA_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_QA_PASSWORD", "secret-not-for-artifact")
    monkeypatch.setenv("NEO4J_QA_TARGET_ID", "container-runner-unit")
    monkeypatch.setenv("NEO4J_QA_TARGET_NONCE_SHA256", "b" * 64)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest().upper()


def test_qa_runner_keeps_submission_on_hold_and_hashes_durable_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_runtime(monkeypatch, tmp_path)
    _set_qa_environment(monkeypatch)

    exit_code, result = runner.run_lab(
        output_dir=".runtime/runner-qa",
        generated_at="2026-08-25T10:00:00+09:00",
        endpoint="http://127.0.0.1:7474",
        run_id=RUN_ID,
        profile=QA_EPHEMERAL_LOOPBACK_PROFILE,
        neo4j_image_digest=IMAGE_DIGEST,
    )

    output = tmp_path / ".runtime/runner-qa"
    evidence = json.loads((output / "neo4j_lab_evidence.json").read_text("utf-8"))
    artifact_manifest = json.loads(
        (output / "artifact_manifest.json").read_text("utf-8")
    )
    checksum_rows = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (output / "checksums.sha256").read_text("utf-8").splitlines()
    }

    assert exit_code == 2
    assert result["application_validation"] == "PASS"
    assert result["submission_status"] == "HOLD_PENDING_INFRA_FINALIZATION"
    assert evidence["result"] == "PARTIAL"
    assert evidence["pm_approval_status"] == "HOLD_PENDING_INFRA_FINALIZATION"
    assert evidence["source"]["validation"]["status"] == "PASS"
    assert "graph_projection.json" not in {path.name for path in output.iterdir()}
    for artifact in artifact_manifest["artifacts"]:
        path = tmp_path / artifact["path"]
        assert artifact["file_sha256"] == _file_sha256(path)
    assert "artifact_manifest.json" in checksum_rows
    assert "checksums.sha256" not in checksum_rows
    for name, expected_hash in checksum_rows.items():
        assert expected_hash == _file_sha256(output / name)
    serialized = json.dumps(evidence, ensure_ascii=False)
    assert "secret-not-for-artifact" not in serialized


def test_clean_lab_pass_is_not_deployment_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_runtime(monkeypatch, tmp_path)

    exit_code, result = runner.run_lab(
        output_dir=".runtime/runner-lab",
        generated_at="2026-08-25T10:00:00+09:00",
        endpoint="http://127.0.0.1:7474",
        run_id=RUN_ID,
        profile=LAB_LOOPBACK_PROFILE,
    )

    assert exit_code == 0
    assert result["result"] == "PASS"
    assert result["submission_status"] == "LAB_PASS_NOT_DEPLOYMENT_EVIDENCE"


def test_git_provenance_fails_on_head_worktree_or_ci_sha_change() -> None:
    baseline = _git_identity()

    assert runner._git_provenance(baseline, dict(baseline))["status"] == "PASS"
    changed_head = {**baseline, "git_sha": "3" * 40}
    changed_worktree = {**baseline, "worktree_status_sha256": "4" * 64}
    ci_mismatch = {**baseline, "ci_sha_matches_head": False}
    assert runner._git_provenance(baseline, changed_head)["status"] == "FAIL"
    assert runner._git_provenance(baseline, changed_worktree)["status"] == "FAIL"
    assert runner._git_provenance(ci_mismatch, ci_mismatch)["status"] == "FAIL"


def test_git_identity_uses_ci_ref_for_detached_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = {
        ("branch", "--show-current"): "",
        ("rev-parse", "HEAD"): "5" * 40,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
    }
    monkeypatch.setattr(runner, "_git_output", lambda *args: outputs[args])
    monkeypatch.setenv("GITHUB_SHA", "5" * 40)
    monkeypatch.setenv("GITHUB_HEAD_REF", "dongyoon")
    monkeypatch.setenv("GITHUB_REF_NAME", "merge")

    identity = runner._git_identity()

    assert identity["checkout_mode"] == "DETACHED"
    assert identity["branch"] == "dongyoon"
    assert identity["ci_sha_matches_head"] is True
