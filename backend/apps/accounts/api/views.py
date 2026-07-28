"""로그인·토큰·현재 사용자 조회 Controller."""

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.api.serializers import (
    DemoLoginRequestSerializer,
    RefreshTokenRequestSerializer,
)
from apps.accounts.services.account_service import AccountService
from apps.accounts.services.authentication_service import (
    AuthenticationService,
    TokenPair,
)
from common.api.response import success_response


def _session_data(user, pair: TokenPair) -> dict:
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "Bearer",
        "access_expires_in": pair.access_expires_in,
        "refresh_expires_in": pair.refresh_expires_in,
        "user": AccountService.user_data(user),
    }


class DemoLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DemoLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, pair = AuthenticationService.demo_login(
            serializer.validated_data["demo_user_code"]
        )
        return success_response(_session_data(user, pair))


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, pair = AuthenticationService.refresh(
            serializer.validated_data["refresh_token"]
        )
        return success_response(_session_data(user, pair))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthenticationService.logout(
            serializer.validated_data["refresh_token"]
        )
        return success_response({"revoked": True})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(AccountService.user_data(request.user))
