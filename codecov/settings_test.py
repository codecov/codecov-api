from .settings_base import *


DEBUG = True
ALLOWED_HOSTS = ['localhost']
WEBHOOK_URL = '' # NGROK TUNNEL HERE
STRIPE_API_KEY = ''
CORS_ORIGIN_WHITELIST = ['localhost:9000']
CORS_ALLOW_CREDENTIALS = True
CODECOV_URL = 'localhost'
DATABASE_HOST = 'localhost'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': DATABASE_NAME,
        'USER': DATABASE_USER,
        'PASSWORD': DATABASE_PASSWORD,
        'HOST': DATABASE_HOST,
        'PORT': '5432',
    }
}
