# BUILD STAGE - Download dependencies from GitHub that require SSH access
FROM python:3.7-alpine as build

RUN             apk update \
                && apk add --update --no-cache \ 
                git \ 
                openssh \ 
                postgresql-dev \
                libffi-dev \
                gcc \
                musl-dev \
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

# RUNTIME STAGE - Copy packages from build stage and install runtime dependencies
FROM            python:3.7-alpine

RUN             apk add --no-cache postgresql-libs && \
                apk add --no-cache --virtual .build-deps gcc \ 
                musl-dev \ 
                postgresql-dev \ 
                python3-dev \
                libffi-dev \
                git

WORKDIR         /pip-packages/
COPY            --from=build /pip-packages/ /pip-packages/
RUN             rm -rf /pip-packages/src
RUN             pip install --find-links=/pip-packages/ /pip-packages/*

EXPOSE          8000

COPY            . /app

WORKDIR         /app
