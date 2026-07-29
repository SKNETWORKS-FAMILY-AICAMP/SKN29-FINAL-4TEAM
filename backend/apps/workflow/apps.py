"""Workflow runtime Django app configuration."""

from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    """Persistence boundary for workflow idempotency and transition history."""

    name = "apps.workflow"
    label = "workflow"
    verbose_name = "Workflow runtime"
