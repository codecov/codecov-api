#!/bin/sh

# Starts the production gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
gunicorn codecov.wsgi:application --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
