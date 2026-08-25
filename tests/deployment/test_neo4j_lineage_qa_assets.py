"""Static safety gates for the optional Neo4j JSONL lineage QA workflow."""

from __future__ import annotations

from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.deployment.finalize_neo4j_lineage_qa import FinalizationError, finalize
from scripts.deployment.prepare_neo4j_lineage_qa import _validated_endpoint


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/neo4j-lineage-qa.yml"
PREPARE = ROOT / "scripts/deployment/prepare_neo4j_lineage_qa.py"
FINALIZE = ROOT / "scripts/deployment/finalize_neo4j_lineage_qa.py"


class Neo4jLineageQaAssetTests(unittest.TestCase):
    def test_workflow_is_manual_and_cannot_block_production_deployment(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        triggers = workflow.get(True, workflow.get("on"))
        self.assertEqual(set(triggers), {"workflow_dispatch"})
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("production-deploy", text)
        self.assertNotIn("workflow_run", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)

    def test_workflow_uses_disposable_loopback_authenticated_target(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("neo4j:2026.07.1", text)
        self.assertIn("numpy==2.5.2", text)
        self.assertIn("docker run --detach --rm", text)
        self.assertIn("--publish 127.0.0.1::7474", text)
        self.assertIn('NEO4J_AUTH=$NEO4J_QA_USERNAME/$NEO4J_QA_PASSWORD', text)
        self.assertIn("prepare_neo4j_lineage_qa.py", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("docker compose down -v", text)

    def test_workflow_runs_real_gate_and_always_cleans_and_uploads(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("AI_NEO4J_LINEAGE_E2E", text)
        self.assertIn("test_neo4j_evidence_lineage_runtime.py", text)
        self.assertIn("Expected QA runner exit 2", text)
        self.assertGreaterEqual(text.count("if: ${{ always() }}"), 3)
        self.assertIn("container_count", text)
        self.assertIn("anonymous_volume_count", text)
        self.assertIn("finalize_neo4j_lineage_qa.py", text)
        self.assertIn("actions/upload-artifact@v6", text)

    def test_helpers_enforce_marker_cleanup_and_exact_artifacts(self) -> None:
        prepare = PREPARE.read_text(encoding="utf-8")
        finalize = FINALIZE.read_text(encoding="utf-8")
        self.assertIn("WaterbridgeQaTarget", prepare)
        self.assertIn("Neo4j QA target is not empty", prepare)
        self.assertIn("REQUIRED_AI_ARTIFACTS", finalize)
        self.assertIn("graph_projection.json", finalize)
        self.assertIn("container_count", finalize)
        self.assertIn("anonymous_volume_count", finalize)

    def test_prepare_rejects_non_loopback_endpoint(self) -> None:
        self.assertEqual(
            _validated_endpoint("http://127.0.0.1:7474/"),
            "http://127.0.0.1:7474",
        )
        with self.assertRaises(Exception):
            _validated_endpoint("https://neo4j.example.com")

    def test_finalizer_requires_clean_passed_ai_and_zero_cleanup(self) -> None:
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        run_id = "neo4j-unit-1"
        git_sha = "1" * 40
        image_digest = "sha256:" + "2" * 64
        with tempfile.TemporaryDirectory(dir=runtime) as directory:
            artifact_dir = Path(directory)
            source = {
                "after": {"git_sha": git_sha, "git_dirty": False},
                "validation": {"status": "PASS"},
            }
            common = {
                "run_id": run_id,
                "application_validation": "PASS",
                "submission_status": "HOLD_PENDING_INFRA_FINALIZATION",
                "source": source,
            }
            payloads = {
                "run_manifest.json": common,
                "projection_manifest.json": {},
                "neo4j_lab_evidence.json": {
                    **common,
                    "graph_cleanup": {"status": "PASS"},
                },
                "neo4j_evidence_lineage_visual.svg": "<svg></svg>\n",
                "visual_query_catalog.json": {},
                "neo4j_browser_visual_query.cypher": "RETURN 1;\n",
                "cleanup_evidence.json": {"status": "PASS"},
            }
            rows = []
            for name, payload in payloads.items():
                path = artifact_dir / name
                if isinstance(payload, str):
                    path.write_text(payload, encoding="utf-8")
                else:
                    path.write_text(json.dumps(payload), encoding="utf-8")
                rows.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "file_sha256": sha256(path.read_bytes()).hexdigest().upper(),
                    }
                )
            (artifact_dir / "artifact_manifest.json").write_text(
                json.dumps({"run_id": run_id, "artifacts": rows}),
                encoding="utf-8",
            )
            cleanup_path = artifact_dir / "infra_cleanup_evidence.json"
            cleanup_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "run_id": run_id,
                        "git_sha": git_sha,
                        "image_repo_digest": image_digest,
                        "container_count": 0,
                        "anonymous_volume_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            submission, checksums = finalize(
                artifact_dir=artifact_dir,
                run_id=run_id,
                git_sha=git_sha,
                image_digest=image_digest,
                ci_run_id="123",
                ci_run_url="https://example.invalid/runs/123",
            )

            self.assertTrue(submission.is_file())
            self.assertTrue(checksums.is_file())
            cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
            cleanup["container_count"] = 1
            cleanup_path.write_text(json.dumps(cleanup), encoding="utf-8")
            submission.unlink()
            checksums.unlink()
            with self.assertRaises(FinalizationError):
                finalize(
                    artifact_dir=artifact_dir,
                    run_id=run_id,
                    git_sha=git_sha,
                    image_digest=image_digest,
                    ci_run_id="123",
                    ci_run_url="https://example.invalid/runs/123",
                )


if __name__ == "__main__":
    unittest.main()
