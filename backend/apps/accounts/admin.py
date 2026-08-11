"""Django Admin boundary for synthetic accounts only."""

from __future__ import annotations

from uuid import UUID, uuid4

from django.contrib import admin, messages
from django.db import transaction

from apps.accounts.admin_forms import (
    AccountLifecycleActionForm,
    SyntheticUserAddForm,
    SyntheticUserChangeForm,
)
from apps.accounts.models import AccountAuditEvent, User
from apps.accounts.repositories.account_audit_repository import (
    AccountAuditRepository,
)
from apps.accounts.services.account_lifecycle_service import (
    AccountLifecycleError,
    AccountLifecycleService,
)


@admin.register(User)
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
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
    )

    @staticmethod
    def _is_operator_staff(request) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and user.role_code == User.Role.OPERATOR
        )

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
        return self.protected_change_fields if obj else ()

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
        return (
            (
                "Immutable identity and access",
                {"fields": self.protected_change_fields},
            ),
            (
                "Editable profile",
                {
                    "fields": (
                        "full_name",
                        "email",
                        "phone",
                        "change_reason",
                    )
                },
            ),
        )

    @staticmethod
    def _correlation_id(request) -> UUID:
        value = getattr(request, "correlation_id", None)
        try:
            return value if isinstance(value, UUID) else UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return uuid4()

    def save_model(self, request, obj, form, change):
        original = None
        if change:
            original = User.objects.get(pk=obj.pk)
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
            if not changed_fields:
                return
            event_type = AccountAuditEvent.EventType.UPDATE
            before_values = AccountLifecycleService._snapshot(original)
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

    @admin.action(description="Deactivate selected synthetic accounts")
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

    @admin.action(description="Reactivate selected synthetic accounts")
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


admin.site.site_header = "WaterCare Internal Administration"
admin.site.site_title = "WaterCare Admin"
admin.site.index_title = "Synthetic account operations"
