import os
from urllib.parse import urlparse

import sentry_sdk
from corsheaders.defaults import default_headers
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from utils.config import SettingsModule, get_config, get_settings_module

SECRET_KEY = get_config("django", "secret_key", default="*")

AUTH_USER_MODEL = "codecov_auth.User"

# Application definition

INSTALLED_APPS = [
    "legacy_migrations",
    "dal",
    "dal_select2",  # needs to be ahead of django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_filters",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "ariadne_django",
    "corsheaders",
    "rest_framework",
    "billing",
    "codecov_auth",
    "api",
    "compare",
    "core",
    "graphql_api",
    "labelanalysis",
    "profiling",
    "reports",
    "staticanalysis",
    "timeseries",
    "django_prometheus",
    "psqlextra",
    "django_better_admin_arrayfield",
    # New Shared Models
    "shared.django_apps.rollouts",
    "shared.django_apps.user_measurements",
]

MIDDLEWARE = [
    "core.middleware.AppMetricsBeforeMiddlewareWithUA",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "codecov_auth.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ServiceMiddleware",
    "codecov_auth.middleware.CurrentOwnerMiddleware",
    "codecov_auth.middleware.ImpersonationMiddleware",
    "core.middleware.AppMetricsAfterMiddlewareWithUA",
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "codecov.urls"

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
            ]
        },
    }
]

WSGI_APPLICATION = "codecov.wsgi.application"

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

db_url = get_config("services", "database_url")
if db_url:
    db_conf = urlparse(db_url)
    DATABASE_USER = db_conf.username
    DATABASE_NAME = db_conf.path.replace("/", "")
    DATABASE_PASSWORD = db_conf.password
    DATABASE_HOST = db_conf.hostname
    DATABASE_PORT = db_conf.port
else:
    DATABASE_USER = get_config("services", "database", "username", default="postgres")
    DATABASE_NAME = get_config("services", "database", "name", default="postgres")
    DATABASE_PASSWORD = get_config(
        "services", "database", "password", default="postgres"
    )
    DATABASE_HOST = get_config("services", "database", "host", default="postgres")
    DATABASE_PORT = get_config("services", "database", "port", default=5432)

DATABASE_READ_REPLICA_ENABLED = get_config(
    "setup", "database", "read_replica_enabled", default=False
)

db_read_url = get_config("services", "database_read_url")
if db_read_url:
    db_conf = urlparse(db_read_url)
    DATABASE_READ_USER = db_conf.username
    DATABASE_READ_NAME = db_conf.path.replace("/", "")
    DATABASE_READ_PASSWORD = db_conf.password
    DATABASE_READ_HOST = db_conf.hostname
    DATABASE_READ_PORT = db_conf.port
else:
    DATABASE_READ_USER = get_config(
        "services", "database_read", "username", default="postgres"
    )
    DATABASE_READ_NAME = get_config(
        "services", "database_read", "name", default="postgres"
    )
    DATABASE_READ_PASSWORD = get_config(
        "services", "database_read", "password", default="postgres"
    )
    DATABASE_READ_HOST = get_config(
        "services", "database_read", "host", default="postgres"
    )
    DATABASE_READ_PORT = get_config("services", "database_read", "port", default=5432)

GRAPHQL_QUERY_COST_THRESHOLD = get_config(
    "setup", "graphql", "query_cost_threshold", default=10000
)

TIMESERIES_ENABLED = get_config("setup", "timeseries", "enabled", default=False)
TIMESERIES_REAL_TIME_AGGREGATES = get_config(
    "setup", "timeseries", "real_time_aggregates", default=False
)

timeseries_database_url = get_config("services", "timeseries_database_url")
if timeseries_database_url:
    timeseries_database_conf = urlparse(timeseries_database_url)
    TIMESERIES_DATABASE_USER = timeseries_database_conf.username
    TIMESERIES_DATABASE_NAME = timeseries_database_conf.path.replace("/", "")
    TIMESERIES_DATABASE_PASSWORD = timeseries_database_conf.password
    TIMESERIES_DATABASE_HOST = timeseries_database_conf.hostname
    TIMESERIES_DATABASE_PORT = timeseries_database_conf.port
else:
    TIMESERIES_DATABASE_USER = get_config(
        "services", "timeseries_database", "username", default="postgres"
    )
    TIMESERIES_DATABASE_NAME = get_config(
        "services", "timeseries_database", "name", default="postgres"
    )
    TIMESERIES_DATABASE_PASSWORD = get_config(
        "services", "timeseries_database", "password", default="postgres"
    )
    TIMESERIES_DATABASE_HOST = get_config(
        "services", "timeseries_database", "host", default="timescale"
    )
    TIMESERIES_DATABASE_PORT = get_config(
        "services", "timeseries_database", "port", default=5432
    )

TIMESERIES_DATABASE_READ_REPLICA_ENABLED = get_config(
    "setup", "timeseries", "read_replica_enabled", default=False
)

timeseries_database_read_url = get_config("services", "timeseries_database_read_url")
if timeseries_database_read_url:
    timeseries_database_conf = urlparse(timeseries_database_read_url)
    TIMESERIES_DATABASE_READ_USER = timeseries_database_conf.username
    TIMESERIES_DATABASE_READ_NAME = timeseries_database_conf.path.replace("/", "")
    TIMESERIES_DATABASE_READ_PASSWORD = timeseries_database_conf.password
    TIMESERIES_DATABASE_READ_HOST = timeseries_database_conf.hostname
    TIMESERIES_DATABASE_READ_PORT = timeseries_database_conf.port
else:
    TIMESERIES_DATABASE_READ_USER = get_config(
        "services", "timeseries_database_read", "username", default="postgres"
    )
    TIMESERIES_DATABASE_READ_NAME = get_config(
        "services", "timeseries_database_read", "name", default="postgres"
    )
    TIMESERIES_DATABASE_READ_PASSWORD = get_config(
        "services", "timeseries_database_read", "password", default="postgres"
    )
    TIMESERIES_DATABASE_READ_HOST = get_config(
        "services", "timeseries_database_read", "host", default="timescale"
    )
    TIMESERIES_DATABASE_READ_PORT = get_config(
        "services", "timeseries_database_read", "port", default=5432
    )

# this is the time in seconds django decides to keep the connection open after the request
# the default is 0 seconds, meaning django closes the connection after every request
# https://docs.djangoproject.com/en/3.1/ref/settings/#conn-max-age
CONN_MAX_AGE = int(get_config("services", "database", "conn_max_age", default=0))

DATABASES = {
    "default": {
        "ENGINE": "psqlextra.backend",
        "NAME": DATABASE_NAME,
        "USER": DATABASE_USER,
        "PASSWORD": DATABASE_PASSWORD,
        "HOST": DATABASE_HOST,
        "PORT": DATABASE_PORT,
        "CONN_MAX_AGE": CONN_MAX_AGE,
    }
}

if DATABASE_READ_REPLICA_ENABLED:
    DATABASES["default_read"] = {
        "ENGINE": "psqlextra.backend",
        "NAME": DATABASE_READ_NAME,
        "USER": DATABASE_READ_USER,
        "PASSWORD": DATABASE_READ_PASSWORD,
        "HOST": DATABASE_READ_HOST,
        "PORT": DATABASE_READ_PORT,
        "CONN_MAX_AGE": CONN_MAX_AGE,
    }

if TIMESERIES_ENABLED:
    DATABASES["timeseries"] = {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": TIMESERIES_DATABASE_NAME,
        "USER": TIMESERIES_DATABASE_USER,
        "PASSWORD": TIMESERIES_DATABASE_PASSWORD,
        "HOST": TIMESERIES_DATABASE_HOST,
        "PORT": TIMESERIES_DATABASE_PORT,
        "CONN_MAX_AGE": CONN_MAX_AGE,
    }

    if TIMESERIES_DATABASE_READ_REPLICA_ENABLED:
        DATABASES["timeseries_read"] = {
            "ENGINE": "django_prometheus.db.backends.postgresql",
            "NAME": TIMESERIES_DATABASE_READ_NAME,
            "USER": TIMESERIES_DATABASE_READ_USER,
            "PASSWORD": TIMESERIES_DATABASE_READ_PASSWORD,
            "HOST": TIMESERIES_DATABASE_READ_HOST,
            "PORT": TIMESERIES_DATABASE_READ_PORT,
            "CONN_MAX_AGE": CONN_MAX_AGE,
        }

# See https://django-postgres-extra.readthedocs.io/en/master/settings.html
POSTGRES_EXTRA_DB_BACKEND_BASE: "django_prometheus.db.backends.postgresql"

# Allows to use the pgpartition command
PSQLEXTRA_PARTITIONING_MANAGER = (
    "shared.django_apps.user_measurements.partitioning.manager"
)

DATABASE_ROUTERS = ["codecov.db.DatabaseRouter"]

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PROMETHEUS_EXPORT_MIGRATIONS = False

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "codecov_auth.authentication.UserTokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "codecov_auth.authentication.SessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "api.shared.pagination.StandardPageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# API auto-documentation settings
# https://drf-spectacular.readthedocs.io/en/latest/settings.html
SPECTACULAR_SETTINGS = {
    "TITLE": "Codecov API",
    "DESCRIPTION": "Public Codecov API",
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_URLCONF": "api.public.v2.urls",
    "SERVERS": [{"url": "/api/v2"}],
    "AUTHENTICATION_WHITELIST": [
        "codecov_auth.authentication.UserTokenAuthentication",
    ],
    "REDOC_DIST": "SIDECAR",  # serve Redoc from Django (not CDN)
}

# The frame-ancestors directive restricts the URLs which can embed the resource using
# frame, iframe, object, or embed. This configuration denies doing so.
CSP_FRAME_ANCESTORS = "'none'"

# Allows GraphQL Playground to render
CSP_DEFAULT_SRC = [
    "'self'",
    "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='",
    "'sha256-eKdXhLyOdPl2/gp1Ob116rCU2Ox54rseyz1MwCmzb6w='",
    "'sha256-a1pELtDJXf8fPX1YL2JiBM91RQBeIAswunzgwMEsvwA='",
    "'sha256-cNIcuS0BVLuBVP5rpfeFE42xHz7r5hMyf9YdfknWuCg='",
    "https://cdn.jsdelivr.net/npm/graphql-playground-react/build/static/js/middleware.js",
    "https://cdn.jsdelivr.net/npm/graphql-playground-react/build/favicon.png",
    "https://cdn.jsdelivr.net/npm/graphql-playground-react/build/static/css/index.css",
]

# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(PROJECT_ROOT, "static")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(message)s %(asctime)s %(name)s %(levelname)s %(lineno)s %(pathname)s %(funcName)s %(threadName)s",
            "class": "utils.logging_configuration.CustomLocalJsonFormatter",
        },
        "json": {
            "format": "%(message)s %(asctime)s %(name)s %(levelname)s %(lineno)s %(pathname)s %(funcName)s %(threadName)s",
            "class": "utils.logging_configuration.CustomDatadogJsonFormatter",
        },
        "gunicorn_json": {
            "class": "utils.logging_configuration.CustomGunicornLogFormatter",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            "format": '%(h)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"',
        },
    },
    "filters": {
        "health_check_filter": {"()": "utils.logging_configuration.HealthCheckFilter"}
    },
    "root": {"handlers": ["default"], "level": "INFO", "propagate": True},
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": (
                "standard"
                if get_settings_module() == SettingsModule.DEV.value
                else "json"
            ),
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Default is stderr
        },
        "json-gunicorn-console": {
            "level": "INFO",
            "formatter": "gunicorn_json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Default is stderr
            "filters": ["health_check_filter"],
        },
    },
    "loggers": {
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["json-gunicorn-console"],
        }
    },
}

MINIO_ACCESS_KEY = get_config("services", "minio", "access_key_id")
MINIO_SECRET_KEY = get_config("services", "minio", "secret_access_key")
MINIO_LOCATION = "codecov.s3.amazonaws.com"
MINIO_HASH_KEY = get_config("services", "minio", "hash_key")
ARCHIVE_BUCKET_NAME = "codecov"
ENCRYPTION_SECRET = get_config("setup", "encryption_secret")

COOKIE_SAME_SITE = "Lax"
COOKIE_SECRET = get_config("setup", "http", "cookie_secret")
COOKIES_DOMAIN = get_config("setup", "http", "cookies_domain", default=".codecov.io")
SESSION_COOKIE_DOMAIN = get_config(
    "setup", "http", "cookies_domain", default=".codecov.io"
)
SESSION_COOKIE_SECURE = get_config("setup", "secure_cookie", default=True)
# Defaulting to 'not found' as opposed to 'None' to avoid None somehow getting through as a bearer token. Token strings can't have spaces, hence 'not found' can never be forced as a header input value
SUPER_API_TOKEN = os.getenv("SUPER_API_TOKEN", "not found")
CODECOV_INTERNAL_TOKEN = os.getenv("CODECOV_INTERNAL_TOKEN", "not found")

CIRCLECI_TOKEN = get_config("circleci", "token")

GITHUB_CLIENT_ID = get_config("github", "client_id")
GITHUB_CLIENT_SECRET = get_config("github", "client_secret")
GITHUB_BOT_KEY = get_config("github", "bot", "key")
GITHUB_TOKENLESS_BOT_KEY = get_config(
    "github", "bots", "tokenless", "key", default=GITHUB_BOT_KEY
)
GITHUB_ACTIONS_TOKEN = get_config("github", "actions_token")

GITHUB_ENTERPRISE_URL = get_config("github_enterprise", "url")
GITHUB_ENTERPRISE_API_URL = get_config("github_enterprise", "api_url")
GITHUB_ENTERPRISE_CLIENT_ID = get_config("github_enterprise", "client_id")
GITHUB_ENTERPRISE_CLIENT_SECRET = get_config("github_enterprise", "client_secret")
GITHUB_ENTERPRISE_BOT_KEY = get_config("github_enterprise", "bot", "key")
GITHUB_ENTERPRISE_TOKENLESS_BOT_KEY = get_config(
    "github_enterprise", "bots", "tokenless", "key", default=GITHUB_ENTERPRISE_BOT_KEY
)
GITHUB_ENTERPRISE_ACTIONS_TOKEN = get_config("github_enterprise", "actions_token")

BITBUCKET_CLIENT_ID = get_config("bitbucket", "client_id")
BITBUCKET_CLIENT_SECRET = get_config("bitbucket", "client_secret")
BITBUCKET_BOT_KEY = get_config("bitbucket", "bot", "key")
BITBUCKET_TOKENLESS_BOT_KEY = get_config(
    "bitbucket", "bots", "tokenless", "key", default=BITBUCKET_BOT_KEY
)
BITBUCKET_REDIRECT_URI = get_config(
    "bitbucket", "redirect_uri", default="https://codecov.io/login/bitbucket"
)

BITBUCKET_SERVER_URL = get_config("bitbucket_server", "url")
BITBUCKET_SERVER_CLIENT_ID = get_config("bitbucket_server", "client_id")
BITBUCKET_SERVER_CLIENT_SECRET = get_config("bitbucket_server", "client_secret")
BITBUCKET_SERVER_BOT_KEY = get_config("bitbucket_server", "bot", "key")
BITBUCKET_SERVER_TOKENLESS_BOT_KEY = get_config(
    "bitbucket_server", "bots", "tokenless", "key", default=BITBUCKET_SERVER_BOT_KEY
)

GITLAB_CLIENT_ID = get_config("gitlab", "client_id")
GITLAB_CLIENT_SECRET = get_config("gitlab", "client_secret")
GITLAB_REDIRECT_URI = get_config(
    "gitlab", "redirect_uri", default="https://codecov.io/login/gitlab"
)

GITLAB_BOT_KEY = get_config("gitlab", "bot", "key")
GITLAB_TOKENLESS_BOT_KEY = get_config(
    "gitlab", "bots", "tokenless", "key", default=GITLAB_BOT_KEY
)


GITLAB_ENTERPRISE_CLIENT_ID = get_config("gitlab_enterprise", "client_id")
GITLAB_ENTERPRISE_CLIENT_SECRET = get_config("gitlab_enterprise", "client_secret")
GITLAB_ENTERPRISE_REDIRECT_URI = get_config(
    "gitlab_enterprise",
    "redirect_uri",
    default="https://codecov.io/login/gitlab_enterprise",
)
GITLAB_ENTERPRISE_BOT_KEY = get_config("gitlab_enterprise", "bot", "key")
GITLAB_ENTERPRISE_TOKENLESS_BOT_KEY = get_config(
    "gitlab_enterprise", "bots", "tokenless", "key", default=GITLAB_ENTERPRISE_BOT_KEY
)
GITLAB_ENTERPRISE_URL = get_config("gitlab_enterprise", "url")
GITLAB_ENTERPRISE_API_URL = get_config("gitlab_enterprise", "api_url")

SEGMENT_API_KEY = get_config("setup", "segment", "key", default=None)
SEGMENT_ENABLED = get_config("setup", "segment", "enabled", default=False) and not bool(
    get_config("setup", "enterprise_license", default=False)
)

CORS_ALLOW_HEADERS = (
    list(default_headers)
    + ["token-type"]
    + get_config("setup", "api_cors_extra_headers", default=["baggage"])
)

SKIP_RISKY_MIGRATION_STEPS = get_config("migrations", "skip_risky_steps", default=False)

DJANGO_ADMIN_URL = get_config("django", "admin_url", default="admin")

IS_ENTERPRISE = get_settings_module() == SettingsModule.ENTERPRISE.value
IS_DEV = get_settings_module() == SettingsModule.DEV.value

DATA_UPLOAD_MAX_MEMORY_SIZE = get_config(
    "setup", "http", "upload_max_memory_size", default=2621440
)
FILE_UPLOAD_MAX_MEMORY_SIZE = get_config(
    "setup", "http", "file_upload_max_memory_size", default=2621440
)


CORS_ALLOWED_ORIGIN_REGEXES = get_config(
    "setup", "api_cors_allowed_origin_regexes", default=[]
)
CORS_ALLOWED_ORIGINS = []

GRAPHQL_PLAYGROUND = True

UPLOAD_THROTTLING_ENABLED = get_config(
    "setup", "upload_throttling_enabled", default=True
)

SENTRY_JWT_SHARED_SECRET = get_config(
    "sentry", "jwt_shared_secret", default=None
) or get_config("setup", "sentry", "jwt_shared_secret", default=None)
SENTRY_USER_WEBHOOK_URL = get_config(
    "sentry", "webhook_url", default=None
) or get_config("setup", "sentry", "webhook_url", default=None)
SENTRY_OAUTH_CLIENT_ID = get_config("sentry", "client_id") or get_config(
    "setup", "sentry", "oauth_client_id"
)
SENTRY_OAUTH_CLIENT_SECRET = get_config("sentry", "client_secret") or get_config(
    "setup", "sentry", "oauth_client_secret"
)
SENTRY_OIDC_SHARED_SECRET = get_config("sentry", "oidc_shared_secret") or get_config(
    "setup", "sentry", "oidc_shared_secret"
)

OKTA_OAUTH_CLIENT_ID = get_config("setup", "okta", "oauth_client_id")
OKTA_OAUTH_CLIENT_SECRET = get_config("setup", "okta", "oauth_client_secret")
OKTA_OAUTH_REDIRECT_URL = get_config("setup", "okta", "oauth_redirect_url")
OKTA_ISS = get_config("setup", "okta", "iss", default=None)

DISABLE_GIT_BASED_LOGIN = IS_ENTERPRISE and get_config(
    "setup", "disable_git_based_login", default=False
)

SHELTER_SHARED_SECRET = get_config("setup", "shelter_shared_secret", default=None)

# list of repo IDs that will use the new-style report builder
# TODO: we can eventually get rid of this once it's confirmed working well for many repos
REPORT_BUILDER_REPO_IDS = get_config("setup", "report_builder", "repo_ids", default=[])

SENTRY_ENV = os.environ.get("CODECOV_ENV", False)
SENTRY_DSN = os.environ.get("SERVICES__SENTRY__SERVER_DSN", None)
SENTRY_DENY_LIST = DEFAULT_DENYLIST + ["_headers", "token_to_use"]

if SENTRY_DSN is not None:
    SENTRY_SAMPLE_RATE = float(os.environ.get("SERVICES__SENTRY__SAMPLE_RATE", 0.1))
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        event_scrubber=EventScrubber(denylist=SENTRY_DENY_LIST),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            HttpxIntegration(),
        ],
        environment=SENTRY_ENV,
        traces_sample_rate=SENTRY_SAMPLE_RATE,
        _experiments={
            "profiles_sample_rate": float(
                os.environ.get("SERVICES__SENTRY__PROFILE_SAMPLE_RATE", 0.01)
            ),
        },
    )
    if os.getenv("CLUSTER_ENV"):
        sentry_sdk.set_tag("cluster", os.getenv("CLUSTER_ENV"))
elif IS_DEV:
    sentry_sdk.init(
        spotlight=IS_DEV,
        event_scrubber=EventScrubber(denylist=SENTRY_DENY_LIST),
    )

SHELTER_PUBSUB_PROJECT_ID = get_config("setup", "shelter", "pubsub_project_id")
SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID = get_config("setup", "shelter", "sync_repo_topic_id")

# Allows to do migrations from another module
MIGRATION_MODULES = {
    "codecov_auth": "shared.django_apps.codecov_auth.migrations",
    "core": "shared.django_apps.core.migrations",
    "reports": "shared.django_apps.reports.migrations",
    "legacy_migrations": "shared.django_apps.legacy_migrations.migrations",
}
