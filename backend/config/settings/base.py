"""앱, 미들웨어, DB, REST Framework 공통 설정."""

import base64
import binascii
import hashlib
import hmac
import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.env import (
    PostgresConnectionConfigurationError,
    build_postgres_connection_options,
    load_backend_env,
)


BASE_DIR = Path(__file__).resolve().parents[2]
load_backend_env(
    settings_module=os.getenv("DJANGO_SETTINGS_MODULE"),
)

DEVELOPMENT_SECRET_KEY = "development-only-not-for-deployment"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)


def _local_derived_secret(label: str) -> str:
    """로컬에서만 Django Secret으로부터 용도 분리 키를 유도한다."""

    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        label.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


IS_LOCAL_SETTINGS = os.getenv("DJANGO_SETTINGS_MODULE") == "config.settings.local"
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1,[::1]",
    ).split(",")
    if host.strip()
]
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
AI_SERVICE_BASE_URL = os.getenv("AI_SERVICE_BASE_URL", "")
AI_SERVICE_MODE = os.getenv("AI_SERVICE_MODE", "local")
AI_SERVICE_TIMEOUT_SECONDS = 30.0
AI_HANDOFF_INTERNAL_TOKEN = os.getenv("AI_HANDOFF_INTERNAL_TOKEN", "")
AI_MODEL_PROVIDER = os.getenv("AI_MODEL_PROVIDER", "waterbridge-local")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "single-rag-pipeline")
AI_PROMPT_VERSION = os.getenv("AI_PROMPT_VERSION", "unknown")
CONTRACT_EMAIL_ENCRYPTION_KEY = os.getenv(
    "CONTRACT_EMAIL_ENCRYPTION_KEY",
    _local_derived_secret("contract-email-encryption")
    if IS_LOCAL_SETTINGS
    else "",
)
CONTRACT_EMAIL_HMAC_KEY = os.getenv(
    "CONTRACT_EMAIL_HMAC_KEY",
    _local_derived_secret("contract-email-lookup")
    if IS_LOCAL_SETTINGS
    else "",
)
CONTRACT_EMAIL_KEY_VERSION = os.getenv(
    "CONTRACT_EMAIL_KEY_VERSION",
    "local-derived-v1" if IS_LOCAL_SETTINGS else "",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.common_codes.apps.CommonCodesConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.products.apps.ProductsConfig",
    "apps.subscriptions.apps.SubscriptionsConfig",
    "apps.inquiries.apps.InquiriesConfig",
    "apps.questionnaires.apps.QuestionnairesConfig",
    "apps.consultations.apps.ConsultationsConfig",
    "apps.visits.apps.VisitsConfig",
    "apps.care.apps.CareConfig",
    "apps.evidence.apps.EvidenceConfig",
    "apps.workflow.apps.WorkflowConfig",
    "apps.audit.apps.AuditConfig",
    "apps.operations.apps.OperationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.correlation_id.CorrelationIdMiddleware",
    "common.middleware.cors.CorsAllowlistMiddleware",
    "common.middleware.request_logging.RequestLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

POSTGRES_OPTIONS: dict[str, str | int] = {}
if os.getenv("DJANGO_SETTINGS_MODULE") != "config.settings.test":
    try:
        POSTGRES_OPTIONS = build_postgres_connection_options(
            os.environ,
            base_dir=BASE_DIR,
            require_verify_full=(
                os.getenv("DJANGO_SETTINGS_MODULE")
                == "config.settings.production"
            ),
        )
    except PostgresConnectionConfigurationError as exc:
        missing = ", ".join(exc.missing_keys)
        suffix = f", missing={missing}" if missing else ""
        raise ImproperlyConfigured(
            "PostgreSQL 연결 환경 설정이 올바르지 않습니다: "
            f"reason={exc.reason}{suffix}"
        ) from None

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "waterbridge"),
        "USER": os.getenv("POSTGRES_USER", "watercare"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        **({"OPTIONS": POSTGRES_OPTIONS} if POSTGRES_OPTIONS else {}),
    }
}

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE")
if not TIME_ZONE:
    raise ImproperlyConfigured(
        "DJANGO_TIME_ZONE이 필요합니다. 로컬 기준값은 Asia/Seoul입니다."
    )
USE_I18N = True
USE_TZ = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "common.authentication.jwt_authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.handler.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Water Bridge API",
    "DESCRIPTION": (
        "Water Bridge Backend Runtime API 문서입니다. "
        "Health 항목은 인증 없이 직접 실행할 수 있습니다."
    ),
    "VERSION": "0.8.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
    },
}

AUTH_USER_MODEL = "accounts.User"


def require_environment_variables(*names: str) -> None:
    missing = sorted(
        name
        for name in names
        if not os.getenv(name, "").strip()
    )
    if missing:
        raise ImproperlyConfigured(
            "필수 환경변수가 없습니다: " + ", ".join(missing)
        )


def require_urlsafe_base64_32(*names: str) -> None:
    invalid = []
    for name in names:
        try:
            decoded = base64.urlsafe_b64decode(
                os.getenv(name, "").encode("ascii")
            )
        except (binascii.Error, ValueError, UnicodeEncodeError):
            decoded = b""
        if len(decoded) != 32:
            invalid.append(name)
    if invalid:
        raise ImproperlyConfigured(
            "32-byte URL-safe base64 환경변수가 올바르지 않습니다: "
            + ", ".join(sorted(invalid))
        )


def require_minimum_secret_bytes(name: str, minimum: int = 32) -> None:
    if len(os.getenv(name, "").encode("utf-8")) < minimum:
        raise ImproperlyConfigured(
            f"{name}은 {minimum}-byte 이상이어야 합니다."
        )


def positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"{name}은 양의 정수여야 합니다."
        ) from exc
    if value <= 0:
        raise ImproperlyConfigured(
            f"{name}은 양의 정수여야 합니다."
        )
    return value


def strict_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    normalized = raw_value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ImproperlyConfigured(
        f"{name}은 true 또는 false여야 합니다."
    )


def sha256_hmac_allowlist_env(
    name: str,
    *,
    expected_count: int,
) -> frozenset[str]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return frozenset()
    values = [item.strip() for item in raw_value.split(",")]
    if (
        len(values) != expected_count
        or len(set(values)) != expected_count
        or any(
            len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
            for item in values
        )
    ):
        raise ImproperlyConfigured(
            f"{name}은 중복 없는 소문자 SHA-256 HMAC "
            f"{expected_count}건이어야 합니다."
        )
    return frozenset(values)


P1_AUTH_HMAC_SECRET = os.getenv(
    "P1_AUTH_HMAC_SECRET",
    _local_derived_secret("p1-auth-hmac") if IS_LOCAL_SETTINGS else "",
)
P1_AUTH_OTP_ENCRYPTION_KEY = os.getenv(
    "P1_AUTH_OTP_ENCRYPTION_KEY",
    _local_derived_secret("p1-auth-otp-encryption")
    if IS_LOCAL_SETTINGS
    else "",
)
P1_AUTH_OTP_TTL_SECONDS = positive_int_env(
    "P1_AUTH_OTP_TTL_SECONDS", 300
)
P1_AUTH_OTP_RESEND_SECONDS = positive_int_env(
    "P1_AUTH_OTP_RESEND_SECONDS", 60
)
P1_AUTH_OTP_MAX_FAILURES = positive_int_env(
    "P1_AUTH_OTP_MAX_FAILURES", 5
)
P1_AUTH_TICKET_TTL_SECONDS = positive_int_env(
    "P1_AUTH_TICKET_TTL_SECONDS", 300
)
P1_AUTH_IDEMPOTENCY_REPLAY_TTL_SECONDS = positive_int_env(
    "P1_AUTH_IDEMPOTENCY_REPLAY_TTL_SECONDS", 300
)
P1_AUTH_CHALLENGE_WINDOW_HOURS = positive_int_env(
    "P1_AUTH_CHALLENGE_WINDOW_HOURS", 1
)
P1_AUTH_CHALLENGE_MAX_PER_WINDOW = positive_int_env(
    "P1_AUTH_CHALLENGE_MAX_PER_WINDOW", 5
)
P1_AUTH_LOGIN_WINDOW_SECONDS = positive_int_env(
    "P1_AUTH_LOGIN_WINDOW_SECONDS", 300
)
P1_AUTH_LOGIN_MAX_FAILURES = positive_int_env(
    "P1_AUTH_LOGIN_MAX_FAILURES", 5
)
P1_AUTH_EMAIL_REDIRECT_TO = os.getenv("P1_AUTH_EMAIL_REDIRECT_TO", "")
P1_AUTH_RUNTIME_ENVIRONMENT = os.getenv(
    "P1_AUTH_RUNTIME_ENVIRONMENT", ""
).strip()
P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED = strict_bool_env(
    "P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED",
    False,
)
P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS = (
    sha256_hmac_allowlist_env(
        "P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS",
        expected_count=6,
    )
)

EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.dummy.EmailBackend",
)
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = positive_int_env("DJANGO_EMAIL_PORT", 587)
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = positive_int_env("DJANGO_EMAIL_TIMEOUT_SECONDS", 10)
DEFAULT_FROM_EMAIL = os.getenv(
    "DJANGO_DEFAULT_FROM_EMAIL",
    "no-reply@waterbridge.invalid",
)


DEMO_LOGIN_ENABLED = (
    os.getenv("DJANGO_DEMO_LOGIN_ENABLED", "false").lower() == "true"
)
DEMO_LOGIN_CODES = {
    code.strip()
    for code in os.getenv("DJANGO_DEMO_LOGIN_CODES", "").split(",")
    if code.strip()
}

# The username is not a secret. It selects the only account allowed to enter
# the internal Django Admin. The password is consumed only by the bootstrap
# command and is never loaded into application settings.
WATERBRIDGE_SUPERVISOR_USERNAME = os.getenv(
    "WATERBRIDGE_SUPERVISOR_USERNAME",
    "",
).strip()

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=positive_int_env("JWT_ACCESS_TTL_MINUTES", 60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        hours=positive_int_env("JWT_REFRESH_TTL_HOURS", 168)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "public_id",
    "USER_ID_CLAIM": "sub",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

LOG_FILE_PATH = Path(
    os.getenv(
        "DJANGO_LOG_FILE",
        str(BASE_DIR / ".runtime" / "logs" / "backend.jsonl"),
    )
)
if not LOG_FILE_PATH.is_absolute():
    LOG_FILE_PATH = BASE_DIR / LOG_FILE_PATH
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "common.logging.filters.RequestContextFilter",
        }
    },
    "formatters": {
        "json": {
            "()": "common.logging.formatter.JsonFormatter",
        }
    },
    "handlers": {
        "backend_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_FILE_PATH),
            "encoding": "utf-8",
            "formatter": "json",
            "filters": ["request_context"],
            "delay": True,
        }
    },
    "loggers": {
        "watercare": {
            "handlers": ["backend_file"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        }
    },
}
