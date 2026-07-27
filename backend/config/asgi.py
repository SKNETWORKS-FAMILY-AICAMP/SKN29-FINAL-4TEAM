"""ASGI 서버 실행 진입점."""

import os

from django.core.asgi import get_asgi_application

from config.env import load_backend_env


load_backend_env()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()
