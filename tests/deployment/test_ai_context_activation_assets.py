"""Static fail-closed gates for persistent JAC104 Context activation."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/deployment/production/manage-ai-context-activation.sh"
)
CALLER = ROOT / ".github/workflows/production-ai-context-activation.yml"
TRUSTED = ROOT / ".github/workflows/production-deploy.yml"
DEPLOY = ROOT / "scripts/deployment/production/deploy-release.sh"
ROLLBACK = ROOT / "scripts/deployment/production/rollback-release.sh"
MAINTENANCE = (
    ROOT / "scripts/deployment/production/maintain_release_images.py"
)
CANARY = (
    ROOT / "scripts/deployment/production/manage-ai-handoff-canary.sh"
)
RUNBOOK = ROOT / "docs/deployment/production-deployment-runbook.md"
DISPATCH = (
    ROOT
    / "backend/apps/inquiries/services/human_review_resume_dispatch_service.py"
)
RESUME_CLIENT = ROOT / "backend/integrations/ai/human_review_resume.py"
AI_POLICY = ROOT / "ai/app/orchestration/harness/product_registry.py"


class AIContextActivationAssetTests(unittest.TestCase):
    def test_caller_uses_protected_trusted_main_operation(self) -> None:
        caller = CALLER.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", caller)
        self.assertIn("expected_release_sha", caller)
        self.assertIn("ai_context_activation", caller)
        self.assertIn("context_activation_action", caller)
        self.assertIn("production-deploy.yml@main", caller)
        for action in ("preflight", "activate", "status", "deactivate"):
            self.assertRegex(caller, rf"(?m)^\s+- {action}$")

    def test_trusted_workflow_validates_and_transports_activation(self) -> None:
        trusted = TRUSTED.read_text(encoding="utf-8")

        self.assertIn("inputs.operation == 'ai_context_activation'", trusted)
        self.assertIn("refs/heads/main", trusted)
        self.assertIn("manage-ai-context-activation.sh", trusted)
        self.assertIn("build_ssm_bash_parameters.py", trusted)
        self.assertIn("AI_CONTEXT_ACTIVATION_PASS", trusted)
        self.assertIn("AI_CONTEXT_DEACTIVATION_PASS", trusted)
        self.assertIn("First E2E failure policy: deactivate and stop", trusted)
        self.assertNotIn("OPENAI_API_KEY=${{", trusted)

    def test_activation_is_exact_release_bound_and_fail_closed(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("current_release_sha_mismatch", script)
        self.assertIn("ai-context-activation.state", script)
        self.assertIn("ai-handoff-canary.state", script)
        self.assertIn("flock -n 9", script)
        self.assertIn("active_ai_runs_present", script)
        self.assertIn('"false:false:false"', script)
        self.assertIn('"true:true:true"', script)
        self.assertIn("set_runtime_enabled false", script)
        self.assertIn("AI_CONTEXT_ACTIVATION_FAILURE_RESTORED", script)
        self.assertIn("AI_CONTEXT_ACTIVATION_FAILURE_FAIL_CLOSED", script)
        self.assertIn("AI_CONTEXT_DEACTIVATION_FAILURE_RESTORED", script)
        self.assertIn("AI_CONTEXT_DEACTIVATION_FAILURE_FAIL_CLOSED", script)
        self.assertIn("compose stop backend ai", script)
        self.assertIn("--force-recreate --wait ai", script)
        self.assertIn("--force-recreate --wait backend", script)
        self.assertIn("os.replace", script)
        self.assertIn("os.fsync", script)
        self.assertIn("protected_environment_drift_detected", script)

    def test_activation_scope_is_policy_not_scenario_hardcoding(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        dispatch = DISPATCH.read_text(encoding="utf-8")
        client = RESUME_CLIENT.read_text(encoding="utf-8")
        ai_policy = AI_POLICY.read_text(encoding="utf-8")

        for text in (script, client, ai_policy):
            self.assertIn("WPUJAC104DWH", text)
        self.assertIn("CONTEXT_RESUME_APPROVED_MODEL_CODES", dispatch)
        self.assertIn("RUNTIME_PRODUCT_NOT_APPROVED", client)
        self.assertIn("RUNTIME_APPROVED_EXACT_MODEL_CODES", ai_policy)
        self.assertNotIn("WPUIAC425SNW", script)
        self.assertNotIn("WPUIAC606SNW", script)
        forbidden = (
            "structured_symptom",
            "evidence_references",
            "ai_draft_summary",
            "customer_query",
            "expected_summary",
        )
        for value in forbidden:
            self.assertNotIn(value, script)

    def test_activation_does_not_mutate_data_or_retry_provider(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8").casefold()

        forbidden_patterns = (
            r"manage\.py\s+migrate",
            r"manage\.py\s+seed",
            r"manage\.py\s+run_ai_context_resume_handoff_canary",
            r"docker\s+compose(?:\s+\s*)*down\s+-v",
            r"openai_api_key",
            r"provider_calls",
            r"while.*provider",
        )
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertNotRegex(script, pattern)

    def test_release_and_canary_are_blocked_while_active(self) -> None:
        deploy = DEPLOY.read_text(encoding="utf-8")
        rollback = ROLLBACK.read_text(encoding="utf-8")
        maintenance = MAINTENANCE.read_text(encoding="utf-8")
        canary = CANARY.read_text(encoding="utf-8")
        trusted = TRUSTED.read_text(encoding="utf-8")

        for text in (deploy, rollback, maintenance, canary, trusted):
            self.assertIn("ai-context-activation.state", text)
        self.assertIn("CONTEXT_ACTIVATION_ACTIVE", maintenance)
        self.assertIn("manage-ai-context-activation.sh", deploy)
        self.assertIn("manage-ai-context-activation.sh", trusted)

    def test_canary_parser_selects_one_anchored_report_from_logs(self) -> None:
        canary = CANARY.read_text(encoding="utf-8")

        self.assertIn("sys.argv[1].splitlines()", canary)
        self.assertIn('"overall_status" in candidate', canary)
        self.assertIn('"canary_scope" in candidate', canary)
        self.assertIn("if len(reports) != 1", canary)
        self.assertNotIn("report = json.loads(sys.argv[1])", canary)

    def test_runbook_requires_one_test_then_stop_on_failure(self) -> None:
        runbook = RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("JAC104 Context Agent limited activation", runbook)
        self.assertIn("JAC104_LIMITED", runbook)
        self.assertIn("run only one approved synthetic JAC104 E2E", runbook)
        self.assertRegex(runbook, r"If it\s+fails, do not replay")
        self.assertIn("Immediately run `deactivate`", runbook)
        self.assertIn("Never hardcode a symptom", runbook)


if __name__ == "__main__":
    unittest.main()
