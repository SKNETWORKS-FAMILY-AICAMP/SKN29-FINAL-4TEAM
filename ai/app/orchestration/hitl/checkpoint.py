"""LangGraph HITL checkpoint helpers."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, ConfigDict, Field


class HumanReviewCheckpoint(BaseModel):
    """Stable checkpoint identity shared by interrupt and resume calls."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    thread_id: str = Field(..., min_length=1, max_length=100)
    state_version: int = Field(..., ge=1)

    def langgraph_config(self) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": self.thread_id}}


def build_hitl_thread_id(
    *,
    inquiry_id: UUID,
    ai_request_id: str,
    state_version: int,
) -> str:
    """Create a deterministic, non-PII LangGraph thread id for one AI request version."""

    raw = f"{inquiry_id}:{ai_request_id}:{state_version}".encode("utf-8")
    digest = sha256(raw).hexdigest()[:32]
    return f"hitl-{digest}"


def create_hitl_checkpointer() -> InMemorySaver:
    """Return the currently available checkpointer.

    InMemorySaver survives interrupt/resume inside one AI process. A persistent
    Postgres/SQLite saver must replace this factory before claiming process-restart
    durability in production.
    """

    return InMemorySaver()
