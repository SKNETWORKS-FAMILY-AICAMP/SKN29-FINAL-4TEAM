"""제품 증상 문의와 명백한 비제품 문의를 결정적으로 구분한다."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..schemas import StructuredSymptom
from .symptom_normalizer import SymptomNormalizer


@dataclass(frozen=True, slots=True)
class ProductSymptomDomainDecision:
    relevance: str
    reason: str


class ProductSymptomDomainGuard:
    """제품 문맥 신호를 우선하고 명백한 외부 도메인만 차단한다."""

    _PRODUCT_CONTEXT = re.compile(
        r"정수기|냉수|온수|찬물|뜨거운\s*물|상온수|출수|수압|수전|"
        r"원수\s*밸브|필터|물맛|누수|기포|미세\s*입자|이물질|떠다|"
        r"버튼|표시창|화면|작동|전원|오류|소리|제품|"
        r"(?:^|\s)물(?:이|에서|에|을|맛)?(?:\s|$)"
    )
    _OFF_DOMAIN_CATEGORIES = (
        (
            "DELIVERY_OR_ORDER",
            re.compile(
                r"배달|배송|택배|주문|음식|"
                r"(?:시킨|주문한).{0,24}(?:안\s*왔|오지\s*않|도착하지\s*않)"
            ),
        ),
        (
            "WEATHER",
            re.compile(r"날씨|일기\s*예보|비가\s*(?:오|내리)|눈이\s*(?:오|내리)|미세먼지"),
        ),
        (
            "TRANSPORTATION",
            re.compile(r"버스|지하철|기차|항공|비행기|택시|교통"),
        ),
    )

    def evaluate(
        self,
        *,
        raw_symptom: str,
        selected_symptoms: list[str],
        structured_symptom: StructuredSymptom | None,
    ) -> ProductSymptomDomainDecision:
        if self._PRODUCT_CONTEXT.search(raw_symptom):
            return ProductSymptomDomainDecision("IN_DOMAIN", "PRODUCT_CONTEXT")

        for selected in selected_symptoms:
            canonical = SymptomNormalizer.canonical_selected_symptom(selected)
            if canonical not in {None, "기타 증상"}:
                return ProductSymptomDomainDecision(
                    "IN_DOMAIN",
                    "SELECTED_PRODUCT_SYMPTOM",
                )

        if (
            structured_symptom is not None
            and structured_symptom.symptom_type != "기타 증상"
        ):
            return ProductSymptomDomainDecision(
                "IN_DOMAIN",
                "STRUCTURED_PRODUCT_SYMPTOM",
            )

        for category, pattern in self._OFF_DOMAIN_CATEGORIES:
            if pattern.search(raw_symptom):
                return ProductSymptomDomainDecision("OFF_DOMAIN", category)

        substantive_length = len(re.sub(r"[^0-9A-Za-z가-힣]", "", raw_symptom))
        if substantive_length >= 8:
            return ProductSymptomDomainDecision(
                "OFF_DOMAIN",
                "NO_PRODUCT_SYMPTOM_SIGNAL",
            )

        # 제품 화면에서 들어온 짧고 모호한 입력을 곧바로 외부 도메인으로
        # 단정하지 않는다. 이후 공식 근거·추가질문 정책이 판단하게 한다.
        return ProductSymptomDomainDecision("UNDETERMINED", "NO_DECISIVE_SIGNAL")


__all__ = ["ProductSymptomDomainDecision", "ProductSymptomDomainGuard"]
