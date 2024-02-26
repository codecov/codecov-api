#!/bin/bash

# Starts the production gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
prefix=""
if [ -f "/usr/local/bin/berglas" ]; then
  prefix="berglas exec --"
fi

export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-$HOME/.prometheus}"
rm -r ${PROMETHEUS_MULTIPROC_DIR?}/* 2> /dev/null
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

$prefix gunicorn codecov.wsgi:application --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT} --timeout "${GUNICORN_TIMEOUT:-600}"
