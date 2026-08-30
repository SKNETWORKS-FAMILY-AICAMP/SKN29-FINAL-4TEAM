#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TEST_PATH = "ai/tests/unit/test_runtime_flow_regressions_20260831.py"

TEST_CONTENT = r'''from types import SimpleNamespace

import pytest

from ai.app.retrieval.filters import evidence_topic_filter as topic_filter_module
from ai.app.retrieval.filters.evidence_topic_filter import EvidenceTopicFilter
from ai.app.schemas import MissingField
from ai.app.structuring.followup_question_generator import FollowUpQuestionGenerator
from ai.app.structuring.llm_contracts import FollowUpWording
from ai.app.structuring.symptom_normalizer import SymptomNormalizer


def test_occurrence_condition_wording_cannot_turn_into_start_time_question():
    generator = FollowUpQuestionGenerator()
    fallback = generator._fixed_questions(
        [
            MissingField(
                field_name="occurrence_condition",
                reason="발생 조건 확인",
                importance="medium",
            )
        ]
    )

    with pytest.raises(ValueError):
        generator._apply_wording(
            fallback,
            [
                FollowUpWording(
                    target_field="occurrence_condition",
                    question_text="증상이 어제부터 발생했나요?",
                )
            ],
        )


def test_occurrence_condition_wording_accepts_condition_question():
    generator = FollowUpQuestionGenerator()
    fallback = generator._fixed_questions(
        [
            MissingField(
                field_name="occurrence_condition",
                reason="발생 조건 확인",
                importance="medium",
            )
        ]
    )

    result = generator._apply_wording(
        fallback,
        [
            FollowUpWording(
                target_field="occurrence_condition",
                question_text="증상이 항상 발생하나요, 아니면 특정 조건에서 발생하나요?",
            )
        ],
    )

    assert result[0].target_field == "occurrence_condition"
    assert result[0].question_text.startswith("증상이 항상")


def test_low_flow_normalizer_understands_jal_an_nawaeyo():
    normalizer = SymptomNormalizer()

    assert (
        normalizer.normalize_symptom_type(
            "어제부터 냉수가 잘 안 나와요",
            [],
        )
        == "출수량 저하"
    )


def test_low_flow_topic_filter_rejects_cold_temperature_chunk(monkeypatch):
    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )
    low_flow = SimpleNamespace(
        chunk_id="LOW",
        topic_code="symptom_low_flow",
    )
    cold_temperature = SimpleNamespace(
        chunk_id="COLD",
        topic_code="symptom_cold_temperature",
    )

    filtered = EvidenceTopicFilter().filter_chunks(
        [cold_temperature, low_flow],
        symptom_type="출수량 저하",
        target_water_type="냉수",
    )

    assert filtered == [low_flow]


def test_temperature_topic_uses_target_water_type(monkeypatch):
    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )
    cold_temperature = SimpleNamespace(
        chunk_id="COLD",
        topic_code="symptom_cold_temperature",
    )
    hot_temperature = SimpleNamespace(
        chunk_id="HOT",
        topic_code="symptom_hot_water_safety",
    )

    cold = EvidenceTopicFilter().filter_chunks(
        [hot_temperature, cold_temperature],
        symptom_type="온도 이상",
        target_water_type="냉수",
    )
    hot = EvidenceTopicFilter().filter_chunks(
        [cold_temperature, hot_temperature],
        symptom_type="온도 이상",
        target_water_type="온수",
    )

    assert cold == [cold_temperature]
    assert hot == [hot_temperature]
'''


PATCHES: dict[str, list[tuple[str, str]]] = {
    "ai/app/structuring/followup_question_generator.py": [
        (
r'''_PRIVATE_QUESTION_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
    re.compile(r"https?://\S+", flags=re.IGNORECASE),
)
''',
r'''_PRIVATE_QUESTION_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
    re.compile(r"https?://\S+", flags=re.IGNORECASE),
)

_QUESTION_SEMANTIC_RULES = {
    "occurrence_time": {
        "required_any": ("언제", "시작", "부터"),
        "forbidden": ("조건", "항상", "간헐", "버튼", "사용 중", "이유", "원인"),
    },
    "target_water_type": {
        "required_any": ("출수", "냉수", "온수", "정수", "물"),
        "forbidden": ("이유", "원인", "언제부터"),
    },
    "occurrence_condition": {
        "required_any": ("조건", "항상", "간헐", "경우", "때", "중"),
        "forbidden": ("부터", "시작", "이유", "원인"),
    },
    "actions_taken": {
        "required_any": ("조치", "확인", "해보", "해 보", "시도", "취하"),
        "forbidden": ("이유", "원인", "언제부터"),
    },
}
'''
        ),
        (
r'''            if (
                len(question_text) > 200
                or "\n" in question_text
                or not question_text.endswith(("?", "？"))
                or any(pattern.search(question_text) for pattern in _PRIVATE_QUESTION_PATTERNS)
            ):
                raise ValueError("Follow-up 질문 문구 형식이 올바르지 않습니다.")
            result.append(
''',
r'''            if (
                len(question_text) > 200
                or "\n" in question_text
                or not question_text.endswith(("?", "？"))
                or any(pattern.search(question_text) for pattern in _PRIVATE_QUESTION_PATTERNS)
                or not FollowUpQuestionGenerator._question_matches_target_field(
                    fixed.target_field,
                    question_text,
                )
            ):
                raise ValueError("Follow-up 질문 문구 형식 또는 의미가 target_field와 일치하지 않습니다.")
            result.append(
'''
        ),
        (
r'''        return result

    @staticmethod
    def _fallback_reason(exc: Exception) -> str:
''',
r'''        return result

    @staticmethod
    def _question_matches_target_field(
        target_field: str,
        question_text: str,
    ) -> bool:
        rule = _QUESTION_SEMANTIC_RULES.get(target_field)
        if rule is None:
            return False
        compact = " ".join(question_text.split())
        if any(token in compact for token in rule["forbidden"]):
            return False
        return any(token in compact for token in rule["required_any"])

    @staticmethod
    def _fallback_reason(exc: Exception) -> str:
'''
        ),
    ],
    "ai/prompts/followup_question/v1/system.txt": [
        (
r'''당신은 SK Watercare 정수기 상담의 후속 질문 문구를 작성하는 AI입니다.
질문 대상 필드는 이미 결정되었으므로 추가·삭제·변경하지 마십시오.
각 target_field를 정확히 한 번 사용하고, 현재 구조화 증상 맥락을 반영한 짧고 자연스러운 한국어 질문을 작성하십시오.
진단, 안전 판정, 해결 방법, 상태 전환을 제안하지 말고 질문 문구만 반환하십시오.
각 question_text는 한 줄이며 물음표로 끝나야 합니다.''',
r'''당신은 SK Watercare 정수기 상담의 후속 질문 문구를 작성하는 AI입니다.
질문 대상 필드는 이미 결정되었으므로 추가·삭제·변경하지 마십시오.
각 target_field를 정확히 한 번 사용하고, 현재 구조화 증상 맥락을 반영한 짧고 자연스러운 한국어 질문을 작성하십시오.

target_field의 의미를 절대 바꾸지 마십시오.
- occurrence_time: 증상이 시작된 시점만 묻습니다. 예: "증상은 언제부터 시작됐나요?"
- target_water_type: 냉수·온수·정수·전체 중 어떤 출수에서 발생하는지만 묻습니다.
- occurrence_condition: 항상/간헐적/출수 버튼 사용/특정 기능 사용 등 발생 조건이나 반복 양상만 묻습니다. 시작 시점, 원인, 이유를 묻지 마십시오.
- actions_taken: 고객이 이미 확인하거나 시도한 조치가 있는지만 묻습니다.

질문 문구는 해당 필드에 준비된 선택지로 자연스럽게 답할 수 있어야 합니다.
진단, 안전 판정, 해결 방법, 상태 전환을 제안하지 말고 질문 문구만 반환하십시오.
각 question_text는 한 줄이며 물음표로 끝나야 합니다.'''
        ),
    ],
    "ai/app/orchestration/pipelines/multi_agent_pipeline.py": [
        (
r'''        if symptom_output.safety_assessment.risk_level == RiskLevel.DANGER:
            shared.handoff(AgentRole.CARE_DECISION, HandoffReason.DANGER_PRIORITY)
            care_agent.run(ctx)
        elif EvidenceApplicabilityGate().requires_more_information(
''',
r'''        if symptom_output.safety_assessment.risk_level == RiskLevel.DANGER:
            shared.handoff(AgentRole.CARE_DECISION, HandoffReason.DANGER_PRIORITY)
            care_agent.run(ctx)
        elif symptom_output.clarification_needed:
            shared.awaiting_customer_input = True
            shared.handoff(
                AgentRole.CARE_DECISION,
                HandoffReason.CUSTOMER_INPUT_PENDING,
            )
            care_agent.run(ctx, awaiting_customer_input=True)
        elif EvidenceApplicabilityGate().requires_more_information(
'''
        ),
    ],
    "ai/app/retrieval/filters/evidence_topic_filter.py": [
        (
r'''    _TOPIC_BY_SYMPTOM_TYPE = {
        "물맛/냄새 이상": "symptom_taste_odor",
    }
''',
r'''    _TOPIC_BY_SYMPTOM_TYPE = {
        "제품 누수": "symptom_leak",
        "출수량 저하": "symptom_low_flow",
        "물맛/냄새 이상": "symptom_taste_odor",
        "소음 이상": "symptom_noise",
    }
    _TEMPERATURE_TOPIC_BY_WATER_TYPE = {
        "냉수": "symptom_cold_temperature",
        "온수": "symptom_hot_water_safety",
    }
'''
        ),
        (
r'''    def filter_chunks(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        symptom_type: str | None,
    ) -> list[RetrievedChunk]:
        candidates = list(chunks)
        expected_topic = self._TOPIC_BY_SYMPTOM_TYPE.get(symptom_type or "")
        if expected_topic is None:
            return candidates
''',
r'''    def filter_chunks(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        symptom_type: str | None,
        target_water_type: str | None = None,
    ) -> list[RetrievedChunk]:
        candidates = list(chunks)
        expected_topic = self._expected_topic(
            symptom_type=symptom_type,
            target_water_type=target_water_type,
        )
        if expected_topic is None:
            return candidates
'''
        ),
        (
r'''        return [
            chunk
            for chunk in candidates
            if (chunk.topic_code or canonical_topics.get(chunk.chunk_id))
            == expected_topic
        ]
''',
r'''        return [
            chunk
            for chunk in candidates
            if (chunk.topic_code or canonical_topics.get(chunk.chunk_id))
            == expected_topic
        ]

    @classmethod
    def _expected_topic(
        cls,
        *,
        symptom_type: str | None,
        target_water_type: str | None,
    ) -> str | None:
        if symptom_type == "온도 이상":
            return cls._TEMPERATURE_TOPIC_BY_WATER_TYPE.get(
                target_water_type or ""
            )
        return cls._TOPIC_BY_SYMPTOM_TYPE.get(symptom_type or "")
'''
        ),
    ],
    "ai/app/orchestration/stages/retrieval_stage.py": [
        (
r'''            chunks = EvidenceTopicFilter().filter_chunks(
                chunks,
                symptom_type=(
                    ctx.structured_symptom.symptom_type
                    if ctx.structured_symptom is not None
                    else None
                ),
            )
''',
r'''            chunks = EvidenceTopicFilter().filter_chunks(
                chunks,
                symptom_type=(
                    ctx.structured_symptom.symptom_type
                    if ctx.structured_symptom is not None
                    else None
                ),
                target_water_type=(
                    ctx.structured_symptom.target_water_type
                    if ctx.structured_symptom is not None
                    else None
                ),
            )
'''
        ),
    ],
    "ai/app/structuring/symptom_normalizer.py": [
        (
r'''            ("졸졸", "쫄쫄", "출수량", "출수양", "물이 안 나", "물 안 나", "수압"),
''',
r'''            (
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
'''
        ),
    ],
    "mobile/customer-app/src/main/java/com/skn29/watercare/customer/feature/customer/guidance/FollowUpQuestionsSection.kt": [
        (
r'''        is FollowUpUiState.Empty -> Unit
''',
r'''        is FollowUpUiState.Empty -> {
            if (
                state.snapshot.statusCode
                    .trim()
                    .uppercase() ==
                "QUESTIONNAIRE_IN_PROGRESS"
            ) {
                SectionCard("답변을 분석하고 있어요") {
                    LiquidGlassPill("AI 분석 중")
                    Text(
                        "추가 답변을 반영해 맞춤 해결 안내를 준비하고 있습니다. 잠시만 기다려 주세요.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
'''
        ),
    ],
}


def _read_normalized(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def _encode(text: str, newline: str) -> bytes:
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def _prepare(root: Path) -> tuple[dict[Path, tuple[str, str]], list[str]]:
    prepared: dict[Path, tuple[str, str]] = {}
    errors: list[str] = []

    for rel, replacements in PATCHES.items():
        path = root / rel
        if not path.is_file():
            errors.append(f"[MISSING] {rel}")
            continue

        text, newline = _read_normalized(path)
        updated = text

        for index, (old, new) in enumerate(replacements, start=1):
            old = old.replace("\r\n", "\n")
            new = new.replace("\r\n", "\n")
            count = updated.count(old)
            if count != 1:
                errors.append(
                    f"[MISMATCH] {rel} replacement #{index}: "
                    f"expected 1 match, found {count}"
                )
                break
            updated = updated.replace(old, new, 1)

        prepared[path] = (updated, newline)

    test_path = root / TEST_PATH
    if test_path.exists():
        existing, newline = _read_normalized(test_path)
        if existing.strip() != TEST_CONTENT.strip():
            errors.append(f"[EXISTS_DIFFERENT] {TEST_PATH}")
        else:
            prepared[test_path] = (existing, newline)
    else:
        prepared[test_path] = (TEST_CONTENT, "\n")

    return prepared, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WaterBridge Follow-up/Routing/RAG/Mobile 통합 회귀 패치"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="SKN29-FINAL-4TEAM 저장소 루트. 기본값은 현재 디렉터리.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="수정 없이 preflight만 수행",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    prepared, errors = _prepare(root)

    if errors:
        print("적용 중단: 현재 파일이 ai/renew 확인본과 일치하지 않습니다.")
        for error in errors:
            print(error)
        print("어떤 파일도 수정하지 않았습니다.")
        return 2

    print("Preflight PASS")
    print("수정 대상:")
    for rel in PATCHES:
        print(f"  - {rel}")
    print("추가 테스트:")
    print(f"  - {TEST_PATH}")

    if args.check:
        print("CHECK ONLY: 실제 파일은 수정하지 않았습니다.")
        return 0

    for path, (updated, newline) in prepared.items():
        if path.as_posix().endswith(TEST_PATH) and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_encode(updated, newline))

    print("APPLIED: Runtime flow 패치 적용 완료.")
    print()
    print("1) AI 회귀 테스트:")
    print(
        r"ai\.venv\Scripts\python.exe -m pytest "
        r"ai\tests\unit\test_runtime_flow_regressions_20260831.py -q -p no:cacheprovider"
    )
    print()
    print("2) 기존 Guidance 회귀 테스트:")
    print(
        r"ai\.venv\Scripts\python.exe -m pytest "
        r"ai\tests\unit\test_llm_guidance.py -q -p no:cacheprovider"
    )
    print()
    print("3) Harness/Handoff/HITL 회귀:")
    print(
        r"ai\.venv\Scripts\python.exe -m pytest "
        r"ai\tests\unit\harness ai\tests\unit\handoff ai\tests\unit\hitl "
        r"-q -p no:cacheprovider"
    )
    print()
    print("4) Mobile compile:")
    print(r"cd mobile && gradlew.bat :customer-app:compileDebugKotlin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
