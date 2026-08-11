"""Accounts App 설정."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """사용자·인증·권한 도메인의 Django App 경계."""

    name = "apps.accounts"
    label = "accounts"

    def ready(self) -> None:
        # Register fixed-group M2M guards after Django's app registry is ready.
        from apps.accounts import account_admin_guards  # noqa: F401

    verbose_name = "사용자 및 권한"
