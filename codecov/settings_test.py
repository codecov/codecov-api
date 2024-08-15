from .settings_base import *

DEBUG = False
ALLOWED_HOSTS = ["localhost"]
WEBHOOK_URL = ""  # NGROK TUNNEL HERE
STRIPE_API_KEY = ""
CORS_ALLOWED_ORIGINS = ["http://localhost:9000", "http://localhost"]
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = "localhost"
CODECOV_API_URL = get_config("setup", "codecov_api_url", default=CODECOV_URL)
DATABASE_HOST = "postgres"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DATABASE_NAME,
        "USER": DATABASE_USER,
        "PASSWORD": DATABASE_PASSWORD,
        "HOST": DATABASE_HOST,
        "PORT": "5432",
    }
}


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
    # Read https://www.django-rest-framework.org/api-guide/throttling/ for additional info on how to
    # modify throttling for codecov-api. Initially, we just want a simple throttle mechanism to prevent
    # burst requests from users/anons on our REST endpoints
    "DEFAULT_THROTTLE_CLASSES": [
        "codecov.rate_limiter.UserBurstRateThrottle",
        "codecov.rate_limiter.AnonBurstRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon-burst": "90001/min",
        "user-burst": "90001/min",
    },
}
