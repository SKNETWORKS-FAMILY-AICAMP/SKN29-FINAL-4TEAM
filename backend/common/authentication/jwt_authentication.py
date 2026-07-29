"""SimpleJWT 서명·만료 검증 뒤 DB 역할 원장을 재검증한다."""

from __future__ import annotations

from rest_framework_simplejwt.authentication import (
    JWTAuthentication as SimpleJWTAuthentication,
)
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from apps.accounts.repositories.account_repository import AccountRepository
from common.authentication.claims import (
    ROLE_CLAIM,
    SUBJECT_CLAIM,
    required_claim,
)


class JWTAuthentication(SimpleJWTAuthentication):
    """Claim의 역할이 현재 활성 사용자 원장과 다르면 인증을 거부한다."""

    def get_user(self, validated_token):
        try:
            subject = required_claim(validated_token, SUBJECT_CLAIM)
            token_role = required_claim(validated_token, ROLE_CLAIM)
        except ValueError as exc:
            raise AuthenticationFailed(
                "토큰 사용자 또는 역할 정보가 없습니다.",
                code="token_claim_missing",
            ) from exc

        user = AccountRepository.find_active_by_subject(subject)
        if user is None:
            raise AuthenticationFailed(
                "활성 사용자를 찾을 수 없습니다.",
                code="user_not_found",
            )
        if not user.is_active or token_role != user.role_code:
            raise AuthenticationFailed(
                "사용자 상태 또는 역할이 변경되었습니다.",
                code="user_state_changed",
            )
        return user
