#!/bin/bash

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"
export PYTHONWARNINGS=always
prefix=""
if [ -f "/usr/local/bin/berglas" ]; then
  prefix="berglas exec --"
fi

if [ "$GUNICORN_WORKERS" -gt 1 ];
then
    export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-$HOME/.prometheus}"
    rm -r ${PROMETHEUS_MULTIPROC_DIR?}/* 2> /dev/null
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

$prefix gunicorn codecov.wsgi:application --reload --workers=${GUNICORN_WORKERS:-2} --threads=${GUNICORN_THREADS:-1} --worker-connections=${GUNICORN_WORKER_CONNECTIONS:-1000} --bind 0.0.0.0:8000 --access-logfile '-' --timeout "${GUNICORN_TIMEOUT:-600}" --disable-redirect-access-to-syslog --config=gunicorn.conf.py
