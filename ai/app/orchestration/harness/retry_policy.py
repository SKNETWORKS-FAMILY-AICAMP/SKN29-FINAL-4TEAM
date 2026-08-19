"""Retry budget enforcement for Harness decisions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .verification_result import HarnessDecision


class HarnessRetryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_retries: int = Field(0, ge=0, le=1)
    generation_retries: int = Field(0, ge=0, le=1)


class RetryPolicyOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: HarnessDecision
    state: HarnessRetryState
    exhausted: bool = False


class HarnessRetryPolicy:
    MAX_RETRIEVAL_RETRIES = 1
    MAX_GENERATION_RETRIES = 1

    def apply(
        self,
        decision: HarnessDecision,
        state: HarnessRetryState,
    ) -> RetryPolicyOutcome:
        if decision == HarnessDecision.RETRY_RETRIEVAL:
            if state.retrieval_retries >= self.MAX_RETRIEVAL_RETRIES:
                return RetryPolicyOutcome(
                    decision=HarnessDecision.ESCALATE,
                    state=state,
                    exhausted=True,
                )
            return RetryPolicyOutcome(
                decision=HarnessDecision.RETRY_RETRIEVAL,
                state=state.model_copy(
                    update={"retrieval_retries": state.retrieval_retries + 1}
                ),
            )

        if decision == HarnessDecision.RETRY_GENERATION:
            if state.generation_retries >= self.MAX_GENERATION_RETRIES:
                return RetryPolicyOutcome(
                    decision=HarnessDecision.ESCALATE,
                    state=state,
                    exhausted=True,
                )
            return RetryPolicyOutcome(
                decision=HarnessDecision.RETRY_GENERATION,
                state=state.model_copy(
                    update={"generation_retries": state.generation_retries + 1}
                ),
            )

        return RetryPolicyOutcome(decision=decision, state=state)
