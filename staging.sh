#!/bin/sh

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"
export PYTHONWARNINGS=always
prefix=""
if [ -f "/usr/local/bin/berglas" ]; then
  prefix="berglas exec --"
fi
suffix=""
if [[ "$STATSD_HOST" ]]; then
  suffix="--statsd-host ${STATSD_HOST}:${STATSD_PORT}"
fi

$prefix gunicorn codecov.wsgi:application --reload --workers=${GUNICORN_WORKERS:-3} --threads=${GUNICORN_THREADS:-6} --worker-class=gthread --bind 0.0.0.0:8000 --access-logfile '-' $suffix
