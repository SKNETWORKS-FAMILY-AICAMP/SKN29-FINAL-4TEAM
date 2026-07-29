from django.contrib import admin

from .models import (
    ServiceCall,
    TechnicianLocation,
    VisitRequest,
)


@admin.register(ServiceCall)
class ServiceCallAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer_name",
        "product_model",
        "status",
        "technician_name",
        "requested_at",
        "updated_at",
    )
    list_filter = ("status", "result_type")
    search_fields = (
        "customer_name",
        "customer_phone",
        "customer_address",
        "technician_name",
        "product_model",
    )
    readonly_fields = (
        "requested_at",
        "accepted_at",
        "departed_at",
        "arrived_at",
        "completed_at",
        "cancelled_at",
        "updated_at",
    )


admin.site.register(VisitRequest)
admin.site.register(TechnicianLocation)
