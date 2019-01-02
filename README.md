Codecov API
-----------

A private Django REST Framework API intended to serve codecov's front end. 

## Getting Started

### Building

This project contains a makefile, to get up and running you will need to build the base image and the development image. Run:

    make build.base
    make build.dev

To build the API.

requirements.txt is used in the base image. If you make changes to requirements.txt you will need to run `make build.base` followed by `make build.dev`

### Running Standalone

This project contains a docker-compose.yml file that is intended to run the api standalone. In this configuration it *does not* share codecov.io's development database; so don't expect parity there. 

Utilizing its own database provides a convenient way for the REST API to provide its own helpful seeds and migrations for active development without potentially destroying/modifying your development database for codecov.io.

Once running, the api will be available at `http://localhost:5100`

### Running with codecov.io

This service will startup when you run codecov.io normally. It is under that `api` block of codecov.io's `docker-compose.yml` file. 

### Secret and Credential Management

This project should store no secrets or credentials in its source. If you need to add to / modify / setup secrets for this project, contact Eli and he'll get you started. 