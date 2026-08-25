"""인증 요청과 현재 사용자 응답 Serializer."""

import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class DemoLoginRequestSerializer(serializers.Serializer):
    demo_user_code = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )


class RefreshTokenRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(trim_whitespace=True)


class AuthenticatedUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField(max_length=100)
    role_code = serializers.ChoiceField(
        choices=[
            "CUSTOMER",
            "CONSULTANT",
            "TECHNICIAN",
            "OPERATOR",
        ]
    )
    is_active = serializers.BooleanField()
    customer_profile = serializers.DictField(allow_null=True)
    allowed_actions = serializers.ListField(
        child=serializers.CharField(),
    )


class P1ChallengeRequestSerializer(serializers.Serializer):
    """동결 Mobile 식별자와 향후 이름·이메일 식별자를 함께 받는다."""

    customer_number = serializers.CharField(
        max_length=40,
        required=False,
        trim_whitespace=True,
    )
    contract_number = serializers.CharField(
        max_length=50,
        required=False,
        trim_whitespace=True,
    )
    name = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    email = serializers.EmailField(
        max_length=254,
        required=False,
    )
    username = serializers.CharField(
        max_length=150,
        required=False,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        contract_values = bool(
            attrs.get("customer_number") or attrs.get("contract_number")
        )
        email_values = bool(attrs.get("name") or attrs.get("email"))
        if contract_values == email_values:
            raise serializers.ValidationError(
                "고객번호·계약번호 또는 이름·이메일 중 한 쌍을 입력해 주세요."
            )
        if contract_values and not (
            attrs.get("customer_number") and attrs.get("contract_number")
        ):
            raise serializers.ValidationError(
                "고객번호와 계약번호를 모두 입력해 주세요."
            )
        if email_values and not (attrs.get("name") and attrs.get("email")):
            raise serializers.ValidationError(
                "이름과 이메일을 모두 입력해 주세요."
            )
        purpose = self.context.get("purpose")
        if (
            email_values
            and purpose == "PASSWORD_RESET"
            and not attrs.get("username")
        ):
            raise serializers.ValidationError(
                {"username": "비밀번호 재설정에는 아이디가 필요합니다."}
            )
        if attrs.get("username") and not (
            email_values and purpose == "PASSWORD_RESET"
        ):
            raise serializers.ValidationError(
                {"username": "이 단계에서는 아이디를 보내지 않습니다."}
            )
        return attrs


class P1OtpVerificationRequestSerializer(serializers.Serializer):
    otp_code = serializers.RegexField(
        regex=r"^[0-9]{6}$",
        min_length=6,
        max_length=6,
        trim_whitespace=False,
        write_only=True,
    )


class P1ConsentSerializer(serializers.Serializer):
    code = serializers.ChoiceField(
        choices=[
            "TERMS_OF_SERVICE",
            "PRIVACY_COLLECTION_USE",
            "MARKETING",
        ]
    )
    version = serializers.CharField(max_length=40, trim_whitespace=True)
    agreed = serializers.BooleanField()


def _validate_p1_password(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
        raise serializers.ValidationError(
            "비밀번호에는 영문과 숫자가 각각 1자 이상 필요합니다."
        )
    try:
        validate_password(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class P1SignupRequestSerializer(serializers.Serializer):
    claim_ticket = serializers.CharField(
        min_length=32,
        max_length=256,
        trim_whitespace=True,
        write_only=True,
    )
    name = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    email = serializers.EmailField(
        max_length=254,
        required=False,
    )
    username = serializers.RegexField(
        regex=r"^[A-Za-z0-9._-]+$",
        min_length=4,
        max_length=150,
        trim_whitespace=True,
    )
    password = serializers.CharField(
        min_length=12,
        max_length=64,
        trim_whitespace=False,
        write_only=True,
        validators=[_validate_p1_password],
    )
    consents = P1ConsentSerializer(many=True, min_length=2)

    def validate(self, attrs):
        if bool(attrs.get("name")) != bool(attrs.get("email")):
            raise serializers.ValidationError(
                "이름과 이메일은 함께 입력해 주세요."
            )
        return attrs

    def validate_consents(self, value):
        codes = [item["code"] for item in value]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("동일한 동의를 중복 제출할 수 없습니다.")
        agreed = {item["code"] for item in value if item["agreed"]}
        required = {"TERMS_OF_SERVICE", "PRIVACY_COLLECTION_USE"}
        if not required.issubset(agreed):
            raise serializers.ValidationError(
                "이용약관과 개인정보 수집 이용 동의가 필요합니다."
            )
        return value


class P1PasswordLoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(
        min_length=1,
        max_length=150,
        trim_whitespace=True,
    )
    password = serializers.CharField(
        min_length=1,
        max_length=64,
        trim_whitespace=False,
        write_only=True,
    )


class P1PasswordResetConfirmRequestSerializer(serializers.Serializer):
    reset_ticket = serializers.CharField(
        min_length=32,
        max_length=256,
        trim_whitespace=True,
        write_only=True,
    )
    password = serializers.CharField(
        min_length=12,
        max_length=64,
        trim_whitespace=False,
        write_only=True,
        validators=[_validate_p1_password],
    )
