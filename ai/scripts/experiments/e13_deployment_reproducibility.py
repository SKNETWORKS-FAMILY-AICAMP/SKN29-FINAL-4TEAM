"""E13 — GitHub Actions + ECR + SSM Deployment Reproducibility.

This experiment is intentionally non-destructive with respect to Production.

What it can do
--------------
1. Validate the committed deployment contract at the current Git HEAD.
2. Reuse a recent successful AWS OIDC Smoke workflow run, or optionally
   dispatch the repository's existing harmless OIDC/ECR/SSM smoke workflow.
3. Find an existing successful Production Deploy run and collect only
   non-sensitive execution evidence from GitHub Actions.
4. Best-effort extract Web/Backend/AI image digests from the successful
   build-and-publish job log without storing the raw log.
5. Verify the successful deploy job actually executed the SSM deployment and
   external HTTPS smoke steps, and best-effort confirm DEPLOYMENT_RUNTIME_PASS.
6. Record the rollback implementation contract without injecting a Production
   fault.

What it never does
------------------
- It never creates or pushes a Git tag.
- It never dispatches Production Deploy.
- It never changes ECR images, EC2 containers, RDS, S3, Secrets Manager, IAM,
  repository variables, or production runtime files.
- It never stores AWS credentials, OIDC tokens, ECR passwords, full SSM stdout,
  customer data, runtime env files, or secrets.

Typical later run
-----------------
    python ai/scripts/experiments/e13_deployment_reproducibility.py \
        --dispatch-oidc-smoke

Status semantics
----------------
E13_COMPLETE
    Source contract PASS + OIDC/ECR/SSM smoke PASS + an existing successful
    Production Deploy run is verified, including its deployment/HTTPS steps.

E13_PARTIAL
    Source contract and OIDC/ECR/SSM smoke are verified, but no suitable
    successful Production Deploy execution is available. This still supports
    the limited claim that GitHub Actions OIDC reaches AWS ECR and SSM.

E13_ENVIRONMENT_BLOCKED
    Local GitHub CLI/authentication or GitHub-side prerequisites prevent the
    evidence collection. Not a deployment failure.

E13_FAILED
    A selected/triggered verification actually failed, or the committed
    deployment contract violates the frozen E13 requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_ROOT = (
    REPO_ROOT
    / "ai"
    / "experiment_results"
    / "e13_deployment_reproducibility"
)

EXPECTED_REPOSITORY = (
    "SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM"
)

OIDC_WORKFLOW_FILE = "aws-oidc-smoke.yml"
PRODUCTION_RELEASE_WORKFLOW_FILE = "production-release.yml"

SOURCE_FILES = {
    "release_entry":
        ".github/workflows/production-release.yml",
    "trusted_deploy":
        ".github/workflows/production-deploy.yml",
    "oidc_smoke":
        ".github/workflows/aws-oidc-smoke.yml",
    "deploy_script":
        "scripts/deployment/production/deploy-release.sh",
    "rollback_script":
        "scripts/deployment/production/rollback-release.sh",
    "runbook":
        "docs/deployment/production-deployment-runbook.md",
}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
SEMVER_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")


class ExperimentBlocked(RuntimeError):
    pass


class ExperimentFailed(RuntimeError):
    pass


def _run(
    args: list[str],
    *,
    cwd: Path = REPO_ROOT,
    timeout: float = 60.0,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
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
            f"Command timed out after {timeout:.0f}s: {args[0]}"
        ) from exc

    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ExperimentBlocked(
            f"Command failed ({result.returncode}): "
            f"{detail[-2000:]}"
        )
    return result


def _git(*args: str) -> str:
    return _run(
        ["git", *args],
        timeout=30.0,
    ).stdout.strip()


def _head_sha() -> str:
    sha = _git("rev-parse", "HEAD")
    if SHA_RE.fullmatch(sha) is None:
        raise ExperimentBlocked(
            "Current Git HEAD is not a canonical 40-char SHA."
        )
    return sha


def _remote_repository() -> str:
    remote = _git("remote", "get-url", "origin")
    patterns = (
        r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?$",
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, remote.strip())
        if match:
            return match.group(1)
    raise ExperimentBlocked(
        "Could not resolve GitHub owner/repository from origin."
    )


def _git_show(sha: str, path: str) -> str:
    result = _run(
        ["git", "show", f"{sha}:{path}"],
        timeout=30.0,
        check=False,
    )
    if result.returncode != 0:
        raise ExperimentFailed(
            f"Committed source is missing at {sha[:12]}: {path}"
        )
    return result.stdout


def _contains(
    text: str,
    *needles: str,
) -> bool:
    return all(needle in text for needle in needles)


def _source_contract(sha: str) -> dict[str, Any]:
    sources = {
        key: _git_show(sha, path)
        for key, path in SOURCE_FILES.items()
    }
    release = sources["release_entry"]
    deploy = sources["trusted_deploy"]
    oidc = sources["oidc_smoke"]
    shell = sources["deploy_script"]
    rollback = sources["rollback_script"]
    runbook = sources["runbook"]

    checks = {
        # Release source.
        "stable_semver_tag_trigger":
            _contains(
                release,
                'tags:',
                '- "v*.*.*"',
            ),
        "release_sha_forwarded":
            "release_sha: ${{ github.sha }}" in release,
        "release_tag_forwarded":
            "release_tag: ${{ github.ref_name }}" in release,
        "trusted_workflow_reference_main":
            ".github/workflows/production-deploy.yml@main"
            in release,

        # OIDC and source guards.
        "oidc_id_token_permission":
            "id-token: write" in deploy
            and "id-token: write" in oidc,
        "aws_role_assumption":
            "aws-actions/configure-aws-credentials@v6.2.3"
            in deploy
            and "role-to-assume:" in deploy,
        "stable_semver_runtime_guard":
            '[[ "$RELEASE_TAG" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+$ ]]'
            in deploy,
        "main_ancestry_guard":
            'git merge-base --is-ancestor "$RELEASE_SHA" origin/main'
            in deploy,
        "non_root_image_guard":
            "Production image must declare a final non-root USER"
            in deploy,
        "healthcheck_guard":
            "Production image must declare HEALTHCHECK"
            in deploy,
        "mutable_latest_guard":
            "Mutable latest image references are forbidden"
            in deploy,

        # CI gates.
        "backend_gate":
            "backend-gate:" in deploy,
        "backend_prod_config_gate":
            "backend-production-config-gate:" in deploy,
        "socket_e2e_gate":
            "socket-e2e-gate:" in deploy,
        "web_gate":
            "web-gate:" in deploy,
        "contract_data_gate":
            "contract-data-gate:" in deploy,

        # ECR publication and digest provenance.
        "web_push":
            _contains(
                deploy,
                "Build and push Web image",
                "push: true",
                "ECR_WEB_REPOSITORY",
            ),
        "backend_push":
            _contains(
                deploy,
                "Build and push Backend image",
                "ECR_BACKEND_REPOSITORY",
            ),
        "ai_push":
            _contains(
                deploy,
                "Build and push AI image",
                "ECR_AI_REPOSITORY",
            ),
        "sha_tagged_images":
            ":${{ env.RELEASE_SHA }}" in deploy,
        "web_digest_output":
            "web_digest: ${{ steps.web-build.outputs.digest }}"
            in deploy,
        "backend_digest_output":
            "backend_digest: ${{ steps.backend-build.outputs.digest }}"
            in deploy,
        "ai_digest_output":
            "ai_digest: ${{ steps.ai-build.outputs.digest }}"
            in deploy,
        "release_bundle_pins_digests":
            _contains(
                deploy,
                "WEB_IMAGE_DIGEST=${WEB_DIGEST}",
                "BACKEND_IMAGE_DIGEST=${BACKEND_DIGEST}",
                "AI_IMAGE_DIGEST=${AI_DIGEST}",
            ),
        "provenance_enabled":
            deploy.count("provenance: true") >= 3,
        "sbom_enabled":
            deploy.count("sbom: true") >= 3,

        # SSM and runtime.
        "ssm_deploy":
            _contains(
                deploy,
                "Deploy the immutable release on EC2",
                "aws ssm send-command",
                "AWS-RunShellScript",
            ),
        "ssm_status_poll":
            "aws ssm get-command-invocation" in deploy,
        "deployment_runtime_marker_gate":
            "grep -q '^DEPLOYMENT_RUNTIME_PASS$'"
            in deploy,
        "external_https_smoke":
            _contains(
                deploy,
                "Run external HTTPS smoke",
                "check_production_deployment.py",
                "https://waterbridge.site",
            ),

        # Host release integrity/runtime script.
        "release_archive_checksum":
            _contains(
                shell,
                "expected_sha256=",
                "actual_sha256=",
                "release checksum mismatch",
            ),
        "ecr_registry_guard":
            "is not an approved ECR image reference"
            in shell,
        "compose_pull_no_build":
            "compose pull" in shell
            and "compose up -d --wait --no-build --remove-orphans"
            in shell,
        "backend_to_ai_socket":
            "BACKEND_TO_AI_SOCKET_PASS" in shell,
        "runtime_marker_emitted":
            "DEPLOYMENT_RUNTIME_PASS" in shell,
        "observability_partial_boundary":
            "observability=OBSERVABILITY_PARTIAL"
            in shell
            and "OBSERVABILITY_PARTIAL" in runbook,

        # Rollback.
        "workflow_rollback_path":
            "Roll back after a post-deployment failure"
            in deploy
            and "rollback-release.sh" in deploy,
        "host_rollback_function":
            "rollback()" in shell
            and "rolling back without deleting volumes"
            in shell,
        "standalone_rollback_asset_nonempty":
            bool(rollback.strip()),
    }

    mandatory_failures = [
        key
        for key, passed in checks.items()
        if not passed
    ]

    workflow_implementation_boundary = {
        "application_source_pinned_to_release_sha": True,
        "workflow_implementation_reference":
            "production-deploy.yml@main",
        "workflow_implementation_pinned_to_release_sha": False,
        "claim": (
            "Application source is pinned to the release SHA, while the "
            "trusted reusable workflow implementation is referenced from main."
        ),
    }

    return {
        "status":
            "PASS"
            if not mandatory_failures
            else "FAIL",
        "checks": checks,
        "failed_checks": mandatory_failures,
        "workflow_implementation_boundary":
            workflow_implementation_boundary,
    }


def _gh_ready(repository: str) -> dict[str, Any]:
    if shutil.which("gh") is None:
        raise ExperimentBlocked(
            "GitHub CLI (gh) is not installed or not on PATH."
        )

    auth = _run(
        ["gh", "auth", "status", "--hostname", "github.com"],
        timeout=30.0,
        check=False,
    )
    if auth.returncode != 0:
        raise ExperimentBlocked(
            "GitHub CLI is not authenticated to github.com."
        )

    resolved = _run(
        [
            "gh",
            "repo",
            "view",
            repository,
            "--json",
            "nameWithOwner",
        ],
        timeout=30.0,
    )
    payload = json.loads(resolved.stdout)
    if payload.get("nameWithOwner") != repository:
        raise ExperimentBlocked(
            "GitHub CLI resolved an unexpected repository."
        )

    return {
        "gh_available": True,
        "gh_authenticated": True,
        "repository": repository,
    }


def _gh_json(args: list[str], *, timeout: float = 60.0) -> Any:
    result = _run(
        ["gh", *args],
        timeout=timeout,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ExperimentBlocked(
            "GitHub CLI returned non-JSON output for an evidence query."
        ) from exc


def _list_runs(
    repository: str,
    workflow: str,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    payload = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            workflow,
            "--limit",
            str(limit),
            "--json",
            (
                "databaseId,workflowName,displayTitle,event,"
                "headBranch,headSha,status,conclusion,createdAt,"
                "updatedAt,url"
            ),
        ],
        timeout=60.0,
    )
    if not isinstance(payload, list):
        raise ExperimentBlocked(
            "GitHub workflow run listing is malformed."
        )
    return [
        item
        for item in payload
        if isinstance(item, dict)
    ]


def _parse_github_time(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def _dispatch_oidc_smoke(
    repository: str,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    before = datetime.now(timezone.utc)
    print(
        "[E13] AWS OIDC Smoke Test dispatch "
        "(existing repository workflow)"
    )

    result = _run(
        [
            "gh",
            "workflow",
            "run",
            OIDC_WORKFLOW_FILE,
            "--repo",
            repository,
            "--ref",
            "main",
        ],
        timeout=30.0,
        check=False,
    )
    if result.returncode != 0:
        raise ExperimentFailed(
            "AWS OIDC Smoke Test dispatch failed."
        )

    run: dict[str, Any] | None = None
    discovery_deadline = time.monotonic() + 90.0
    while time.monotonic() < discovery_deadline:
        for item in _list_runs(
            repository,
            OIDC_WORKFLOW_FILE,
            limit=20,
        ):
            if (
                item.get("event") == "workflow_dispatch"
                and item.get("headBranch") == "main"
                and isinstance(item.get("createdAt"), str)
                and _parse_github_time(item["createdAt"])
                >= before - timedelta(seconds=5)
            ):
                run = item
                break
        if run is not None:
            break
        time.sleep(3)

    if run is None:
        raise ExperimentBlocked(
            "Dispatched OIDC smoke run could not be identified."
        )

    run_id = int(run["databaseId"])
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        view = _gh_json(
            [
                "run",
                "view",
                str(run_id),
                "--repo",
                repository,
                "--json",
                (
                    "databaseId,status,conclusion,headSha,"
                    "createdAt,updatedAt,url"
                ),
            ],
            timeout=30.0,
        )
        status = view.get("status")
        if status == "completed":
            return view
        time.sleep(5)

    raise ExperimentBlocked(
        "AWS OIDC Smoke Test did not finish within the timeout."
    )


def _select_recent_successful_smoke(
    repository: str,
    *,
    max_age_days: int,
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    for run in _list_runs(
        repository,
        OIDC_WORKFLOW_FILE,
        limit=50,
    ):
        if (
            run.get("conclusion") == "success"
            and run.get("headBranch") == "main"
            and isinstance(run.get("createdAt"), str)
        ):
            age = now - _parse_github_time(
                run["createdAt"]
            )
            if age <= timedelta(days=max_age_days):
                return run
    return None


def _api_jobs(
    repository: str,
    run_id: int,
) -> list[dict[str, Any]]:
    payload = _gh_json(
        [
            "api",
            "--paginate",
            f"repos/{repository}/actions/runs/{run_id}/jobs",
        ],
        timeout=90.0,
    )

    # gh --paginate may concatenate JSON objects, so normally this helper
    # receives one object for <=100 jobs. Fall back to `gh api` without
    # paginate if the result is unexpected.
    if isinstance(payload, dict):
        jobs = payload.get("jobs")
        if isinstance(jobs, list):
            return [
                job
                for job in jobs
                if isinstance(job, dict)
            ]

    payload = _gh_json(
        [
            "api",
            f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100",
        ],
        timeout=60.0,
    )
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise ExperimentBlocked(
            "GitHub Actions jobs response is malformed."
        )
    return [
        job
        for job in jobs
        if isinstance(job, dict)
    ]


def _step_map(job: dict[str, Any]) -> dict[str, str | None]:
    steps = job.get("steps", [])
    if not isinstance(steps, list):
        return {}
    result: dict[str, str | None] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        name = step.get("name")
        if isinstance(name, str):
            result[name] = (
                step.get("conclusion")
                if isinstance(
                    step.get("conclusion"),
                    str,
                )
                else None
            )
    return result


def _find_job(
    jobs: list[dict[str, Any]],
    name_fragment: str,
) -> dict[str, Any] | None:
    candidates = [
        job
        for job in jobs
        if isinstance(job.get("name"), str)
        and name_fragment.casefold()
        in job["name"].casefold()
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # Prefer a completed successful candidate if GitHub includes
        # reusable-workflow name prefixes.
        successful = [
            job
            for job in candidates
            if job.get("conclusion") == "success"
        ]
        if len(successful) == 1:
            return successful[0]
    return None


def _validate_oidc_run(
    repository: str,
    run: dict[str, Any],
) -> dict[str, Any]:
    run_id = int(run["databaseId"])
    jobs = _api_jobs(repository, run_id)

    job = _find_job(
        jobs,
        "Verify AWS OIDC, ECR, and SSM",
    )
    if job is None:
        raise ExperimentFailed(
            "OIDC smoke verification job was not found."
        )

    steps = _step_map(job)
    expected_steps = (
        "Validate repository variables",
        "Configure temporary AWS credentials",
        "Verify assumed AWS account and role",
        "Verify ECR repositories",
        "Verify SSM command path",
    )
    checks = {
        name: steps.get(name) == "success"
        for name in expected_steps
    }

    overall = (
        run.get("conclusion") == "success"
        and job.get("conclusion") == "success"
        and all(checks.values())
    )

    return {
        "status": "PASS" if overall else "FAIL",
        "workflow_run_id": run_id,
        "workflow_run_url": run.get("url"),
        "head_sha": run.get("headSha"),
        "created_at": run.get("createdAt"),
        "conclusion": run.get("conclusion"),
        "job_id": job.get("id"),
        "job_conclusion": job.get("conclusion"),
        "steps": checks,
        "claims": {
            "github_oidc_to_aws_role": overall,
            "ecr_repositories_3_of_3":
                checks.get(
                    "Verify ECR repositories",
                    False,
                ),
            "ssm_command_path":
                checks.get(
                    "Verify SSM command path",
                    False,
                ),
        },
        "sensitive_values_captured": False,
    }


def _production_runs(
    repository: str,
) -> list[dict[str, Any]]:
    return _list_runs(
        repository,
        PRODUCTION_RELEASE_WORKFLOW_FILE,
        limit=50,
    )


def _is_ancestor(
    older: str,
    newer: str,
) -> bool:
    if (
        SHA_RE.fullmatch(older or "") is None
        or SHA_RE.fullmatch(newer or "") is None
    ):
        return False
    result = _run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            older,
            newer,
        ],
        timeout=30.0,
        check=False,
    )
    return result.returncode == 0


def _select_production_run(
    repository: str,
    *,
    current_sha: str,
    explicit_run_id: int | None,
) -> dict[str, Any] | None:
    runs = _production_runs(repository)

    if explicit_run_id is not None:
        for run in runs:
            if int(run.get("databaseId", -1)) == explicit_run_id:
                if run.get("conclusion") != "success":
                    raise ExperimentFailed(
                        "Explicit Production run is not successful."
                    )
                return run

        view = _gh_json(
            [
                "run",
                "view",
                str(explicit_run_id),
                "--repo",
                repository,
                "--json",
                (
                    "databaseId,workflowName,displayTitle,event,"
                    "headBranch,headSha,status,conclusion,createdAt,"
                    "updatedAt,url"
                ),
            ],
            timeout=30.0,
        )
        if view.get("conclusion") != "success":
            raise ExperimentFailed(
                "Explicit Production run is not successful."
            )
        return view

    for run in runs:
        if (
            run.get("conclusion") == "success"
            and isinstance(run.get("headSha"), str)
            and SHA_RE.fullmatch(run["headSha"])
            and _is_ancestor(
                run["headSha"],
                current_sha,
            )
        ):
            return run

    return None


def _job_log(
    repository: str,
    job_id: int,
) -> str:
    result = _run(
        [
            "gh",
            "run",
            "view",
            "--repo",
            repository,
            "--job",
            str(job_id),
            "--log",
        ],
        timeout=240.0,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _extract_component_digests(
    build_log: str,
) -> dict[str, str | None]:
    if not build_log:
        return {
            "web": None,
            "backend": None,
            "ai": None,
        }

    component_markers = {
        "web": "Build and push Web image",
        "backend": "Build and push Backend image",
        "ai": "Build and push AI image",
    }
    result: dict[str, str | None] = {
        "web": None,
        "backend": None,
        "ai": None,
    }

    # First try to associate digest lines with the prefixed GitHub step name.
    for component, marker in component_markers.items():
        candidates: list[str] = []
        for line in build_log.splitlines():
            if marker in line:
                for digest in DIGEST_RE.findall(line):
                    candidates.append(digest)
        if candidates:
            result[component] = candidates[-1]

    # BuildKit logs often place the step name in the GitHub log prefix, then
    # the digest on following lines. Track the current known component and use
    # only digest-labelled lines to avoid collecting base-image digests.
    current: str | None = None
    for line in build_log.splitlines():
        for component, marker in component_markers.items():
            if marker in line:
                current = component
                break

        if current is None:
            continue

        lower = line.casefold()
        if "digest" not in lower:
            continue

        matches = DIGEST_RE.findall(line)
        if matches:
            result[current] = matches[-1]

    return result


def _validate_production_run(
    repository: str,
    run: dict[str, Any],
    *,
    current_sha: str,
) -> dict[str, Any]:
    run_id = int(run["databaseId"])
    jobs = _api_jobs(repository, run_id)

    source_job = _find_job(
        jobs,
        "Verify release source and container boundaries",
    )
    build_job = _find_job(
        jobs,
        "Build and publish immutable images",
    )
    deploy_job = _find_job(
        jobs,
        "Deploy through SSM and verify HTTPS",
    )

    if build_job is None or deploy_job is None:
        raise ExperimentFailed(
            "Successful Production run is missing required build/deploy jobs."
        )

    build_steps = _step_map(build_job)
    deploy_steps = _step_map(deploy_job)

    required_build_steps = (
        "Validate AWS repository variables",
        "Configure AWS Credentials",
        "Login to Amazon ECR",
        "Build and push Web image",
        "Build and push Backend image",
        "Build and push AI image",
        "Verify published images are non-root and executable",
        "Create and upload the release bundle",
    )
    # Action-generated step display names can vary slightly.  For action steps
    # we therefore verify by semantic fragments.
    def semantic_step_success(
        steps: dict[str, str | None],
        fragment: str,
    ) -> bool:
        matches = [
            conclusion
            for name, conclusion in steps.items()
            if fragment.casefold() in name.casefold()
        ]
        return bool(matches) and all(
            item == "success"
            for item in matches
        )

    build_checks = {
        "validate_aws_variables":
            semantic_step_success(
                build_steps,
                "Validate AWS repository variables",
            ),
        "aws_credentials":
            semantic_step_success(
                build_steps,
                "configure-aws-credentials",
            )
            or semantic_step_success(
                build_steps,
                "Configure AWS Credentials",
            ),
        "ecr_login":
            semantic_step_success(
                build_steps,
                "amazon-ecr-login",
            )
            or semantic_step_success(
                build_steps,
                "Login to Amazon ECR",
            ),
        "web_build_push":
            semantic_step_success(
                build_steps,
                "Build and push Web image",
            ),
        "backend_build_push":
            semantic_step_success(
                build_steps,
                "Build and push Backend image",
            ),
        "ai_build_push":
            semantic_step_success(
                build_steps,
                "Build and push AI image",
            ),
        "published_image_runtime_checks":
            semantic_step_success(
                build_steps,
                "Verify published images are non-root and executable",
            ),
        "release_bundle_upload":
            semantic_step_success(
                build_steps,
                "Create and upload the release bundle",
            ),
    }

    deploy_checks = {
        "aws_credentials":
            semantic_step_success(
                deploy_steps,
                "configure-aws-credentials",
            )
            or semantic_step_success(
                deploy_steps,
                "Configure AWS Credentials",
            ),
        "ssm_deployment":
            semantic_step_success(
                deploy_steps,
                "Deploy the immutable release on EC2",
            ),
        "external_https_smoke":
            semantic_step_success(
                deploy_steps,
                "Run external HTTPS smoke",
            ),
        "record_deployment_result":
            semantic_step_success(
                deploy_steps,
                "Record deployment result",
            ),
    }

    source_guard_success = (
        source_job is not None
        and source_job.get("conclusion") == "success"
    )
    build_success = (
        build_job.get("conclusion") == "success"
        and all(build_checks.values())
    )
    deploy_success = (
        deploy_job.get("conclusion") == "success"
        and all(deploy_checks.values())
    )

    build_log = _job_log(
        repository,
        int(build_job["id"]),
    )
    digests = _extract_component_digests(
        build_log
    )
    digest_checks = {
        component: (
            isinstance(value, str)
            and DIGEST_RE.fullmatch(value)
            is not None
        )
        for component, value in digests.items()
    }

    deploy_log = _job_log(
        repository,
        int(deploy_job["id"]),
    )
    runtime_marker = (
        "DEPLOYMENT_RUNTIME_PASS"
        in deploy_log
    )
    observability_partial_marker = (
        "OBSERVABILITY_PARTIAL"
        in deploy_log
    )

    release_sha = run.get("headSha")
    tag_candidate = (
        run.get("headBranch")
        or run.get("displayTitle")
        or ""
    )

    overall = (
        run.get("conclusion") == "success"
        and source_guard_success
        and build_success
        and deploy_success
    )

    return {
        "status":
            "VERIFIED"
            if overall
            else "FAILED",
        "workflow_run_id": run_id,
        "workflow_run_url": run.get("url"),
        "created_at": run.get("createdAt"),
        "release_sha": release_sha,
        "release_sha_canonical":
            isinstance(release_sha, str)
            and SHA_RE.fullmatch(release_sha)
            is not None,
        "release_sha_is_ancestor_of_current_head":
            isinstance(release_sha, str)
            and _is_ancestor(
                release_sha,
                current_sha,
            ),
        "tag_or_branch_observed":
            tag_candidate,
        "stable_semver_observed":
            isinstance(tag_candidate, str)
            and SEMVER_RE.fullmatch(
                tag_candidate
            )
            is not None,
        "source_guard_job":
            {
                "present":
                    source_job is not None,
                "success":
                    source_guard_success,
            },
        "build_job": {
            "job_id":
                build_job.get("id"),
            "success":
                build_success,
            "checks":
                build_checks,
        },
        "deploy_job": {
            "job_id":
                deploy_job.get("id"),
            "success":
                deploy_success,
            "checks":
                deploy_checks,
        },
        "ecr_image_digest_evidence": {
            "web": digests["web"],
            "backend": digests["backend"],
            "ai": digests["ai"],
            "canonical_digest_checks":
                digest_checks,
            "exact_digests_captured":
                all(digest_checks.values()),
            "note": (
                "Digest values are best-effort extracted from the "
                "successful build job log. A successful Production run "
                "still executes the committed digest-pinning workflow "
                "contract even when GitHub log formatting prevents exact "
                "digest extraction."
            ),
        },
        "runtime_markers": {
            "deployment_runtime_pass_seen":
                runtime_marker,
            "observability_partial_seen":
                observability_partial_marker,
            "marker_source":
                "deploy_job_log_best_effort",
        },
        "sensitive_values_captured": False,
        "raw_job_logs_persisted": False,
    }


def _rollback_contract(
    sha: str,
) -> dict[str, Any]:
    deploy = _git_show(
        sha,
        SOURCE_FILES["trusted_deploy"],
    )
    shell = _git_show(
        sha,
        SOURCE_FILES["deploy_script"],
    )
    rollback = _git_show(
        sha,
        SOURCE_FILES["rollback_script"],
    )

    checks = {
        "workflow_post_failure_rollback":
            _contains(
                deploy,
                "Roll back after a post-deployment failure",
                "failure()",
                "mutation_started == 'true'",
            ),
        "rollback_via_ssm":
            _contains(
                deploy,
                "rollback-release.sh",
                "aws ssm send-command",
                "AWS-RunShellScript",
            ),
        "host_previous_release_restore":
            _contains(
                shell,
                "previous_target",
                "current.rollback",
                "restore_previous_worker",
            ),
        "volumes_not_deleted":
            "rolling back without deleting volumes"
            in shell,
        "standalone_rollback_asset":
            bool(rollback.strip()),
    }
    return {
        "status":
            "PASS"
            if all(checks.values())
            else "FAIL",
        "checks": checks,
        "fault_injection_performed": False,
        "real_rollback_execution":
            "NOT_REQUIRED_FOR_E13",
        "claim_boundary": (
            "Rollback implementation contract is verified statically. "
            "E13 does not inject a Production failure."
        ),
    }


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


def _report(
    path: Path,
    summary: dict[str, Any],
) -> None:
    oidc = summary["oidc_evidence"]
    prod = summary["production_deployment_evidence"]
    source = summary["source_contract"]
    rollback = summary["rollback_contract"]

    lines = [
        "# E13 — GitHub Actions + ECR + SSM Deployment Reproducibility",
        "",
        f"- Status: **{summary['status']}**",
        f"- Current Git SHA: `{summary['git_sha']}`",
        f"- Repository: `{summary['repository']}`",
        "",
        "## E13-01 Release Source / CI Contract",
        "",
        f"- Source contract: `{source['status']}`",
        (
            "- Application source pinned to release SHA: "
            "`True`"
        ),
        (
            "- Reusable workflow implementation pinned to release SHA: "
            "`False` (`production-deploy.yml@main`)"
        ),
        "",
        "## E13-02 GitHub OIDC → AWS → ECR / SSM",
        "",
        f"- Status: `{oidc['status']}`",
        (
            "- Workflow run ID: "
            f"`{oidc.get('workflow_run_id')}`"
        ),
        (
            "- ECR repositories 3/3 verified: "
            f"`{oidc.get('claims', {}).get('ecr_repositories_3_of_3')}`"
        ),
        (
            "- SSM command path verified: "
            f"`{oidc.get('claims', {}).get('ssm_command_path')}`"
        ),
        "",
        "## E13-03/E13-04 Existing Production Release Evidence",
        "",
    ]

    if prod.get("status") == "VERIFIED":
        digest = prod["ecr_image_digest_evidence"]
        lines.extend(
            [
                "- Existing successful Production Deploy: `VERIFIED`",
                (
                    "- Production workflow run ID: "
                    f"`{prod['workflow_run_id']}`"
                ),
                (
                    "- Release SHA: "
                    f"`{prod['release_sha']}`"
                ),
                (
                    "- Build and publish job: "
                    f"`{prod['build_job']['success']}`"
                ),
                (
                    "- SSM deploy job: "
                    f"`{prod['deploy_job']['checks']['ssm_deployment']}`"
                ),
                (
                    "- External HTTPS smoke: "
                    f"`{prod['deploy_job']['checks']['external_https_smoke']}`"
                ),
                (
                    "- Exact Web/Backend/AI digest values recovered from "
                    f"log: `{digest['exact_digests_captured']}`"
                ),
                (
                    "- DEPLOYMENT_RUNTIME_PASS marker recovered from log: "
                    f"`{prod['runtime_markers']['deployment_runtime_pass_seen']}`"
                ),
            ]
        )
    else:
        lines.extend(
            [
                "- Existing successful Production Deploy: `NOT_VERIFIED`",
                (
                    "- E13 intentionally did not create a release tag or "
                    "dispatch a Production deployment."
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## E13-05 Rollback Contract",
            "",
            f"- Rollback contract: `{rollback['status']}`",
            "- Production fault injection: `False`",
            "",
            "## Security / Evidence Boundary",
            "",
            "- AWS credentials captured: `False`",
            "- OIDC token captured: `False`",
            "- ECR password captured: `False`",
            "- Raw SSM stdout persisted: `False`",
            "- Raw GitHub job logs persisted: `False`",
            "",
            "## Interpretation",
            "",
            (
                "E13_COMPLETE는 기존 성공 Production Release의 GitHub "
                "Actions 실행 증거까지 확인한 경우에만 사용한다. "
                "E13_PARTIAL은 GitHub OIDC → AWS Role → ECR repository "
                "검증 → 실제 SSM command path까지는 확인했지만, 적절한 "
                "성공 Production Release 실행 증거를 확인하지 못한 경우다."
            ),
            "",
            (
                "현재 배포 경계는 `DEPLOYMENT_RUNTIME_PASS`와 "
                "`OBSERVABILITY_PARTIAL`을 구분한다. E13은 완전한 "
                "distributed tracing 완료를 주장하지 않는다."
            ),
            "",
            "## Presentation-ready Claim",
            "",
            (
                "GitHub Actions에서 장기 Access Key 대신 OIDC로 AWS "
                "Role을 획득하고 ECR 및 SSM 연결 경로를 검증했다. "
                "성공 Production Release가 확인된 경우에는 검증을 통과한 "
                "Web·Backend·AI 이미지를 ECR에 게시하고 Image Digest를 "
                "Release Bundle에 고정한 뒤, SSM을 통해 EC2에서 배포하고 "
                "외부 HTTPS Smoke까지 통과한 실행 증거를 연결했다."
            ),
            "",
        ]
    )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )


def _write_checksums(
    result_dir: Path,
) -> None:
    rows = []
    for path in sorted(
        item
        for item in result_dir.iterdir()
        if item.is_file()
        and item.name != "artifact_checksums.json"
    ):
        rows.append(
            {
                "path": path.name,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    _write_json(
        result_dir / "artifact_checksums.json",
        {
            "algorithm": "SHA-256",
            "artifacts": rows,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "E13 GitHub Actions + ECR + SSM deployment "
            "reproducibility evidence collector."
        )
    )
    parser.add_argument(
        "--dispatch-oidc-smoke",
        action="store_true",
        help=(
            "Dispatch the repository's existing AWS OIDC Smoke Test "
            "and wait for it. This does NOT deploy Production."
        ),
    )
    parser.add_argument(
        "--oidc-max-age-days",
        type=int,
        default=30,
        help=(
            "Maximum age for reusing a previous successful OIDC smoke "
            "when --dispatch-oidc-smoke is not supplied."
        ),
    )
    parser.add_argument(
        "--production-run-id",
        type=int,
        help=(
            "Use one existing successful Production workflow run ID. "
            "No Production workflow is dispatched."
        ),
    )
    parser.add_argument(
        "--wait-timeout-seconds",
        type=int,
        default=900,
    )
    args = parser.parse_args()

    git_sha: str | None = None
    result_dir: Path | None = None

    print(
        "=== E13: GitHub Actions + ECR + SSM "
        "Deployment Reproducibility ==="
    )
    print(
        "[E13] Production mutation policy: READ-ONLY "
        "(no tag creation / no Production dispatch)"
    )

    try:
        git_sha = _head_sha()
        repository = _remote_repository()

        if repository != EXPECTED_REPOSITORY:
            raise ExperimentBlocked(
                f"Unexpected repository: {repository}"
            )

        run_stamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%SZ")
        result_dir = (
            RESULT_ROOT
            / f"e13-{run_stamp}-{git_sha[:8]}"
        )
        result_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        print(f"[E13] git_sha={git_sha}")
        print(f"[E13] repository={repository}")

        source = _source_contract(git_sha)
        _write_json(
            result_dir / "source_contract.json",
            source,
        )
        print(
            f"[E13] E13-01 Source Contract: "
            f"{source['status']}"
        )
        if source["status"] != "PASS":
            raise ExperimentFailed(
                "Committed deployment source contract failed: "
                + ", ".join(source["failed_checks"])
            )

        gh_state = _gh_ready(repository)
        print(
            "[E13] GitHub CLI/Auth: PASS"
        )

        if args.dispatch_oidc_smoke:
            smoke_run = _dispatch_oidc_smoke(
                repository,
                timeout_seconds=args.wait_timeout_seconds,
            )
            # gh run view returns databaseId with requested fields.
            if "databaseId" not in smoke_run:
                # Re-query via listing to normalize.
                candidates = _list_runs(
                    repository,
                    OIDC_WORKFLOW_FILE,
                    limit=10,
                )
                if candidates:
                    smoke_run = candidates[0]
        else:
            smoke_run = _select_recent_successful_smoke(
                repository,
                max_age_days=args.oidc_max_age_days,
            )
            if smoke_run is None:
                raise ExperimentBlocked(
                    "No recent successful AWS OIDC Smoke Test is "
                    "available. Later rerun with --dispatch-oidc-smoke."
                )

        if smoke_run.get("conclusion") != "success":
            raise ExperimentFailed(
                "AWS OIDC Smoke Test did not conclude successfully."
            )

        oidc = _validate_oidc_run(
            repository,
            smoke_run,
        )
        _write_json(
            result_dir / "oidc_ssm_evidence.json",
            oidc,
        )
        print(
            f"[E13] E13-02 OIDC/ECR/SSM: "
            f"{oidc['status']}"
        )
        if oidc["status"] != "PASS":
            raise ExperimentFailed(
                "OIDC/ECR/SSM smoke evidence failed."
            )

        prod_run = _select_production_run(
            repository,
            current_sha=git_sha,
            explicit_run_id=args.production_run_id,
        )

        if prod_run is None:
            production = {
                "status": "NOT_VERIFIED",
                "reason": (
                    "NO_SUITABLE_SUCCESSFUL_PRODUCTION_RELEASE_RUN"
                ),
                "production_dispatch_performed": False,
                "claim_boundary": (
                    "E13 does not create a tag or trigger Production."
                ),
            }
            print(
                "[E13] E13-03/E13-04 Production Deploy: "
                "NOT_VERIFIED"
            )
        else:
            production = _validate_production_run(
                repository,
                prod_run,
                current_sha=git_sha,
            )
            print(
                "[E13] E13-03/E13-04 Existing Production Deploy: "
                f"{production['status']}"
            )
            if production["status"] != "VERIFIED":
                raise ExperimentFailed(
                    "Selected successful Production workflow did not "
                    "contain the required deployment evidence."
                )

        _write_json(
            result_dir / "deployment_evidence.json",
            production,
        )

        rollback = _rollback_contract(git_sha)
        _write_json(
            result_dir / "rollback_contract.json",
            rollback,
        )
        print(
            f"[E13] E13-05 Rollback Contract: "
            f"{rollback['status']}"
        )
        if rollback["status"] != "PASS":
            raise ExperimentFailed(
                "Rollback implementation contract failed."
            )

        status = (
            "E13_COMPLETE"
            if production.get("status") == "VERIFIED"
            else "E13_PARTIAL"
        )

        summary = {
            "status": status,
            "git_sha": git_sha,
            "repository": repository,
            "source_contract": source,
            "github_cli": gh_state,
            "oidc_evidence": oidc,
            "production_deployment_evidence":
                production,
            "rollback_contract": rollback,
            "production_dispatch_performed": False,
            "git_tag_created": False,
            "sensitive_evidence": {
                "aws_credentials": False,
                "oidc_token": False,
                "ecr_password": False,
                "runtime_env": False,
                "raw_ssm_stdout": False,
                "raw_github_job_logs": False,
                "customer_data": False,
            },
            "claim_boundary": {
                "deployment_runtime":
                    "VERIFIED"
                    if status == "E13_COMPLETE"
                    else "NOT_VERIFIED",
                "observability":
                    "OBSERVABILITY_PARTIAL",
                "zero_downtime_claim": False,
                "blue_green_claim": False,
                "production_fault_injection": False,
                "real_rollback_execution_required":
                    False,
            },
        }
        _write_json(
            result_dir / "summary.json",
            summary,
        )
        _report(
            result_dir / "report.md",
            summary,
        )
        _write_checksums(result_dir)

        final = {
            "status": status,
            "git_sha": git_sha,
            "oidc_ecr_ssm":
                oidc["status"],
            "oidc_workflow_run_id":
                oidc["workflow_run_id"],
            "ecr_repositories":
                "3/3"
                if oidc["claims"][
                    "ecr_repositories_3_of_3"
                ]
                else "NOT_VERIFIED",
            "ssm_command_path":
                "PASS"
                if oidc["claims"][
                    "ssm_command_path"
                ]
                else "FAIL",
            "production_deployment":
                production.get("status"),
            "production_workflow_run_id":
                production.get(
                    "workflow_run_id"
                ),
            "runtime_marker_seen":
                production.get(
                    "runtime_markers",
                    {},
                ).get(
                    "deployment_runtime_pass_seen"
                ),
            "external_https_smoke":
                production.get(
                    "deploy_job",
                    {},
                ).get(
                    "checks",
                    {},
                ).get(
                    "external_https_smoke"
                ),
            "exact_image_digests_captured":
                production.get(
                    "ecr_image_digest_evidence",
                    {},
                ).get(
                    "exact_digests_captured"
                ),
            "rollback_contract":
                rollback["status"],
            "production_dispatch_performed":
                False,
            "output_dir":
                result_dir.relative_to(
                    REPO_ROOT
                ).as_posix(),
        }

        print()
        print("=" * 88)
        print("[E13] FINAL")
        print(
            json.dumps(
                final,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    except ExperimentBlocked as exc:
        if result_dir is not None:
            payload = {
                "status":
                    "E13_ENVIRONMENT_BLOCKED",
                "git_sha": git_sha,
                "error_type":
                    type(exc).__name__,
                "message": str(exc),
                "production_dispatch_performed":
                    False,
                "result_interpretation":
                    "NOT_A_VALID_E13_RESULT",
            }
            _write_json(
                result_dir / "summary.json",
                payload,
            )
        print()
        print("=" * 88)
        print("[E13] E13_ENVIRONMENT_BLOCKED")
        print(str(exc))
        return 2

    except Exception as exc:
        if result_dir is not None:
            payload = {
                "status": "E13_FAILED",
                "git_sha": git_sha,
                "error_type":
                    type(exc).__name__,
                "message": str(exc),
                "production_dispatch_performed":
                    False,
                "result_interpretation":
                    "E13 verification executed but did not satisfy "
                    "the frozen contract.",
            }
            _write_json(
                result_dir / "summary.json",
                payload,
            )
        print()
        print("=" * 88)
        print("[E13] E13_FAILED")
        print(
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
