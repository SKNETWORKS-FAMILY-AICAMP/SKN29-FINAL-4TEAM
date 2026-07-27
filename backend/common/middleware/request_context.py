"""요청 범위 추적 Context."""

from contextvars import ContextVar, Token


_correlation_id_context: ContextVar[str | None] = ContextVar(
    "correlation_id",
    default=None,
)


def set_correlation_id(correlation_id: str) -> Token:
    return _correlation_id_context.set(correlation_id)


def get_correlation_id() -> str | None:
    return _correlation_id_context.get()


def reset_correlation_id(token: Token) -> None:
    _correlation_id_context.reset(token)
