"""Field-visit domain Django app configuration."""

from django.apps import AppConfig


class VisitsConfig(AppConfig):
    """Runtime boundary for field-visit lifecycle persistence."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.visits"
    label = "visits"
    verbose_name = "Field service visits"
