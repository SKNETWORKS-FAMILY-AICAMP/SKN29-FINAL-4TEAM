"""확정된 대문자 코드 계약만 공통코드 레지스트리에 적재한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.common_codes.models import CommonCode, CommonCodeGroup


CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class SeedSpec:
    filename: str
    group_code: str
    group_name: str


SEED_SPECS = (
    SeedSpec("user-roles.yaml", "USER_ROLE", "사용자 역할"),
    SeedSpec(
        "management-types.yaml",
        "MANAGEMENT_TYPE",
        "구독 관리 유형",
    ),
    SeedSpec(
        "subscription-statuses.yaml",
        "SUBSCRIPTION_STATUS",
        "구독 상태",
    ),
    SeedSpec("care-types.yaml", "CARE_TYPE", "케어 유형"),
    SeedSpec("care-statuses.yaml", "CARE_STATUS", "케어 상태"),
    SeedSpec("data-sources.yaml", "DATA_SOURCE", "데이터 출처"),
    SeedSpec("care-results.yaml", "CARE_RESULT", "케어 결과"),
    SeedSpec(
        "inquiry-cancellation-reasons.yaml",
        "INQUIRY_CANCELLATION_REASON",
        "문의 취소 사유",
    ),
    SeedSpec(
        "usage-guidance-statuses.yaml",
        "USAGE_GUIDANCE_STATUS",
        "사용 안내 상태",
    ),
    SeedSpec("visit-statuses.yaml", "VISIT_STATUS", "방문 상태"),
    SeedSpec(
        "ai-task-types.yaml",
        "AI_TASK_TYPE",
        "AI 작업 유형",
    ),
    SeedSpec(
        "ai-schema-validation-statuses.yaml",
        "AI_SCHEMA_VALIDATION_STATUS",
        "AI 스키마 검증 상태",
    ),
    SeedSpec(
        "ai-run-statuses.yaml",
        "AI_RUN_STATUS",
        "AI 실행 상태",
    ),
    SeedSpec(
        "dataset-scopes.yaml",
        "DATASET_SCOPE",
        "데이터 범위",
    ),
    SeedSpec(
        "ingestion-source-types.yaml",
        "INGESTION_SOURCE_TYPE",
        "수집 소스 유형",
    ),
    SeedSpec(
        "ingestion-statuses.yaml",
        "INGESTION_STATUS",
        "수집 실행 상태",
    ),
)


def load_contract_codes(path: Path) -> list[str]:
    """Seed 대상 YAML의 비어 있지 않은 대문자 코드 목록을 읽는다."""

    if not path.is_file():
        raise CommandError(f"코드 계약 파일이 없습니다: {path}")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise CommandError(f"코드 계약이 object가 아닙니다: {path.name}")
    codes = document.get("codes")
    if (
        not isinstance(codes, list)
        or not codes
        or not all(isinstance(code, str) for code in codes)
    ):
        raise CommandError(
            f"비어 있지 않은 문자열 codes 목록이 필요합니다: {path.name}"
        )
    invalid_codes = [
        code
        for code in codes
        if CODE_PATTERN.fullmatch(code) is None
    ]
    if invalid_codes:
        raise CommandError(
            f"대문자 코드 형식과 충돌합니다: {path.name} "
            f"({', '.join(invalid_codes)})"
        )
    if len(codes) != len(set(codes)):
        raise CommandError(f"중복 코드가 있습니다: {path.name}")
    return codes


class Command(BaseCommand):
    help = (
        "T-005 공통코드 중 물리 계약과 충돌하지 않는 확정 16개 "
        "그룹을 update_or_create합니다."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        del args, options
        contract_dir = (
            Path(settings.BASE_DIR).parent / "contracts" / "codes"
        )
        group_created = 0
        group_updated = 0
        code_created = 0
        code_updated = 0
        code_deactivated = 0

        for group_order, spec in enumerate(SEED_SPECS, start=1):
            contract_path = contract_dir / spec.filename
            codes = load_contract_codes(contract_path)
            source_contract = f"contracts/codes/{spec.filename}"
            group, created = CommonCodeGroup.objects.update_or_create(
                group_code=spec.group_code,
                defaults={
                    "group_name": spec.group_name,
                    "description": f"{source_contract} 기준 코드",
                    "display_order": group_order,
                    "is_active": True,
                },
            )
            group_created += int(created)
            group_updated += int(not created)

            for code_order, code_value in enumerate(codes, start=1):
                _, created = CommonCode.objects.update_or_create(
                    group=group,
                    code=code_value,
                    defaults={
                        "code_name": code_value,
                        "description": None,
                        "display_order": code_order,
                        "is_active": True,
                        "metadata": {
                            "source_contract": source_contract
                        },
                    },
                )
                code_created += int(created)
                code_updated += int(not created)

            code_deactivated += (
                CommonCode.objects.filter(
                    group=group,
                    is_active=True,
                    metadata__source_contract=source_contract,
                )
                .exclude(code__in=codes)
                .update(is_active=False)
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Confirmed common-code registry ready "
                f"(groups: created={group_created}, "
                f"updated={group_updated}; codes: "
                f"created={code_created}, updated={code_updated}, "
                f"deactivated={code_deactivated})"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "BLOCKED_CONTRACT_MAPPING: risk-levels.yaml의 "
                "general/caution/danger는 common_code 대문자 CHECK와 "
                "충돌하므로 적재하지 않았습니다. 빈 계약·미매핑 계약도 "
                "자동 추론하지 않습니다. ai-stages.yaml은 확정된 "
                "common_code group mapping이 없어 이번 Wave에서 "
                "적재하지 않습니다."
            )
        )
