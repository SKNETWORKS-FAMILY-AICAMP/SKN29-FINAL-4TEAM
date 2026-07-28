"""자동 테스트 환경 설정."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("DJANGO_TIME_ZONE", "UTC")

from .base import *  # noqa: F403


DEBUG = False
SECRET_KEY = "test-only-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CORS_ALLOWED_ORIGINS = ["https://approved.example"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DJANGO_TEST_DATABASE_NAME", ":memory:"),
    }
}
