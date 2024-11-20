#!/bin/bash

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

export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-$HOME/.prometheus}"
rm -r ${PROMETHEUS_MULTIPROC_DIR?}/* 2> /dev/null
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

$prefix gunicorn codecov.wsgi:application --reload --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' --timeout "${GUNICORN_TIMEOUT:-600}" $suffix
