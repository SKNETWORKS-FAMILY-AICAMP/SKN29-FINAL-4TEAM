"""다양한 증상 표현을 공개 계약의 표준 증상 값으로 정규화."""

from __future__ import annotations

import re


class SymptomNormalizer:
    """결정적인 규칙으로 대표 증상·출수 종류·시간 표현을 정규화한다."""

    _SELECTED_SYMPTOM_CODE_MAP = {
        "NO_WATER": "출수량 저하",
        "LOW_FLOW": "출수량 저하",
        "LEAK": "제품 누수",
        "ODOR": "물맛/냄새 이상",
        "TASTE": "물맛/냄새 이상",
        "TASTE_ODOR": "물맛/냄새 이상",
        "TEMPERATURE_ABNORMAL": "온도 이상",
        "NOISE": "소음 이상",
        "DISPLAY_ERROR": "기타 증상",
        "OTHER": "기타 증상",
    }

    @classmethod
    def canonical_selected_symptom(cls, value: str) -> str | None:
        """Backend 코드 또는 canonical label을 선택 증상 계약으로 변환한다."""

        mapped = cls._SELECTED_SYMPTOM_CODE_MAP.get(value.upper())
        if mapped is not None:
            return mapped
        canonical = {
            "제품 누수",
            "전기 이상",
            "온도 이상",
            "출수량 저하",
            "물맛/냄새 이상",
            "소음 이상",
            "필터/관리 문의",
            "기타 증상",
        }
        return value if value in canonical else None

    _SYMPTOM_RULES = (
        ("제품 누수", ("누수", "물이 새", "물 새", "바닥에 물", "젖어")),
        ("전기 이상", ("스파크", "탄 냄새", "타는 냄새", "연기", "전원선")),
        ("온도 이상", ("미지근", "안 차갑", "차갑지", "안 뜨겁", "뜨겁지", "온도", "덜 뜨거", "안 시원", "시원하지", "덜 시원")),
        (
            "출수량 저하",
            (
                "졸졸",
                "쫄쫄",
                "출수량",
                "출수양",
                "물이 안 나",
                "물 안 나",
                "잘 안 나",
                "안 나와",
                "적게 나",
                "약하게 나",
                "출수가 안",
                "수압",
            ),
        ),
        (
            "물맛/냄새 이상",
            (
                "물맛",
                "이상한 맛",
                "흙맛",
                "흙 맛",
                "흙냄새",
                "흙 냄새",
                "토양 냄새",
                "냄새",
                "비린",
                "역한",
            ),
        ),
        ("소음 이상", ("소음", "진동", "웅웅", "덜컹")),
        ("필터/관리 문의", ("필터", "교체 주기", "관리 주기")),
    )

    _WATER_RULES = (
        ("냉수", ("냉수", "찬물", "차가운 물")),
        ("온수", ("온수", "따뜻한 물", "뜨거운 물")),
        ("정수", ("정수", "상온수")),
    )

    _TIME_PATTERNS = (
        r"\d+\s*(?:분|시간|일|주|개월)\s*전(?:부터)?",
        r"(?:지난\s*(?:주말|주|달)|며칠\s*전)(?:부터)?",
        r"(?:오늘|어제|그제|방금|아까|최근|처음부터|설치 후|교체 후)(?:부터)?",
        r"(?:계속|항상|간헐적으로|가끔|때때로)",
    )

    _NEGATED_SYMPTOM_PATTERNS = (
        r"누수(?:는|가)?\s*(?:아니(?:에요|예요|고|라|며)?|없(?:어요|습니다|고)?)",
        r"물(?:이)?\s*(?:안\s*새|새지\s*않)",
        r"냄새(?:는|가)?\s*(?:안\s*나|없)",
    )

    def normalize_symptom_type(self, raw_text: str, selected_symptoms: list[str]) -> str:
        normalized_text = raw_text
        for pattern in self._NEGATED_SYMPTOM_PATTERNS:
            normalized_text = re.sub(pattern, " ", normalized_text)
        for normalized, keywords in self._SYMPTOM_RULES:
            if any(keyword in normalized_text for keyword in keywords):
                return normalized
        for selected in selected_symptoms:
            mapped = self.canonical_selected_symptom(selected)
            if mapped not in {None, "기타 증상"}:
                # A selected label cannot resurrect a symptom explicitly denied.
                if mapped == "제품 누수" and re.search(self._NEGATED_SYMPTOM_PATTERNS[0], raw_text):
                    continue
                return mapped
        return "기타 증상"

    def normalize_water_type(self, text: str) -> str | None:
        # A normally functioning water type is context, not the affected type.
        text = re.sub(
            r"(?:냉수|온수|정수|찬물|뜨거운 물|차가운 물)(?:는|은|가)?\s*"
            r"(?:정상(?:이에요|입니다|이고|인데|이지만)?|문제(?:는|가)?\s*없[가-힣]*)",
            " ", text,
        )
        found = []
        for normalized, keywords in self._WATER_RULES:
            matched = any(keyword in text for keyword in keywords)
            if normalized == "정수" and "정수" in text:
                matched = matched and re.search(r"정수(?!기)", text) is not None
            if matched:
                found.append(normalized)
        if len(found) > 1:
            return "전체"
        return found[0] if found else None

    def extract_occurrence_time(self, text: str) -> str | None:
        for pattern in self._TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def extract_occurrence_condition(text: str) -> str | None:
        markers = (
            ("출수 버튼을 누를 때", ("출수 버튼을 누르면", "버튼을 누르면")),
            ("사용할 때", ("사용할 때", "사용 중에", "사용 중")),
            ("출수할 때", ("출수할 때",)),
            ("작동할 때", ("작동할 때",)),
            ("특정 조건", ("동안", "경우")),
        )
        for canonical, phrases in markers:
            if any(phrase in text for phrase in phrases):
                return canonical
        return None

    @staticmethod
    def extract_error_code(text: str) -> str | None:
        match = re.search(
            r"(?<![A-Za-z0-9])(?:ERR|ER|E)[-_ ]?\d{1,4}(?!\d)",
            text,
            flags=re.IGNORECASE,
        )
        return match.group(0).upper().replace(" ", "") if match else None

    @staticmethod
    def extract_actions(text: str) -> list[str]:
        rules = (
            ("전원 재부팅", ("재부팅", "전원을 껐다", "전원 껐다")),
            ("원수 밸브 확인", ("밸브 확인", "원수 밸브")),
            ("필터 교체", ("필터를 교체", "필터 교체했")),
            ("청소", ("청소했", "닦아봤")),
        )
        return [label for label, keywords in rules if any(keyword in text for keyword in keywords)]
