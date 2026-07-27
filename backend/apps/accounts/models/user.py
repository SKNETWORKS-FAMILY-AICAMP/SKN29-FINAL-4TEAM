"""가상 사용자·역할·활성 상태 Model."""

from __future__ import annotations

from django.contrib.auth.base_user import (
    AbstractBaseUser,
    BaseUserManager,
)
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from common.identifiers import generate_user_id, validate_domain_id
from common.models.base import TimestampedModel


class UserManager(BaseUserManager):
    """도메인형 ID를 사용하는 사용자 생성 Manager."""

    use_in_migrations = True

    def _create_user(
        self,
        username: str,
        password: str | None,
        **extra_fields,
    ):
        if not username:
            raise ValueError("username은 필수입니다.")
        user = self.model(
            username=str(username).strip(),
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_user(
        self,
        username: str,
        password: str | None = None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, password, **extra_fields)

    def create_superuser(
        self,
        username: str,
        password: str,
        **extra_fields,
    ):
        extra_fields.setdefault("role_code", User.Role.OPERATOR)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields.get("employee_no"):
            raise ValueError("superuser employee_no는 필수입니다.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("superuser is_staff는 True여야 합니다.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("superuser is_superuser는 True여야 합니다.")
        return self._create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    """고객·상담사·기사·운영자의 인증 계정."""

    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "고객"
        CONSULTANT = "CONSULTANT", "상담사"
        TECHNICIAN = "TECHNICIAN", "방문기사"
        OPERATOR = "OPERATOR", "운영자"

    id = models.CharField(
        primary_key=True,
        max_length=48,
        default=generate_user_id,
        editable=False,
        validators=[validate_domain_id],
    )
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True)
    role_code = models.CharField(
        max_length=40,
        choices=Role.choices,
    )
    employee_no = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        unique=True,
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["full_name", "role_code"]

    class Meta:
        db_table = "accounts_user"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    role_code__in=[
                        "CUSTOMER",
                        "CONSULTANT",
                        "TECHNICIAN",
                        "OPERATOR",
                    ]
                ),
                name="accounts_user_valid_role",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        role_code="CUSTOMER",
                        employee_no__isnull=True,
                    )
                    | Q(
                        role_code__in=[
                            "CONSULTANT",
                            "TECHNICIAN",
                            "OPERATOR",
                        ],
                        employee_no__isnull=False,
                    )
                ),
                name="accounts_user_employee_by_role",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.role_code})"
