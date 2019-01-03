FROM python:3.7-alpine

RUN \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev python3-dev
COPY . app

WORKDIR app

RUN pip install -r requirements.txt
