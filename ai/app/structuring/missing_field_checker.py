"""증상 분석에 필요한 필수 정보 누락 여부 검사."""

from ..schemas import MissingField, StructuredSymptom


class MissingFieldChecker:
    """이미 확인된 값은 제외하고 최소 추가 확인 항목만 반환한다."""

    _DEFAULT_FIELD_RULES = (
        ("occurrence_time", "증상이 시작된 시점을 확인하면 도움이 됩니다.", "medium"),
        ("target_water_type", "영향을 받는 출수 종류를 확인해야 합니다.", "medium"),
        ("occurrence_condition", "증상이 발생하는 조건이나 지속 여부를 확인해야 합니다.", "medium"),
    )
    _FIELD_RULES_BY_SYMPTOM = {
        "제품 누수": (),
        "전기 이상": (),
        "온도 이상": (
            ("occurrence_time", "증상이 시작된 시점을 확인하면 도움이 됩니다.", "medium"),
            ("target_water_type", "냉수 또는 온수 중 영향을 받는 출수를 확인해야 합니다.", "high"),
            ("occurrence_condition", "온도 이상이 지속되는 조건을 확인해야 합니다.", "medium"),
        ),
        "출수량 저하": (
            ("occurrence_time", "증상이 시작된 시점이 필요합니다.", "medium"),
            ("target_water_type", "출수량이 저하된 출수 종류를 확인해야 합니다.", "high"),
            ("occurrence_condition", "출수량이 저하되는 조건을 확인해야 합니다.", "medium"),
        ),
        "소음 이상": (
            ("occurrence_time", "소음이 시작된 시점을 확인해야 합니다.", "medium"),
            ("occurrence_condition", "소음이 발생하는 동작이나 조건을 확인해야 합니다.", "high"),
        ),
        "물맛/냄새 이상": (
            ("occurrence_time", "맛·냄새 이상이 시작된 시점을 확인해야 합니다.", "high"),
            ("target_water_type", "영향을 받는 출수 종류를 확인해야 합니다.", "medium"),
        ),
        "필터/관리 문의": (
            ("occurrence_time", "문의가 시작된 시점을 확인해야 합니다.", "medium"),
            ("occurrence_condition", "관리 문의의 발생 조건을 확인해야 합니다.", "medium"),
        ),
    }

    def check(self, symptom: StructuredSymptom) -> list[MissingField]:
        missing: list[MissingField] = []
        rules = self._FIELD_RULES_BY_SYMPTOM.get(
            symptom.symptom_type,
            self._DEFAULT_FIELD_RULES,
        )
        for field_name, reason, importance in rules:
            if getattr(symptom, field_name) in (None, ""):
                missing.append(MissingField(field_name=field_name, reason=reason, importance=importance))
        if not symptom.actions_taken and symptom.symptom_type not in {"제품 누수", "전기 이상"}:
            missing.append(
                MissingField(
                    field_name="actions_taken",
                    reason="이미 수행한 확인이나 조치가 있는지 확인해야 합니다.",
                    importance="low",
                )
            )
        return missing
