"""T-032 단계별 Timeout·협력적 취소 정책 검증."""

import time

import pytest

from ai.app.common.timeout import (
    CancellationToken,
    PipelineStageTimeoutError,
    get_stage_timeout_policy,
)
from ai.app.common.retry import get_retry_policy
from ai.app.common.protected_database import ProtectedDatabaseOperationError


def test_stage_timeout_policy_matches_configured_budget():
    policy = get_stage_timeout_policy()

    assert policy.for_stage("STRUCTURING") == 5.0
    assert policy.for_stage("CHECKING_MISSING_FIELDS") == 5.0
    assert policy.for_stage("SAFETY_CHECK") == 3.0
    assert policy.for_stage("RETRIEVING") == 5.0
    assert policy.for_stage("GENERATING") == 15.0
    assert policy.for_stage("VALIDATING") == 3.0


def test_retry_policy_is_enabled_for_transient_failures_only():
    policy = get_retry_policy()

    assert policy.max_retry_count == 1
    assert policy.backoff_seconds(1) == 0.5
    assert policy.can_retry(ConnectionError("temporary"), retry_count=0) is True
    assert policy.can_retry(ConnectionError("temporary"), retry_count=1) is False
    assert policy.can_retry(ValueError("invalid"), retry_count=0) is False
    assert policy.is_retryable_exception(ConnectionError("temporary")) is True
    assert policy.is_retryable_exception(ValueError("invalid")) is False
    assert policy.is_retryable_exception(
        ProtectedDatabaseOperationError("safe", retryable=True)
    ) is True
    assert policy.is_retryable_exception(
        ProtectedDatabaseOperationError("safe", retryable=False)
    ) is False


def test_deadline_scope_raises_stage_specific_timeout():
    token = CancellationToken()

    with pytest.raises(PipelineStageTimeoutError) as raised:
        with token.deadline_scope(0.001, "RETRIEVING"):
            time.sleep(0.01)

    assert raised.value.stage == "RETRIEVING"


def test_deadline_scope_restores_outer_token_for_following_stage():
    token = CancellationToken()

    with token.deadline_scope(0.1, "STRUCTURING"):
        token.raise_if_cancelled()
    token.raise_if_cancelled()
