"""검증된 retry_policy.yaml을 HTTP Runtime에 강제하는 로더."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RuntimePolicy:
    overall_timeout_seconds: float
    backend_retry_count: int
    ai_internal_max_retry_count: int
    ai_internal_retry_enabled: bool = False


@lru_cache(maxsize=1)
def get_runtime_policy() -> RuntimePolicy:
    config_path = Path(__file__).resolve().parents[3] / "configs" / "retry_policy.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    policy = RuntimePolicy(
        overall_timeout_seconds=float(config["backend_integration"]["overall_timeout_seconds"]),
        backend_retry_count=int(config["backend_integration"]["backend_retry_count"]),
        ai_internal_max_retry_count=int(config["ai_internal_retry"]["max_retry_count"]),
        ai_internal_retry_enabled=bool(config["ai_internal_retry"].get("enabled", False)),
    )
    if policy.overall_timeout_seconds != 30.0:
        raise ValueError("AI 전체 Timeout은 계약값 30초여야 합니다.")
    if policy.backend_retry_count != 0:
        raise ValueError("Backend 자동 재시도는 계약값 0회여야 합니다.")
    if policy.ai_internal_max_retry_count != 1:
        raise ValueError("AI 내부 최대 재시도는 계약값 1회여야 합니다.")
    if policy.ai_internal_retry_enabled:
        raise ValueError("현재 Runtime에는 Retry Loop가 없으므로 enabled는 false여야 합니다.")
    return policy
