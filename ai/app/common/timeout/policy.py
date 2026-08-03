"""파이프라인 단계별 Timeout 설정 로더."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class StageTimeoutPolicy:
    structuring_seconds: float
    safety_seconds: float
    retrieval_seconds: float
    generation_seconds: float
    validation_seconds: float

    def for_stage(self, stage: str) -> float:
        mapping = {
            "STRUCTURING": self.structuring_seconds,
            "CHECKING_MISSING_FIELDS": self.structuring_seconds,
            "SAFETY_CHECK": self.safety_seconds,
            "RETRIEVING": self.retrieval_seconds,
            "GENERATING": self.generation_seconds,
            "VALIDATING": self.validation_seconds,
        }
        try:
            return mapping[stage]
        except KeyError as exc:
            raise ValueError(f"단계별 Timeout이 정의되지 않았습니다: {stage}") from exc


@lru_cache(maxsize=1)
def get_stage_timeout_policy() -> StageTimeoutPolicy:
    config_path = Path(__file__).resolve().parents[3] / "configs" / "retry_policy.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["stage_timeouts"]
    policy = StageTimeoutPolicy(
        structuring_seconds=float(config["structuring_timeout_seconds"]),
        safety_seconds=float(config["safety_timeout_seconds"]),
        retrieval_seconds=float(config["retrieval_timeout_seconds"]),
        generation_seconds=float(config["generation_timeout_seconds"]),
        validation_seconds=float(config["validation_timeout_seconds"]),
    )
    if any(value <= 0 for value in policy.__dict__.values()):
        raise ValueError("모든 단계별 Timeout은 0보다 커야 합니다.")
    stage_budgets = (
        policy.structuring_seconds,
        policy.safety_seconds,
        policy.retrieval_seconds,
        policy.generation_seconds,
        policy.validation_seconds,
    )
    if max(stage_budgets) >= 30.0:
        raise ValueError("개별 단계 Timeout은 전체 30초 Timeout보다 작아야 합니다.")
    return policy
