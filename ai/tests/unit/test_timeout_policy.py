"""T-032 단계별 Timeout·협력적 취소 정책 검증."""

import time

import pytest

from ai.app.common.timeout import (
    CancellationToken,
    PipelineStageTimeoutError,
    get_stage_timeout_policy,
)


def test_stage_timeout_policy_matches_configured_budget():
    policy = get_stage_timeout_policy()

    assert policy.for_stage("STRUCTURING") == 5.0
    assert policy.for_stage("CHECKING_MISSING_FIELDS") == 5.0
    assert policy.for_stage("SAFETY_CHECK") == 3.0
    assert policy.for_stage("RETRIEVING") == 5.0
    assert policy.for_stage("GENERATING") == 15.0
    assert policy.for_stage("VALIDATING") == 3.0


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
