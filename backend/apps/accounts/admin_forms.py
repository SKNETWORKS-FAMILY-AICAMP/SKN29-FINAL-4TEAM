"""Restricted forms for the internal synthetic-account Admin."""

from __future__ import annotations

from django import forms
from django.contrib.admin.helpers import ActionForm
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.credential_policy import (
    SYNTHETIC_USERNAME_PREFIXES,
    normalize_synthetic_username,
    validate_consultant_password,
)


class AccountLifecycleActionForm(ActionForm):
    """Require an explicit business reason for lifecycle Admin actions."""

    lifecycle_reason = forms.CharField(
        label="Change reason",
        max_length=500,
        required=True,
    )


SYNTHETIC_NAME_MARKERS = ("SYNTHETIC", "DEMO", "합성")


class SyntheticProfileValidationMixin:
    """Reject values that could be mistaken for real personal information."""

    def clean_full_name(self) -> str:
        full_name = str(self.cleaned_data["full_name"]).strip()
        normalized = full_name.upper()
        if not any(marker in normalized for marker in SYNTHETIC_NAME_MARKERS):
            raise ValidationError(
                "Synthetic names must include Synthetic, Demo, or 합성."
            )
        return full_name

    def clean_email(self) -> str:
        email = str(self.cleaned_data.get("email") or "").strip().lower()
        if email and not email.endswith(".invalid"):
            raise ValidationError(
                "Synthetic email addresses must use the .invalid domain."
            )
        return email

    def clean_phone(self) -> str:
        phone = str(self.cleaned_data.get("phone") or "").strip()
        digits = "".join(character for character in phone if character.isdigit())
        if phone and (not digits or set(digits) != {"0"}):
            raise ValidationError(
                "Synthetic phone numbers must contain zero digits only."
            )
        return phone


class SyntheticUserAddForm(
    SyntheticProfileValidationMixin,
    forms.ModelForm,
):
    """Create synthetic users without exposing Django privilege fields."""

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Password confirmation",
        strip=False,
        widget=forms.PasswordInput,
    )
    change_reason = forms.CharField(
        label="Change reason",
        max_length=500,
        required=True,
    )

    class Meta:
        model = User
        fields = (
            "username",
            "full_name",
            "email",
            "phone",
            "role_code",
            "employee_no",
        )

    def clean_username(self) -> str:
        return normalize_synthetic_username(self.cleaned_data["username"])

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two passwords do not match.")
        if password1:
            try:
                password_validation.validate_password(
                    password1,
                    self.instance,
                )
            except ValidationError as exc:
                self.add_error("password1", exc)

        role_code = cleaned_data.get("role_code")
        if role_code == User.Role.CONSULTANT and password1:
            try:
                validate_consultant_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        employee_no = cleaned_data.get("employee_no")
        if role_code == User.Role.CUSTOMER and employee_no:
            self.add_error(
                "employee_no",
                "Customer synthetic accounts cannot have an employee number.",
            )
        if role_code and role_code != User.Role.CUSTOMER and not employee_no:
            self.add_error(
                "employee_no",
                "Staff-role synthetic accounts require an employee number.",
            )
        if (
            role_code
            and role_code != User.Role.CUSTOMER
            and employee_no
            and not str(employee_no).upper().startswith(
                SYNTHETIC_USERNAME_PREFIXES
            )
        ):
            self.add_error(
                "employee_no",
                "Synthetic employee numbers must start with DEMO- or SYN-.",
            )
        return cleaned_data

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.is_synthetic = True
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class SyntheticUserChangeForm(
    SyntheticProfileValidationMixin,
    forms.ModelForm,
):
    """Allow only non-identity profile fields to change in T-017B."""

    change_reason = forms.CharField(
        label="Change reason",
        max_length=500,
        required=True,
    )
    new_password1 = forms.CharField(
        label="새 비밀번호",
        strip=False,
        required=False,
        widget=forms.PasswordInput,
        help_text=(
            "상담사만 변경할 수 있습니다. 12~64자 영문·숫자 조합이며 "
            "기존 비밀번호는 표시되지 않습니다."
        ),
    )
    new_password2 = forms.CharField(
        label="새 비밀번호 확인",
        strip=False,
        required=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ("username", "full_name", "email", "phone")

    def clean_username(self) -> str:
        if self.instance.role_code != User.Role.CONSULTANT:
            return self.instance.username
        return normalize_synthetic_username(self.cleaned_data["username"])

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 or password2:
            if self.instance.role_code != User.Role.CONSULTANT:
                self.add_error(
                    "new_password1",
                    "상담사 계정의 비밀번호만 이 화면에서 초기화할 수 있습니다.",
                )
            if password1 != password2:
                self.add_error("new_password2", "두 비밀번호가 일치하지 않습니다.")
            if password1:
                try:
                    validate_consultant_password(password1)
                except ValidationError as exc:
                    self.add_error("new_password1", exc)
        return cleaned_data
