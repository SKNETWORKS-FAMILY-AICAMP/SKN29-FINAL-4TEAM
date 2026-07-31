"""T-017 사용자·합성 고객 Profile Model 검증."""

from uuid import UUID

import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from apps.accounts.models import CustomerProfile, User


pytestmark = pytest.mark.django_db


def test_user_manager_hashes_password_and_uses_internal_integer_id():
    user = User.objects.create_user(
        username="DEMO-CUSTOMER-101",
        password="not-a-real-password",
        full_name="합성 고객",
        role_code=User.Role.CUSTOMER,
    )

    assert isinstance(user.pk, int)
    assert user.legacy_id is None
    assert isinstance(user.public_id, UUID)
    assert user.check_password("not-a-real-password") is True
    assert user.password != "not-a-real-password"


def test_employee_number_contract_fails_closed_by_role():
    with pytest.raises(ValidationError):
        User.objects.create_user(
            username="DEMO-CUSTOMER-102",
            full_name="잘못된 고객",
            role_code=User.Role.CUSTOMER,
            employee_no="SHOULD-NOT-EXIST",
        )

    with pytest.raises(ValidationError):
        User.objects.create_user(
            username="DEMO-TECHNICIAN-102",
            full_name="사번 없는 기사",
            role_code=User.Role.TECHNICIAN,
        )


def test_customer_profile_rejects_non_customer_and_protects_user():
    technician = User.objects.create_user(
        username="DEMO-TECHNICIAN-103",
        full_name="합성 기사",
        role_code=User.Role.TECHNICIAN,
        employee_no="DEMO-EMP-103",
    )
    invalid_profile = CustomerProfile(
        user=technician,
        customer_no="SYN-CUSTOMER-103",
        customer_name="잘못된 프로필",
    )

    with pytest.raises(ValidationError):
        invalid_profile.full_clean()

    customer = User.objects.create_user(
        username="DEMO-CUSTOMER-104",
        full_name="합성 고객 104",
        role_code=User.Role.CUSTOMER,
    )
    profile = CustomerProfile.objects.create(
        user=customer,
        customer_no="SYN-CUSTOMER-104",
        customer_name="합성 고객 104",
    )
    assert isinstance(profile.public_id, UUID)
    assert isinstance(profile.pk, int)
    assert profile.legacy_id is None
    assert profile.public_id != customer.public_id

    with pytest.raises(ProtectedError):
        customer.delete()
