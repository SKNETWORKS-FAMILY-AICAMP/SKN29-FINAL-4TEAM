"""Restricted Supervisor forms for consultation operations."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.consultations.models import Consultation


class SupervisorConsultationChangeForm(forms.ModelForm):
    """Expose only assignment and canonical editable consultation details."""

    operation_reason = forms.CharField(
        label="변경 사유",
        max_length=500,
        required=True,
    )

    class Meta:
        model = Consultation
        fields = (
            "consultant",
            "summary",
            "consultation_note",
            "additional_check",
            "customer_guidance",
            "outcome",
            "usage_guidance_status",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["consultant"].queryset = User.objects.filter(
            role_code=User.Role.CONSULTANT,
            is_active=True,
            is_synthetic=True,
        ).order_by("username")
        if self.instance.status not in {
            Consultation.Status.COMPLETED,
            Consultation.Status.CANCELLED,
        }:
            self.fields["consultant"].required = True

    def clean(self):
        cleaned_data = super().clean()
        business_changes = set(self.changed_data) - {"operation_reason"}
        if not business_changes:
            return cleaned_data
        if self.instance.status in {
            Consultation.Status.COMPLETED,
            Consultation.Status.CANCELLED,
        }:
            raise ValidationError("완료 또는 취소된 상담은 수정할 수 없습니다.")
        detail_changes = business_changes - {"consultant"}
        if detail_changes and self.instance.status != Consultation.Status.IN_PROGRESS:
            raise ValidationError(
                "상담 내용을 수정하려면 먼저 목록에서 상담 시작 작업을 실행해 주세요."
            )
        return cleaned_data
