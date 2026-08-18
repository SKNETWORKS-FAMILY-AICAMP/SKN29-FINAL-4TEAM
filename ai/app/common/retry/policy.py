"""설정 기반 AI 내부 재시도 정책."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RetryPolicy:
    """일시적 Provider 오류에만 적용하는 최대 1회 재시도 정책."""

    enabled: bool
    max_retry_count: int
    backoff_factor_seconds: float
    retryable_exception_names: frozenset[str]

    def is_retryable_exception(self, exc: Exception) -> bool:
        explicit_retryable = getattr(exc, "retryable", None)
        if isinstance(explicit_retryable, bool):
            return explicit_retryable
        exception_names = {cls.__name__ for cls in type(exc).__mro__}
        return bool(exception_names & self.retryable_exception_names)

    def can_retry(self, exc: Exception, retry_count: int) -> bool:
        return (
            self.enabled
            and retry_count < self.max_retry_count
            and self.is_retryable_exception(exc)
        )

    def backoff_seconds(self, retry_count: int) -> float:
        """다음 시도 전 대기 시간. retry_count는 이미 수행한 재시도 횟수다."""
        if retry_count < 1:
            return 0.0
        return self.backoff_factor_seconds * (2 ** (retry_count - 1))


@lru_cache(maxsize=1)
def get_retry_policy() -> RetryPolicy:
    config_path = Path(__file__).resolve().parents[3] / "configs" / "retry_policy.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["ai_internal_retry"]
    names = config.get("retry_on_exceptions", [])
    policy = RetryPolicy(
        enabled=bool(config.get("enabled", False)),
        max_retry_count=int(config["max_retry_count"]),
        backoff_factor_seconds=float(config["backoff_factor"]),
        retryable_exception_names=frozenset(str(name) for name in names),
    )
    if not policy.enabled:
        raise ValueError("AI 내부 재시도는 Runtime에서 활성화되어야 합니다.")
    if policy.max_retry_count != 1:
        raise ValueError("AI 내부 최대 재시도는 계약값 1회여야 합니다.")
    if not 0.0 <= policy.backoff_factor_seconds < 5.0:
        raise ValueError("AI 내부 재시도 Backoff는 0초 이상 5초 미만이어야 합니다.")
    if not policy.retryable_exception_names:
        raise ValueError("AI 내부 재시도 대상 예외가 비어 있습니다.")
    return policy
