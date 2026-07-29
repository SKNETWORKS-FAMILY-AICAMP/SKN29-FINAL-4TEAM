"""Customer inquiry Django app configuration."""

from django.apps import AppConfig


class InquiriesConfig(AppConfig):
    """Runtime boundary for customer inquiry creation and lifecycle data."""

    name = "apps.inquiries"
    label = "inquiries"
    verbose_name = "Customer inquiries"
