"""Safety boundary for the isolated P1 rollback E2E command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


pytestmark = pytest.mark.django_db


def test_command_refuses_non_isolated_test_database():
    with pytest.raises(CommandError, match="P1 격리 PostgreSQL"):
        call_command(
            "verify_p1_team_isolated_e2e",
            stdout=StringIO(),
        )
