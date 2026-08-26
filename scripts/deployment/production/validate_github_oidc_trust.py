"""Render and validate the production GitHub OIDC trust boundary.

The deployment role accepts two GitHub identities only:

* the repository main branch for bootstrap and read-only smoke workflows;
* jobs scoped to the production Environment and implemented by the trusted
  reusable workflow on main.

The tag-triggered workflow only forwards the immutable release identity.  The
trusted reusable workflow on main independently enforces the push/tag context,
strict numeric SemVer, input identity, and main ancestry before an
Environment-scoped job can request AWS credentials.  IAM pins that reusable
workflow, repository identity, production Environment, and audience without
hard-coding one release tag.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


OIDC_HOST = "token.actions.githubusercontent.com"
AUDIENCE_CLAIM = f"{OIDC_HOST}:aud"
SUBJECT_CLAIM = f"{OIDC_HOST}:sub"
REF_CLAIM = f"{OIDC_HOST}:ref"
REPOSITORY_CLAIM = f"{OIDC_HOST}:repository"
REPOSITORY_ID_CLAIM = f"{OIDC_HOST}:repository_id"
REPOSITORY_OWNER_ID_CLAIM = f"{OIDC_HOST}:repository_owner_id"
ENVIRONMENT_CLAIM = f"{OIDC_HOST}:environment"
JOB_WORKFLOW_REF_CLAIM = f"{OIDC_HOST}:job_workflow_ref"
AUDIENCE = "sts.amazonaws.com"
PRODUCTION_ENVIRONMENT = "production"
PRODUCTION_WORKFLOW_PATH = ".github/workflows/production-deploy.yml"
POLICY_VERSION = "2012-10-17"

_ACCOUNT_ID_RE = re.compile(r"^[0-9]{12}$")
_REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
)
_GITHUB_ID_RE = re.compile(r"^[1-9][0-9]*$")


class TrustPolicyError(ValueError):
    """The policy does not match the approved GitHub OIDC boundary."""


def render_policy(
    *,
    account_id: str,
    repository: str,
    repository_id: str,
    repository_owner_id: str,
) -> dict[str, Any]:
    """Return the complete canonical trust policy for the deployment role."""

    _validate_identity_inputs(
        account_id=account_id,
        repository=repository,
        repository_id=repository_id,
        repository_owner_id=repository_owner_id,
    )
    provider_arn = (
        f"arn:aws:iam::{account_id}:oidc-provider/{OIDC_HOST}"
    )
    return {
        "Version": POLICY_VERSION,
        "Statement": [
            {
                "Sid": "GitHubActionsMainBootstrap",
                "Effect": "Allow",
                "Principal": {"Federated": provider_arn},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        AUDIENCE_CLAIM: AUDIENCE,
                        SUBJECT_CLAIM: (
                            f"repo:{repository}:ref:refs/heads/main"
                        ),
                        REF_CLAIM: "refs/heads/main",
                        REPOSITORY_CLAIM: repository,
                        REPOSITORY_ID_CLAIM: repository_id,
                        REPOSITORY_OWNER_ID_CLAIM: repository_owner_id,
                    }
                },
            },
            {
                "Sid": "GitHubActionsProductionEnvironment",
                "Effect": "Allow",
                "Principal": {"Federated": provider_arn},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        AUDIENCE_CLAIM: AUDIENCE,
                        SUBJECT_CLAIM: (
                            f"repo:{repository}:environment:"
                            f"{PRODUCTION_ENVIRONMENT}"
                        ),
                        REPOSITORY_CLAIM: repository,
                        REPOSITORY_ID_CLAIM: repository_id,
                        REPOSITORY_OWNER_ID_CLAIM: repository_owner_id,
                        ENVIRONMENT_CLAIM: PRODUCTION_ENVIRONMENT,
                        JOB_WORKFLOW_REF_CLAIM: (
                            f"{repository}/{PRODUCTION_WORKFLOW_PATH}"
                            "@refs/heads/main"
                        ),
                    },
                },
            },
        ],
    }


def validate_policy(
    policy: Any,
    *,
    account_id: str,
    repository: str,
    repository_id: str,
    repository_owner_id: str,
) -> None:
    """Require the full policy to equal the canonical least-trust document."""

    expected = render_policy(
        account_id=account_id,
        repository=repository,
        repository_id=repository_id,
        repository_owner_id=repository_owner_id,
    )
    if not isinstance(policy, dict):
        raise TrustPolicyError("trust policy must be a JSON object")
    if policy != expected:
        raise TrustPolicyError(
            "trust policy does not match the canonical main and production "
            "SemVer-tag boundary"
        )


def _validate_identity_inputs(
    *,
    account_id: str,
    repository: str,
    repository_id: str,
    repository_owner_id: str,
) -> None:
    if _ACCOUNT_ID_RE.fullmatch(account_id) is None:
        raise TrustPolicyError("account id must contain exactly 12 digits")
    if _REPOSITORY_RE.fullmatch(repository) is None:
        raise TrustPolicyError("repository must use owner/name format")
    if _GITHUB_ID_RE.fullmatch(repository_id) is None:
        raise TrustPolicyError("repository id must contain only positive digits")
    if _GITHUB_ID_RE.fullmatch(repository_owner_id) is None:
        raise TrustPolicyError(
            "repository owner id must contain only positive digits"
        )


def _load_policy(path: str) -> Any:
    try:
        if path == "-":
            return json.load(sys.stdin)
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrustPolicyError("trust policy could not be read as JSON") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render or validate the WaterBridge GitHub OIDC trust policy."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("render", "validate"):
        command = subparsers.add_parser(name)
        command.add_argument("--account-id", required=True)
        command.add_argument("--repository", required=True)
        command.add_argument("--repository-id", required=True)
        command.add_argument("--repository-owner-id", required=True)
        if name == "validate":
            command.add_argument(
                "--policy-file",
                default="-",
                help="JSON file path or '-' for stdin.",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "render":
            policy = render_policy(
                account_id=args.account_id,
                repository=args.repository,
                repository_id=args.repository_id,
                repository_owner_id=args.repository_owner_id,
            )
            print(json.dumps(policy, ensure_ascii=False, indent=2))
            return 0

        policy = _load_policy(args.policy_file)
        validate_policy(
            policy,
            account_id=args.account_id,
            repository=args.repository,
            repository_id=args.repository_id,
            repository_owner_id=args.repository_owner_id,
        )
    except TrustPolicyError as exc:
        print(
            f"GITHUB_OIDC_TRUST_FAILED reason={exc}",
            file=sys.stderr,
        )
        return 1

    print("GITHUB_OIDC_TRUST_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
