#!/bin/sh

# starts the development server using gunicorn
# NEVER run production with the --reload option command
echo "Starting gunicorn in dev mode"
export PYTHONWARNINGS=always
suffix=""
if [[ "$STATSD_HOST" ]]; then
  suffix="--statsd-host ${STATSD_HOST}:${STATSD_PORT}"
fi
if [[ "$RUN_ENV" == "enterprise" ]]; then
  python manage.py migrate
fi
if [ "$EDITABLE_SHARED" = "y" ]; then
pip install -e ./shared
fi
watchmedo auto-restart --patterns="*.py;*.sh" --recursive --signal=SIGTERM sh gunicorn.sh
