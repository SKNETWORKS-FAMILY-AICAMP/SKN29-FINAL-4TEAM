"""Idempotent local seed for the consultant dashboard projection."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.operations.models import (
    DashboardNotice,
    InquiryDashboardProfile,
    StaffDirectoryEntry,
)
from apps.operations.repositories import (
    PersistResult,
    SyntheticImportConflict,
    SyntheticImportRepository,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


SEED_PREFIX = "SYN-WEB-DASH"
DEMO_CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")

CONSULTANT_DIRECTORY = (
    ("김하윤", "고객케어팀", "팀장", "02-0000-9501", "hayoon.kim"),
    ("한예나", "고객케어팀", "상담사", "02-0000-9502", "yena.han"),
    ("임현우", "품질관리팀", "매니저", "02-0000-9503", "hyunwoo.lim"),
    ("박지우", "품질관리팀", "담당", "02-0000-9504", "jiwoo.park"),
    ("이서연", "방문지원팀", "매니저", "02-0000-9505", "seoyeon.lee"),
    ("최지우", "방문지원팀", "담당", "02-0000-9506", "jiwoo.choi"),
    ("정하윤", "시스템운영팀", "매니저", "02-0000-9507", "hayoon.jeong"),
    ("강민준", "시스템운영팀", "담당", "02-0000-9508", "minjun.kang"),
)

TECHNICIAN_DIRECTORY = (
    ("오민석", "서울동부지사", "010-0000-5001", "minseok.oh"),
    ("서지훈", "서울서부지사", "010-0000-5002", "jihoon.seo"),
    ("윤도현", "경기남부지사", "010-0000-5003", "dohyun.yoon"),
    ("배수아", "경기북부지사", "010-0000-5004", "sua.bae"),
)

NOTICE_FIXTURES = (
    (
        "EMERGENCY",
        "긴급 문의 응대 절차 안내",
        "누수·감전·이상 냄새 등 안전 위험 문의는 고객의 제품 사용을 중지시키고 긴급 상담 절차로 우선 연결해 주세요.",
        "고객케어팀",
        date(2026, 8, 18),
    ),
    (
        "EVENT",
        "고객 만족도 조사 참여 안내",
        "상담 종료 고객에게 만족도 조사 참여 방법을 안내하되 응답을 강요하거나 상담 결과와 연계하지 말아 주세요.",
        "고객경험팀",
        date(2026, 8, 18),
    ),
    (
        "SYSTEM",
        "상담 시스템 정기 점검 안내",
        "정기 점검 시간에는 신규 문의 저장 지연이 발생할 수 있으므로 처리 중인 문의의 상태와 상관 ID를 먼저 확인해 주세요.",
        "시스템운영팀",
        date(2026, 8, 17),
    ),
    (
        "WORK",
        "8월 상담 근무 일정 확인 요청",
        "팀별 근무표와 긴급 문의 당번을 확인하고 일정 변경이 필요한 경우 고객케어팀에 알려 주세요.",
        "고객케어팀",
        date(2026, 8, 16),
    ),
    (
        "WELFARE",
        "임직원 건강검진 신청 안내",
        "대상자는 사내 복지 절차에 따라 검진 일정을 신청하고 근무 일정과 겹치는 경우 사전에 조정해 주세요.",
        "경영지원팀",
        date(2026, 8, 15),
    ),
    (
        "TRAINING",
        "정수기 안전 점검 상담 교육",
        "제품별 안전 점검 문구와 방문 전환 기준을 숙지하고 확정 진단이나 임의 분해 안내를 하지 말아 주세요.",
        "품질관리팀",
        date(2026, 8, 14),
    ),
)

PRODUCTS = (
    ("SYN-WEB-WP-001", "WaterBridge 직수 정수기 A"),
    ("SYN-WEB-WP-002", "WaterBridge 냉온 정수기 B"),
    ("SYN-WEB-WP-003", "WaterBridge 슬림 정수기 C"),
)

CUSTOMER_NAMES = (
    "김가람", "이나래", "박도윤", "최서윤", "정하람", "강지우",
    "윤시온", "한아름", "오민재", "서유진", "배준호", "임다은",
    "조현서", "신예린", "유태오", "홍서아", "문지호", "노하린",
    "권도현", "장수빈", "백이안", "송나윤", "안재민", "전유나",
    "고은찬", "양세아", "황준서", "민채원", "진우림", "표다온",
)

RISK_CONTENT = {
    "danger": (
        "정수기 주변에 물이 새고 타는 냄새가 납니다.",
        "온수 출수부에서 과열 소리와 연기가 보입니다.",
        "본체 아래로 누수가 빠르게 번지고 있습니다.",
        "전원 연결부가 뜨겁고 이상 냄새가 납니다.",
        "제품 내부에서 큰 소음과 함께 물이 튑니다.",
        "온수가 멈추지 않고 계속 배출됩니다.",
        "정수기 외관에 전기가 흐르는 느낌이 듭니다.",
        "제품이 넘어지며 급수 호스가 분리됐습니다.",
        "누수와 함께 차단기가 반복해서 내려갑니다.",
        "어린이가 닿는 위치로 뜨거운 물이 샙니다.",
    ),
    "caution": (
        "출수량이 갑자기 크게 줄었습니다.",
        "정수된 물에서 평소와 다른 냄새가 납니다.",
        "냉수 온도가 일정하게 유지되지 않습니다.",
        "필터 교체 후에도 알림이 사라지지 않습니다.",
        "출수 버튼이 간헐적으로 반응하지 않습니다.",
        "제품 안쪽에서 평소보다 큰 진동음이 납니다.",
        "급수 이후 물방울이 오랫동안 떨어집니다.",
        "온수 잠금 기능이 간헐적으로 풀립니다.",
        "정수된 물에 미세한 부유물이 보입니다.",
        "살균 기능 실행 중 오류 코드가 표시됩니다.",
    ),
    "general": (
        "필터 교체 주기와 신청 방법을 확인하고 싶습니다.",
        "자가관리 키트 사용 순서를 안내해 주세요.",
        "다음 정기 관리 방문일을 확인하고 싶습니다.",
        "제품 절전 모드 설정 방법을 알고 싶습니다.",
        "출수량 기본 설정을 바꾸는 방법이 궁금합니다.",
        "이사 후 설치 주소 변경 절차를 문의합니다.",
        "냉수 기능을 잠시 끄는 방법을 알려 주세요.",
        "정수기 외부 청소 권장 방법이 궁금합니다.",
        "구독 제품의 관리 유형을 확인하고 싶습니다.",
        "제품 표시등의 의미를 안내해 주세요.",
    ),
}

BUCKETS = (
    ("NEW", Inquiry.Status.CONSULTATION_REQUIRED, 3),
    ("IN_PROGRESS", Inquiry.Status.CONSULTATION_IN_PROGRESS, 5),
    ("COMPLETED", Inquiry.Status.RESOLVED, 8),
)


@dataclass(frozen=True)
class ConsultantDashboardSeedResult:
    """Serializable result for one local dashboard seed execution."""

    dry_run: bool
    created_count: int
    updated_count: int
    unchanged_count: int
    verification: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConsultantDashboardSeedService:
    """Create only namespaced, synthetic dashboard records."""

    def __init__(
        self,
        *,
        repository: SyntheticImportRepository | None = None,
    ) -> None:
        self.repository = repository or SyntheticImportRepository()
        self.actions: list[str] = []

    def run(self, *, dry_run: bool = False) -> ConsultantDashboardSeedResult:
        with transaction.atomic():
            self.actions = []
            actor = self._ensure_demo_consultant()
            self._seed_staff_directory()
            products = self._seed_products()
            customers = self._seed_customers()
            subscriptions = self._seed_subscriptions(customers, products)
            self._seed_inquiries(actor, subscriptions)
            self._seed_notices()
            verification = self._verify(actor)
            counts = Counter(self.actions)
            result = ConsultantDashboardSeedResult(
                dry_run=dry_run,
                created_count=counts["CREATED"],
                updated_count=counts["UPDATED"],
                unchanged_count=counts["UNCHANGED"],
                verification=verification,
            )
            if dry_run:
                transaction.set_rollback(True)
        return result

    def _ensure_demo_consultant(self) -> User:
        actor = User.objects.filter(
            username=DEMO_CONSULTANT_USERNAME
        ).first()
        if actor is None:
            actor = User.objects.create_user(
                public_id=self._uuid("user/demo-consultant"),
                username=DEMO_CONSULTANT_USERNAME,
                full_name="합성 상담사 001",
                role_code=User.Role.CONSULTANT,
                employee_no="DEMO-EMP-CNS-001",
                is_active=True,
                is_synthetic=True,
            )
            self.actions.append("CREATED")
            return actor
        if (
            actor.role_code != User.Role.CONSULTANT
            or not actor.is_active
            or not actor.is_synthetic
        ):
            raise SyntheticImportConflict(
                "DEMO-CONSULTANT-001 must remain an active synthetic consultant."
            )
        self.actions.append("UNCHANGED")
        return actor

    def _seed_staff_directory(self) -> None:
        for sequence, fixture in enumerate(CONSULTANT_DIRECTORY, start=1):
            name, department, position, extension, email_local = fixture
            user = self._persist(
                User,
                public_id=self._uuid(f"staff/consultant/{sequence}"),
                business_lookup={
                    "username": f"{SEED_PREFIX}-CONSULTANT-{sequence:03d}"
                },
                immutable_values={
                    "role_code": User.Role.CONSULTANT,
                    "employee_no": f"{SEED_PREFIX}-CNS-{sequence:03d}",
                },
                values={
                    "full_name": name,
                    "email": f"{email_local}@waterbridge.example",
                    "phone": "",
                    "is_active": True,
                    "is_staff": False,
                    "is_synthetic": True,
                },
                prepare_new=lambda instance: instance.set_unusable_password(),
            )
            self._persist(
                StaffDirectoryEntry,
                public_id=self._uuid(f"directory/consultant/{sequence}"),
                business_lookup={"user": user},
                immutable_values={
                    "staff_type": StaffDirectoryEntry.StaffType.CONSULTANT
                },
                values={
                    "department_name": department,
                    "position_title": position,
                    "extension_number": extension,
                    "branch_name": "",
                    "display_order": sequence,
                    "is_active": True,
                },
            )

        for sequence, fixture in enumerate(TECHNICIAN_DIRECTORY, start=1):
            name, branch, phone, email_local = fixture
            user = self._persist(
                User,
                public_id=self._uuid(f"staff/technician/{sequence}"),
                business_lookup={
                    "username": f"{SEED_PREFIX}-TECHNICIAN-{sequence:03d}"
                },
                immutable_values={
                    "role_code": User.Role.TECHNICIAN,
                    "employee_no": f"{SEED_PREFIX}-TEC-{sequence:03d}",
                },
                values={
                    "full_name": name,
                    "email": f"{email_local}@waterbridge.example",
                    "phone": phone,
                    "is_active": True,
                    "is_staff": False,
                    "is_synthetic": True,
                },
                prepare_new=lambda instance: instance.set_unusable_password(),
            )
            self._persist(
                StaffDirectoryEntry,
                public_id=self._uuid(f"directory/technician/{sequence}"),
                business_lookup={"user": user},
                immutable_values={
                    "staff_type": StaffDirectoryEntry.StaffType.TECHNICIAN
                },
                values={
                    "department_name": "",
                    "position_title": "",
                    "extension_number": "",
                    "branch_name": branch,
                    "display_order": sequence,
                    "is_active": True,
                },
            )

    def _seed_products(self) -> list[ProductModel]:
        products: list[ProductModel] = []
        for sequence, (model_code, model_name) in enumerate(PRODUCTS, start=1):
            products.append(
                self._persist(
                    ProductModel,
                    public_id=self._uuid(f"product/{sequence}"),
                    business_lookup={"model_code": model_code},
                    values={
                        "model_name": model_name,
                        "generation_code": "DEMO",
                        "manufacturer": "WaterBridge",
                        "launched_on": date(2025, 1, sequence),
                        "discontinued_on": None,
                        "features": {
                            "data_classification": "synthetic",
                            "dashboard_seed": SEED_PREFIX,
                        },
                        "is_supported_mvp": True,
                        "is_active": True,
                    },
                )
            )
        return products

    def _seed_customers(self) -> list[CustomerProfile]:
        profiles: list[CustomerProfile] = []
        for sequence, name in enumerate(CUSTOMER_NAMES, start=1):
            user = self._persist(
                User,
                public_id=self._uuid(f"customer-user/{sequence}"),
                business_lookup={
                    "username": f"{SEED_PREFIX}-CUSTOMER-{sequence:03d}"
                },
                immutable_values={
                    "role_code": User.Role.CUSTOMER,
                    "employee_no": None,
                },
                values={
                    "full_name": f"{name} (합성)",
                    "email": f"customer{sequence:03d}@waterbridge.example",
                    "phone": "",
                    "is_active": True,
                    "is_staff": False,
                    "is_synthetic": True,
                },
                prepare_new=lambda instance: instance.set_unusable_password(),
            )
            district = ("마포구", "송파구", "영등포구")[
                (sequence - 1) % 3
            ]
            profile = self._persist(
                CustomerProfile,
                public_id=self._uuid(f"customer-profile/{sequence}"),
                business_lookup={
                    "customer_no": f"{SEED_PREFIX}-CUSTOMER-{sequence:03d}"
                },
                immutable_values={"user": user},
                values={
                    "customer_name": f"{name} (합성)",
                    "phone": f"010-0001-{sequence:04d}",
                    "postal_code": f"{40000 + sequence:05d}",
                    "address_line1": f"서울특별시 {district} 합성로 {sequence}",
                    "address_line2": f"테스트동 {100 + sequence}호",
                    "consent_version": "SYNTHETIC-DEMO-1",
                    "consented_at": self._aware(2026, 7, 1, 9, 0),
                    "is_synthetic": True,
                    "deleted_at": None,
                    "deleted_by": None,
                },
            )
            profiles.append(profile)
        return profiles

    def _seed_subscriptions(
        self,
        customers: list[CustomerProfile],
        products: list[ProductModel],
    ) -> list[CustomerSubscription]:
        subscriptions: list[CustomerSubscription] = []
        for sequence, customer in enumerate(customers, start=1):
            product = products[(sequence - 1) % len(products)]
            address = f"{customer.address_line1} {customer.address_line2}"
            subscriptions.append(
                self._persist(
                    CustomerSubscription,
                    public_id=self._uuid(f"subscription/{sequence}"),
                    business_lookup={
                        "contract_no": f"{SEED_PREFIX}-SUB-{sequence:03d}"
                    },
                    immutable_values={
                        "customer": customer,
                        "product_model": product,
                    },
                    values={
                        "serial_no": f"{SEED_PREFIX}-SERIAL-{sequence:03d}",
                        "management_type_code": (
                            CustomerSubscription.ManagementType.VISIT_CARE
                            if sequence % 2
                            else CustomerSubscription.ManagementType.SELF_MANAGED
                        ),
                        "status_code": CustomerSubscription.Status.ACTIVE,
                        "started_on": date(2024, 1, 1)
                        + timedelta(days=sequence * 7),
                        "ended_on": None,
                        "installed_at": None,
                        "installed_on": date(2024, 1, 1)
                        + timedelta(days=sequence * 7),
                        "source_customer_product_public_id": self._uuid(
                            f"customer-product/{sequence}"
                        ),
                        "installation_address": address,
                        "next_care_on": date(2026, 9, 1)
                        + timedelta(days=sequence),
                    },
                )
            )
        return subscriptions

    def _seed_inquiries(
        self,
        actor: User,
        subscriptions: list[CustomerSubscription],
    ) -> None:
        base_time = self._aware(2026, 8, 18, 9, 0)
        for bucket_order, (bucket, status, state_version) in enumerate(BUCKETS):
            for sequence, subscription in enumerate(subscriptions, start=1):
                risk, risk_index = self._risk(sequence)
                detail = RISK_CONTENT[risk][risk_index]
                title = detail.rstrip(".")
                inquiry_time = base_time - timedelta(
                    days=bucket_order,
                    minutes=sequence * 3,
                )
                business_sequence = bucket_order * 30 + sequence
                inquiry = self._persist(
                    Inquiry,
                    public_id=self._uuid(f"inquiry/{bucket}/{sequence}"),
                    business_lookup={
                        "inquiry_code": (
                            f"{SEED_PREFIX}-INQ-{business_sequence:03d}"
                        )
                    },
                    immutable_values={
                        "scenario_code": (
                            f"{SEED_PREFIX}-{bucket}-{sequence:03d}"
                        ),
                        "subscription": subscription,
                        "initiated_by": subscription.customer.user,
                    },
                    values={
                        "assigned_user": actor,
                        "assigned_role_code": Inquiry.AssignedRole.CONSULTANT,
                        "channel_code": Inquiry.Channel.MOBILE,
                        "raw_text": (
                            f"{detail} 상담 화면 연동 검증을 위한 합성 문의이며 "
                            "실제 고객 정보가 아닙니다."
                        ),
                        "risk_level_code": risk,
                        "priority_code": self._priority(risk),
                        "usage_guidance_status": self._usage_status(risk),
                        "evidence_ids": [],
                        "evidence_mode": Inquiry.EvidenceMode.NO_EVIDENCE,
                        "requires_fallback": True,
                        "source_idempotency_key": (
                            f"{SEED_PREFIX}-IDEMP-{business_sequence:03d}"
                        ),
                        "source_correlation_id": self._uuid(
                            f"correlation/{bucket}/{sequence}"
                        ),
                        "questionnaire_session_public_id": None,
                        "status_code": status,
                        "state_version": state_version,
                        "cancelled_at": None,
                        "cancellation_reason_code": None,
                        "cancellation_reason_detail": None,
                    },
                    source_created_at=inquiry_time,
                    source_updated_at=inquiry_time + timedelta(minutes=20),
                )
                self._persist(
                    SymptomEntry,
                    public_id=self._uuid(f"symptom/{bucket}/{sequence}"),
                    business_lookup={"inquiry": inquiry},
                    values={
                        "symptom_type_code": f"DASHBOARD_{risk.upper()}",
                        "structured_payload": {
                            "title": title,
                            "detail": detail,
                            "data_classification": "synthetic",
                        },
                        "schema_version": "dashboard-v1",
                        "is_customer_confirmed": True,
                    },
                )
                warranty_ends_on = (
                    date(2027, 2, 28)
                    if sequence <= 15
                    else date(2025, 12, 31)
                )
                self._persist(
                    InquiryDashboardProfile,
                    public_id=self._uuid(f"inquiry-profile/{bucket}/{sequence}"),
                    business_lookup={"inquiry": inquiry},
                    values={
                        "title": title,
                        "warranty_ends_on": warranty_ends_on,
                        "previous_visit_count": (sequence - 1) % 5,
                        "is_synthetic": True,
                    },
                )
                if bucket != "NEW":
                    self._seed_consultation(
                        inquiry=inquiry,
                        actor=actor,
                        bucket=bucket,
                        sequence=sequence,
                        created_at=inquiry_time + timedelta(minutes=5),
                    )

    def _seed_consultation(
        self,
        *,
        inquiry: Inquiry,
        actor: User,
        bucket: str,
        sequence: int,
        created_at: datetime,
    ) -> None:
        completed = bucket == "COMPLETED"
        started_at = created_at + timedelta(minutes=5)
        completed_at = started_at + timedelta(minutes=25) if completed else None
        self._persist(
            Consultation,
            public_id=self._uuid(f"consultation/{bucket}/{sequence}"),
            business_lookup={
                "consultation_code": f"{SEED_PREFIX}-CON-{bucket}-{sequence:03d}"
            },
            immutable_values={
                "inquiry": inquiry,
                "sequence": 1,
            },
            values={
                "consultant": actor,
                "status": (
                    Consultation.Status.COMPLETED
                    if completed
                    else Consultation.Status.IN_PROGRESS
                ),
                "outcome": (
                    Consultation.Outcome.COMPLETED_NO_VISIT
                    if completed
                    else Consultation.Outcome.PENDING
                ),
                "summary": (
                    "합성 상담을 완료하고 고객 확인을 기록했습니다."
                    if completed
                    else "합성 상담을 진행 중입니다."
                ),
                "ai_draft_summary": None,
                "confirmed_summary": (
                    "고객 안내 후 정상 사용을 확인했습니다."
                    if completed
                    else None
                ),
                "summary_confirmed_at": completed_at,
                "consultation_note": "대시보드 연동 검증용 합성 상담입니다.",
                "additional_check": None,
                "customer_guidance": (
                    "안내 내용을 확인하고 이상이 재발하면 다시 문의해 주세요."
                    if completed
                    else None
                ),
                "usage_guidance_status": inquiry.usage_guidance_status,
                "visit_review_reason_code": None,
                "visit_review_reason_detail": None,
                "visit_not_needed_reason_code": (
                    "GUIDANCE_RESOLVED" if completed else None
                ),
                "visit_not_needed_reason_detail": (
                    "합성 상담에서 안내로 해결됨" if completed else None
                ),
                "state_version": 2 if completed else 1,
                "idempotency_key": (
                    f"{SEED_PREFIX}-CON-IDEMP-{bucket}-{sequence:03d}"
                ),
                "correlation_id": self._uuid(
                    f"consultation-correlation/{bucket}/{sequence}"
                ),
                "started_at": started_at,
                "completed_at": completed_at,
                "data_classification": Consultation.DataClassification.SYNTHETIC,
                "created_at": created_at,
            },
            source_created_at=created_at,
            source_updated_at=completed_at or started_at,
        )

    def _seed_notices(self) -> None:
        for sequence, fixture in enumerate(NOTICE_FIXTURES, start=1):
            category, title, body, department, published_on = fixture
            self._persist(
                DashboardNotice,
                public_id=self._uuid(f"notice/{sequence}"),
                business_lookup={
                    "notice_code": f"{SEED_PREFIX}-NOTICE-{sequence:03d}"
                },
                values={
                    "category_code": category,
                    "title": title,
                    "body": body,
                    "department_name": department,
                    "published_on": published_on,
                    "display_order": sequence,
                    "is_published": True,
                    "is_synthetic": True,
                },
            )

    def _verify(self, actor: User) -> dict[str, Any]:
        profiles = InquiryDashboardProfile.objects.filter(
            inquiry__scenario_code__startswith=f"{SEED_PREFIX}-",
            inquiry__assigned_user=actor,
            is_synthetic=True,
        )
        status_risk_counts = {
            f"{row['inquiry__status_code']}:{row['inquiry__risk_level_code']}": (
                row["total"]
            )
            for row in profiles.values(
                "inquiry__status_code",
                "inquiry__risk_level_code",
            ).annotate(total=Count("id"))
        }
        expected_status_risk = {
            f"{status}:{risk}": 10
            for _, status, _ in BUCKETS
            for risk in Inquiry.RiskLevel.values
        }
        verification = {
            "consultants": StaffDirectoryEntry.objects.filter(
                staff_type=StaffDirectoryEntry.StaffType.CONSULTANT,
                user__username__startswith=f"{SEED_PREFIX}-",
                is_active=True,
            ).count(),
            "technicians": StaffDirectoryEntry.objects.filter(
                staff_type=StaffDirectoryEntry.StaffType.TECHNICIAN,
                user__username__startswith=f"{SEED_PREFIX}-",
                is_active=True,
            ).count(),
            "customers": CustomerProfile.objects.filter(
                customer_no__startswith=f"{SEED_PREFIX}-CUSTOMER-",
                is_synthetic=True,
            ).count(),
            "inquiries": profiles.count(),
            "notices": DashboardNotice.objects.filter(
                notice_code__startswith=f"{SEED_PREFIX}-NOTICE-",
                is_published=True,
                is_synthetic=True,
            ).count(),
            "status_risk_counts": status_risk_counts,
        }
        expected = {
            "consultants": 8,
            "technicians": 4,
            "customers": 30,
            "inquiries": 90,
            "notices": 6,
        }
        for key, expected_value in expected.items():
            if verification[key] != expected_value:
                raise SyntheticImportConflict(
                    f"Dashboard seed verification failed: {key}="
                    f"{verification[key]} expected={expected_value}"
                )
        if status_risk_counts != expected_status_risk:
            raise SyntheticImportConflict(
                "Dashboard seed status/risk distribution mismatch: "
                f"actual={status_risk_counts} expected={expected_status_risk}"
            )
        return verification

    def _persist(self, model, **kwargs):
        result: PersistResult = self.repository.persist(model, **kwargs)
        self.actions.append(result.action)
        return result.instance

    @staticmethod
    def _uuid(key: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"https://waterbridge.example/{SEED_PREFIX.lower()}/{key}",
        )

    @staticmethod
    def _aware(
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
    ) -> datetime:
        return timezone.make_aware(
            datetime(year, month, day, hour, minute),
            BUSINESS_TIMEZONE,
        )

    @staticmethod
    def _risk(sequence: int) -> tuple[str, int]:
        if sequence <= 10:
            return Inquiry.RiskLevel.DANGER, sequence - 1
        if sequence <= 20:
            return Inquiry.RiskLevel.CAUTION, sequence - 11
        return Inquiry.RiskLevel.GENERAL, sequence - 21

    @staticmethod
    def _priority(risk: str) -> str:
        return {
            Inquiry.RiskLevel.DANGER: Inquiry.Priority.URGENT,
            Inquiry.RiskLevel.CAUTION: Inquiry.Priority.HIGH,
            Inquiry.RiskLevel.GENERAL: Inquiry.Priority.NORMAL,
        }[risk]

    @staticmethod
    def _usage_status(risk: str) -> str:
        return {
            Inquiry.RiskLevel.DANGER: Inquiry.UsageGuidanceStatus.TOTAL_STOP,
            Inquiry.RiskLevel.CAUTION: (
                Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
            ),
            Inquiry.RiskLevel.GENERAL: Inquiry.UsageGuidanceStatus.NORMAL,
        }[risk]
