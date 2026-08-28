"""Supervisor Admin for consultation assignment and lifecycle operations."""

from __future__ import annotations

from django.contrib import admin, messages

from apps.accounts.admin_forms import AccountLifecycleActionForm
from apps.accounts.admin_site import waterbridge_admin_site
from apps.consultations.admin_forms import SupervisorConsultationChangeForm
from apps.consultations.models import Consultation
from apps.consultations.services.supervisor_consultation_service import (
    SupervisorConsultationService,
)


@admin.register(Consultation, site=waterbridge_admin_site)
class ConsultationAdmin(admin.ModelAdmin):
    """Operate one synthetic consultation through canonical workflow services."""

    form = SupervisorConsultationChangeForm
    list_display = (
        "consultation_code",
        "inquiry",
        "consultant",
        "status",
        "outcome",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "outcome", "consultant")
    search_fields = (
        "consultation_code",
        "inquiry__inquiry_code",
        "consultant__username",
    )
    ordering = ("-created_at",)
    actions = (
        "start_consultations",
        "confirm_consultations",
        "complete_consultations",
        "cancel_consultations",
    )
    action_form = AccountLifecycleActionForm
    readonly_fields = (
        "public_id",
        "consultation_code",
        "inquiry",
        "sequence",
        "status",
        "ai_draft_summary",
        "confirmed_summary",
        "summary_confirmed_at",
        "state_version",
        "idempotency_key",
        "correlation_id",
        "started_at",
        "completed_at",
        "data_classification",
        "created_at",
    )
    fieldsets = (
        (
            "식별 및 현재 상태",
            {
                "fields": (
                    "public_id",
                    "consultation_code",
                    "inquiry",
                    "sequence",
                    "status",
                    "state_version",
                )
            },
        ),
        (
            "담당 및 상담 내용",
            {
                "fields": (
                    "consultant",
                    "summary",
                    "consultation_note",
                    "additional_check",
                    "customer_guidance",
                    "outcome",
                    "usage_guidance_status",
                    "operation_reason",
                )
            },
        ),
        (
            "확정 및 이력",
            {
                "fields": (
                    "ai_draft_summary",
                    "confirmed_summary",
                    "summary_confirmed_at",
                    "started_at",
                    "completed_at",
                    "idempotency_key",
                    "correlation_id",
                    "data_classification",
                    "created_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                data_classification=Consultation.DataClassification.SYNTHETIC,
                inquiry__initiated_by__is_synthetic=True,
                inquiry__subscription__customer__is_synthetic=True,
            )
            .select_related("inquiry", "consultant")
        )

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

    def save_model(self, request, obj, form, change):
        del change
        original = Consultation.objects.get(pk=obj.pk)
        reason = str(form.cleaned_data["operation_reason"]).strip()
        if "consultant" in form.changed_data:
            obj = SupervisorConsultationService.reassign(
                actor=request.user,
                consultation_id=obj.pk,
                target_consultant_id=form.cleaned_data["consultant"].pk,
                reason=reason,
            )
            self.log_change(request, obj, f"상담 담당자 변경: {reason}")

        request_field_map = {
            "summary": "summary",
            "consultation_note": "consultation_note",
            "additional_check": "additional_check",
            "customer_guidance": "customer_guidance",
            "outcome": "result_code",
            "usage_guidance_status": "usage_guidance_status",
        }
        values = {
            request_name: form.cleaned_data[model_name]
            for model_name, request_name in request_field_map.items()
            if model_name in form.changed_data
        }
        if values:
            obj = SupervisorConsultationService.update_details(
                actor=request.user,
                consultation_id=original.pk,
                values=values,
            )
            self.log_change(request, obj, f"상담 내용 수정: {reason}")
        obj.refresh_from_db()

    def _run_action(self, request, queryset, method_name: str, label: str):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        if not reason:
            self.message_user(request, "작업 사유가 필요합니다.", messages.ERROR)
            return
        completed = 0
        for consultation in queryset.order_by("pk"):
            try:
                if method_name == "cancel_consultation":
                    SupervisorConsultationService.cancel_consultation(
                        actor=request.user,
                        consultation_id=consultation.pk,
                        reason=reason,
                    )
                else:
                    method = getattr(SupervisorConsultationService, method_name)
                    method(actor=request.user, consultation_id=consultation.pk)
                self.log_change(request, consultation, f"{label}: {reason}")
                completed += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"{consultation.consultation_code}: {exc}",
                    level=messages.ERROR,
                )
        self.message_user(request, f"{label} {completed}건 완료")

    @admin.action(description="선택한 상담 시작")
    def start_consultations(self, request, queryset):
        self._run_action(request, queryset, "start", "상담 시작")

    @admin.action(description="선택한 상담 요약 확정")
    def confirm_consultations(self, request, queryset):
        self._run_action(request, queryset, "confirm", "요약 확정")

    @admin.action(description="선택한 상담 완료")
    def complete_consultations(self, request, queryset):
        self._run_action(request, queryset, "complete", "상담 완료")

    @admin.action(description="선택한 상담을 포함한 문의 전체 취소")
    def cancel_consultations(self, request, queryset):
        self._run_action(
            request,
            queryset,
            "cancel_consultation",
            "문의 전체 취소",
        )
