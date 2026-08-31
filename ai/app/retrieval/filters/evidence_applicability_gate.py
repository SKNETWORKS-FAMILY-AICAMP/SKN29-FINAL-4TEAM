"""조건부 공식 근거를 사용하기 전 필요한 문진·적용성 Gate."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
import unicodedata

from ...schemas import FollowUpQuestion
from ..models.retrieved_chunk import RetrievedChunk


class EvidenceApplicability(str, Enum):
    """고객 원문 대신 내부에서 사용하는 고정 근거 적용 조건."""

    ABSENCE_WITHIN_10_DAYS = "ABSENCE_WITHIN_10_DAYS"
    ABSENCE_OVER_10_DAYS = "ABSENCE_OVER_10_DAYS"
    LONG_UNUSED = "LONG_UNUSED"
    UNSUITABLE_INSTALLATION = "UNSUITABLE_INSTALLATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"

    @property
    def provider_label(self) -> str | None:
        """Provider에 전달 가능한 비식별 고정 요약을 반환한다."""

        return {
            self.ABSENCE_WITHIN_10_DAYS: "10일 이내 부재 후",
            self.ABSENCE_OVER_10_DAYS: "10일 이상 부재 후",
            self.LONG_UNUSED: "장시간 미사용 후",
            self.UNSUITABLE_INSTALLATION: "부적합 장소 설치 후",
            self.NOT_APPLICABLE: None,
            self.UNKNOWN: None,
        }[self]

    @property
    def questionnaire_label(self) -> str:
        """구조화 증상에 저장할 비식별 고정 문진 값을 반환한다."""

        return {
            self.NOT_APPLICABLE: "해당 없음",
            self.UNKNOWN: "확인 불가",
        }.get(self, self.provider_label or "확인 불가")


class EvidenceApplicabilityGate:
    """적용 조건이 필요한 증상은 문진 완료 전 검색·생성을 보류한다."""

    QUESTION_ID = "followup-taste-odor-applicability"
    TARGET_FIELD = "taste_odor_applicability"
    _TASTE_OR_ODOR_SYMPTOM = "물맛/냄새 이상"
    _ANSWER_OPTIONS = {
        "10일 이내 부재 후": EvidenceApplicability.ABSENCE_WITHIN_10_DAYS,
        "10일 이상 부재 후": EvidenceApplicability.ABSENCE_OVER_10_DAYS,
        "장시간 미사용 후": EvidenceApplicability.LONG_UNUSED,
        "부적합 장소 설치 후": EvidenceApplicability.UNSUITABLE_INSTALLATION,
        "해당 없음": EvidenceApplicability.NOT_APPLICABLE,
        "확인 불가": EvidenceApplicability.UNKNOWN,
    }
    _INTENTIONAL_NON_ANSWERS = {
        "답변하지 않음",
        "답변 거절",
        "모름",
        "모르겠음",
    }

    _REQUIRED_FIELDS_BY_SYMPTOM_TYPE = {
        "물맛/냄새 이상": frozenset(
            {
                "occurrence_time",
                "target_water_type",
                "actions_taken",
                "taste_odor_applicability",
            }
        ),
    }

    def requires_more_information(
        self,
        *,
        symptom_type: str | None,
        missing_field_names: Iterable[str],
        previous_answers: Iterable[dict[str, str]] = (),
    ) -> bool:
        required_fields = self._REQUIRED_FIELDS_BY_SYMPTOM_TYPE.get(
            symptom_type or "",
            frozenset(),
        )
        if required_fields.intersection(missing_field_names):
            return True
        return (
            symptom_type == self._TASTE_OR_ODOR_SYMPTOM
            and self.classify(previous_answers) is None
        )

    def followup_question(
        self,
        *,
        symptom_type: str | None,
        previous_answers: Iterable[dict[str, str]],
    ) -> FollowUpQuestion | None:
        """적용 조건이 확정되지 않았을 때 전용 질문을 반환한다."""

        if (
            symptom_type != self._TASTE_OR_ODOR_SYMPTOM
            or self.classify(previous_answers) is not None
        ):
            return None
        return FollowUpQuestion(
            question_id=self.QUESTION_ID,
            question_text=(
                "맛·냄새 이상이 장기 부재, 장시간 미사용 또는 설치 장소 문제 후 "
                "시작됐나요?"
            ),
            options=list(self._ANSWER_OPTIONS),
            target_field=self.TARGET_FIELD,
        )

    def classify(
        self,
        previous_answers: Iterable[dict[str, str]],
    ) -> EvidenceApplicability | None:
        """허용된 전용 문진 답변만 고정 적용 조건으로 정규화한다."""

        answers = list(previous_answers)
        for answer in reversed(answers):
            if (
                not isinstance(answer, dict)
                or answer.get("question_id") != self.QUESTION_ID
            ):
                continue
            answer_text = answer.get("answer_text")
            if not isinstance(answer_text, str):
                return None
            normalized = unicodedata.normalize(
                "NFC",
                answer_text,
            ).strip()
            if normalized in self._INTENTIONAL_NON_ANSWERS:
                return EvidenceApplicability.UNKNOWN
            return self._ANSWER_OPTIONS.get(normalized)
        return None

    def classify_for_symptom(
        self,
        *,
        symptom_type: str | None,
        previous_answers: Iterable[dict[str, str]],
    ) -> EvidenceApplicability | None:
        """다른 증상의 오래된 문진 답변이 재사용되지 않도록 증상 경계를 확인한다."""

        if symptom_type != self._TASTE_OR_ODOR_SYMPTOM:
            return None
        return self.classify(previous_answers)

    def filter_chunks(
        self,
        chunks: Iterable[RetrievedChunk],
        *,
        symptom_type: str | None,
        applicability: EvidenceApplicability | None,
    ) -> list[RetrievedChunk]:
        """조건이 확인된 경우에만 물맛·냄새 근거를 생성 경계로 전달한다."""

        candidates = list(chunks)
        if symptom_type != self._TASTE_OR_ODOR_SYMPTOM:
            return candidates
        if applicability in {
            EvidenceApplicability.ABSENCE_WITHIN_10_DAYS,
            EvidenceApplicability.ABSENCE_OVER_10_DAYS,
            EvidenceApplicability.LONG_UNUSED,
            EvidenceApplicability.UNSUITABLE_INSTALLATION,
        }:
            return candidates
        return []
