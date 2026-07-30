"""Operations application configuration."""

from django.apps import AppConfig


class OperationsConfig(AppConfig):
    """Register import-ledger and operational support models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.operations"
    verbose_name = "Operations"
