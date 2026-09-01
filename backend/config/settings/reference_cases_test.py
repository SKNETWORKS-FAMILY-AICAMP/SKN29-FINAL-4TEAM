"""Isolated test profile for the local-only reference scenario catalogue."""

from .test import *  # noqa: F403


INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,  # noqa: F405
    "local_apps.reference_cases.apps.ReferenceCasesConfig",
]
