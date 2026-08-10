"""WSGI 서버 실행 진입점."""

import os

from django.core.wsgi import get_wsgi_application

from config.env import load_backend_env


PRODUCTION_SETTINGS_MODULE = "config.settings.production"
os.environ["DJANGO_SETTINGS_MODULE"] = PRODUCTION_SETTINGS_MODULE
load_backend_env(settings_module=PRODUCTION_SETTINGS_MODULE)

application = get_wsgi_application()
