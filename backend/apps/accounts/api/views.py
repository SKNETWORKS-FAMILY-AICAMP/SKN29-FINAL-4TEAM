"""로그인·토큰·현재 사용자 조회 Controller."""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.api.serializers import (
    DemoLoginRequestSerializer,
    P1ChallengeRequestSerializer,
    P1OtpVerificationRequestSerializer,
    P1PasswordLoginRequestSerializer,
    P1PasswordResetConfirmRequestSerializer,
    P1SignupRequestSerializer,
    RefreshTokenRequestSerializer,
)
from apps.accounts.models import P1AuthOtpChallenge
from apps.accounts.services.account_service import AccountService
from apps.accounts.services.authentication_service import (
    AuthenticationService,
    TokenPair,
)
from apps.accounts.services.p1_auth_service import P1AuthService
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


def _idempotency_key(request) -> str:
    return request.headers.get("Idempotency-Key", "")


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


class P1ChallengeCreateView(APIView):
    permission_classes = [AllowAny]
    purpose = ""

    def post(self, request):
        serializer = P1ChallengeRequestSerializer(
            data=request.data,
            context={"purpose": self.purpose},
        )
        serializer.is_valid(raise_exception=True)
        data = P1AuthService.create_challenge(
            purpose=self.purpose,
            identity=dict(serializer.validated_data),
            idempotency_key=_idempotency_key(request),
        )
        return _no_store(success_response(data, status_code=202))


class ContractVerificationChallengeView(P1ChallengeCreateView):
    purpose = P1AuthOtpChallenge.Purpose.SIGNUP


class UsernameRecoveryChallengeView(P1ChallengeCreateView):
    purpose = P1AuthOtpChallenge.Purpose.USERNAME_RECOVERY


class PasswordResetChallengeView(P1ChallengeCreateView):
    purpose = P1AuthOtpChallenge.Purpose.PASSWORD_RESET


class P1OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    verify_method = None

    def post(self, request, challenge_id):
        serializer = P1OtpVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = self.verify_method(
            challenge_id=challenge_id,
            otp_code=serializer.validated_data["otp_code"],
        )
        return _no_store(success_response(data))


class ContractVerificationChallengeVerifyView(P1OtpVerifyView):
    verify_method = P1AuthService.verify_signup_challenge


class UsernameRecoveryChallengeVerifyView(P1OtpVerifyView):
    verify_method = P1AuthService.verify_username_challenge


class PasswordResetChallengeVerifyView(P1OtpVerifyView):
    verify_method = P1AuthService.verify_password_reset_challenge


class P1SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = P1SignupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = P1AuthService.signup(
            **serializer.validated_data,
            idempotency_key=_idempotency_key(request),
            correlation_id=request.correlation_id,
        )
        data = _session_data(result.user, result.pair)
        if result.idempotent_replay:
            data["idempotent_replay"] = True
        return _no_store(success_response(data, status_code=201))


class P1PasswordLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = P1PasswordLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, pair = P1AuthService.login(**serializer.validated_data)
        return _no_store(success_response(_session_data(user, pair)))


class P1PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = P1PasswordResetConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = P1AuthService.confirm_password_reset(
            **serializer.validated_data,
            idempotency_key=_idempotency_key(request),
            correlation_id=request.correlation_id,
        )
        return _no_store(success_response(data))
