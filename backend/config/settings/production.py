"""Kubernetes Demo 배포 환경 설정.

배포 비밀값·허용 호스트·서버 구성은 배포 환경변수로 주입한다.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


DEBUG = False

require_environment_variables(  # noqa: F405
    "DJANGO_SECRET_KEY",
    "DJANGO_TIME_ZONE",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "AI_SERVICE_BASE_URL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)

if SECRET_KEY == DEVELOPMENT_SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("배포 환경에는 DJANGO_SECRET_KEY가 필요합니다.")

if not os.getenv("DJANGO_ALLOWED_HOSTS"):
    raise ImproperlyConfigured(
        "배포 환경에는 명시적인 DJANGO_ALLOWED_HOSTS가 필요합니다."
    )
