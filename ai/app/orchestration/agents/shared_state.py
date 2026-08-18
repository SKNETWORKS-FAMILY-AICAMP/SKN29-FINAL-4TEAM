"""3-Agent가 공유하는 내부 실행 State."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .contracts import AgentHandoff, AgentRole, HandoffReason, MultiAgentRunMetadata
from ..pipeline_context import PipelineContext


class AgentHopLimitExceeded(RuntimeError):
    """Supervisor가 허용된 역할 전환 횟수를 초과한 경우."""


class MultiAgentSharedState(BaseModel):
    """Backend 업무 State와 분리된 AI 내부 State."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    context: PipelineContext
    current_agent: AgentRole = AgentRole.SUPERVISOR
    handoffs: list[AgentHandoff] = Field(default_factory=list)
    hop_count: int = Field(default=0, ge=0, le=8)
    max_hops: int = Field(default=8, ge=1, le=8)
    awaiting_customer_input: bool = False
    feedback_handoff_count: int = Field(default=0, ge=0, le=1)

    def handoff(self, to_agent: AgentRole, reason: HandoffReason) -> None:
        """민감 본문 없이 허용된 역할 전환만 기록한다."""

        if self.hop_count >= self.max_hops:
            raise AgentHopLimitExceeded(
                f"Multi-Agent 최대 Handoff {self.max_hops}회를 초과했습니다."
            )
        trace = self.context.trace_context
        next_hop = self.hop_count + 1
        self.handoffs.append(
            AgentHandoff(
                inquiry_id=trace.inquiry_id,
                correlation_id=trace.correlation_id,
                ai_request_id=trace.ai_request_id,
                state_version=trace.state_version,
                from_agent=self.current_agent,
                to_agent=to_agent,
                reason_code=reason,
                hop_count=next_hop,
                retry_count=self.context.retry_count,
            )
        )
        self.current_agent = to_agent
        self.hop_count = next_hop

    def metadata(self) -> MultiAgentRunMetadata:
        return MultiAgentRunMetadata(
            hop_count=self.hop_count,
            awaiting_customer_input=self.awaiting_customer_input,
            handoffs=list(self.handoffs),
        )
