"""지연 시간 및 성능 지표 모듈."""

from typing import List


def calculate_average_latency(latencies_ms: List[float]) -> float:
    """평균 지연시간(ms) 연산"""
    if not latencies_ms:
        return 0.0
    return round(sum(latencies_ms) / len(latencies_ms), 2)
