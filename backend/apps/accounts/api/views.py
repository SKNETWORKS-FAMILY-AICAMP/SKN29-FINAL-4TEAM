"""로그인·토큰·현재 사용자 조회 Controller."""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
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

    @extend_schema(
        operation_id="demoLogin",
        summary="상담사 Demo 계정으로 로그인",
        description=(
            "Swagger 검증용 Demo 계정 로그인을 수행합니다. "
            "응답의 access_token을 상단 Authorize 버튼에 입력하세요."
        ),
        tags=["Auth"],
        auth=[],
        request=DemoLoginRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Demo JWT access_token과 사용자 정보를 반환합니다.",
            ),
        },
        examples=[
            OpenApiExample(
                "상담사 Demo 로그인",
                value={"demo_user_code": "DEMO-CONSULTANT-001"},
                request_only=True,
            ),
        ],
    )
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
