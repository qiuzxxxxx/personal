"""Django settings for the zixxx self-hosted deployment."""
import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Environment
# --------------------------------------------------------------------------- #
# "production" is the default for a deployed instance: DEBUG is off, the
# secret key must be stable and the cookie flags are hardened.
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"


def _require_in_production(name: str, value: str, hint: str) -> str:
    """Refuse to start without a value that must not change between runs."""
    if value:
        return value
    if IS_PRODUCTION:
        raise RuntimeError(
            f"生产环境缺少 {name}。{hint}"
        )
    return ""


_secret_key_env = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if IS_PRODUCTION:
    # A random key would invalidate every session and signed cookie on every
    # restart, so a stable value is mandatory in production.
    _require_in_production(
        "DJANGO_SECRET_KEY",
        _secret_key_env,
        '请生成一个 50 字符以上的随机值并写入 .env，可用 python -c "import secrets;'
        'print(secrets.token_urlsafe(64))"。',
    )
SECRET_KEY = _secret_key_env or get_random_secret_key()

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "channels",
    "accounts",
    "agent",
    "chat",
    "transfer",
    "workspace",
    "knowledge",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_ENGINE = os.environ.get("DATABASE_ENGINE", "sqlite3").strip().lower()

if DATABASE_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "zixxx"),
            "USER": os.environ.get("POSTGRES_USER", "zixxx"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            # Section 12.7: a bounded connection lifetime keeps the pool
            # small enough for a 30 connection server.
            "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": int(os.environ.get("POSTGRES_CONNECT_TIMEOUT", "10")),
            },
        }
    }
else:
    # NEXUS_DB_PATH lets smoke and acceptance runs use a scratch database
    # instead of the developer's working db.sqlite3.  Scratch databases run
    # with the in-memory rollback journal: this sandboxed Windows environment
    # can leave a hot -journal file behind, which would roll back committed
    # transactions of the next connection.
    scratch_db = os.environ.get("NEXUS_DB_PATH")
    scratch_options = {"timeout": 20}
    if scratch_db:
        scratch_options["init_command"] = "PRAGMA journal_mode=MEMORY"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": scratch_db or BASE_DIR / "db.sqlite3",
            "OPTIONS": scratch_options,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Large multipart uploads are streamed to a temporary file by Django.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1

# Public address of the workbench. QR codes must point at a phone reachable
# address, so the value is configured explicitly and never taken from Host.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

# Phone upload sessions (QR codes).
UPLOAD_SESSION_TTL_SECONDS = int(os.environ.get("UPLOAD_SESSION_TTL_SECONDS", "600"))
UPLOAD_SESSION_MAX_FILES = int(os.environ.get("UPLOAD_SESSION_MAX_FILES", "20"))
UPLOAD_SESSION_MAX_BYTES = int(
    os.environ.get("UPLOAD_SESSION_MAX_BYTES", str(500 * 1024 * 1024))
)
UPLOAD_SESSION_MAX_FILE_BYTES = int(
    os.environ.get("UPLOAD_SESSION_MAX_FILE_BYTES", str(100 * 1024 * 1024))
)
UPLOAD_SESSION_MAX_ACTIVE = int(os.environ.get("UPLOAD_SESSION_MAX_ACTIVE", "3"))
UPLOAD_RECEIPT_LEASE_SECONDS = int(os.environ.get("UPLOAD_RECEIPT_LEASE_SECONDS", "1200"))

NEXUS_BUILTIN_LLM_API_KEY = os.environ.get("NEXUS_BUILTIN_LLM_API_KEY", "")
NEXUS_TRUSTED_PROXY_HOPS = max(0, int(os.environ.get("NEXUS_TRUSTED_PROXY_HOPS", "0")))
NEXUS_LLM_PRIVATE_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("NEXUS_LLM_PRIVATE_ORIGINS", "").split(",")
    if origin.strip()
]

# --------------------------------------------------------------------------- #
# Public transfer station budget
# --------------------------------------------------------------------------- #
# Anonymous uploads share a budget per client address so that the public
# station cannot fill the disk of the server. 0 disables the limit.
TRANSFER_ANONYMOUS_TOTAL_BYTES = int(
    os.environ.get("TRANSFER_ANONYMOUS_TOTAL_BYTES", str(2 * 1024 * 1024 * 1024))
)
TRANSFER_ANONYMOUS_WINDOW_SECONDS = int(
    os.environ.get("TRANSFER_ANONYMOUS_WINDOW_SECONDS", "3600")
)
TRANSFER_ANONYMOUS_MAX_FILES_PER_WINDOW = int(
    os.environ.get("TRANSFER_ANONYMOUS_MAX_FILES_PER_WINDOW", "60")
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DATETIME_FORMAT": "iso-8601",
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# --------------------------------------------------------------------------- #
# Redis (cache, rate limiting and channel layer)
# --------------------------------------------------------------------------- #
# Section 12.7: Redis only stores small short-lived values (rate limit
# counters, channel messages). File contents and chat bodies never go here.
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": int(os.environ.get("REDIS_CACHE_TIMEOUT", "300")),
            "OPTIONS": {
                "db": int(os.environ.get("REDIS_CACHE_DB", "1")),
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
            },
            "KEY_PREFIX": os.environ.get("REDIS_KEY_PREFIX", "zixxx"),
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                # A channel layer message is small; the default capacity is
                # enough for a single user on one server.
                "capacity": int(os.environ.get("REDIS_CHANNEL_CAPACITY", "100")),
                "expiry": int(os.environ.get("REDIS_CHANNEL_EXPIRY", "60")),
            },
        }
    }
    REDIS_CHANNEL_URL = os.environ.get("REDIS_CHANNEL_URL", REDIS_URL).strip()
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "zixxx-local",
        }
    }
    REDIS_CHANNEL_URL = ""

if IS_PRODUCTION and not REDIS_URL:
    # A single process may still run without Redis, but the limit and the
    # broadcast layer then only work inside that process. The operator must
    # know that instead of silently losing cross-process behaviour.
    import warnings

    warnings.warn(
        "生产环境未配置 REDIS_URL：限速与频道广播只在单个进程内有效。"
        "多进程部署前必须配置 Redis。",
        RuntimeWarning,
    )

# The frontend is normally served through Vite's same-origin /api proxy. These
# options keep direct development on :5173 working as well.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-session-key",
]
CORS_EXPOSE_HEADERS = ["Content-Disposition", "Content-Length"]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------- #
# Transport security (production only)
# --------------------------------------------------------------------------- #
if IS_PRODUCTION:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Nginx terminates TLS and forwards the real client address.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    USE_X_FORWARDED_HOST = True
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        }
    },
    "loggers": {
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
