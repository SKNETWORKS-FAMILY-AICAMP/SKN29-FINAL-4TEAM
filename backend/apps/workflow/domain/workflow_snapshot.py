"""상태 전이 계산에 필요한 현재 Aggregate Snapshot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    """DB를 변경하지 않는 순수 상태 전이 입력값."""

    inquiry_state: str | None
    state_version: int | None
    visit_status: str | None = None

    def __post_init__(self) -> None:
        if self.inquiry_state is None:
            if self.state_version is not None:
                raise ValueError(
                    "문의가 없으면 state_version도 없어야 합니다."
                )
        else:
            if (
                not isinstance(self.inquiry_state, str)
                or not self.inquiry_state.strip()
            ):
                raise ValueError("inquiry_state는 비어 있을 수 없습니다.")
            if (
                not isinstance(self.state_version, int)
                or isinstance(self.state_version, bool)
                or self.state_version < 1
            ):
                raise ValueError(
                    "기존 문의의 state_version은 1 이상이어야 합니다."
                )

        if self.visit_status is not None:
            if (
                not isinstance(self.visit_status, str)
                or not self.visit_status.strip()
            ):
                raise ValueError("visit_status는 비어 있을 수 없습니다.")
