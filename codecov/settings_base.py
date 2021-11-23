import os

from corsheaders.defaults import default_headers

from utils.config import SettingsModule, get_config, get_settings_module

# SECURITY WARNING: keep the secret key used in production secret!
# TODO: get this out of source control
SECRET_KEY = "^fe*h^lqve%4)tl)0*rvx^zax$_5zu$7jg6o@2y!!-4*l^tne5"


YAML_SECRET_KEY = b"]\xbb\x13\xf9}\xb3\xb7\x03)*0Kv\xb2\xcet"


AUTH_USER_MODEL = "codecov_auth.Owner"

# Application definition

INSTALLED_APPS = [
    "legacy_migrations",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ariadne_django",
    "corsheaders",
    "rest_framework",
    "billing",
    "core",
    "codecov_auth",
    "reports",
    "internal_api",
    "graphql_api",
    "compare",
    "profiling",
    "public_api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "codecov_auth.authentication.CodecovTokenAuthenticationBackend",
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
            ],
        },
    },
]

WSGI_APPLICATION = "codecov.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases
DATABASE_USER = get_config("services", "database", "username", default="postgres")
DATABASE_NAME = get_config("services", "database", "name", default="postgres")
DATABASE_PASSWORD = get_config("services", "database", "password", default="postgres")
DATABASE_HOST = get_config("services", "database", "host", default="postgres")
DATABASE_PORT = get_config("services", "database", "port", default=5432)
# this is the time in seconds django decides to keep the connection open after the request
# the default is 0 seconds, meaning django closes the connection after every request
# https://docs.djangoproject.com/en/3.1/ref/settings/#conn-max-age
CONN_MAX_AGE = int(get_config("services", "database", "conn_max_age", default=0))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DATABASE_NAME,
        "USER": DATABASE_USER,
        "PASSWORD": DATABASE_PASSWORD,
        "HOST": DATABASE_HOST,
        "PORT": DATABASE_PORT,
        "CONN_MAX_AGE": CONN_MAX_AGE,
    }
}
# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]


REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "codecov_auth.authentication.CodecovTokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "internal_api.pagination.StandardPageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "PAGE_SIZE": 20,
}


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

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
    },
    "root": {"handlers": ["default"], "level": "INFO", "propagate": True},
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard"
            if get_settings_module() == SettingsModule.DEV.value
            else "json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # Default is stderr
        },
    },
    "loggers": {},
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

CIRCLECI_TOKEN = get_config("circleci", "token")

GITHUB_CLIENT_ID = get_config("github", "client_id")
GITHUB_CLIENT_SECRET = get_config("github", "client_secret")
GITHUB_BOT_KEY = get_config("github", "bot", "key")
GITHUB_ACTIONS_TOKEN = get_config("github", "actions_token")

BITBUCKET_CLIENT_ID = get_config("bitbucket", "client_id")
BITBUCKET_CLIENT_SECRET = get_config("bitbucket", "client_secret")
BITBUCKET_BOT_KEY = get_config("bitbucket", "bot", "key")
BITBUCKET_REDIRECT_URI = get_config(
    "bitbucket", "redirect_uri", default="https://codecov.io/login/bitbucket"
)

GITLAB_CLIENT_ID = get_config("gitlab", "client_id")
GITLAB_CLIENT_SECRET = get_config("gitlab", "client_secret")
GITLAB_REDIRECT_URI = get_config(
    "gitlab", "redirect_uri", default="https://codecov.io/login/gitlab"
)
GITLAB_BOT_KEY = get_config("gitlab", "bot", "key")


SEGMENT_API_KEY = get_config("setup", "segment", "key", default=None)
SEGMENT_ENABLED = get_config("setup", "segment", "enabled", default=False) and not bool(
    get_config("setup", "enterprise_license", default=False)
)

CORS_ALLOW_HEADERS = list(default_headers) + [
    "token-type",
]

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


CORS_ALLOWED_ORIGIN_REGEXES = []
CORS_ALLOWED_ORIGINS = []

GRAPHQL_PLAYGROUND = False

UPLOAD_THROTTLING_ENABLED = True
