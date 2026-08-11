"""합성 사용자 로그인과 JWT 수명주기 Service."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import (
    AuthenticationFailed,
    PermissionDenied,
)
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import (
    datetime_from_epoch,
    datetime_to_epoch,
)

from apps.accounts.models import User
from apps.accounts.repositories.account_repository import (
    AccountRepository,
)
from common.authentication.claims import (
    AUTH_VERSION_CLAIM,
    ROLE_CLAIM,
    SUBJECT_CLAIM,
    required_claim,
    required_positive_int_claim,
)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


class AuthenticationService:
    """JWT 발급·rotation·revocation을 단일 경계에서 수행한다."""

    repository = AccountRepository

    @classmethod
    def demo_login(cls, demo_user_code: str) -> tuple[User, TokenPair]:
        code = str(demo_user_code).strip()
        if not settings.DEMO_LOGIN_ENABLED:
            raise PermissionDenied("가상 로그인이 비활성화되어 있습니다.")
        if (
            code not in settings.DEMO_LOGIN_CODES
            or not code.startswith(("DEMO-", "SYN-"))
        ):
            raise AuthenticationFailed(
                "허용되지 않은 합성 사용자입니다.",
                code="demo_user_not_allowed",
            )

        user = cls.repository.find_active_by_demo_code(code)
        if user is None:
            raise AuthenticationFailed(
                "활성 합성 사용자를 찾을 수 없습니다.",
                code="demo_user_not_found",
            )
        return user, cls.issue_pair(user)

    @classmethod
    @transaction.atomic
    def issue_pair(
        cls,
        user: User,
        *,
        refresh_absolute_exp: int | None = None,
    ) -> TokenPair:
        user = cls.repository.lock_active_by_pk(user.pk)
        if user is None:
            raise AuthenticationFailed(
                "비활성 사용자는 토큰을 발급받을 수 없습니다.",
                code="user_inactive",
            )
        refresh = RefreshToken.for_user(user)
        refresh[ROLE_CLAIM] = user.role_code
        refresh[AUTH_VERSION_CLAIM] = user.auth_version
        if refresh_absolute_exp is not None:
            current_epoch = datetime_to_epoch(refresh.current_time)
            if refresh_absolute_exp <= current_epoch:
                raise AuthenticationFailed(
                    "refresh token의 절대 만료시각이 지났습니다.",
                    code="refresh_token_expired",
                )
            refresh["exp"] = refresh_absolute_exp
            OutstandingToken.objects.filter(
                jti=str(refresh["jti"])
            ).update(
                token=str(refresh),
                expires_at=datetime_from_epoch(refresh_absolute_exp),
            )
        else:
            OutstandingToken.objects.filter(
                jti=str(refresh["jti"])
            ).update(token=str(refresh))
        access = refresh.access_token
        # SimpleJWT anchors the access expiry to the refresh creation time,
        # while its default access iat can cross into the next second.
        # Keep both claims on the same token-pair clock so the advertised
        # one-hour lifetime and the JWT claim lifetime remain identical.
        access.set_iat(at_time=refresh.current_time)
        return TokenPair(
            access_token=str(access),
            refresh_token=str(refresh),
            access_expires_in=int(access["exp"]) - int(access["iat"]),
            refresh_expires_in=max(
                0,
                int(refresh["exp"])
                - datetime_to_epoch(refresh.current_time),
            ),
        )

    @classmethod
    @transaction.atomic
    def refresh(cls, raw_refresh_token: str) -> tuple[User, TokenPair]:
        refresh = cls._validated_refresh(raw_refresh_token)
        user = cls._active_user_for_refresh(refresh)
        new_pair = cls.issue_pair(
            user,
            refresh_absolute_exp=int(refresh["exp"]),
        )
        cls._blacklist_refresh(refresh, user)
        return user, new_pair

    @classmethod
    @transaction.atomic
    def logout(cls, raw_refresh_token: str) -> None:
        refresh = cls._validated_refresh(raw_refresh_token)
        user = cls._active_user_for_refresh(refresh)
        cls._blacklist_refresh(refresh, user)

    @staticmethod
    def _validated_refresh(raw_refresh_token: str) -> RefreshToken:
        try:
            return RefreshToken(str(raw_refresh_token).strip())
        except (TokenError, ValueError, TypeError) as exc:
            raise AuthenticationFailed(
                "유효하지 않거나 만료·폐기된 refresh token입니다.",
                code="refresh_token_invalid",
            ) from exc

    @classmethod
    def _active_user_for_refresh(
        cls,
        refresh: RefreshToken,
    ) -> User:
        try:
            user_id = required_claim(refresh, SUBJECT_CLAIM)
            token_role = required_claim(refresh, ROLE_CLAIM)
            token_auth_version = required_positive_int_claim(
                refresh,
                AUTH_VERSION_CLAIM,
            )
        except ValueError as exc:
            raise AuthenticationFailed(
                "refresh token 필수 정보가 없습니다.",
                code="refresh_claim_missing",
            ) from exc

        user = cls.repository.lock_active_by_subject(user_id)
        if (
            user is None
            or user.role_code != token_role
            or user.auth_version != token_auth_version
        ):
            raise AuthenticationFailed(
                "사용자 상태 또는 역할이 변경되었습니다.",
                code="user_state_changed",
            )
        return user

    @staticmethod
    def _blacklist_refresh(refresh: RefreshToken, user: User) -> None:
        """검증된 공개 UUID subject의 refresh token을 jti 기준으로 폐기한다."""
        outstanding, _ = OutstandingToken.objects.get_or_create(
            jti=str(refresh["jti"]),
            defaults={
                "user": user,
                "token": str(refresh),
                "created_at": datetime_from_epoch(int(refresh["iat"])),
                "expires_at": datetime_from_epoch(int(refresh["exp"])),
            },
        )
        BlacklistedToken.objects.get_or_create(token=outstanding)
