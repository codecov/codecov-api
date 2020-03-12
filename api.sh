#!/bin/sh


echo "Starting server on django"
while true; do
    gunicorn codecov.wsgi:application --bind 0.0.0.0:8000
    echo "Closing server on django"
done
