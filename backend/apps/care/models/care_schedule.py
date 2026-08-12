"""T-020 다음 케어 계산용 비영속 계약 객체."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import models


class CareScheduleBasis(models.TextChoices):
    OFFICIAL = "OFFICIAL", "공식 운영 기준"
    TEAM_RULE = "TEAM_RULE", "승인된 팀 규칙"


class CareScheduleStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "계산 완료"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED", "확인 필요"


@dataclass(frozen=True)
class CareCycleRule:
    """호출자가 출처와 함께 전달하는 승인된 관리 주기."""

    care_type_code: str
    interval_months: int
    basis: str
    source_reference: str
    source_version: str

    def __post_init__(self) -> None:
        if not 1 <= self.interval_months <= 120:
            raise ValueError("interval_months must be between 1 and 120")
        if self.basis not in CareScheduleBasis.values:
            raise ValueError("basis must be OFFICIAL or TEAM_RULE")
        if not self.care_type_code.strip():
            raise ValueError("care_type_code is required")
        if not self.source_reference.strip():
            raise ValueError("source_reference is required")
        if not self.source_version.strip():
            raise ValueError("source_version is required")


@dataclass(frozen=True)
class NextCareSchedule:
    status: str
    next_care_on: date | None
    basis: str | None
    base_on: date
    care_type_code: str | None
    source_reference: str | None
    source_version: str | None
