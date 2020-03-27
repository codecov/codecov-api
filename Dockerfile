# BUILD STAGE - Download dependencies from GitHub that require SSH access
FROM python:3.7.4-alpine as build

RUN             apk update \
                && apk add --update --no-cache \
                git \
                openssh \
                postgresql-dev \
                musl-dev \
                libxslt-dev \
                python-dev \
                libffi-dev \
                gcc \
                bash \
                && pip install --upgrade pip

ARG             SSH_PRIVATE_KEY
RUN             mkdir /root/.ssh/
RUN             echo "${SSH_PRIVATE_KEY}" > /root/.ssh/id_rsa
RUN             ssh-keyscan -H github.com >> /root/.ssh/known_hosts
RUN             chmod 600 /root/.ssh/id_rsa

COPY            requirements.txt /
WORKDIR         /pip-packages/
RUN             git config --global url."git@github.com:".insteadOf "https://github.com/"
RUN             pip download -r /requirements.txt
RUN             pip download setuptools wheel




# RUNTIME STAGE - Copy packages from build stage and install runtime dependencies
FROM            python:3.7.4-alpine

RUN             apk add --no-cache postgresql-libs && \
                apk add --no-cache --virtual .build-deps gcc \
                musl-dev \
                postgresql-dev \
                libxslt-dev \
                python-dev \
                libffi-dev \
                openssl-dev \
                make \
                python3-dev

RUN             wget -q -O /usr/local/bin/berglas https://storage.googleapis.com/berglas/0.5.0/linux_amd64/berglas && \
                chmod +x /usr/local/bin/berglas

WORKDIR         /pip-packages/
COPY            --from=build /pip-packages/ /pip-packages/

RUN             rm -rf /pip-packages/src
RUN             pip install --find-links=/pip-packages/ /pip-packages/*

EXPOSE          8000

COPY            . /app

WORKDIR         /app
