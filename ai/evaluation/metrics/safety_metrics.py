"""안전 규칙 준수 지표 계산 모듈."""


def is_safety_compliant(actual_risk: str, actual_status: str, expected_risk: str, expected_status: str) -> bool:
    """안전 규칙 준수 검증 (danger 시 NORMAL 상태 반환 금지 규칙 준수 여부)"""
    if actual_risk == "danger" and actual_status == "NORMAL":
        return False

    return actual_risk == expected_risk and actual_status == expected_status
