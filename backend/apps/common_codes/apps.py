"""Common Codes App 설정."""

from django.apps import AppConfig


class CommonCodesConfig(AppConfig):
    """업무 공통코드의 표시·정렬·메타데이터 레지스트리 경계."""

    name = "apps.common_codes"
    label = "common_codes"
    verbose_name = "공통코드"
