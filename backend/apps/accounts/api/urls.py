"""인증 API URL."""

from django.urls import path

from apps.accounts.api.views import (
    ContractVerificationChallengeVerifyView,
    ContractVerificationChallengeView,
    DemoLoginView,
    LogoutView,
    MeView,
    P1PasswordLoginView,
    P1PasswordResetConfirmView,
    P1SignupView,
    PasswordResetChallengeVerifyView,
    PasswordResetChallengeView,
    TokenRefreshView,
    UsernameRecoveryChallengeVerifyView,
    UsernameRecoveryChallengeView,
)


urlpatterns = [
    path(
        "auth/contract-verification/challenges",
        ContractVerificationChallengeView.as_view(),
        name="contract-verification-challenge",
    ),
    path(
        "auth/contract-verification/challenges/<uuid:challenge_id>/verify",
        ContractVerificationChallengeVerifyView.as_view(),
        name="contract-verification-verify",
    ),
    path("auth/signup", P1SignupView.as_view(), name="p1-signup"),
    path("auth/login", P1PasswordLoginView.as_view(), name="p1-login"),
    path(
        "auth/account-recovery/username/challenges",
        UsernameRecoveryChallengeView.as_view(),
        name="username-recovery-challenge",
    ),
    path(
        "auth/account-recovery/username/challenges/"
        "<uuid:challenge_id>/verify",
        UsernameRecoveryChallengeVerifyView.as_view(),
        name="username-recovery-verify",
    ),
    path(
        "auth/password-reset/challenges",
        PasswordResetChallengeView.as_view(),
        name="password-reset-challenge",
    ),
    path(
        "auth/password-reset/challenges/<uuid:challenge_id>/verify",
        PasswordResetChallengeVerifyView.as_view(),
        name="password-reset-verify",
    ),
    path(
        "auth/password-reset/confirm",
        P1PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path(
        "auth/demo-login",
        DemoLoginView.as_view(),
        name="demo-login",
    ),
    path(
        "auth/refresh",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "auth/logout",
        LogoutView.as_view(),
        name="logout",
    ),
    path("me", MeView.as_view(), name="me"),
]
