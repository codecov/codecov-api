#!/bin/sh

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"
export PYTHONWARNINGS=always
suffix=""
if [[ "$STATSD_HOST" ]]; then
  suffix="--statsd-host ${STATSD_HOST}:${STATSD_PORT}"
fi
if [[ "$RUN_ENV" == "enterprise" ]]; then
  python manage.py migrate
fi
gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' --timeout "${GUNICORN_TIMEOUT:-600}" $suffix
