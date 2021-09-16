#!/bin/sh

# Starts the production gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
prefix=""
if [ -f "/usr/local/bin/berglas" ]; then
  prefix="berglas exec --"
fi

if [ $ELASTIC_APM_ENABLED ]; then
  $prefix gunicorn codecov.wsgi:application --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
else
  $prefix ddtrace-run gunicorn codecov.wsgi:application --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
fi
