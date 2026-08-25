FROM python:3.13.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_LOG_FILE=/dev/stdout

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 waterbridge \
    && useradd --uid 10001 --gid waterbridge --create-home waterbridge

WORKDIR /workspace/backend

COPY requirements/ /tmp/requirements/
RUN python -m pip install pip==26.0.1 \
    && python -m pip install \
      --constraint /tmp/requirements/constraints-py313.txt \
      --requirement /tmp/requirements/production.txt \
    && python -m pip check \
    && gunicorn --version | grep -Fx "gunicorn (version 26.0.0)"

COPY apps/ ./apps/
COPY common/ ./common/
COPY config/ ./config/
COPY integrations/ ./integrations/
COPY manage.py ./manage.py
COPY --from=state_machine_contracts . /workspace/contracts/state-machine/

RUN python -c \
    "from apps.workflow.contracts import load_state_machine_contract; load_state_machine_contract(); print('BACKEND_STATE_MACHINE_CONTRACT_PASS')" \
    && DJANGO_SETTINGS_MODULE=config.settings.test python -c \
    "import django; django.setup(); from django.conf import settings; settings.STATIC_ROOT='/workspace/backend/staticfiles'; from django.core.management import call_command; call_command('collectstatic', interactive=False, verbosity=0)" \
    && chown -R waterbridge:waterbridge /workspace/backend/staticfiles

USER waterbridge

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=8 \
  CMD python -c "import os,urllib.request; host=os.environ['DJANGO_ALLOWED_HOSTS'].split(',')[0].strip(); request=urllib.request.Request('http://127.0.0.1:8000/health', headers={'Host': host}); urllib.request.urlopen(request, timeout=3)" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--worker-class", "sync", "--access-logfile", "-", "--error-logfile", "-"]
