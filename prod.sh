#!/bin/sh

# Starts the production gunicorn server (no --reload)
echo "Starting gunicorn in production mode"
if [ -f "/usr/local/bin/berglas" ]; then
  berglas exec -- python manage.py collectstatic --no-input
  berglas exec -- ddtrace-run gunicorn codecov.wsgi:application --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
else
  python manage.py collectstatic --no-input
  ddtrace-run gunicorn codecov.wsgi:application --workers=2 --bind 0.0.0.0:8000 --access-logfile '-' --statsd-host ${STATSD_HOST}:${STATSD_PORT}
fi
