"""인증 요청과 현재 사용자 응답 Serializer."""

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
