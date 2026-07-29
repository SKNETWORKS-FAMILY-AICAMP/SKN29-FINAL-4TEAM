"""Subscriptions App 설정."""

from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    """고객과 제품 구독 관계의 Django App 경계."""

    name = "apps.subscriptions"
    label = "subscriptions"
    verbose_name = "고객 구독"
