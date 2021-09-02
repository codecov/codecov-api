#!/bin/sh

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"
export PYTHONWARNINGS=always
prefix=""
#comment this for now to avoid changing k8s while in staging
#if [ -f "/usr/local/bin/berglas" ]; then
#prefix="berglas exec --"
#fi
suffix=""
if [[ "$STATSD_HOST" ]]; then
  suffix="--statsd-host ${STATSD_HOST}:${STATSD_PORT}"
fi
if [ $ELASTIC_APM_ENABLED ]; then
  $prefix gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' $suffix
else
  $prefix ddtrace-run gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' $suffix
fi