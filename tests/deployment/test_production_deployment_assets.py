"""Static safety gates for WaterBridge production deployment assets."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/docker/compose/production/compose.yml"
TEMPO = ROOT / "infra/docker/compose/production/tempo.yml"
STORAGE = ROOT / "infra/cloud/aws/deployment/storage-stack.yml"
DEPLOY = ROOT / "scripts/deployment/production/deploy-release.sh"
ROLLBACK = ROOT / "scripts/deployment/production/rollback-release.sh"
BOOTSTRAP = ROOT / "scripts/deployment/production/bootstrap-host.sh"
WORKFLOW = ROOT / ".github/workflows/production-deploy.yml"
BOOTSTRAP_WORKFLOW = ROOT / ".github/workflows/production-bootstrap.yml"
BACKEND_PREFLIGHT = ROOT / "scripts/deployment/production/validate_backend_runtime.py"
AI_PREFLIGHT = ROOT / "scripts/deployment/production/validate_ai_readonly_runtime.py"


class ProductionDeploymentAssetTests(unittest.TestCase):
    def test_compose_has_exactly_four_runtime_services(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        service_block = text.split("services:\n", 1)[1].split("\nnetworks:\n", 1)[0]
        services = re.findall(r"^  ([a-z][a-z0-9-]*):$", service_block, re.MULTILINE)
        self.assertEqual(services, ["web", "backend", "ai", "trace-store"])
        self.assertNotRegex(text, r"(?m)^  postgres(?:ql)?:$")
        self.assertNotIn("docker compose down -v", text)
        deploy = DEPLOY.read_text(encoding="utf-8")
        self.assertIn("compose config --services | sort", deploy)
        self.assertIn("expected_services=(ai backend trace-store web)", deploy)
        self.assertIn("compose config --images", deploy)
        self.assertNotIn("if compose config | grep", deploy)

    def test_application_images_are_digest_addressed(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        for service in ("WEB", "BACKEND", "AI"):
            expected = (
                f'${{{service}_IMAGE:?{service}_IMAGE is required}}'
                f'@${{{service}_IMAGE_DIGEST:?{service}_IMAGE_DIGEST is required}}'
            )
            self.assertIn(expected, text)
        self.assertIn(
            "grafana/tempo:3.0.3@sha256:05321ebf1f191fde34282b3dc86e68f511d489133df7963cd1670a2e1e11b33c",
            text,
        )
        self.assertNotRegex(text, r"(?m)(?:^|:)latest(?:$|\s)")

    def test_production_compose_never_runs_database_mutation(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (COMPOSE, DEPLOY, ROLLBACK, WORKFLOW)
        ).casefold()
        forbidden_patterns = (
            r"manage\.py\s+migrate",
            r"manage\.py\s+seed",
            r"manage\.py\s+import",
            r"docker\s+compose(?:\s+\S+)*\s+down\s+-v",
        )
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, combined))

    def test_tempo_uses_s3_and_fourteen_day_retention(self) -> None:
        text = TEMPO.read_text(encoding="utf-8")
        compose = COMPOSE.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        self.assertIn("backend: s3", text)
        self.assertIn("prefix: tempo", text)
        self.assertGreaterEqual(text.count("block_retention: 336h"), 2)
        self.assertIn("path: /var/tempo/wal", text)
        self.assertIn("live_store:", text)
        self.assertIn("max_trace_idle: 5s", text)
        self.assertIn("max_block_duration: 30s", text)
        self.assertIn("-health.url=http://127.0.0.1:3200/ready", compose)
        self.assertIn("-config.verify=true", deploy)
        self.assertIn("TRACE_S3_RESTART_QUERY_PASS", deploy)
        self.assertIn("compose restart trace-store", deploy)

    def test_storage_is_private_encrypted_versioned_and_retained(self) -> None:
        text = STORAGE.read_text(encoding="utf-8")
        bootstrap = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
        for key in (
            "SSEAlgorithm: AES256",
            "BlockPublicAcls: true",
            "BlockPublicPolicy: true",
            "IgnorePublicAcls: true",
            "RestrictPublicBuckets: true",
            "Status: Enabled",
            "NoncurrentDays: 14",
            "DaysAfterInitiation: 1",
            "aws:SecureTransport",
        ):
            self.assertIn(key, text)
        self.assertIn("DeletionPolicy: Retain", text)
        self.assertIn("Sid: AllowEc2TempoObjects", text)
        self.assertIn("Sid: AllowEc2ReleaseReads", text)
        self.assertIn('Condition.Bool["aws:SecureTransport"]', bootstrap)
        self.assertIn('(.Filter.Prefix // .Prefix) == "tempo/"', bootstrap)

    def test_web_container_is_remote_only_and_spa_safe(self) -> None:
        dockerfile = (ROOT / "web/Dockerfile").read_text(encoding="utf-8")
        dockerignore = (ROOT / "web/.dockerignore").read_text(encoding="utf-8")
        nginx = (ROOT / "web/nginx.conf").read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        web_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "web/src").rglob("*")
            if path.suffix in {".ts", ".tsx"}
        )
        self.assertIn("VITE_API_BASE_URL=/api/v1", dockerfile)
        self.assertIn("VITE_USE_MOCK_API=false", dockerfile)
        self.assertIn("VITE_ENABLE_DESIGN_MOCK_FALLBACK=false", dockerfile)
        self.assertIn("USER nginx", dockerfile)
        self.assertIn("tests/", dockerignore)
        self.assertIn("context: web", workflow)
        self.assertNotIn("COPY web/", dockerfile)
        self.assertNotRegex(
            web_source,
            r"data/(?:synthetic/fixtures|processed/structured/evidence)",
        )
        self.assertIn("listen 8080;", nginx)
        self.assertIn("proxy_temp_path /tmp/proxy_temp;", nginx)
        self.assertIn("proxy_pass http://backend:8000", nginx)
        self.assertIn("try_files $uri $uri/ /index.html;", nginx)
        self.assertNotIn("localhost", nginx)

    def test_ai_image_is_non_root_and_uses_linux_lock(self) -> None:
        text = (ROOT / "ai/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python:3.13.13-slim-bookworm", text)
        self.assertIn("ai/requirements-linux.lock", text)
        self.assertIn("FROM dependencies AS qa", text)
        self.assertNotIn("COPY --chown=waterbridge:waterbridge . /workspace/", text)
        self.assertIn("ARG RELEASE_SHA", text)
        self.assertIn("qa-git-metadata.sh", text)
        self.assertIn("RUN python -m pytest ai/tests/unit", text)
        self.assertIn("FROM dependencies AS runtime", text)
        self.assertIn("USER waterbridge", text)
        self.assertIn("ai.app.main:app", text)

    def test_backend_and_ai_use_separate_protected_env_files(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        self.assertIn("${BACKEND_RUNTIME_ENV_FILE:?", text)
        self.assertIn("${AI_RUNTIME_ENV_FILE:?", text)
        self.assertNotIn("WATERBRIDGE_RUNTIME_ENV_FILE", text)
        self.assertIn("validate_backend_runtime.py", deploy)
        self.assertIn("validate_ai_readonly_runtime.py", deploy)
        self.assertIn("--env PYTHONPATH=/workspace/backend", deploy)
        self.assertIn("BACKEND_TO_AI_SOCKET_PASS", deploy)

    def test_backend_and_ai_mount_the_rds_ca_read_only(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        ca_mount = (
            '"${RDS_CA_HOST_PATH:?RDS_CA_HOST_PATH is required}'
            ':/run/secrets/rds-ca.pem:ro"'
        )
        self.assertEqual(text.count(ca_mount), 2)
        ai_service = text.split("  ai:\n", maxsplit=1)[1].split(
            "  trace-store:\n", maxsplit=1
        )[0]
        self.assertIn("PGSSLROOTCERT: /run/secrets/rds-ca.pem", ai_service)
        self.assertIn(ca_mount, ai_service)

    def test_backend_image_is_non_root_locked_and_collects_static(self) -> None:
        dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python:3.13.13-slim-bookworm", dockerfile)
        self.assertIn("requirements/production.txt", dockerfile)
        self.assertIn("constraints-py313.txt", dockerfile)
        self.assertIn("gunicorn (version 26.0.0)", dockerfile)
        self.assertIn("collectstatic", dockerfile)
        self.assertIn("DJANGO_LOG_FILE=/dev/stdout", dockerfile)
        self.assertIn("USER waterbridge", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("DJANGO_ALLOWED_HOSTS", dockerfile)
        self.assertIn("headers={'Host': host}", dockerfile)
        self.assertIn("context: backend", workflow)

    def test_gunicorn_config_gate_uses_verify_full_without_runtime_secrets(
        self,
    ) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("DJANGO_SECRET_KEY=ci-production-config-check-only", workflow)
        self.assertIn("POSTGRES_SSLMODE=verify-full", workflow)
        self.assertIn(
            "POSTGRES_SSLROOTCERT=/etc/ssl/certs/ca-certificates.crt",
            workflow,
        )
        self.assertNotIn("secrets.", workflow)

    def test_runtime_preflights_enforce_approved_database_boundary(self) -> None:
        backend = BACKEND_PREFLIGHT.read_text(encoding="utf-8")
        ai = AI_PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn("0014_decouple_ai_view_product_eligibility", backend)
        self.assertIn("0005_replace_visit_result_assignment_fk", backend)
        self.assertIn('("160014",)', backend)
        self.assertIn("is_supported_pgvector_version", backend)
        self.assertIn('("0.8.2", "0.8.6")', ai)
        self.assertIn("EXPECTED_MODEL_COUNTS", ai)
        self.assertIn("(53, 53, 1024, 1024, 53)", ai)
        self.assertIn("complete_lineage=53", ai)
        self.assertIn("default_transaction_read_only", ai)
        self.assertNotIn("print(dsn", ai)
        for stage in (
            "DJANGO_SETUP",
            "DATABASE_CONNECTION",
            "POSTGRES_VERSION",
            "PGVECTOR_VERSION",
            "MIGRATION_MARKERS",
            "EVIDENCE_0014",
            "VISITS_0005_HOLD",
            "MIGRATION_PLAN",
        ):
            self.assertIn(stage, backend)
        self.assertIn(
            'f"reason={stage} error_type={type(exc).__name__}"', backend
        )
        self.assertNotIn("print(exc", backend)

    def test_ssm_failures_always_emit_deploy_and_rollback_results(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("aws ssm get-command-invocation"), 2)
        self.assertIn("SSM_DEPLOY_WAITER_FAILED status=%s", workflow)
        self.assertIn("SSM_ROLLBACK_WAITER_FAILED status=%s", workflow)
        self.assertIn('[[ "$status" == "Success" ]]', workflow)
        self.assertIn('[[ "$rollback_status" == "Success" ]]', workflow)

    def test_host_scripts_do_not_print_or_copy_secret_values(self) -> None:
        deploy = DEPLOY.read_text(encoding="utf-8")
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in (BOOTSTRAP, DEPLOY, ROLLBACK)
        )
        self.assertNotRegex(combined, r"(?m)^\s*(?:cat|head|tail)\s+.*runtime.*env")
        self.assertNotIn("set -x", combined)
        self.assertNotIn("docker compose down -v", combined)
        self.assertIn("without deleting volumes", combined)
        self.assertIn("NO_PREVIOUS_RELEASE_NEW_SERVICES_STOPPED", combined)
        self.assertIn("aws ecr get-login-password", deploy)
        self.assertIn("docker login --username AWS --password-stdin", deploy)
        self.assertIn('export DOCKER_CONFIG="$docker_config_dir"', deploy)
        self.assertIn('rm -rf -- "$docker_config_dir"', deploy)

    def test_deployment_is_sha_locked_and_serialized(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("github.event.workflow_run.head_sha", text)
        self.assertIn("ref: ${{ env.RELEASE_SHA }}", text)
        self.assertIn(
            "tests.deployment.test_production_deployment_assets -v", text
        )
        self.assertNotIn("discover -s tests/deployment", text)
        self.assertIn("environment: production", text)
        self.assertIn("OBSERVABILITY_PARTIAL", text)
        self.assertIn("final non-root USER", text)
        self.assertIn("collectstatic", text)
        self.assertIn("Build AI Linux unit-test target", text)
        self.assertIn("target: qa", text)
        self.assertIn("build-args: RELEASE_SHA=${{ env.RELEASE_SHA }}", text)
        self.assertNotIn("ai-gate:", text)
        self.assertIn("Verify published images are non-root and executable", text)
        self.assertIn(
            "data/(synthetic/fixtures|processed/structured/evidence)", text
        )


if __name__ == "__main__":
    unittest.main()
