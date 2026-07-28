"""로컬 개발 환경 설정."""

import os

from .base import *  # noqa: F403


require_environment_variables(  # noqa: F405
    "DJANGO_SECRET_KEY",
    "DJANGO_TIME_ZONE",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "AI_SERVICE_BASE_URL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
