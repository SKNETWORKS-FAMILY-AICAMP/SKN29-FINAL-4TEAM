"""Static fail-closed gates for the production AI Handoff Canary assets."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deployment/production/manage-ai-handoff-canary.sh"
AUTO_RUNNER = (
    ROOT
    / "scripts/deployment/production/run-ai-resume-handoff-canary.sh"
)
DISPATCH = ROOT / ".github/workflows/production-ai-handoff-canary.yml"
TRUSTED = ROOT / ".github/workflows/production-deploy.yml"
DEPLOY = ROOT / "scripts/deployment/production/deploy-release.sh"
ENV_PREPARE = (
    ROOT
    / "scripts/deployment/production/prepare_ai_handoff_runtime_env.py"
)
RESUME_ENV_PREPARE = (
    ROOT
    / "scripts/deployment/production/prepare_ai_resume_runtime_env.py"
)
NGINX_PREPARE = (
    ROOT / "scripts/deployment/production/prepare_ai_handoff_nginx.py"
)
ROLLBACK = ROOT / "scripts/deployment/production/rollback-release.sh"
RUNBOOK = ROOT / "docs/deployment/production-deployment-runbook.md"


class AIHandoffCanaryAssetTests(unittest.TestCase):
    def test_dispatch_uses_the_existing_oidc_pinned_reusable_workflow(self) -> None:
        dispatch = DISPATCH.read_text(encoding="utf-8")
        trusted = TRUSTED.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", dispatch)
        for name in (
            "action:",
            "expected_release_sha:",
            "inquiry_id:",
            "operator_ip:",
        ):
            self.assertIn(name, dispatch)
        for action in ("preflight", "open", "run", "status", "close"):
            self.assertRegex(dispatch, rf"(?m)^          - {action}$")
        self.assertIn(
            "SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM/"
            ".github/workflows/production-deploy.yml@main",
            dispatch,
        )
        self.assertNotIn("environment: production", dispatch)
        self.assertIn("operation: ai_handoff_canary", dispatch)
        self.assertIn("if: ${{ inputs.operation == 'ai_handoff_canary' }}", trusted)
        self.assertIn("environment: production", trusted)
        self.assertIn("aws-actions/configure-aws-credentials@v6.2.3", trusted)
        self.assertIn("allowed-account-ids: ${{ env.AWS_ACCOUNT_ID }}", trusted)
        self.assertIn("printf -v canary_command '%q %q %q %q %q'", trusted)
        self.assertIn("SSM_CANARY_POLL_TIMEOUT seconds=1200", trusted)
        self.assertIn("CANARY_OPEN_PASS", trusted)
        self.assertIn("CANARY_RUN_PASS", trusted)
        self.assertIn("Always-on activation:", trusted)
        self.assertIn("HOLD", trusted)

    def test_canary_script_is_bundled_and_deploy_is_window_aware(self) -> None:
        trusted = TRUSTED.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        rollback = ROLLBACK.read_text(encoding="utf-8")

        self.assertGreaterEqual(
            trusted.count("manage-ai-handoff-canary.sh"),
            2,
        )
        self.assertGreaterEqual(
            trusted.count("run-ai-resume-handoff-canary.sh"),
            2,
        )
        self.assertIn("chmod 0750", trusted)
        self.assertIn("ai-handoff-canary.state", deploy)
        self.assertIn("DEPLOYMENT_BLOCKED: active AI Handoff Canary window", deploy)
        self.assertIn("DEPLOYMENT_MUTATION_STARTED", deploy)
        self.assertIn("mutation_started=true", trusted)
        self.assertIn("steps.deploy.outputs.mutation_started == 'true'", trusted)
        self.assertIn("steps.deploy.outcome == 'success'", trusted)
        self.assertIn("DEPLOYMENT_BLOCKED: active AI Handoff Canary window", trusted)
        self.assertIn("ROLLBACK_BLOCKED: active AI Handoff Canary window", rollback)

    def test_automatic_runner_always_closes_after_execute(self) -> None:
        runner = AUTO_RUNNER.read_text(encoding="utf-8")

        self.assertIn('"$manager" preflight', runner)
        self.assertIn('"$manager" open', runner)
        self.assertIn('"$manager" execute', runner)
        self.assertIn('"$manager" close', runner)
        self.assertIn("trap close_after_run EXIT", runner)
        self.assertIn("CANARY_RUN_FAILURE_RESTORED", runner)
        self.assertIn("CANARY_RUN_FAILURE_FAIL_CLOSED", runner)
        self.assertIn("CANARY_RUN_PASS", runner)
        self.assertLess(
            runner.index('"$manager" execute'),
            runner.index('"$manager" close'),
        )

    def test_release_prepares_fail_closed_handoff_environment(self) -> None:
        trusted = TRUSTED.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        prepare = ENV_PREPARE.read_text(encoding="utf-8")

        self.assertIn("prepare_ai_handoff_runtime_env.py", trusted)
        self.assertIn("prepare_ai_handoff_runtime_env.py", deploy)
        self.assertLess(
            deploy.index("DEPLOYMENT_MUTATION_STARTED"),
            deploy.index('python3 "$ai_handoff_env_prepare_script"'),
        )
        self.assertIn('"AI_HANDOFF_BACKEND_ENABLED": "false"', prepare)
        self.assertIn('"AI_BACKEND_BASE_URL": "http://backend:8000"', prepare)
        self.assertIn('"AI_HANDOFF_TIMEOUT_SECONDS": "2.0"', prepare)
        self.assertIn("os.replace", prepare)
        self.assertIn("os.fsync", prepare)
        self.assertNotIn("print(secret_value", prepare)
        self.assertIn("secret_values_printed=false", prepare)

    def test_release_prepares_fail_closed_resume_environment(self) -> None:
        trusted = TRUSTED.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        prepare = RESUME_ENV_PREPARE.read_text(encoding="utf-8")

        self.assertIn("prepare_ai_resume_runtime_env.py", trusted)
        self.assertIn("prepare_ai_resume_runtime_env.py", deploy)
        self.assertLess(
            deploy.index("DEPLOYMENT_MUTATION_STARTED"),
            deploy.index('python3 "$ai_resume_env_prepare_script"'),
        )
        self.assertIn("AI_HUMAN_REVIEW_RESUME_ENABLED", prepare)
        self.assertIn("AI_HUMAN_REVIEW_RESUME_TOKEN", prepare)
        self.assertIn("DOMAIN_SEPARATED_DERIVATION", prepare)
        self.assertIn("hmac.new", prepare)
        self.assertIn("os.replace", prepare)
        self.assertIn("os.fsync", prepare)
        self.assertNotIn("print(resume_token", prepare)
        self.assertIn("secret_values_printed=false", prepare)

    def test_release_prepares_exact_canary_nginx_server_scope(self) -> None:
        trusted = TRUSTED.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        prepare = NGINX_PREPARE.read_text(encoding="utf-8")

        self.assertIn("prepare_ai_handoff_nginx.py", trusted)
        self.assertIn("prepare_ai_handoff_nginx.py", deploy)
        self.assertLess(
            deploy.index("DEPLOYMENT_MUTATION_STARTED"),
            deploy.index('python3 "$ai_handoff_nginx_prepare_script"'),
        )
        self.assertIn("expected exactly one Canary server block", prepare)
        self.assertIn("/etc/nginx/waterbridge-server.d/*.conf", prepare)
        self.assertIn('"127.0.0.1:18080"', prepare)
        self.assertIn("resolve(strict=True)", prepare)
        self.assertIn("os.replace", prepare)
        self.assertIn("Nginx backup checksum collision", prepare)
        self.assertIn('["nginx", "-t"]', prepare)
        self.assertIn('["systemctl", "reload", "nginx"]', prepare)

    def test_script_has_exact_target_gate_and_denies_all_other_ai_entries(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "location ~ ^/api/v1/inquiries/${inquiry_id}/(submit|answers)/?$",
            script,
        )
        self.assertRegex(
            script,
            r'location ~ "\^/api/v1/inquiries/\[0-9a-fA-F\]',
        )
        self.assertGreaterEqual(script.count("deny all;"), 2)
        self.assertIn("inquiries/human-reviews/", script)
        self.assertIn("/decision/?$", script)
        self.assertIn("allow ${operator_ip};", script)
        self.assertIn("nginx_canary_server_scope_invalid", script)
        self.assertIn("nginx -t", script)
        self.assertIn("systemctl reload nginx", script)
        self.assertIn("nginx_original_checksum_not_restored", script)

    def test_script_starts_false_and_fail_closes_every_open_failure(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")

        for key in (
            "AI_HANDOFF_BACKEND_ENABLED",
            "AI_BACKEND_BASE_URL",
            "AI_HANDOFF_INTERNAL_TOKEN",
            "AI_HANDOFF_TIMEOUT_SECONDS",
            "AI_HUMAN_REVIEW_RESUME_ENABLED",
            "AI_HUMAN_REVIEW_RESUME_TOKEN",
        ):
            self.assertIn(key, script)
        self.assertIn("resume_and_handoff_must_start_disabled", script)
        self.assertIn("ENVIRONMENT_BLOCKED reason=", script)
        self.assertIn("set_runtime_enabled false", script)
        self.assertIn("compose stop backend ai", script)
        self.assertIn('"false:false:false"', script)
        self.assertIn('"true:true:true"', script)
        self.assertIn("pending_human_reviews", script)
        self.assertIn("non_synthetic_pending_human_reviews", script)
        self.assertIn("pending_human_reviews_before", script)
        self.assertIn("pending_review_scope=SYNTHETIC_ONLY", script)
        self.assertNotIn('pending_human_reviews=0', script)
        self.assertIn("recreate_runtime", script)
        self.assertIn("run_ai_context_resume_handoff_canary", script)
        self.assertIn("AWS_AUTO_CONTEXT_HANDOFF_PASS", script)
        self.assertIn("CANARY_EXECUTE_PASS", script)
        self.assertIn("CANARY_OPEN_FAILURE_RESTORED", script)
        self.assertIn("CANARY_OPEN_FAILURE_FAIL_CLOSED", script)
        self.assertIn("CANARY_CLOSE_FAILURE_RESTORED", script)
        self.assertIn("CANARY_CLOSE_FAILURE_FAIL_CLOSED", script)
        self.assertIn("trap on_exit EXIT", script)
        self.assertIn("systemd-run", script)
        self.assertIn("max_window_minutes=15", script)
        self.assertIn("drain_seconds=65", script)
        self.assertIn("other_window_ai_runs=", script)
        self.assertIn("target_payload_hashes=", script)
        self.assertIn("os.replace", script)
        self.assertIn("os.fsync", script)

    def test_script_does_not_mutate_schema_seed_or_disclose_env_values(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        casefolded = script.casefold()

        forbidden = (
            r"manage\.py\s+migrate",
            r"manage\.py\s+seed",
            r"docker\s+compose(?:\s+\S+)*\s+down\s+-v",
            r"(?m)^\s*(?:cat|head|tail)\s+.*ai\.env",
            r"set\s+-x",
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotRegex(casefolded, pattern)
        self.assertNotIn("AI_HANDOFF_INTERNAL_TOKEN=$", script)
        self.assertNotIn("print(values", script)
        self.assertNotIn("sanitized_payload", script)
        self.assertNotIn("ai_draft_summary", script)

    def test_runbook_keeps_canary_and_always_on_approval_separate(self) -> None:
        runbook = RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("AI Resume and Handoff Canary", runbook)
        self.assertIn("AI_HANDOFF_BACKEND_ENABLED=false", runbook)
        self.assertIn("15분", runbook)
        self.assertIn("상시 활성화", runbook)
        self.assertIn("Migration", runbook)
        self.assertIn("Seed", runbook)


if __name__ == "__main__":
    unittest.main()
