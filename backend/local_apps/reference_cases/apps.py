"""Reference scenario application configuration."""

from django.apps import AppConfig


class ReferenceCasesConfig(AppConfig):
    """Register the isolated, reference-only scenario catalogue."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "local_apps.reference_cases"
    verbose_name = "AI reference cases"
