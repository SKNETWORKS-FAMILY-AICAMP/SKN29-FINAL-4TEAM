"""자동 테스트 환경 설정."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("DJANGO_TIME_ZONE", "UTC")

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CORS_ALLOWED_ORIGINS = ["https://approved.example"]
CONTRACT_EMAIL_ENCRYPTION_KEY = (
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)
CONTRACT_EMAIL_HMAC_KEY = (
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
)
CONTRACT_EMAIL_KEY_VERSION = "test-v1"
P1_AUTH_HMAC_SECRET = "test-p1-auth-secret-32-bytes-minimum-value"
P1_AUTH_OTP_ENCRYPTION_KEY = (
    "AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI="
)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
P1_AUTH_EMAIL_REDIRECT_TO = "p1-auth-test@waterbridge.invalid"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DJANGO_TEST_DATABASE_NAME", ":memory:"),
    }
}
