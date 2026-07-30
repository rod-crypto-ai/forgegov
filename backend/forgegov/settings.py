from pathlib import Path
from datetime import timedelta
import os
from urllib.parse import urlparse
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-key-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
_insecure_secret_keys = {"", "development-only-key-change-me", "replace-with-a-long-random-value"}
if not DEBUG and (SECRET_KEY in _insecure_secret_keys or len(SECRET_KEY) < 40):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a strong value of at least 40 characters when DJANGO_DEBUG=false.")
def _hostname_from_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or ""


_allowed_hosts = {
    x.strip()
    for x in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if x.strip()
}
for candidate in (
    os.getenv("RENDER_EXTERNAL_HOSTNAME", ""),
    _hostname_from_url(os.getenv("API_PUBLIC_URL", "")),
):
    if candidate:
        _allowed_hosts.add(candidate)
ALLOWED_HOSTS = sorted(_allowed_hosts)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "core",
]

MIDDLEWARE = [
    "core.middleware.RenderHealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "forgegov.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "forgegov.wsgi.application"
ASGI_APPLICATION = "forgegov.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [x.strip() for x in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if x.strip()]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.authentication.CookieJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.ForgeGovPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "sam_live": os.getenv("SAM_LIVE_SEARCH_RATE", "120/hour"),
        "auth_login": os.getenv("AUTH_LOGIN_RATE", "10/minute"),
        "auth_register": os.getenv("AUTH_REGISTER_RATE", "5/hour"),
        "openai_chat": os.getenv("OPENAI_CHAT_RATE", "60/hour"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

AUTH_ACCESS_COOKIE_NAME = "forgegov_access"
AUTH_REFRESH_COOKIE_NAME = "forgegov_refresh"
AUTH_ACCESS_COOKIE_MAX_AGE = 30 * 60
AUTH_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("CACHE_URL", CELERY_BROKER_URL),
        "KEY_PREFIX": "forgegov",
    }
}
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "1"))
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BEAT_SCHEDULE = {}
if os.getenv("SAM_SYNC_ENABLED", "false").lower() == "true":
    CELERY_BEAT_SCHEDULE["sync-recent-sam-opportunities"] = {
        "task": "core.tasks.sync_recent_sam_opportunities",
        "schedule": 24 * 60 * 60,
        "kwargs": {"days": 1, "limit": int(os.getenv("SAM_DAILY_SYNC_LIMIT", "1000"))},
    }
if os.getenv("ALERTS_ENABLED", "true").lower() == "true":
    CELERY_BEAT_SCHEDULE["evaluate-saved-search-alerts"] = {
        "task": "core.tasks.evaluate_saved_search_alerts",
        "schedule": 24 * 60 * 60,
    }

SAM_GOV_API_KEY = os.getenv("SAM_GOV_API_KEY", "")
SAM_GOV_BASE_URL = os.getenv("SAM_GOV_BASE_URL", "https://api.sam.gov/opportunities/v2/search")
SAM_CONTRACT_AWARDS_BASE_URL = os.getenv("SAM_CONTRACT_AWARDS_BASE_URL", "https://api.sam.gov/contract-awards/v1/search")
SAM_SUBAWARDS_BASE_URL = os.getenv("SAM_SUBAWARDS_BASE_URL", "https://api.sam.gov/prod/contract/v1/subcontracts/search")
SBA_SUBNET_URL = os.getenv("SBA_SUBNET_URL", "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities")
USASPENDING_BASE_URL = os.getenv("USASPENDING_BASE_URL", "https://api.usaspending.gov")

GRANTS_GOV_BASE_URL = os.getenv("GRANTS_GOV_BASE_URL", "https://api.grants.gov/v1/api")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
SEARXNG_URL = os.getenv("SEARXNG_URL", "").strip()
AI_WEB_SEARCH_ENABLED = os.getenv("AI_WEB_SEARCH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "90"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1800"))


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
PUBLIC_REGISTRATION_ENABLED = os.getenv("PUBLIC_REGISTRATION_ENABLED", "true").lower() == "true"
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv("CSRF_TRUSTED_ORIGINS", FRONTEND_URL).split(",") if x.strip()]
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"
CSRF_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
REFERRER_POLICY = "same-origin"
