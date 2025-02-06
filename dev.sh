#!/bin/bash

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "API: Starting gunicorn in dev mode"

_start_gunicorn() {
  if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
      rm -r ${PROMETHEUS_MULTIPROC_DIR?}/* 2> /dev/null
      mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
  fi

  export PYTHONWARNINGS=always
  suffix=""
  if [[ "$STATSD_HOST" ]]; then
    suffix="--statsd-host ${STATSD_HOST}:${STATSD_PORT}"
  fi
  if [ "$RUN_ENV" == "ENTERPRISE" ] || [ "$RUN_ENV" == "DEV" ]; then
    python manage.py migrate
    python manage.py migrate --database "timeseries" timeseries
    python manage.py pgpartition --yes --skip-delete
    python manage.py insert_data_to_db_from_csv core/management/commands/codecovTiers-Jan25.csv --model tiers
    python manage.py insert_data_to_db_from_csv core/management/commands/codecovPlans-Jan25.csv --model plans
  fi
  if [[ "$DEBUGPY" ]]; then
      pip install debugpy
      python -m debugpy --listen 0.0.0.0:12345 -m gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' --timeout "${GUNICORN_TIMEOUT:-600}" $suffix
  fi
  gunicorn codecov.wsgi:application --reload --bind 0.0.0.0:8000 --access-logfile '-' --timeout "${GUNICORN_TIMEOUT:-600}" $suffix
}

if [ -z "$1" ];
then
  _start_gunicorn
else
  exec "$@"
fi
