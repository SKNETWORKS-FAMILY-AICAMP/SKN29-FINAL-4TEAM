"""Database invariants that keep candidate scenarios outside runtime use."""

from __future__ import annotations

import os

import pytest

if (
    os.getenv("DJANGO_SETTINGS_MODULE")
    != "config.settings.reference_cases_test"
):
    pytest.skip(
        "requires the isolated reference_cases_test settings profile",
        allow_module_level=True,
    )

from django.conf import settings
from django.db import IntegrityError, transaction

from local_apps.reference_cases.catalog import load_reference_catalog
from local_apps.reference_cases.importer import ReferenceScenarioImporter
from local_apps.reference_cases.models import ReferenceScenario
from config.settings import base
from config.settings import test as default_test_settings


pytestmark = pytest.mark.django_db


def test_reference_app_is_installed_only_in_explicit_local_test_profile():
    app = "local_apps.reference_cases.apps.ReferenceCasesConfig"

    assert app not in base.INSTALLED_APPS
    assert app not in default_test_settings.INSTALLED_APPS
    assert app in settings.INSTALLED_APPS


def test_database_rejects_runtime_activation():
    catalog = load_reference_catalog()
    ReferenceScenarioImporter.persist(catalog)
    row = ReferenceScenario.objects.first()
    assert row is not None

    with pytest.raises(IntegrityError), transaction.atomic():
        ReferenceScenario.objects.filter(pk=row.pk).update(
            is_runtime_enabled=True
        )


def test_database_separates_consultation_and_publication_gate_fields():
    catalog = load_reference_catalog()
    ReferenceScenarioImporter.persist(catalog)

    consultation = ReferenceScenario.objects.get(
        scenario_id="REF-IAC425-C-001"
    )
    review_only = ReferenceScenario.objects.get(
        scenario_id="REF-IAC425-C-003"
    )
    assert consultation.expected_requires_consultation is True
    assert review_only.expected_requires_consultation is False
    assert review_only.expected_publication_gate == "HUMAN_APPROVAL_REQUIRED"
    assert review_only.expected_usage_guidance_status == "PARTIAL_STOP"
