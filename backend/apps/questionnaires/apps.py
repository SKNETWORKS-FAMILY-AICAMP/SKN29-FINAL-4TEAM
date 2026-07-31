"""Questionnaires App 설정."""

from django.apps import AppConfig


class QuestionnairesConfig(AppConfig):
    """사전 문진 세션의 Django App 경계."""

    name = "apps.questionnaires"
    label = "questionnaires"
    verbose_name = "사전 문진"
