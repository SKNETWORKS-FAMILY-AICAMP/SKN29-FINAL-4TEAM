"""증상 필드 구조화 정확도 지표 모듈."""

from typing import Dict, Any


def calculate_structuring_accuracy(actual_symptom: Dict[str, Any], expected_symptom: Dict[str, Any]) -> float:
    """구조화 필드 일치 비율 연산"""
    if not expected_symptom:
        return 1.0

    match_count = 0
    total_keys = len(expected_symptom)

    for k, expected_v in expected_symptom.items():
        if actual_symptom.get(k) == expected_v:
            match_count += 1

    return match_count / total_keys if total_keys > 0 else 1.0
