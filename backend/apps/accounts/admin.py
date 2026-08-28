"""Django Admin boundary for synthetic accounts only."""

from __future__ import annotations

from uuid import UUID, uuid4

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from apps.accounts.admin_forms import (
    AccountLifecycleActionForm,
    SyntheticUserAddForm,
    SyntheticUserChangeForm,
)
from apps.accounts.admin_site import waterbridge_admin_site
from apps.accounts.models import AccountAuditEvent, CustomerProfile, User
from apps.accounts.repositories.account_audit_repository import (
    AccountAuditRepository,
)
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)
from apps.accounts.supervisor_policy import is_waterbridge_supervisor


@admin.register(User, site=waterbridge_admin_site)
class SyntheticUserAdmin(admin.ModelAdmin):
    """Operate synthetic users without exposing privilege escalation fields."""

    list_display = (
        "username",
        "full_name",
        "role_code",
        "is_active",
        "is_synthetic",
        "updated_at",
    )
    list_filter = ("role_code", "is_active")
    search_fields = ("username", "full_name", "email", "employee_no")
    ordering = ("username",)
    actions = ("deactivate_accounts", "reactivate_accounts")
    action_form = AccountLifecycleActionForm

    protected_change_fields = (
        "username",
        "public_id",
        "legacy_id",
        "role_code",
        "employee_no",
        "is_synthetic",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
    )

    @staticmethod
    def _is_operator_staff(request) -> bool:
        return is_waterbridge_supervisor(request.user)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_synthetic=True)

    def has_module_permission(self, request):
        return self._is_operator_staff(request) and super().has_module_permission(
            request
        )

    def has_view_permission(self, request, obj=None):
        return self._is_operator_staff(request) and super().has_view_permission(
            request,
            obj,
        )

    def has_add_permission(self, request):
        return self._is_operator_staff(request) and super().has_add_permission(
            request
        )

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser:
            return False
        return self._is_operator_staff(request) and super().has_change_permission(
            request,
            obj,
        )

    def has_delete_permission(self, request, obj=None):
        del request, obj
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_form(self, request, obj=None, change=False, **kwargs):
        kwargs["form"] = (
            SyntheticUserChangeForm if obj else SyntheticUserAddForm
        )
        return super().get_form(request, obj, change=change, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        del request
        if obj is None:
            return ()
        if obj.role_code == User.Role.CONSULTANT:
            return tuple(
                field
                for field in self.protected_change_fields
                if field != "username"
            )
        return self.protected_change_fields

    def get_fieldsets(self, request, obj=None):
        del request
        if obj is None:
            return (
                (
                    None,
                    {
                        "fields": (
                            "username",
                            "password1",
                            "password2",
                            "change_reason",
                        )
                    },
                ),
                (
                    "Synthetic account",
                    {
                        "fields": (
                            "role_code",
                            "employee_no",
                            "full_name",
                            "email",
                            "phone",
                        )
                    },
                ),
            )
        editable_profile_fields = ["full_name", "email", "phone"]
        if obj.role_code == User.Role.CONSULTANT:
            editable_profile_fields = [
                "username",
                *editable_profile_fields,
                "new_password1",
                "new_password2",
            ]
        editable_profile_fields.append("change_reason")
        immutable_fields = self.protected_change_fields
        if obj.role_code == User.Role.CONSULTANT:
            immutable_fields = tuple(
                field for field in immutable_fields if field != "username"
            )
        return (
            (
                "Immutable identity and access",
                {"fields": immutable_fields},
            ),
            (
                "Editable profile",
                {"fields": tuple(editable_profile_fields)},
            ),
        )

    @staticmethod
    def _correlation_id(request) -> UUID:
        value = getattr(request, "correlation_id", None)
        try:
            return value if isinstance(value, UUID) else UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return uuid4()

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        original = None
        requested_username = None
        requested_password = None
        if change:
            original = User.objects.get(pk=obj.pk)
            if original.role_code == User.Role.CONSULTANT:
                requested_username = form.cleaned_data.get("username")
                requested_password = form.cleaned_data.get("new_password1") or None
            for field_name in self.protected_change_fields:
                if field_name in {"created_at", "updated_at", "last_login"}:
                    continue
                setattr(obj, field_name, getattr(original, field_name))
        else:
            obj.is_synthetic = True
            obj.is_active = True
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)
        reason = str(form.cleaned_data["change_reason"]).strip()
        if change:
            changed_fields = sorted(
                set(form.changed_data) & {"full_name", "email", "phone"}
            )
            if changed_fields:
                AccountAuditRepository.record(
                    actor=request.user,
                    target=obj,
                    event_type=AccountAuditEvent.EventType.UPDATE,
                    before_values=AccountLifecycleService._snapshot(original),
                    after_values=AccountLifecycleService._snapshot(obj),
                    changed_fields=changed_fields,
                    reason=reason,
                    correlation_id=self._correlation_id(request),
                )
            credential_requested = bool(
                original.role_code == User.Role.CONSULTANT
                and (
                    requested_username != original.username
                    or requested_password
                )
            )
            if credential_requested:
                try:
                    AccountLifecycleService.update_consultant_credentials(
                        actor=request.user,
                        target=obj,
                        username=requested_username,
                        new_password=requested_password,
                        reason=reason,
                        correlation_id=self._correlation_id(request),
                    )
                except AccountLifecycleError as exc:
                    raise ValueError(f"{exc.code}: {exc}") from exc
                obj.refresh_from_db()
            return
        else:
            changed_fields = ["account_created"]
            event_type = AccountAuditEvent.EventType.CREATE
            before_values = {}
        AccountAuditRepository.record(
            actor=request.user,
            target=obj,
            event_type=event_type,
            before_values=before_values,
            after_values=AccountLifecycleService._snapshot(obj),
            changed_fields=changed_fields,
            reason=reason,
            correlation_id=self._correlation_id(request),
        )

    @admin.action(description="선택한 합성 계정 비활성화")
    def deactivate_accounts(self, request, queryset):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        candidates = list(
            queryset.filter(is_active=True, is_synthetic=True)
            .exclude(pk=request.user.pk)
            .exclude(is_superuser=True)
            .order_by("pk")
        )
        try:
            with transaction.atomic():
                for target in candidates:
                    AccountLifecycleService.deactivate(
                        actor=request.user,
                        target=target,
                        reason=reason,
                        correlation_id=self._correlation_id(request),
                    )
        except AccountLifecycleError as exc:
            self.message_user(
                request,
                f"{exc.code}: {exc}",
                level=messages.ERROR,
            )
            return
        self.message_user(
            request,
            f"Deactivated {len(candidates)} synthetic account(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="선택한 합성 계정 재활성화")
    def reactivate_accounts(self, request, queryset):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        candidates = list(
            queryset.filter(is_active=False, is_synthetic=True)
            .exclude(pk=request.user.pk)
            .exclude(is_superuser=True)
            .order_by("pk")
        )
        try:
            with transaction.atomic():
                for target in candidates:
                    AccountLifecycleService.reactivate(
                        actor=request.user,
                        target=target,
                        reason=reason,
                        correlation_id=self._correlation_id(request),
                    )
        except AccountLifecycleError as exc:
            self.message_user(
                request,
                f"{exc.code}: {exc}",
                level=messages.ERROR,
            )
            return
        self.message_user(
            request,
            f"Reactivated {len(candidates)} synthetic account(s).",
            level=messages.SUCCESS,
        )

@admin.register(CustomerProfile, site=waterbridge_admin_site)
class SyntheticCustomerProfileAdmin(admin.ModelAdmin):
    """Manage synthetic customer profiles while preserving referenced rows."""

    list_display = (
        "customer_no",
        "customer_name",
        "user",
        "is_deleted",
        "updated_at",
    )
    list_filter = ("deleted_at",)
    search_fields = ("customer_no", "customer_name", "user__username")
    ordering = ("customer_no",)
    actions = ("deactivate_profiles", "reactivate_profiles")
    action_form = AccountLifecycleActionForm
    readonly_fields = (
        "public_id",
        "legacy_id",
        "is_synthetic",
        "deleted_at",
        "deleted_by",
        "created_at",
        "updated_at",
    )

    @admin.display(boolean=True, description="비활성")
    def is_deleted(self, obj) -> bool:
        return obj.deleted_at is not None

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_synthetic=True)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(
                role_code=User.Role.CUSTOMER,
                is_synthetic=True,
            ).order_by("username")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        del request, obj
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def save_model(self, request, obj, form, change):
        obj.is_synthetic = True
        obj.full_clean()
        super().save_model(request, obj, form, change=change)

    @admin.action(description="선택한 고객 프로필 비활성화(논리 삭제)")
    def deactivate_profiles(self, request, queryset):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        if not reason:
            self.message_user(request, "변경 사유가 필요합니다.", messages.ERROR)
            return
        for profile in queryset.filter(deleted_at__isnull=True):
            profile.deleted_at = timezone.now()
            profile.deleted_by = request.user
            profile.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
            self.log_change(request, profile, f"비활성화: {reason}")

    @admin.action(description="선택한 고객 프로필 재활성화")
    def reactivate_profiles(self, request, queryset):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        if not reason:
            self.message_user(request, "변경 사유가 필요합니다.", messages.ERROR)
            return
        for profile in queryset.filter(deleted_at__isnull=False):
            profile.deleted_at = None
            profile.deleted_by = None
            profile.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
            self.log_change(request, profile, f"재활성화: {reason}")
