"""문장 생성 및 Grounding 지표 모듈."""

from typing import List


def calculate_grounding_score(generated_text: str, evidence_texts: List[str]) -> float:
    """생성 텍스트의 근거 준수율 연산 (키워드 매칭 기반)"""
    if not evidence_texts:
        return 0.0

    combined_evidence = " ".join(evidence_texts)
    words = generated_text.split()
    if not words:
        return 1.0

    grounded_words = [w for w in words if w in combined_evidence]
    return len(grounded_words) / len(words)
