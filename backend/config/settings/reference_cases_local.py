"""Dedicated local PostgreSQL profile for reference scenario curation."""

from .local import *  # noqa: F403


INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,  # noqa: F405
    "local_apps.reference_cases.apps.ReferenceCasesConfig",
]
