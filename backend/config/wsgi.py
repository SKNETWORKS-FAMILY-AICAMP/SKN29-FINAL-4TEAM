"""WSGI 서버 실행 진입점."""

import os

from django.core.wsgi import get_wsgi_application

from config.env import load_backend_env


load_backend_env()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()
