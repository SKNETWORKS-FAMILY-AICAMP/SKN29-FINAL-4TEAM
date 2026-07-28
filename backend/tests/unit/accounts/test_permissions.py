"""T-017 역할·소유자·배정자 권한 프리미티브 검증."""

from types import SimpleNamespace

from apps.accounts.permissions import (
    HasAllowedRole,
    IsAssignedActor,
    IsObjectOwner,
    scope_queryset_for_user,
)


def request_for(
    *,
    user_id: str = "DEMO-USER-001",
    role_code: str = "CUSTOMER",
    authenticated: bool = True,
    active: bool = True,
):
    return SimpleNamespace(
        user=SimpleNamespace(
            pk=user_id,
            role_code=role_code,
            is_authenticated=authenticated,
            is_active=active,
        )
    )


def test_role_permission_allows_only_configured_active_role():
    permission = HasAllowedRole()
    view = SimpleNamespace(allowed_roles={"CUSTOMER", "TECHNICIAN"})

    assert permission.has_permission(request_for(), view) is True
    assert permission.has_permission(
        request_for(role_code="CONSULTANT"),
        view,
    ) is False
    assert permission.has_permission(
        request_for(active=False),
        view,
    ) is False


def test_role_permission_fails_closed_without_view_contract():
    assert HasAllowedRole().has_permission(
        request_for(),
        SimpleNamespace(),
    ) is False


def test_user_without_active_flag_is_denied():
    request = SimpleNamespace(
        user=SimpleNamespace(
            pk="DEMO-USER-001",
            role_code="CUSTOMER",
            is_authenticated=True,
        )
    )
    view = SimpleNamespace(allowed_roles={"CUSTOMER"})

    assert HasAllowedRole().has_permission(request, view) is False


def test_object_scope_permissions_allow_only_configured_detail_requests():
    request = request_for()

    assert IsObjectOwner().has_permission(
        request,
        SimpleNamespace(detail=True, owner_attribute="customer_user"),
    ) is True
    assert IsAssignedActor().has_permission(
        request,
        SimpleNamespace(
            kwargs={"visit_id": "DEMO-VISIT-001"},
            lookup_url_kwarg="visit_id",
            assignee_attribute="technician",
        ),
    ) is True
    assert IsObjectOwner().has_permission(
        request,
        SimpleNamespace(detail=False, owner_attribute="customer_user"),
    ) is False
    assert IsAssignedActor().has_permission(
        request,
        SimpleNamespace(detail=True),
    ) is False


def test_owner_permission_accepts_direct_or_related_identifier():
    permission = IsObjectOwner()
    view = SimpleNamespace(owner_attribute="customer_user")
    request = request_for()

    assert permission.has_object_permission(
        request,
        view,
        SimpleNamespace(customer_user="DEMO-USER-001"),
    ) is True
    assert permission.has_object_permission(
        request,
        view,
        SimpleNamespace(
            customer_user=SimpleNamespace(pk="DEMO-USER-001")
        ),
    ) is True


def test_owner_permission_denies_other_or_unconfigured_scope():
    permission = IsObjectOwner()
    request = request_for()

    assert permission.has_object_permission(
        request,
        SimpleNamespace(owner_attribute="customer_user"),
        SimpleNamespace(customer_user="DEMO-USER-999"),
    ) is False
    assert permission.has_object_permission(
        request,
        SimpleNamespace(),
        SimpleNamespace(customer_user="DEMO-USER-001"),
    ) is False


def test_assigned_actor_permission_checks_configured_assignment():
    permission = IsAssignedActor()
    view = SimpleNamespace(assignee_attribute="technician")
    request = request_for(
        user_id="DEMO-TECH-001",
        role_code="TECHNICIAN",
    )

    assert permission.has_object_permission(
        request,
        view,
        SimpleNamespace(technician="DEMO-TECH-001"),
    ) is True
    assert permission.has_object_permission(
        request,
        view,
        SimpleNamespace(technician="DEMO-TECH-002"),
    ) is False


def test_object_scope_denies_unauthenticated_user():
    request = request_for(authenticated=False)
    obj = SimpleNamespace(
        customer_user="DEMO-USER-001",
        technician="DEMO-USER-001",
    )

    assert IsObjectOwner().has_object_permission(
        request,
        SimpleNamespace(owner_attribute="customer_user"),
        obj,
    ) is False
    assert IsAssignedActor().has_object_permission(
        request,
        SimpleNamespace(assignee_attribute="technician"),
        obj,
    ) is False


def test_role_and_owner_permissions_must_both_pass():
    view = SimpleNamespace(
        detail=True,
        allowed_roles={"CUSTOMER"},
        owner_attribute="customer_user",
    )
    obj = SimpleNamespace(customer_user="DEMO-USER-001")
    customer_request = request_for()
    consultant_request = request_for(role_code="CONSULTANT")
    role_permission = HasAllowedRole()
    owner_permission = IsObjectOwner()

    assert role_permission.has_permission(customer_request, view) is True
    assert owner_permission.has_permission(customer_request, view) is True
    assert owner_permission.has_object_permission(
        customer_request,
        view,
        obj,
    ) is True

    assert role_permission.has_permission(consultant_request, view) is False
    assert owner_permission.has_permission(consultant_request, view) is True
    assert owner_permission.has_object_permission(
        consultant_request,
        view,
        obj,
    ) is True


def test_role_and_assignee_permissions_must_both_pass():
    view = SimpleNamespace(
        detail=True,
        allowed_roles={"TECHNICIAN"},
        assignee_attribute="technician",
    )
    obj = SimpleNamespace(technician="DEMO-TECH-001")
    technician_request = request_for(
        user_id="DEMO-TECH-001",
        role_code="TECHNICIAN",
    )
    customer_request = request_for(
        user_id="DEMO-TECH-001",
        role_code="CUSTOMER",
    )
    role_permission = HasAllowedRole()
    assignee_permission = IsAssignedActor()

    assert role_permission.has_permission(technician_request, view) is True
    assert assignee_permission.has_permission(
        technician_request,
        view,
    ) is True
    assert assignee_permission.has_object_permission(
        technician_request,
        view,
        obj,
    ) is True

    assert role_permission.has_permission(customer_request, view) is False
    assert assignee_permission.has_permission(
        customer_request,
        view,
    ) is True
    assert assignee_permission.has_object_permission(
        customer_request,
        view,
        obj,
    ) is True


class FakeQueryset:
    def __init__(self):
        self.operation = None

    def filter(self, **kwargs):
        self.operation = ("filter", kwargs)
        return self

    def none(self):
        self.operation = ("none", {})
        return self


def test_customer_list_scope_filters_to_authenticated_owner():
    queryset = FakeQueryset()

    result = scope_queryset_for_user(
        queryset,
        request_for().user,
        customer_owner_lookup="customer_user_id",
        technician_assignee_lookup="technician_id",
    )

    assert result.operation == (
        "filter",
        {"customer_user_id": "DEMO-USER-001"},
    )


def test_technician_list_scope_filters_to_assignment():
    queryset = FakeQueryset()

    result = scope_queryset_for_user(
        queryset,
        request_for(
            user_id="DEMO-TECH-001",
            role_code="TECHNICIAN",
        ).user,
        customer_owner_lookup="customer_user_id",
        technician_assignee_lookup="technician_id",
    )

    assert result.operation == (
        "filter",
        {"technician_id": "DEMO-TECH-001"},
    )


def test_list_scope_fails_closed_without_lookup_or_explicit_privilege():
    missing_lookup = FakeQueryset()
    consultant = FakeQueryset()
    privileged = FakeQueryset()

    scope_queryset_for_user(
        missing_lookup,
        request_for().user,
    )
    scope_queryset_for_user(
        consultant,
        request_for(role_code="CONSULTANT").user,
        customer_owner_lookup="customer_user_id",
    )
    result = scope_queryset_for_user(
        privileged,
        request_for(role_code="CONSULTANT").user,
        privileged_roles={"CONSULTANT"},
    )

    assert missing_lookup.operation == ("none", {})
    assert consultant.operation == ("none", {})
    assert result is privileged
