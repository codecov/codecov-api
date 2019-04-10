#!/bin/sh


echo "Starting server on django"
while true; do
    python manage.py runserver 0.0.0.0:8000 --verbosity 2;
    echo "Closing server on django"
done
