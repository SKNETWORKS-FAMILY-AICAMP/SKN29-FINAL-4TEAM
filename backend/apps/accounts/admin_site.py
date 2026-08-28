"""Water Bridge supervisor-only Django Admin site."""

from __future__ import annotations

from functools import update_wrapper

from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import PermissionDenied

from apps.accounts.supervisor_policy import is_waterbridge_supervisor


class SupervisorAuthenticationForm(AdminAuthenticationForm):
    """Reject every valid Django credential except the configured supervisor."""

    def confirm_login_allowed(self, user) -> None:
        super().confirm_login_allowed(user)
        if not is_waterbridge_supervisor(user):
            raise self.get_invalid_login_error()


class WaterBridgeAdminSite(AdminSite):
    """Internal operations UI with a fail-closed supervisor boundary."""

    site_header = "Water Bridge 운영 관리"
    site_title = "Water Bridge Admin"
    index_title = "고객·구독·상담 운영"
    login_form = SupervisorAuthenticationForm
    login_template = "waterbridge_admin/login.html"

    def has_permission(self, request) -> bool:
        return is_waterbridge_supervisor(request.user)

    def login(self, request, extra_context=None):
        if request.user.is_authenticated and not self.has_permission(request):
            raise PermissionDenied
        return super().login(request, extra_context=extra_context)

    def admin_view(self, view, cacheable=False):
        protected_view = super().admin_view(view, cacheable=cacheable)

        def inner(request, *args, **kwargs):
            if request.user.is_authenticated and not self.has_permission(request):
                raise PermissionDenied
            return protected_view(request, *args, **kwargs)

        return update_wrapper(inner, view)


waterbridge_admin_site = WaterBridgeAdminSite(name="admin")
