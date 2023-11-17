#!/bin/sh

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"

if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
    rm -r ${PROMETHEUS_MULTIPROC_DIR?}/* 2> /dev/null
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

export PYTHONWARNINGS=always
suffix=""
if [[ "$STATSD_HOST" ]]; then
  suffix="--statsd-host ${STATSD_HOST}:${STATSD_PORT}"
fi
if [[ "$RUN_ENV" == "enterprise" ]] || [[ "$RUN_ENV" == "DEV" ]]; then
  python manage.py migrate
fi
gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' --timeout "${GUNICORN_TIMEOUT:-600}" $suffix
