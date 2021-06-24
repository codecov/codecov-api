#!/bin/sh

# Starts the enterprise gunicorn server (no --reload)
echo "Starting api"

if [[ "$CODECOV_WRAPPER" ]]; then
SUB="$CODECOV_WRAPPER"
else
SUB=""
fi
if [[ "$DD_ENABLED" ]]; then
DDTRACE="ddtrace-run "
else
DDTRACE=""
fi
if [[ "$CODECOV_WRAPPER_POST" ]]; then
POST="$CODECOV_WRAPPER_POST"
else
POST=""
fi
if [ "$1" = "api" ];
then
  /home/api migrate
  ${SUB}${DDTRACE}/home/api runserver 0.0.0.0:8000 --noreload${POST}
elif [ -z "$1" ];
then
  /home/api migrate
  ${SUB}${DDTRACE}/home/api runserver 0.0.0.0:8000 --noreload${POST}
else
  exec "$@"
fi



