"""P1 OTP와 Ticket 사용 직전의 현재 계약 권한 재검증."""

from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.models import (
    ContractEmailContact,
    CustomerAccountLink,
    CustomerProfile,
    P1AuthOtpChallenge,
    User,
)
from apps.subscriptions.models import CustomerSubscription


@dataclass(frozen=True)
class CurrentAuthTarget:
    customer: CustomerProfile
    contact: ContractEmailContact
    user: User | None
    subscription: CustomerSubscription | None


class P1AuthTargetService:
    @staticmethod
    def lock_current(
        challenge: P1AuthOtpChallenge,
    ) -> CurrentAuthTarget | None:
        """호출자의 atomic 안에서 계약·연락처·계정 철회를 잠금 검증한다."""

        if not challenge.customer_id or not challenge.contact_id:
            return None
        customer = (
            CustomerProfile.objects.select_for_update(of=("self",))
            .filter(
                pk=challenge.customer_id,
                is_synthetic=True,
                deleted_at__isnull=True,
            )
            .first()
        )
        if customer is None:
            return None
        contact = (
            ContractEmailContact.objects.select_for_update(of=("self",))
            .filter(
                pk=challenge.contact_id,
                customer=customer,
                is_active=True,
                is_primary=True,
                data_classification="synthetic",
            )
            .first()
        )
        if contact is None:
            return None

        subscriptions = (
            CustomerSubscription.objects.select_for_update(of=("self",))
            .filter(
                customer=customer,
                status_code=CustomerSubscription.Status.ACTIVE,
            )
            .order_by("pk")
        )
        if challenge.subscription_id:
            subscriptions = subscriptions.filter(pk=challenge.subscription_id)
        subscription = subscriptions.first()
        if subscription is None:
            return None

        if challenge.purpose == P1AuthOtpChallenge.Purpose.SIGNUP:
            active_link = (
                CustomerAccountLink.objects.select_for_update(of=("self",))
                .filter(customer=customer, is_active=True)
                .exists()
            )
            if customer.user_id is not None or active_link:
                return None
            return CurrentAuthTarget(
                customer=customer,
                contact=contact,
                user=None,
                subscription=(
                    subscription if challenge.subscription_id else None
                ),
            )

        if not challenge.user_id or customer.user_id != challenge.user_id:
            return None
        user = (
            User.objects.select_for_update(of=("self",))
            .filter(
                pk=challenge.user_id,
                is_active=True,
                role_code=User.Role.CUSTOMER,
                is_synthetic=True,
            )
            .first()
        )
        if user is None:
            return None
        active_link = (
            CustomerAccountLink.objects.select_for_update(of=("self",))
            .filter(customer=customer, user=user, is_active=True)
            .exists()
        )
        if not active_link:
            return None
        return CurrentAuthTarget(
            customer=customer,
            contact=contact,
            user=user,
            subscription=(subscription if challenge.subscription_id else None),
        )
