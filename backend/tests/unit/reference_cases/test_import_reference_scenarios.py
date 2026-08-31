"""Local-only, rollback-first reference scenario import checks."""

from __future__ import annotations

from io import StringIO
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

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from local_apps.reference_cases.catalog import load_reference_catalog
from local_apps.reference_cases.importer import ReferenceScenarioImporter
from local_apps.reference_cases.management.commands import (
    import_reference_scenarios as command_module,
)
from local_apps.reference_cases.models import ReferenceScenario


pytestmark = pytest.mark.django_db


def _database_name() -> str:
    return str(connection.settings_dict["NAME"])


class _PostgresIdentityCursor:
    def __init__(self, database_name: str, system_identifier: str):
        self.result = (database_name, system_identifier)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback

    def execute(self, sql):
        assert "pg_control_system()" in sql

    def fetchone(self):
        return self.result


class _PostgresIdentityConnection:
    vendor = "postgresql"

    def __init__(self, database_name: str, system_identifier: str):
        self.settings_dict = {
            "NAME": database_name,
            "HOST": "127.0.0.1",
        }
        self._system_identifier = system_identifier

    def cursor(self):
        return _PostgresIdentityCursor(
            str(self.settings_dict["NAME"]),
            self._system_identifier,
        )


def test_default_command_runs_full_write_path_then_rolls_back():
    stdout = StringIO()

    call_command("import_reference_scenarios", stdout=stdout)

    assert ReferenceScenario.objects.count() == 0
    assert "DRY_RUN_READY" in stdout.getvalue()
    assert "records=45" in stdout.getvalue()


def test_apply_and_replay_are_insert_only_and_idempotent():
    first = StringIO()
    call_command(
        "import_reference_scenarios",
        "--apply",
        "--confirm-database",
        _database_name(),
        stdout=first,
    )
    identities = {
        (row.catalog_version, row.scenario_id): (row.pk, row.public_id)
        for row in ReferenceScenario.objects.all()
    }

    second = StringIO()
    call_command(
        "import_reference_scenarios",
        "--apply",
        "--confirm-database",
        _database_name(),
        stdout=second,
    )

    assert ReferenceScenario.objects.count() == 45
    assert {
        (row.catalog_version, row.scenario_id): (row.pk, row.public_id)
        for row in ReferenceScenario.objects.all()
    } == identities
    assert "created=45 unchanged=0" in first.getvalue()
    assert "created=0 unchanged=45" in second.getvalue()


def test_apply_requires_exact_database_confirmation():
    with pytest.raises(CommandError, match="--confirm-database"):
        call_command("import_reference_scenarios", "--apply")


def test_postgres_import_requires_exact_cluster_identity(monkeypatch):
    fake_connection = _PostgresIdentityConnection(
        "waterbridge_reference_cases_local_test",
        "7500123456789012345",
    )
    monkeypatch.setattr(command_module, "connection", fake_connection)

    with pytest.raises(CommandError, match="confirm-system-identifier"):
        command_module.Command._assert_local_database(None)
    with pytest.raises(CommandError, match="does not match"):
        command_module.Command._assert_local_database("wrong-cluster")

    assert command_module.Command._assert_local_database(
        "7500123456789012345"
    ) == "waterbridge_reference_cases_local_test"


def test_late_conflict_rolls_back_all_new_rows():
    catalog = load_reference_catalog()
    last = catalog.rows[-1]
    values = ReferenceScenarioImporter._values(catalog, last)
    values["title"] = "의도적으로 충돌시킨 제목"
    ReferenceScenario.objects.create(
        scenario_id=last["scenario_id"],
        catalog_version=catalog.catalog_version,
        **values,
    )

    with pytest.raises(CommandError, match="immutable scenario drift"):
        call_command(
            "import_reference_scenarios",
            "--apply",
            "--confirm-database",
            _database_name(),
        )

    assert ReferenceScenario.objects.count() == 1
    assert ReferenceScenario.objects.get().title == "의도적으로 충돌시킨 제목"
