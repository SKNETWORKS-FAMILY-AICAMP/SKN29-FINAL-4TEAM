"""증상 분석에 필요한 필수 정보 누락 여부 검사."""

from ..schemas import MissingField, StructuredSymptom


class MissingFieldChecker:
    """이미 확인된 값은 제외하고 최소 추가 확인 항목만 반환한다."""

    _FIELD_RULES = (
        ("occurrence_time", "증상이 시작된 시점이 필요합니다.", "high"),
        ("target_water_type", "영향을 받는 출수 종류를 확인해야 합니다.", "medium"),
        ("occurrence_condition", "증상이 발생하는 조건이나 지속 여부를 확인해야 합니다.", "medium"),
    )

    def check(self, symptom: StructuredSymptom) -> list[MissingField]:
        missing: list[MissingField] = []
        for field_name, reason, importance in self._FIELD_RULES:
            if getattr(symptom, field_name) in (None, ""):
                missing.append(MissingField(field_name=field_name, reason=reason, importance=importance))
        if not symptom.actions_taken:
            missing.append(
                MissingField(
                    field_name="actions_taken",
                    reason="이미 수행한 확인이나 조치가 있는지 확인해야 합니다.",
                    importance="low",
                )
            )
        return missing
