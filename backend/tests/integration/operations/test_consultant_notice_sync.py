from __future__ import annotations

from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.accounts.models import CustomerProfile
from apps.inquiries.models import Inquiry
from apps.operations.models import DashboardNotice, StaffDirectoryEntry
from apps.operations.services import ConsultantDashboardSeedService
from apps.operations.services.consultant_dashboard_seed_service import (
    NOTICE_FIXTURES,
)
from apps.operations.services.consultant_notice_sync_service import (
    ConsultantNoticeSyncService,
)


pytestmark = pytest.mark.django_db


def _domain_counts() -> dict[str, int]:
    return {
        "customers": CustomerProfile.objects.count(),
        "inquiries": Inquiry.objects.count(),
        "staff": StaffDirectoryEntry.objects.count(),
        "notices": DashboardNotice.objects.count(),
    }


def test_notice_fixtures_have_summary_and_rich_detail() -> None:
    assert len(NOTICE_FIXTURES) == 6
    for _, _, body, _, _ in NOTICE_FIXTURES:
        paragraphs = body.split("\n\n")
        assert len(paragraphs) >= 3
        assert 25 <= len(paragraphs[0]) <= 90
        assert len(body) >= 150
        assert "<script" not in body.lower()


def test_notice_sync_is_scoped_dry_run_safe_and_replay_safe() -> None:
    ConsultantDashboardSeedService().run()
    target = DashboardNotice.objects.get(
        notice_code="SYN-WEB-DASH-NOTICE-001"
    )
    target.body = "기존 한 줄 공지"
    target.save(update_fields=["body", "updated_at"])
    unrelated = DashboardNotice.objects.create(
        public_id=uuid4(),
        notice_code="SYN-UNRELATED-NOTICE-001",
        category_code=DashboardNotice.Category.SYSTEM,
        title="다른 공지",
        body="변경되면 안 되는 공지",
        department_name="테스트팀",
        published_on=target.published_on,
        display_order=99,
        is_published=True,
        is_synthetic=True,
    )
    before_counts = _domain_counts()

    plan = ConsultantNoticeSyncService().run(mode="plan")
    assert plan.updated_count == 1
    target.refresh_from_db()
    assert target.body == "기존 한 줄 공지"

    dry_run = ConsultantNoticeSyncService().run(mode="dry-run")
    assert dry_run.updated_count == 1
    target.refresh_from_db()
    assert target.body == "기존 한 줄 공지"

    applied = ConsultantNoticeSyncService().run(mode="apply")
    assert applied.updated_count == 1
    assert applied.before_sha256 != applied.after_sha256
    target.refresh_from_db()
    assert "일반 문의보다 먼저 처리합니다" in target.body

    replay = ConsultantNoticeSyncService().run(mode="apply")
    assert replay.updated_count == 0
    assert replay.unchanged_count == 6
    assert replay.before_sha256 == replay.after_sha256

    unrelated.refresh_from_db()
    assert unrelated.body == "변경되면 안 되는 공지"
    assert _domain_counts() == before_counts


def test_notice_sync_command_requires_exact_apply_target() -> None:
    ConsultantDashboardSeedService().run()
    output = StringIO()

    call_command("sync_consultant_notices", stdout=output)
    assert '"mode": "plan"' in output.getvalue()

    with pytest.raises(CommandError, match="requires"):
        call_command("sync_consultant_notices", apply=True)

    with pytest.raises(CommandError, match="database"):
        call_command(
            "sync_consultant_notices",
            apply=True,
            expected_database="wrong-database",
            expected_host=str(connection.settings_dict["HOST"] or "localhost"),
        )
