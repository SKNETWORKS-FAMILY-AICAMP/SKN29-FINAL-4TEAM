"""공통코드 Model 값 검증."""

from django.core.exceptions import ValidationError


def validate_json_object(value: object) -> None:
    """확장속성은 JSON 최상위 object만 허용한다."""

    if not isinstance(value, dict):
        raise ValidationError(
            "metadata는 JSON object 형식이어야 합니다.",
            code="invalid_json_object",
        )
