"""Consultation domain Django app configuration."""

from django.apps import AppConfig


class ConsultationsConfig(AppConfig):
    """Runtime boundary for consultation lifecycle persistence."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.consultations"
    label = "consultations"
    verbose_name = "Customer consultations"
