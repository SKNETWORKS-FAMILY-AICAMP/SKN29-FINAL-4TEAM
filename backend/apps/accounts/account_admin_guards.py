"""Prevent direct M2M changes from bypassing T-017C lifecycle auditing."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from apps.accounts.account_admin_policy import (
    ACCOUNT_ADMIN_GROUP,
)
from apps.accounts.models import User


_M2M_CHANGE_ALLOWED: ContextVar[bool] = ContextVar(
    "account_admin_m2m_change_allowed",
    default=False,
)


@contextmanager
def allow_account_admin_m2m_change():
    """Allow only the lifecycle service to mutate the fixed policy M2M rows."""

    token = _M2M_CHANGE_ALLOWED.set(True)
    try:
        yield
    finally:
        _M2M_CHANGE_ALLOWED.reset(token)


def _blocked() -> None:
    raise ValidationError(
        "The fixed account-administrator policy must be changed through "
        "AccountLifecycleService."
    )


@receiver(m2m_changed, sender=User.groups.through)
def guard_account_admin_membership(
    sender,
    instance,
    action,
    reverse,
    model,
    pk_set,
    **kwargs,
):
    del sender, model, kwargs
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return
    if _M2M_CHANGE_ALLOWED.get():
        return
    fixed_group = Group.objects.filter(name=ACCOUNT_ADMIN_GROUP).first()
    if fixed_group is None:
        return
    if reverse:
        touches_policy = isinstance(instance, Group) and instance.pk == fixed_group.pk
    elif action == "pre_clear":
        touches_policy = instance.groups.filter(pk=fixed_group.pk).exists()
    else:
        touches_policy = fixed_group.pk in (pk_set or set())
    if touches_policy:
        _blocked()


@receiver(m2m_changed, sender=Group.permissions.through)
def guard_account_admin_permissions(
    sender,
    instance,
    action,
    reverse,
    model,
    pk_set,
    **kwargs,
):
    del sender, model, kwargs
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return
    if _M2M_CHANGE_ALLOWED.get():
        return
    fixed_group = Group.objects.filter(name=ACCOUNT_ADMIN_GROUP).first()
    if fixed_group is None:
        return
    if reverse:
        if action == "pre_clear":
            touches_policy = instance.group_set.filter(pk=fixed_group.pk).exists()
        else:
            touches_policy = fixed_group.pk in set(pk_set or set())
    else:
        touches_policy = isinstance(instance, Group) and instance.pk == fixed_group.pk
    if touches_policy:
        _blocked()
