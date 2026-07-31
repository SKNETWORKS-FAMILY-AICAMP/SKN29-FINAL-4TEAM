"""Evidence App 설정."""

from django.apps import AppConfig


class EvidenceConfig(AppConfig):
    """공식 지식 수집과 근거 추적 경계를 등록한다."""

    name = "apps.evidence"
    label = "evidence"
    verbose_name = "지식 및 근거"
