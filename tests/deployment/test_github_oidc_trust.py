"""Tests for the canonical production GitHub OIDC trust boundary."""

from __future__ import annotations

import copy
import unittest

from scripts.deployment.production.validate_github_oidc_trust import (
    ENVIRONMENT_CLAIM,
    JOB_WORKFLOW_REF_CLAIM,
    REF_CLAIM,
    SUBJECT_CLAIM,
    TrustPolicyError,
    render_policy,
    validate_policy,
)


ACCOUNT_ID = "123456789012"
REPOSITORY = "SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM"
REPOSITORY_ID = "1295987066"
REPOSITORY_OWNER_ID = "169222902"


class GitHubOidcTrustPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = render_policy(
            account_id=ACCOUNT_ID,
            repository=REPOSITORY,
            repository_id=REPOSITORY_ID,
            repository_owner_id=REPOSITORY_OWNER_ID,
        )

    def test_canonical_policy_accepts_main_and_production_environment(self) -> None:
        validate_policy(
            self.policy,
            account_id=ACCOUNT_ID,
            repository=REPOSITORY,
            repository_id=REPOSITORY_ID,
            repository_owner_id=REPOSITORY_OWNER_ID,
        )
        production = self.policy["Statement"][1]
        self.assertEqual(
            production["Sid"],
            "GitHubActionsProductionEnvironment",
        )
        self.assertNotIn(
            REF_CLAIM,
            production["Condition"]["StringEquals"],
        )
        self.assertEqual(
            production["Condition"]["StringEquals"][ENVIRONMENT_CLAIM],
            "production",
        )
        self.assertEqual(
            production["Condition"]["StringEquals"][JOB_WORKFLOW_REF_CLAIM],
            f"{REPOSITORY}/.github/workflows/production-deploy.yml"
            "@refs/heads/main",
        )
        self.assertNotIn("StringLike", production["Condition"])

    def test_rejects_one_release_tag_hardcoding(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["Statement"][1]["Condition"]["StringEquals"][REF_CLAIM] = (
            "refs/tags/v0.1.1"
        )
        with self.assertRaises(TrustPolicyError):
            validate_policy(
                policy,
                account_id=ACCOUNT_ID,
                repository=REPOSITORY,
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )

    def test_rejects_overbroad_tag_wildcard(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["Statement"][1]["Condition"]["StringLike"] = {
            REF_CLAIM: "refs/tags/*"
        }
        with self.assertRaises(TrustPolicyError):
            validate_policy(
                policy,
                account_id=ACCOUNT_ID,
                repository=REPOSITORY,
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )

    def test_rejects_unpinned_reusable_workflow(self) -> None:
        policy = copy.deepcopy(self.policy)
        condition = policy["Statement"][1]["Condition"]["StringEquals"]
        condition[JOB_WORKFLOW_REF_CLAIM] = (
            f"{REPOSITORY}/.github/workflows/production-deploy.yml@*"
        )
        with self.assertRaises(TrustPolicyError):
            validate_policy(
                policy,
                account_id=ACCOUNT_ID,
                repository=REPOSITORY,
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )

    def test_rejects_overbroad_repository_subject(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["Statement"][1]["Condition"]["StringEquals"][SUBJECT_CLAIM] = (
            "repo:SKNETWORKS-FAMILY-AICAMP/*:environment:production"
        )
        with self.assertRaises(TrustPolicyError):
            validate_policy(
                policy,
                account_id=ACCOUNT_ID,
                repository=REPOSITORY,
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )

    def test_rejects_an_additional_trusted_identity(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["Statement"].append(copy.deepcopy(policy["Statement"][0]))
        with self.assertRaises(TrustPolicyError):
            validate_policy(
                policy,
                account_id=ACCOUNT_ID,
                repository=REPOSITORY,
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )

    def test_rejects_invalid_identity_inputs(self) -> None:
        with self.assertRaises(TrustPolicyError):
            render_policy(
                account_id="123",
                repository=REPOSITORY,
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )
        with self.assertRaises(TrustPolicyError):
            render_policy(
                account_id=ACCOUNT_ID,
                repository="missing-owner",
                repository_id=REPOSITORY_ID,
                repository_owner_id=REPOSITORY_OWNER_ID,
            )
        with self.assertRaises(TrustPolicyError):
            render_policy(
                account_id=ACCOUNT_ID,
                repository=REPOSITORY,
                repository_id="0",
                repository_owner_id=REPOSITORY_OWNER_ID,
            )


if __name__ == "__main__":
    unittest.main()
