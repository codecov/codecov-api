# syntax=docker/dockerfile:1.4
ARG REQUIREMENTS_IMAGE
ARG BUILD_ENV=self-hosted
ARG BERGLAS_VERSION=2.0.6

FROM us-docker.pkg.dev/berglas/berglas/berglas:$BERGLAS_VERSION as berglas

FROM $REQUIREMENTS_IMAGE as app

COPY . /app/apps/codecov-api
WORKDIR /app/apps/codecov-api
RUN python manage.py collectstatic --no-input


FROM app as local

FROM app as cloud
ARG RELEASE_VERSION
ENV RELEASE_VERSION=$RELEASE_VERSION
COPY --chmod=755 --from=berglas /bin/berglas /usr/local/bin/berglas

FROM app as self-hosted

# set settings module
ENV DJANGO_SETTINGS_MODULE="codecov.settings_enterprise"
# Remove the settings dev and enterprise files.
# These should *never* make it to enterprise.
RUN rm /app/apps/codecov-api/codecov/settings_dev.py && \
    rm /app/apps/codecov-api/codecov/settings_prod.py && \
    rm /app/apps/codecov-api/codecov/settings_test.py && \
    rm /app/apps/codecov-api/codecov/settings_staging.py && \
    rm /app/apps/codecov-api/dev.sh && \
    rm /app/apps/codecov-api/migrate.sh && \
    rm /app/apps/codecov-api/prod.sh && \
    rm /app/apps/codecov-api/staging.sh && \
    rm /app/apps/codecov-api/production.yml && \
    rm /app/apps/codecov-api/development.yml
# Remove unneeded folders
RUN rm -rf /app/apps/codecov-api/.github
RUN rm -rf /app/apps/codecov-api/.circleci
# Create the codecov user to run the container as
RUN addgroup --system application \
    && adduser --system codecov --ingroup application --home /home/codecov
RUN mkdir -p /config && chown codecov:application /config
# copy the enterprise settings module.
WORKDIR /app/apps/codecov-api
RUN chmod +x enterprise.sh && \
    chown codecov:application /app/apps/codecov-api
ARG RELEASE_VERSION
ENV RUN_ENV="ENTERPRISE"
ENV RELEASE_VERSION=$RELEASE_VERSION
ENV DJANGO_SETTINGS_MODULE="codecov.settings_enterprise"
ENV CODECOV_API_PORT=8000
ENTRYPOINT ["./enterprise.sh"]

FROM self-hosted as self-hosted-runtime
USER root
ARG EXTERNAL_DEPS_FOLDER=./external_deps
RUN mkdir $EXTERNAL_DEPS_FOLDER
RUN pip install --target $EXTERNAL_DEPS_FOLDER psycopg2-binary tlslite-ng
RUN chown codecov:application $EXTERNAL_DEPS_FOLDER
USER codecov

FROM ${BUILD_ENV}
