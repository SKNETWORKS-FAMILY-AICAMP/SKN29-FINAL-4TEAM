"""Audit application configuration."""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Register append-only audit persistence models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    verbose_name = "Audit"
