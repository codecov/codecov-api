Codecov API
-----------

A private Django REST Framework API intended to serve codecov's front end. 

## Getting Started

### Building

This project contains a makefile. To build the docker image:

    make build

`requirements.txt` is used in the base image. If you make changes to `requirements.txt` you will need to rebuild.

### Running Standalone

This project contains a `docker-compose.yml` file that is intended to run the api standalone. In this configuration it **does not** share codecov.io's development database; so don't expect parity there. 

To start the service, do

`docker-compose up`

Utilizing its own database provides a convenient way for the REST API to provide its own helpful seeds and migrations for active development without potentially destroying/modifying your development database for codecov.io.

Once running, the api will be available at `http://localhost:5100`

### Running with codecov.io

This service will startup when you run codecov.io normally. It is under that `api` block of codecov.io's `docker-compose.yml` file. 

### Testing

The easiest way to run tests (that doesn't require installing postgres and other dependencies) is to run inside of docker:

    docker-compose up
    docker exec -it codecov-api_api_1 pytest -rf

### Testing standalone

If you would like to use pytest directly (Either through an IDE like PyCharm or with the CLI), you will need to change the settings file used by pytest. Run this command to have the tests executed (You will need an instance of postgres running locally):

    RUN_ENV=TESTING DJANGO_SETTINGS_MODULE=codecov.settings_test pytest

Make sure to have all the requirements from `requirements.txt` installed.

### Deploying

All work merged into the `master` branch is immediately deployed to the production environment. More context on this strategy can be found [here](https://codecovio.atlassian.net/wiki/spaces/ENG/pages/507445249/Branching+and+Continuous+Delivery+Strategy+Proposal).

### Deploying to Staging environment

To deploy to our staging environment it's crucial to follow these steps:

1. Check in Slack to see if anyone is currently using the staging environment
2. If not, delete the current `staging` branch
3. Create a new `staging` branch and merge your feature branch into it

Steps 2 and 3 are important to limit interaction between features not yet merged into master. This approach was inspired by this document: https://codecovio.atlassian.net/wiki/spaces/ENG/pages/507445249/Branching+and+Continuous+Delivery+Strategy+Proposal

### Secret and Credential Management

This project should store no secrets or credentials in its source. If you need to add to / modify / setup secrets for this project, contact Eli and he'll get you started..
