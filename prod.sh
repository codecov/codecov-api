#!/bin/sh

# Starts the production gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
if [ -f "/usr/local/bin/berglas" ]; then
  berglas exec -- ddtrace-run gunicorn codecov.wsgi:application --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
else
  ddtrace-run gunicorn codecov.wsgi:application --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
fi
