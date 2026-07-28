"""Products App 설정."""

from django.apps import AppConfig


class ProductsConfig(AppConfig):
    """지원 제품 모델 레지스트리의 Django App 경계."""

    name = "apps.products"
    label = "products"
    verbose_name = "지원 제품"
