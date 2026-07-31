"""가명·합성 Demo 계정을 반복 실행에 안전하게 생성한다."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import CustomerProfile, User


DEMO_USERS = (
    {
        "username": "DEMO-CUSTOMER-001",
        "full_name": "합성 고객 001",
        "role_code": User.Role.CUSTOMER,
        "employee_no": None,
    },
    {
        "username": "DEMO-CONSULTANT-001",
        "full_name": "합성 상담사 001",
        "role_code": User.Role.CONSULTANT,
        "employee_no": "DEMO-EMP-CNS-001",
    },
    {
        "username": "DEMO-TECHNICIAN-001",
        "full_name": "합성 기사 001",
        "role_code": User.Role.TECHNICIAN,
        "employee_no": "DEMO-EMP-TEC-001",
    },
    {
        "username": "DEMO-OPERATOR-001",
        "full_name": "합성 운영자 001",
        "role_code": User.Role.OPERATOR,
        "employee_no": "DEMO-EMP-OPS-001",
    },
)

DEMO_CUSTOMER_NO = "DEMO-CUSTOMER-001"


class Command(BaseCommand):
    help = "T-017 합성 Demo 계정 4개를 update_or_create합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for user_data in DEMO_USERS:
            user, created = User.objects.update_or_create(
                username=user_data["username"],
                defaults={
                    "full_name": user_data["full_name"],
                    "email": "",
                    "phone": "",
                    "role_code": user_data["role_code"],
                    "employee_no": user_data["employee_no"],
                    "is_active": True,
                    "is_staff": False,
                },
            )
            user.set_unusable_password()
            user.save(update_fields=["password", "updated_at"])
            created_count += int(created)
            updated_count += int(not created)

        customer = User.objects.get(username="DEMO-CUSTOMER-001")
        CustomerProfile.objects.update_or_create(
            user=customer,
            defaults={
                "customer_no": DEMO_CUSTOMER_NO,
                "customer_name": "합성 고객 001",
                "phone": "",
                "postal_code": "",
                "address_line1": "",
                "address_line2": "",
                "consent_version": "DEMO-1",
                "is_synthetic": True,
                "deleted_at": None,
                "deleted_by": None,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo accounts ready "
                f"(created={created_count}, updated={updated_count})"
            )
        )
