#!/bin/sh

## remove all the files from prod/dev systems that we won't need in enteprise
cd /
mkdir enterprise
cp -a /app/build/lib.linux-x86_64-3.7/. /enterprise/
cp /app/manage.py /enterprise/manage.py
cp /app/conftest.py /enterprise/conftest.py
cp /app/celery_config.py /enterprise/celery_config.py

# must copy over migrations because they don't compile.
cp -rf /app/core/migrations/ /enterprise/migrations

# delete the .py files, etc
rm -rf /app

# move needed files back to /app directory
mv /enterprise /app
