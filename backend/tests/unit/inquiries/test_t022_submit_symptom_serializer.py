"""Request boundary tests for the T-022 SUBMIT_SYMPTOM slice."""

import pytest

from apps.inquiries.api.serializers import SymptomSubmissionSerializer


@pytest.mark.parametrize("state_version", [1, 2, 999])
def test_serializer_accepts_positive_state_version_only(state_version):
    serializer = SymptomSubmissionSerializer(
        data={"state_version": state_version}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"state_version": state_version}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"state_version": 0},
        {"state_version": -1},
        {"state_version": "not-an-integer"},
    ],
)
def test_serializer_rejects_missing_or_invalid_state_version(payload):
    serializer = SymptomSubmissionSerializer(data=payload)

    assert serializer.is_valid() is False
    assert "state_version" in serializer.errors


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_text", "overwrite attempt"),
        ("representative_symptom_code", "LEAK"),
        ("attachments", []),
    ],
)
def test_serializer_rejects_fields_that_could_overwrite_saved_input(
    field,
    value,
):
    serializer = SymptomSubmissionSerializer(
        data={"state_version": 1, field: value}
    )

    assert serializer.is_valid() is False
    assert serializer.errors == {
        field: ["지원하지 않는 필드입니다."],
    }
