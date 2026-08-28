"""Read-mostly Supervisor Admin for synthetic inquiries."""

from __future__ import annotations

from django.contrib import admin, messages

from apps.accounts.admin_forms import AccountLifecycleActionForm
from apps.accounts.admin_site import waterbridge_admin_site
from apps.consultations.services.supervisor_consultation_service import (
    SupervisorConsultationService,
)
from apps.inquiries.models import Inquiry


@admin.register(Inquiry, site=waterbridge_admin_site)
class InquiryAdmin(admin.ModelAdmin):
    """Expose inquiry state and cancellation without direct field mutation."""

    list_display = (
        "inquiry_code",
        "subscription",
        "status_code",
        "assigned_user",
        "priority_code",
        "created_at",
    )
    list_filter = ("status_code", "priority_code", "channel_code")
    search_fields = (
        "inquiry_code",
        "subscription__contract_no",
        "assigned_user__username",
    )
    ordering = ("-created_at",)
    actions = ("cancel_inquiries",)
    action_form = AccountLifecycleActionForm

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                initiated_by__is_synthetic=True,
                subscription__customer__is_synthetic=True,
            )
            .select_related("subscription", "assigned_user")
        )

    def get_readonly_fields(self, request, obj=None):
        del request, obj
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        del request
        return False

    def has_delete_permission(self, request, obj=None):
        del request, obj
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="선택한 문의·상담 취소")
    def cancel_inquiries(self, request, queryset):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        if not reason:
            self.message_user(request, "취소 사유가 필요합니다.", messages.ERROR)
            return
        completed = 0
        for inquiry in queryset.order_by("pk"):
            try:
                SupervisorConsultationService.cancel_inquiry(
                    actor=request.user,
                    inquiry_id=inquiry.pk,
                    reason=reason,
                )
                self.log_change(request, inquiry, f"문의·상담 취소: {reason}")
                completed += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"{inquiry.inquiry_code}: {exc}",
                    level=messages.ERROR,
                )
        self.message_user(request, f"문의·상담 취소 {completed}건 완료")
