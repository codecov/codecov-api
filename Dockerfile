FROM            codecov/baseapi

EXPOSE          8000

COPY            . /app

WORKDIR         /app

RUN             python manage.py collectstatic --no-input
