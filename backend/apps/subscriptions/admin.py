"""Supervisor Admin for synthetic customer subscriptions."""

from __future__ import annotations

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from apps.accounts.admin_forms import AccountLifecycleActionForm
from apps.accounts.admin_site import waterbridge_admin_site
from apps.accounts.models import CustomerProfile
from apps.subscriptions.models import CustomerSubscription


@admin.register(CustomerSubscription, site=waterbridge_admin_site)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    """Create and maintain synthetic subscriptions without deleting history."""

    list_display = (
        "contract_no",
        "customer",
        "product_model",
        "management_type_code",
        "status_code",
        "started_on",
        "ended_on",
    )
    list_filter = ("status_code", "management_type_code", "product_model")
    search_fields = (
        "contract_no",
        "serial_no",
        "customer__customer_no",
        "customer__customer_name",
    )
    ordering = ("contract_no",)
    actions = ("cancel_subscriptions",)
    action_form = AccountLifecycleActionForm
    readonly_fields = (
        "public_id",
        "source_customer_product_public_id",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(customer__is_synthetic=True)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = CustomerProfile.objects.filter(
                is_synthetic=True,
                deleted_at__isnull=True,
            ).order_by("customer_no")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        del request, obj
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def save_model(self, request, obj, form, change):
        if not obj.customer.is_synthetic or obj.customer.deleted_at is not None:
            raise ValueError("활성 합성 고객의 구독만 관리할 수 있습니다.")
        obj.full_clean()
        super().save_model(request, obj, form, change)

    @admin.action(description="선택한 구독 해지(이력 보존)")
    def cancel_subscriptions(self, request, queryset):
        reason = str(request.POST.get("lifecycle_reason") or "").strip()
        if not reason:
            self.message_user(request, "변경 사유가 필요합니다.", messages.ERROR)
            return
        changed = 0
        with transaction.atomic():
            for subscription in queryset.select_for_update().filter(
                status_code__in={
                    CustomerSubscription.Status.ACTIVE,
                    CustomerSubscription.Status.SUSPENDED,
                }
            ):
                subscription.status_code = CustomerSubscription.Status.CANCELLED
                subscription.ended_on = subscription.ended_on or timezone.localdate()
                subscription.full_clean()
                subscription.save(
                    update_fields=["status_code", "ended_on", "updated_at"]
                )
                self.log_change(request, subscription, f"구독 해지: {reason}")
                changed += 1
        self.message_user(request, f"구독 {changed}건을 해지했습니다.")
