"""SimpleJWT 서명·만료 검증 뒤 DB 역할 원장을 재검증한다."""

from __future__ import annotations

from rest_framework_simplejwt.authentication import (
    JWTAuthentication as SimpleJWTAuthentication,
)
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from common.authentication.claims import ROLE_CLAIM, required_claim


class JWTAuthentication(SimpleJWTAuthentication):
    """Claim의 역할이 현재 활성 사용자 원장과 다르면 인증을 거부한다."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        try:
            token_role = required_claim(validated_token, ROLE_CLAIM)
        except ValueError as exc:
            raise AuthenticationFailed(
                "토큰 역할 정보가 없습니다.",
                code="token_role_missing",
            ) from exc

        if not user.is_active or token_role != user.role_code:
            raise AuthenticationFailed(
                "사용자 상태 또는 역할이 변경되었습니다.",
                code="user_state_changed",
            )
        return user
