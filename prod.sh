#!/bin/bash

# Starts the production gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
prefix=""
if [ -f "/usr/local/bin/berglas" ]; then
  prefix="berglas exec --"
fi

GUNICORN_WORKERS=${GUNICORN_WORKERS:-2}
if [ "$GUNICORN_WORKERS" -gt 1 ];
then
    export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-$HOME/.prometheus}"
    rm -r ${PROMETHEUS_MULTIPROC_DIR?}/* 2> /dev/null
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

$prefix gunicorn codecov.wsgi:application --workers=${GUNICORN_WORKERS} --threads=${GUNICORN_THREADS:-1} --worker-connections=${GUNICORN_WORKER_CONNECTIONS:-1000} --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT} --timeout "${GUNICORN_TIMEOUT:-600}" --disable-redirect-access-to-syslog --max-requests=50000 --max-requests-jitter=300
