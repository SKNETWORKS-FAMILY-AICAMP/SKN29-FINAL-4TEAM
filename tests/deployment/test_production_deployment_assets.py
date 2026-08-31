"""Static safety gates for WaterBridge production deployment assets."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
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
RELEASE_WORKFLOW = ROOT / ".github/workflows/production-release.yml"
BOOTSTRAP_WORKFLOW = ROOT / ".github/workflows/production-bootstrap.yml"
OIDC_SMOKE_WORKFLOW = ROOT / ".github/workflows/aws-oidc-smoke.yml"
BACKEND_PREFLIGHT = ROOT / "scripts/deployment/production/validate_backend_runtime.py"
AI_PREFLIGHT = ROOT / "scripts/deployment/production/validate_ai_readonly_runtime.py"
OIDC_TRUST = ROOT / "scripts/deployment/production/validate_github_oidc_trust.py"
SECRET_SYNC = (
    ROOT / "scripts/deployment/production/sync_backend_email_auth_secret.py"
)
WORKER_PREFLIGHT = (
    ROOT
    / "scripts/deployment/production/validate_p1_auth_email_worker_runtime.py"
)
WORKER_RUNNER = (
    ROOT / "scripts/deployment/production/run_p1_auth_email_worker.sh"
)
WORKER_UNIT = (
    ROOT / "infra/systemd/waterbridge-p1-auth-email-worker.service"
)


class ProductionDeploymentAssetTests(unittest.TestCase):
    def _rollback_health_command(self) -> re.Match[str]:
        text = ROLLBACK.read_text(encoding="utf-8")
        match = re.search(r"(?m)^curl\b.*?(?=\n\ncurrent_target=)", text, re.DOTALL)
        self.assertIsNotNone(match)
        return match

    def test_rollback_health_uses_public_host_before_switching_release(self) -> None:
        text = ROLLBACK.read_text(encoding="utf-8")
        match = self._rollback_health_command()
        command = shlex.split(match.group().replace("\\\n", " "))
        self.assertIn("--fail", command)
        self.assertIn("--max-time", command)
        self.assertIn("--header", command)
        self.assertEqual(command[command.index("--header") + 1], "Host: waterbridge.site")
        self.assertIn("http://127.0.0.1:18080/health", command)
        self.assertIn("set -euo pipefail", text)
        self.assertLess(match.start(), text.index('ln -sfn "$previous_target" "${base_dir}/current.next"'))

    def test_rollback_health_command_stops_on_http_failure(self) -> None:
        bash = shutil.which("bash")
        if os.name == "nt":
            # Do not accidentally launch the Windows WSL shim.
            git = shutil.which("git")
            candidate = Path(git).resolve().parents[1] / "bin/bash.exe" if git else None
            bash = str(candidate) if candidate and candidate.is_file() else None
        if not bash:
            self.skipTest("Bash is required for the isolated shell regression")
        command = self._rollback_health_command().group()
        for status in (0, 22):
            with self.subTest(curl_exit=status):
                script = (
                    "set -euo pipefail\n"
                    "curl() {\n"
                    '  printf \'%s\\n\' "$@" >&2\n'
                    f"  return {status}\n"
                    "}\n"
                    f"{command}\n"
                    "printf 'HEALTH_PROBE_COMPLETED\\n'\n"
                )
                # Only the extracted health command runs, with curl replaced by
                # a shell function. No HTTP, Docker, systemd or release writes.
                result = subprocess.run(
                    [bash, "--noprofile", "--norc", "-c", script],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(status, result.returncode, result.stderr)
                self.assertIn("Host: waterbridge.site", result.stderr)
                self.assertEqual(status == 0, "HEALTH_PROBE_COMPLETED" in result.stdout)

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

    def test_p1_email_worker_reuses_backend_container_under_systemd(self) -> None:
        compose = COMPOSE.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        rollback = ROLLBACK.read_text(encoding="utf-8")
        runner = WORKER_RUNNER.read_text(encoding="utf-8")
        unit = WORKER_UNIT.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertNotRegex(compose, r"(?m)^  p1-auth-email-worker:$")
        self.assertEqual(
            WORKER_UNIT.name,
            "waterbridge-p1-auth-email-worker.service",
        )
        self.assertIn("Restart=always", unit)
        self.assertIn("RestartSec=2s", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("ConditionPathIsSymbolicLink=", unit)
        self.assertIn("compose exec -T backend", runner)
        self.assertIn(
            "process_p1_auth_email_outbox --poll-seconds 2",
            runner,
        )
        self.assertIn(
            "supervisor_lock=/run/lock/waterbridge-p1-auth-email-worker.lock",
            runner,
        )
        self.assertIn("flock -n 9", runner)
        self.assertIn("another worker supervisor is active", runner)
        self.assertIn("wait_for_worker_exit", runner)
        self.assertIn("stale worker process could not be stopped", runner)
        self.assertIn("P1_AUTH_EMAIL_WORKER_STALE_PROCESS_CLEANED", runner)
        self.assertIn("P1_AUTH_EMAIL_WORKER_PROCESS_PASS", runner)
        self.assertIn('raw.split(b"\\0")', runner)
        self.assertNotIn('raw.split(b"\\\\0")', runner)
        self.assertIn(
            'worker process count=${#running_pids[@]}; expected=1',
            runner,
        )
        self.assertNotIn("docker run", runner)
        for text in (deploy, rollback):
            self.assertIn("activate_worker_release", text)
            self.assertIn("deactivate_worker", text)
            self.assertIn("p1-auth-email-worker.release", text)
        for asset in (
            "run_p1_auth_email_worker.sh",
            "validate_p1_auth_email_worker_runtime.py",
            "waterbridge-p1-auth-email-worker.service",
        ):
            self.assertIn(asset, workflow)

    def test_email_auth_secret_sync_is_fail_closed_and_value_safe(self) -> None:
        sync = SECRET_SYNC.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        preflight = WORKER_PREFLIGHT.read_text(encoding="utf-8")

        self.assertIn("aws", sync)
        self.assertIn("secretsmanager", sync)
        self.assertIn("get-secret-value", sync)
        self.assertIn("SECRET_DOCUMENT_COUNT_INVALID", sync)
        self.assertIn("SECRET_KEY_DUPLICATED", sync)
        self.assertIn("SECRET_KEY_UNKNOWN", sync)
        self.assertIn("ALLOWLIST_COUNT_INVALID", sync)
        self.assertIn("ALLOWLIST_DUPLICATED", sync)
        self.assertIn("os.replace", sync)
        self.assertIn("os.fchmod(temporary.fileno(), 0o600)", sync)
        self.assertIn("os.fchown(temporary.fileno(), 0, 0)", sync)
        self.assertIn("secret_values_printed=false", sync)
        self.assertNotIn("print(secret_string", sync)
        self.assertIn("BACKEND_EMAIL_AUTH_SECRET_ID", workflow)
        self.assertIn("${{ vars.BACKEND_EMAIL_AUTH_SECRET_ID }}", workflow)
        self.assertIn("sync_backend_email_auth_secret.py", workflow)
        self.assertIn('"$BACKEND_EMAIL_AUTH_SECRET_ID"', workflow)
        for key in (
            "P1_AUTH_RUNTIME_ENVIRONMENT",
            "P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED",
            "P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS",
        ):
            self.assertIn(key, deploy)
            self.assertIn(key, workflow)
            self.assertIn(key, preflight)
        self.assertIn("BACKEND_OWNER_WAIT", deploy)
        self.assertIn("pending_deliverable=0", preflight)
        self.assertNotIn("print(approved_hmacs", preflight)

    def test_source_guard_uses_runner_builtin_search_tools(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertNotRegex(workflow, r"(?m)^[ \t]*rg(?:[ \t]|$)")
        self.assertIn(
            "grep -R -n -E \\\n"
            "            'data/(synthetic/fixtures|processed/structured/evidence)'",
            workflow,
        )
        self.assertIn(
            "grep -R -n -E '(^|[[:space:]])(latest|:latest)([[:space:]]|$)'",
            workflow,
        )
        self.assertIn('grep -R -Fq -- "SKN-${index}" backend/apps', workflow)
        self.assertIn(
            'grep -R -Fq -- "SYN-P1-TEAM-CONTRACT-${index}" backend/apps',
            workflow,
        )

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
        self.assertIn("prefix: tempo/", text)
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
        compose = COMPOSE.read_text(encoding="utf-8")
        deploy = DEPLOY.read_text(encoding="utf-8")
        runtime_example = (
            ROOT / "infra/docker/compose/production/runtime.env.example"
        ).read_text(encoding="utf-8")
        base_settings = (ROOT / "backend/config/settings/base.py").read_text(
            encoding="utf-8"
        )
        production_settings = (
            ROOT / "backend/config/settings/production.py"
        ).read_text(encoding="utf-8")
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
        self.assertIn("location = /admin {", nginx)
        self.assertIn("return 308 /admin/;", nginx)
        self.assertIn("location ^~ /admin/ {", nginx)
        self.assertIn("location ^~ /static/ {", nginx)
        self.assertIn('add_header Cache-Control "no-store" always;', nginx)
        self.assertIn(
            'add_header Cache-Control "public, max-age=300, must-revalidate";',
            nginx,
        )
        static_location = nginx.split("location ^~ /static/ {", 1)[1].split(
            "\n    }", 1
        )[0]
        self.assertNotIn("immutable", static_location)
        self.assertLess(
            nginx.index("location ^~ /admin/ {"),
            nginx.index("location / {"),
        )
        self.assertIn(
            "admin_static:/usr/share/nginx/html/static:ro", compose
        )
        self.assertIn(
            "admin_static:/workspace/backend/staticfiles:ro", compose
        )
        self.assertIn(
            'name: "waterbridge-admin-static-${RELEASE_SHA:', compose
        )
        self.assertIn("printf '\\nRELEASE_SHA=%s\\n' \"$release_sha\"", deploy)
        self.assertIn(
            "RELEASE_SHA=0000000000000000000000000000000000000000",
            runtime_example,
        )
        self.assertIn('STATIC_URL = "/static/"', base_settings)
        self.assertIn('STATIC_ROOT = BASE_DIR / "staticfiles"', base_settings)
        self.assertIn(
            'SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")',
            production_settings,
        )
        self.assertIn("SESSION_COOKIE_SECURE = True", production_settings)
        self.assertIn("CSRF_COOKIE_SECURE = True", production_settings)
        self.assertNotIn("localhost", nginx)

    def test_ai_image_is_non_root_and_uses_linux_lock(self) -> None:
        text = (ROOT / "ai/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python:3.13.13-slim-bookworm", text)
        self.assertIn("ai/requirements-linux.lock", text)
        self.assertIn("FROM dependencies AS qa", text)
        self.assertNotIn("COPY --chown=waterbridge:waterbridge . /workspace/", text)
        self.assertIn("ARG RELEASE_SHA", text)
        self.assertIn("qa-git-metadata.sh", text)
        self.assertIn("apt-get install --yes --no-install-recommends git", text)
        self.assertIn("/usr/bin/git init --quiet /workspace", text)
        self.assertIn("COPY --chown=waterbridge:waterbridge .gitignore", text)
        self.assertLess(
            text.index("FROM dependencies AS qa"),
            text.index("apt-get install --yes --no-install-recommends git"),
        )
        self.assertLess(
            text.index("apt-get install --yes --no-install-recommends git"),
            text.index("FROM dependencies AS runtime"),
        )
        runtime = text.split("FROM dependencies AS runtime", maxsplit=1)[1]
        self.assertNotIn("apt-get install --yes --no-install-recommends git", runtime)
        self.assertIn("RUN python -m pytest ai/tests/unit", text)
        self.assertIn("FROM dependencies AS runtime", text)
        self.assertIn("USER waterbridge", text)
        self.assertIn("ai.app.main:app", text)

    def test_ai_qa_git_adapter_uses_real_ignore_rules_without_path_allowlist(
        self,
    ) -> None:
        qa_git = (
            ROOT / "scripts/deployment/production/qa-git-metadata.sh"
        ).read_text(encoding="utf-8")

        for command in ("rev-parse)", "branch)", "status)", "check-ignore)"):
            self.assertIn(command, qa_git)
        self.assertIn("origin/main)", qa_git)
        self.assertIn('validate_relative_path "$path"', qa_git)
        self.assertIn('""|/*|..|../*|*/..|*/../*', qa_git)
        self.assertIn(
            'exec "$system_git" -C "$repository_root" check-ignore --quiet -- "$@"',
            qa_git,
        )
        self.assertIn(
            'exec "$system_git" -C "$repository_root" check-ignore -- "$@"',
            qa_git,
        )
        self.assertNotIn('exec "$system_git" "$@"', qa_git)
        self.assertNotIn(".pytest-tmp", qa_git)

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
        ai_service = text.split("\n  ai:\n", maxsplit=1)[1].split(
            "\n  trace-store:\n", maxsplit=1
        )[0]
        self.assertIn("PGSSLROOTCERT: /run/secrets/rds-ca.pem", ai_service)
        self.assertIn(ca_mount, ai_service)

    def test_ai_and_trace_store_have_private_outbound_egress(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        ai_service = text.split("\n  ai:\n", maxsplit=1)[1].split(
            "\n  trace-store:\n", maxsplit=1
        )[0]
        trace_store = text.split("\n  trace-store:\n", maxsplit=1)[1].split(
            "\nnetworks:\n", maxsplit=1
        )[0]
        network_definitions = text.split("\nnetworks:\n", maxsplit=1)[1].split(
            "\nvolumes:\n", maxsplit=1
        )[0]

        for service in (ai_service, trace_store):
            self.assertIn("      - internal", service)
            self.assertIn("      - egress", service)
            self.assertNotRegex(service, r"(?m)^    ports:$")
        self.assertIn(
            "  internal:\n    driver: bridge\n    internal: true",
            network_definitions,
        )
        self.assertIn("  egress:\n    driver: bridge", network_definitions)

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
        self.assertIn(
            "COPY --from=state_machine_contracts . "
            "/workspace/contracts/state-machine/",
            dockerfile,
        )
        self.assertIn(
            "COPY --from=api_contracts action-operation-crosswalk.yaml "
            "/workspace/contracts/api/action-operation-crosswalk.yaml",
            dockerfile,
        )
        self.assertIn(
            "COPY --from=ai_contracts . /workspace/contracts/ai/",
            dockerfile,
        )
        self.assertIn(
            "COPY --from=code_contracts safety-rule-ids.yaml "
            "/workspace/contracts/codes/safety-rule-ids.yaml",
            dockerfile,
        )
        self.assertIn("load_state_machine_contract()", dockerfile)
        self.assertIn(
            "load_yaml_mapping("
            "Path('/workspace/contracts/api/action-operation-crosswalk.yaml')"
            ")",
            dockerfile,
        )
        self.assertIn("AIContractValidator()", dockerfile)
        self.assertIn("load_safety_rule_registry()", dockerfile)
        self.assertIn(
            "state_machine_contracts=contracts/state-machine",
            workflow,
        )
        self.assertIn("api_contracts=contracts/api", workflow)
        self.assertIn("ai_contracts=contracts/ai", workflow)
        self.assertIn("code_contracts=contracts/codes", workflow)
        self.assertIn("BACKEND_RUNTIME_CONTRACTS_PASS", workflow)
        self.assertIn("BACKEND_AI_CONTRACTS_PASS", workflow)
        self.assertIn("BACKEND_SAFETY_RULE_REGISTRY_PASS", workflow)

    def test_gunicorn_config_gate_uses_verify_full_without_runtime_secrets(
        self,
    ) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("DJANGO_SECRET_KEY=ci-production-config-check-only", workflow)
        for key in (
            "CONTRACT_EMAIL_ENCRYPTION_KEY",
            "CONTRACT_EMAIL_HMAC_KEY",
            "CONTRACT_EMAIL_KEY_VERSION",
            "P1_AUTH_HMAC_SECRET",
            "P1_AUTH_OTP_ENCRYPTION_KEY",
            "P1_AUTH_EMAIL_REDIRECT_TO",
            "P1_AUTH_RUNTIME_ENVIRONMENT",
            "P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED",
            "P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS",
            "DJANGO_EMAIL_BACKEND",
            "DJANGO_EMAIL_HOST",
            "DJANGO_EMAIL_HOST_USER",
            "DJANGO_EMAIL_HOST_PASSWORD",
            "DJANGO_DEFAULT_FROM_EMAIL",
        ):
            self.assertIn(f"{key}=", workflow)
        self.assertIn("POSTGRES_SSLMODE=verify-full", workflow)
        self.assertIn(
            "POSTGRES_SSLROOTCERT=/etc/ssl/certs/ca-certificates.crt",
            workflow,
        )
        self.assertNotIn("secrets.", workflow)

    def test_host_bootstrap_requires_systemd_and_python_without_secret_access(
        self,
    ) -> None:
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("flock python3 systemctl", bootstrap)
        self.assertIn("systemd=available", bootstrap)
        self.assertNotIn("get-secret-value", bootstrap)

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
        for stage in (
            "ENVIRONMENT",
            "DATABASE_CONNECTION",
            "POSTGRES_VERSION",
            "PGVECTOR_VERSION",
            "TRANSACTION_READ_ONLY",
            "PUBLIC_SCHEMA_PRIVILEGE",
            "VIEW_PRIVILEGE_BOUNDARY",
            "BASE_TABLE_BOUNDARY",
            "VIEW_COUNTS_AND_LINEAGE",
            "MODEL_DISTRIBUTION",
        ):
            self.assertIn(stage, ai)
        self.assertIn(
            'f"reason={stage} error_type={type(exc).__name__}"', backend
        )
        self.assertIn(
            'f"reason={stage} error_type={type(exc).__name__}"', ai
        )
        self.assertNotIn("print(exc", backend)
        self.assertNotIn("print(exc", ai)

    def test_ssm_polling_waits_for_terminal_deploy_and_rollback_results(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("aws ssm get-command-invocation"), 3)
        self.assertNotIn("aws ssm wait command-executed", workflow)
        self.assertIn("deadline=$((SECONDS + 1200))", workflow)
        self.assertIn("deadline=$((SECONDS + 600))", workflow)
        self.assertEqual(workflow.count("Pending|InProgress|Delayed|Cancelling"), 3)
        self.assertIn("SSM_CANARY_POLL_TIMEOUT seconds=1200", workflow)
        self.assertIn("SSM_DEPLOY_POLL_TIMEOUT seconds=1200", workflow)
        self.assertIn("SSM_ROLLBACK_POLL_TIMEOUT seconds=600", workflow)
        self.assertIn('[[ "$status" == "Success" ]]', workflow)
        self.assertIn('[[ "$rollback_status" == "Success" ]]', workflow)

    def test_bootstrap_and_oidc_polling_collect_terminal_output(self) -> None:
        cases = (
            (
                BOOTSTRAP_WORKFLOW,
                600,
                "SSM_BOOTSTRAP_POLL_TIMEOUT seconds=600",
                "HOST_BOOTSTRAP_PASS",
            ),
            (
                OIDC_SMOKE_WORKFLOW,
                120,
                "SSM_OIDC_POLL_TIMEOUT seconds=120",
                "AWS_OIDC_SSM_PATH_PASS",
            ),
        )
        for path, timeout, timeout_marker, success_marker in cases:
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("aws ssm wait command-executed", text)
                self.assertIn(f"deadline=$((SECONDS + {timeout}))", text)
                self.assertIn("Success|Failed|Cancelled|TimedOut", text)
                self.assertIn("Pending|InProgress|Delayed|Cancelling", text)
                self.assertIn("sleep 5", text)
                self.assertIn(timeout_marker, text)
                self.assertIn('.StandardOutputContent // ""', text)
                self.assertIn('.StandardErrorContent // ""', text)
                self.assertIn('[[ "$status" == "Success" ]]', text)
                self.assertIn(f"grep -q '^{success_marker}$'", text)

    def test_remote_ssm_inputs_are_validated_and_shell_escaped(self) -> None:
        bootstrap = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
        deploy = WORKFLOW.read_text(encoding="utf-8")
        bucket_pattern = "^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"

        self.assertIn(bucket_pattern, bootstrap)
        self.assertIn(bucket_pattern, deploy)
        self.assertIn('[[ "$value" =~ ^/[A-Za-z0-9._/-]+$ ]]', bootstrap)
        self.assertIn('realpath -m -- "$value"', bootstrap)
        self.assertNotIn("REQUESTED_BUCKET//[[:space:]]", bootstrap)
        self.assertGreaterEqual(bootstrap.count("printf -v"), 4)
        self.assertGreaterEqual(deploy.count("printf -v"), 6)
        self.assertGreaterEqual(bootstrap.count("%q"), 10)
        self.assertGreaterEqual(deploy.count("%q"), 12)
        for text in (bootstrap, deploy):
            self.assertNotIn('("aws s3 cp s3://" + $bucket', text)

    def test_production_aws_credentials_are_version_and_account_locked(
        self,
    ) -> None:
        bootstrap = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
        deploy = WORKFLOW.read_text(encoding="utf-8")
        oidc = OIDC_SMOKE_WORKFLOW.read_text(encoding="utf-8")
        combined = "\n".join((bootstrap, deploy, oidc))

        self.assertEqual(
            combined.count("aws-actions/configure-aws-credentials@v6.2.3"),
            5,
        )
        self.assertNotIn("aws-actions/configure-aws-credentials@v5", combined)
        for text in (bootstrap, deploy, oidc):
            self.assertIn("AWS_ACCOUNT_ID", text)
            self.assertIn("allowed-account-ids: ${{ env.AWS_ACCOUNT_ID }}", text)
            self.assertIn("role-session-name:", text)
        self.assertEqual(deploy.count("role-session-name:"), 3)
        self.assertIn("runs-on: ubuntu-24.04", oidc)
        self.assertNotIn("runs-on: ubuntu-latest", oidc)
        self.assertIn('expected_role_name="${AWS_ROLE_ARN##*/}"', oidc)
        self.assertNotIn("WaterBridgeGitHubDeployRole", oidc)

    def test_host_scripts_do_not_print_or_copy_secret_values(self) -> None:
        deploy = DEPLOY.read_text(encoding="utf-8")
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                BOOTSTRAP,
                DEPLOY,
                ROLLBACK,
                SECRET_SYNC,
                WORKER_PREFLIGHT,
                WORKER_RUNNER,
            )
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
        release = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        backend_ci = (ROOT / ".github/workflows/backend-ci.yml").read_text(
            encoding="utf-8"
        )
        socket_ci = (ROOT / ".github/workflows/ai-backend-socket-e2e.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("workflow_run", text)
        self.assertIn('      - "v*.*.*"', release)
        self.assertIn("workflow_call:", text)
        self.assertIn("RELEASE_SHA: ${{ inputs.release_sha }}", text)
        self.assertIn("release_sha: ${{ github.sha }}", release)
        self.assertIn("release_tag: ${{ github.ref_name }}", release)
        self.assertIn(
            "SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM/"
            ".github/workflows/production-deploy.yml@main",
            release,
        )
        self.assertIn('[[ "$CALLER_EVENT" == "push" ]]', text)
        self.assertIn('[[ "$CALLER_REF_TYPE" == "tag" ]]', text)
        self.assertIn('[[ "$CALLER_SHA" == "$RELEASE_SHA" ]]', text)
        self.assertIn(r"^v[0-9]+\.[0-9]+\.[0-9]+$", text)
        self.assertIn("git fetch --no-tags origin main:refs/remotes/origin/main", text)
        self.assertIn('git merge-base --is-ancestor "$RELEASE_SHA" origin/main', text)
        self.assertIn("ref: ${{ env.RELEASE_SHA }}", text)
        self.assertIn("tests.deployment.test_production_deployment_assets", text)
        self.assertIn("tests.deployment.test_backend_email_auth_secret_sync", text)
        self.assertIn("tests.deployment.test_github_oidc_trust", text)
        self.assertIn("tests.deployment.test_backend_ci_workflow", text)
        self.assertIn("tests.deployment.test_data_ci_workflow", text)
        self.assertNotIn("discover -s tests/deployment", text)
        self.assertIn("environment: production", text)
        self.assertIn("OBSERVABILITY_PARTIAL", text)
        self.assertIn("final non-root USER", text)
        self.assertIn("collectstatic", text)
        self.assertIn("Build AI Linux unit-test target", text)
        self.assertIn("target: qa", text)
        self.assertIn("build-args: RELEASE_SHA=${{ env.RELEASE_SHA }}", text)
        self.assertNotIn("ai-gate:", text)
        self.assertIn("uses: ./.github/workflows/backend-ci.yml", text)
        self.assertIn("uses: ./.github/workflows/ai-backend-socket-e2e.yml", text)
        self.assertIn("backend-production-config-gate", text)
        self.assertIn("workflow_call:", backend_ci)
        self.assertIn("workflow_call:", socket_ci)
        self.assertIn("Verify published images are non-root and executable", text)
        self.assertIn(
            "data/(synthetic/fixtures|processed/structured/evidence)", text
        )

    def test_socket_gate_filters_unrelated_changes_but_release_remains_full(self) -> None:
        production = WORKFLOW.read_text(encoding="utf-8")
        socket = (ROOT / ".github/workflows/ai-backend-socket-e2e.yml").read_text(
            encoding="utf-8"
        )
        relevant_paths = (
            "ai/**",
            "backend/**",
            "contracts/**",
            "data/**",
            "scripts/development/**",
            ".github/workflows/ai-backend-socket-e2e.yml",
        )

        self.assertIn("workflow_call:\n", socket)
        self.assertIn("workflow_dispatch:\n", socket)
        self.assertIn("pull_request:\n    paths:\n", socket)
        self.assertIn("push:\n    branches:\n      - main\n    paths:\n", socket)
        for path in relevant_paths:
            self.assertEqual(socket.count(f'      - "{path}"'), 2)

        self.assertNotIn("paths-ignore:", socket)
        self.assertNotIn(".github/workflows/production-deploy.yml", socket)
        self.assertRegex(
            production,
            r"(?ms)^  socket-e2e-gate:\n"
            r"    name: Re-run AI Backend Socket E2E gate\n"
            r"    needs: source-guard\n"
            r"    uses: \./\.github/workflows/ai-backend-socket-e2e\.yml\n",
        )
        self.assertIn("      - socket-e2e-gate", production)

    def test_bootstrap_validates_reusable_semver_oidc_trust(self) -> None:
        bootstrap = BOOTSTRAP_WORKFLOW.read_text(encoding="utf-8")
        trust = OIDC_TRUST.read_text(encoding="utf-8")
        self.assertIn("Production Bootstrap must run from the main branch", bootstrap)
        self.assertIn("aws iam get-role", bootstrap)
        self.assertIn("validate_github_oidc_trust.py", bootstrap)
        self.assertIn("GITHUB_REPOSITORY", bootstrap)
        self.assertIn("github.repository_id", bootstrap)
        self.assertIn("github.repository_owner_id", bootstrap)
        self.assertIn("GitHubActionsProductionEnvironment", trust)
        self.assertIn("ENVIRONMENT_CLAIM: PRODUCTION_ENVIRONMENT", trust)
        self.assertNotIn("StringLike", trust)
        self.assertIn("JOB_WORKFLOW_REF_CLAIM", trust)
        self.assertIn("@refs/heads/main", trust)
        self.assertNotRegex(trust, r"refs/tags/v\d+\.\d+\.\d+")
        environment_workflows = [
            path.name
            for path in (ROOT / ".github/workflows").glob("*.yml")
            if "environment: production" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(environment_workflows, ["production-deploy.yml"])


if __name__ == "__main__":
    unittest.main()
