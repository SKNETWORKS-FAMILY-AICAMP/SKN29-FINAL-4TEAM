"""Care App 설정."""

from django.apps import AppConfig


class CareConfig(AppConfig):
    """제품 케어 일정과 처리 이력의 Django App 경계."""

    name = "apps.care"
    label = "care"
    verbose_name = "제품 케어"
