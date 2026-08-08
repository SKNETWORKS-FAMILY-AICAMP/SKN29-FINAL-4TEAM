"""Restricted forms for the internal synthetic-account Admin."""

from __future__ import annotations

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from apps.accounts.models import User


SYNTHETIC_USERNAME_PREFIXES = ("DEMO-", "SYN-")
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
        username = str(self.cleaned_data["username"]).strip().upper()
        if not username.startswith(SYNTHETIC_USERNAME_PREFIXES):
            raise ValidationError(
                "Synthetic Admin usernames must start with DEMO- or SYN-."
            )
        return username

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

    class Meta:
        model = User
        fields = ("full_name", "email", "phone")
