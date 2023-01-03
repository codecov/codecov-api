#!/bin/sh

# Starts the enterprise gunicorn server (no --reload)
echo "Starting api"

if [[ "$CODECOV_WRAPPER" ]]; then
SUB="$CODECOV_WRAPPER"
else
SUB=""
fi
if [[ "$CODECOV_WRAPPER_POST" ]]; then
POST="$CODECOV_WRAPPER_POST"
else
POST=""
fi
if [[ "$1" = "api" || -z "$1" ]];
then
  # Migrate
  /home/api migrate
  # Migrate timescale
  # TODO make this optional somehow
  /home/api migrate --database=timeseries timeseries
  # Start api
  ${SUB}/home/api run${POST}
elif [[ "$1" = "rti" ]];
then
  # Start api
  ${SUB}/home/api run${POST}
else
  exec "$@"
fi
