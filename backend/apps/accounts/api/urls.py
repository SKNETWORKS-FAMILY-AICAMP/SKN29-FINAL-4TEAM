"""인증 API URL."""

from django.urls import path

from apps.accounts.api.views import (
    DemoLoginView,
    LogoutView,
    MeView,
    TokenRefreshView,
)


urlpatterns = [
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
