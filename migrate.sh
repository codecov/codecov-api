#!/bin/sh

echo "Running Django migrations"
prefix=""
if [ -f "/usr/local/bin/berglas" ]; then
  prefix="berglas exec --"
fi

$prefix python manage.py migrate
$prefix python manage.py pgpartition --yes --skip-delete