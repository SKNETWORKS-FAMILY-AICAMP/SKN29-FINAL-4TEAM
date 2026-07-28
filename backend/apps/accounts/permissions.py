"""역할·소유자·배정자 범위를 기본 거부 방식으로 검사한다."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework.permissions import BasePermission


def _active_authenticated_user(request: Any) -> Any | None:
    user = getattr(request, "user", None)
    if user is None:
        return None
    if not bool(getattr(user, "is_authenticated", False)):
        return None
    if not bool(getattr(user, "is_active", False)):
        return None
    return user


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    candidate = getattr(value, "pk", value)
    if candidate is None:
        return None
    normalized = str(candidate).strip()
    return normalized or None


def _object_scope_identifier(instance: Any, attribute_name: str) -> str | None:
    if not attribute_name:
        return None
    return _identifier(getattr(instance, attribute_name, None))


def _is_detail_request(view: Any) -> bool:
    if bool(getattr(view, "detail", False)):
        return True

    kwargs = getattr(view, "kwargs", None)
    if not isinstance(kwargs, Mapping):
        return False
    lookup_key = (
        getattr(view, "lookup_url_kwarg", None)
        or getattr(view, "lookup_field", None)
        or "pk"
    )
    return lookup_key in kwargs


def _has_object_scope_prerequisites(
    request: Any,
    view: Any,
    attribute_setting: str,
) -> bool:
    if _active_authenticated_user(request) is None:
        return False
    if not str(getattr(view, attribute_setting, "")).strip():
        return False
    return _is_detail_request(view)


def scope_queryset_for_user(
    queryset: Any,
    user: Any,
    *,
    customer_owner_lookup: str = "",
    technician_assignee_lookup: str = "",
    privileged_roles: set[str] | frozenset[str] = frozenset(),
):
    """목록 조회를 역할별 owner·assignee 조건으로 제한한다."""

    request = type("_ScopeRequest", (), {"user": user})()
    active_user = _active_authenticated_user(request)
    if active_user is None:
        return queryset.none()

    role_code = str(getattr(active_user, "role_code", "")).strip()
    user_id = _identifier(active_user)
    if (
        role_code == "CUSTOMER"
        and customer_owner_lookup
        and user_id
    ):
        return queryset.filter(
            **{customer_owner_lookup: user_id}
        )
    if (
        role_code == "TECHNICIAN"
        and technician_assignee_lookup
        and user_id
    ):
        return queryset.filter(
            **{technician_assignee_lookup: user_id}
        )
    if role_code in set(privileged_roles):
        return queryset
    return queryset.none()


class OwnedOrAssignedQuerysetMixin:
    """ViewSet 목록에 owner·assignee 범위를 빠뜨리지 않게 하는 Mixin."""

    customer_owner_lookup = ""
    technician_assignee_lookup = ""
    privileged_roles: set[str] | frozenset[str] = frozenset()

    def get_queryset(self):
        queryset = super().get_queryset()
        return scope_queryset_for_user(
            queryset,
            getattr(self.request, "user", None),
            customer_owner_lookup=self.customer_owner_lookup,
            technician_assignee_lookup=self.technician_assignee_lookup,
            privileged_roles=self.privileged_roles,
        )


class HasAllowedRole(BasePermission):
    """View의 ``allowed_roles``에 명시된 활성 사용자만 허용한다."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = _active_authenticated_user(request)
        allowed_roles = getattr(view, "allowed_roles", None)
        if user is None or not allowed_roles:
            return False

        role_code = str(getattr(user, "role_code", "")).strip()
        return bool(role_code and role_code in set(allowed_roles))


class IsObjectOwner(BasePermission):
    """View가 지정한 소유자 필드와 현재 사용자 ID가 같을 때 허용한다."""

    def has_permission(self, request: Any, view: Any) -> bool:
        return _has_object_scope_prerequisites(
            request,
            view,
            "owner_attribute",
        )

    def has_object_permission(
        self,
        request: Any,
        view: Any,
        obj: Any,
    ) -> bool:
        user = _active_authenticated_user(request)
        owner_attribute = str(
            getattr(view, "owner_attribute", "")
        ).strip()
        if user is None or not owner_attribute:
            return False

        return _identifier(user) == _object_scope_identifier(
            obj,
            owner_attribute,
        )


class IsAssignedActor(BasePermission):
    """View가 지정한 배정자 필드와 현재 사용자 ID가 같을 때 허용한다."""

    def has_permission(self, request: Any, view: Any) -> bool:
        return _has_object_scope_prerequisites(
            request,
            view,
            "assignee_attribute",
        )

    def has_object_permission(
        self,
        request: Any,
        view: Any,
        obj: Any,
    ) -> bool:
        user = _active_authenticated_user(request)
        assignee_attribute = str(
            getattr(view, "assignee_attribute", "")
        ).strip()
        if user is None or not assignee_attribute:
            return False

        return _identifier(user) == _object_scope_identifier(
            obj,
            assignee_attribute,
        )
