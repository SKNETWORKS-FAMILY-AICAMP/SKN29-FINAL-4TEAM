"""Inquiry Domain을 AI 증상 분석 요청 계약으로 변환한다."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist

from integrations.ai.exceptions import AIRequestValidationError
from integrations.ai.schema_validator import AIContractValidator


DECLINED_ANSWER_TEXT = "명시적 답변 거절"


def build_symptom_analysis_request(
    *,
    inquiry_id: UUID | str,
    correlation_id: UUID | str,
    ai_request_id: UUID | str,
    state_version: int,
    raw_symptom: str,
    model_code: str,
    selected_symptoms: Iterable[str] = (),
    previous_answers: Iterable[Mapping[str, Any]] = (),
    validator: AIContractValidator | None = None,
) -> dict[str, Any]:
    """순수 입력값을 Canonical AI 요청 Payload로 만든다."""

    payload = {
        "inquiry_id": _canonical_uuid(inquiry_id, "inquiry_id"),
        "correlation_id": _canonical_uuid(
            correlation_id,
            "correlation_id",
        ),
        "ai_request_id": _required_text(
            ai_request_id,
            "ai_request_id",
            max_length=100,
        ),
        "state_version": _positive_int(state_version, "state_version"),
        "raw_symptom": _required_text(
            raw_symptom,
            "raw_symptom",
            max_length=4000,
            preserve_original=True,
        ),
        "model_code": _required_text(
            model_code,
            "model_code",
            max_length=100,
        ),
        "selected_symptoms": _selected_symptoms(selected_symptoms),
        "previous_answers": _previous_answers(previous_answers),
    }
    (validator or AIContractValidator()).validate_request(payload)
    return payload


def build_request_from_inquiry(
    inquiry: Any,
    *,
    correlation_id: UUID | str,
    ai_request_id: UUID | str,
    validator: AIContractValidator | None = None,
) -> dict[str, Any]:
    """관련 객체가 로드된 Inquiry에서 저장된 값만 읽어 요청한다."""

    selected_symptoms: list[str] = []
    try:
        representative = inquiry.representative_symptom
    except ObjectDoesNotExist:
        representative = None
    if representative is not None:
        selected_symptoms.append(representative.symptom_type_code)

    previous_answers = []
    for qa in inquiry.qa_entries.filter(
        answered_at__isnull=False,
    ).order_by("sequence_no"):
        answer_text = (qa.answer_text or "").strip()
        if not answer_text and isinstance(qa.answer_payload, dict):
            if qa.answer_payload.get("refused") is True:
                answer_text = DECLINED_ANSWER_TEXT
        if not answer_text:
            continue
        previous_answers.append(
            {
                "question_id": qa.question_code or str(qa.public_id),
                "answer_text": answer_text,
            }
        )

    return build_symptom_analysis_request(
        inquiry_id=inquiry.public_id,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        state_version=inquiry.state_version,
        raw_symptom=inquiry.raw_text,
        model_code=inquiry.subscription.product_model.model_code,
        selected_symptoms=selected_symptoms,
        previous_answers=previous_answers,
        validator=validator,
    )


def _canonical_uuid(value: UUID | str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AIRequestValidationError(
            f"{field}는 UUID여야 합니다.",
            validation_errors=[f"{field}: invalid UUID"],
        ) from exc


def _required_text(
    value: Any,
    field: str,
    *,
    max_length: int,
    preserve_original: bool = False,
) -> str:
    text = str(value) if value is not None else ""
    if not text.strip() or len(text) > max_length:
        raise AIRequestValidationError(
            f"{field} 값이 허용 범위를 벗어났습니다.",
            validation_errors=[f"{field}: required, max {max_length}"],
        )
    return text if preserve_original else text.strip()


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AIRequestValidationError(
            f"{field}는 1 이상의 정수여야 합니다.",
            validation_errors=[f"{field}: positive integer required"],
        )
    return value


def _selected_symptoms(values: Iterable[str]) -> list[str]:
    result = []
    for value in values:
        text = _required_text(
            value,
            "selected_symptoms[]",
            max_length=200,
        )
        if text not in result:
            result.append(text)
    return result


def _previous_answers(
    values: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    result = []
    seen = set()
    for value in values:
        question_id = _required_text(
            value.get("question_id"),
            "previous_answers.question_id",
            max_length=100,
        )
        answer_text = _required_text(
            value.get("answer_text"),
            "previous_answers.answer_text",
            max_length=1000,
        )
        if question_id in seen:
            raise AIRequestValidationError(
                "같은 추가 질문 답변을 중복 전송할 수 없습니다.",
                validation_errors=[
                    f"previous_answers: duplicate {question_id}"
                ],
            )
        seen.add(question_id)
        result.append(
            {"question_id": question_id, "answer_text": answer_text}
        )
    return result
