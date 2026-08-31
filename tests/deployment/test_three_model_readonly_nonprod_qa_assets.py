"""Static safety gates for the three-model Readonly NONPROD QA path."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/three-model-readonly-nonprod-qa.yml"
DOCKERFILE = ROOT / "ai/Dockerfile"


class ThreeModelReadonlyNonprodQaAssetsTests(unittest.TestCase):
    def test_workflow_is_manual_nonprod_only_and_pins_the_requested_source(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotRegex(text, r"(?m)^  pull_request:\s*$")
        self.assertNotRegex(text, r"(?m)^  push:\s*$")
        self.assertIn("environment: nonprod", text)
        self.assertNotIn("environment: production", text)
        self.assertIn(
            "RELEASE_SHA: f595dd8777eaf3f3f7f59ff63aa8bb2a250225ab",
            text,
        )
        self.assertIn('[[ "$GITHUB_REF" == "refs/heads/main" ]]', text)
        self.assertIn('git -C source merge-base --is-ancestor', text)

    def test_workflow_uses_nonprod_oidc_ecr_digest_and_ssm(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for name in (
            "NONPROD_AWS_REGION",
            "NONPROD_AWS_ACCOUNT_ID",
            "NONPROD_AWS_ROLE_ARN",
            "NONPROD_EC2_INSTANCE_ID",
            "NONPROD_ECR_AI_QA_REPOSITORY",
            "NONPROD_AI_VECTOR_SECRET_ID",
        ):
            self.assertIn(name, text)
        self.assertIn("id-token: write", text)
        self.assertIn("aws-actions/configure-aws-credentials@v6.2.3", text)
        self.assertIn("target: readonly-qa", text)
        self.assertIn("push: true", text)
        self.assertIn("@${BUILD_DIGEST}", text)
        self.assertIn("aws ssm send-command", text)
        self.assertIn("aws ssm get-command-invocation", text)
        self.assertNotIn("production-deploy.yml", text)

    def test_ssm_gate_is_one_shot_readonly_and_does_not_expose_the_dsn(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("/dev/shm/waterbridge-three-model-qa", text)
        self.assertIn("--read-only", text)
        self.assertIn("--cap-drop ALL", text)
        self.assertIn("--security-opt no-new-privileges", text)
        self.assertIn("validate_ai_readonly_runtime.py", text)
        self.assertIn("ai.scripts.verify_three_model_readonly_runtime", text)
        self.assertIn("RUNNING_AI_MUTATED=false", text)
        self.assertIn("DATABASE_MUTATED=false", text)
        self.assertIn("SECRET_EXPOSURE=false", text)
        self.assertIn("docker image rm \"$IMAGE_REF\"", text)
        self.assertIn(
            'rm -f "$evidence_dir/ssm-stdout.txt" "$evidence_dir/ssm-stderr.txt"',
            text,
        )
        for forbidden in (
            "docker compose",
            "docker restart",
            "docker stop",
            "manage.py migrate",
            "seed_demo_accounts",
        ):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("secrets.", text)

    def test_workflow_enforces_all_fifty_case_acceptance_values(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for assertion in (
            '.case_count == 50',
            '.passed_count == 50',
            '.positive_group_hit_count == 43',
            '.negative_no_evidence_count == 7',
            '.cross_model_hit_count == 0',
            '.direct_parent_hit_count == 0',
            '.unverified_evidence_hit_count == 0',
            '.public_runtime_activation == "HOLD"',
        ):
            self.assertIn(assertion, text)
        self.assertIn("actions/upload-artifact@v6", text)
        self.assertIn("evidence.sha256", text)

    def test_readonly_qa_image_bakes_the_pinned_model_and_runs_offline(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("FROM qa AS readonly-qa", text)
        self.assertIn("validate_ai_readonly_runtime.py", text)
        self.assertIn("SentenceTransformer('BAAI/bge-m3'", text)
        self.assertIn(
            "AI_EMBEDDING_REVISION=5617a9f61b028005a4858fdac845db406aefb181",
            text,
        )
        self.assertIn("HF_HUB_OFFLINE=1", text)
        self.assertIn("TRANSFORMERS_OFFLINE=1", text)


if __name__ == "__main__":
    unittest.main()
