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

# SMTP 자격증명이 없는 로컬 E2E에서는 OTP를 Git 제외 Runtime 폴더에
# RFC822 파일로 남긴다. SMTP 환경변수가 있으면 base 설정이 그대로
# 실제 시험 수신함 redirect를 사용한다.
if not os.getenv("DJANGO_EMAIL_BACKEND"):
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / ".runtime" / "p1-auth-emails"  # noqa: F405
    EMAIL_FILE_PATH.mkdir(parents=True, exist_ok=True)
if not P1_AUTH_EMAIL_REDIRECT_TO:  # noqa: F405
    P1_AUTH_EMAIL_REDIRECT_TO = "p1-local-inbox@waterbridge.invalid"
