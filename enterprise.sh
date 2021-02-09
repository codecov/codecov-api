#!/bin/sh

# Starts the enterprise gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
if [[ "$STATSD_HOST" ]]; then
PARAMS="--statsd-host ${STATSD_HOST}:${STATSD_PORT:-8125}"
else
PARAMS=""
fi
if [[ "$DD_ENABLED" ]]; then
SUB="ddtrace-run "
else
SUB=""
fi
${SUB}gunicorn codecov.wsgi:application --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' ${PARAMS}

