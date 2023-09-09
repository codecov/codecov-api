# syntax=docker/dockerfile:1.4
ARG REQUIREMENTS_IMAGE
ARG BERGLAS_VERSION=1.0.3
FROM us-docker.pkg.dev/berglas/berglas/berglas:$BERGLAS_VERSION as berglas

FROM $REQUIREMENTS_IMAGE

COPY --chmod=755 --from=berglas /bin/berglas /usr/local/bin/berglas

COPY . /app
WORKDIR /app

RUN python manage.py collectstatic --no-input