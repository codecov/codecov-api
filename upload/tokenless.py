import os
import logging
import requests
from json import load
from rest_framework import status
from upload.constants import errors
from django.http import HttpResponse
from rest_framework.exceptions import NotFound

from datetime import datetime, timedelta

log = logging.getLogger(__name__)

def verify_travis(upload_params):
    
    log.info(f"Started travis tokenless upload",
        extra=dict(
            commit=upload_params['commit'],
            repo_name=upload_params['repo'],
            job=upload_params['job'],
            owner=upload_params['owner']
        )
    )

    # find repo in travis.com
    travisDotComJobReturned = True
    job = None

    try:
        job = requests.get(
            'https://api.travis-ci.com/job/{}'.format(upload_params['job']),
            headers={
                'Travis-API-Version': '3',
                'User-Agent': 'Codecov'
            }
        )
    except requests.exceptions.HTTPError as e:
        log.info(f"HTTP error {e}",
            extra=dict(
                commit=upload_params['commit'],
                repo_name=upload_params['repo'],
                job=upload_params['job'],
                owner=upload_params['owner']
            )
        )
        travisDotComJobReturned = False
        pass
    except requests.exceptions.ConnectionError as e:
        log.info(f"Connection error {e}",
            extra=dict(
                commit=upload_params['commit'],
                repo_name=upload_params['repo'],
                job=upload_params['job'],
                owner=upload_params['owner']
            )
        )
        travisDotComJobReturned = False
        pass
    # url to settings page for repo, only used when travis-tokenless-general-error is thrown
    codecovUrl = 'https://codecov.io/gh/{0}/{1}/settings'.format(upload_params['owner'], upload_params['repo'])
    slug = f"{upload_params['owner']}/{upload_params['repo']}"
    # if job not found in travis.com try travis.org
    if not travisDotComJobReturned or travisDotComJobReturned and job.json()['repository']['slug'] != slug:
        try:
            job = requests.get(
                'https://api.travis-ci.org/job/{}'.format(upload_params['job']),
                headers={
                    'Travis-API-Version': '3',
                    'User-Agent': 'Codecov'
                },
            )
        except requests.exceptions.HTTPError as e:
            log.info(f"HTTP error {e}",
                extra=dict(
                    commit=upload_params['commit'],
                    repo_name=upload_params['repo'],
                    job=upload_params['job'],
                    owner=upload_params['owner']
                )
            )
            raise NotFound(errors['travis']['tokenless-general-error'].format(codecovUrl))
        except requests.exceptions.ConnectionError as e:
            # repo is private and could not be found via travis api, throw general error
            log.info(f"Connection error {e}",
                extra=dict(
                    commit=upload_params['commit'],
                    repo_name=upload_params['repo'],
                    job=upload_params['job'],
                    owner=upload_params['owner']
                )
            )
            raise NotFound(errors['travis']['tokenless-general-error'].format(codecovUrl))

    # if job is not defined at this point, throw general error
    if job:
        job = job.json()
        log.info(f"Travis CI job response: {job}",
            extra=dict(
                commit=upload_params['commit'],
                repo_name=upload_params['repo'],
                job=upload_params['job'],
                owner=upload_params['owner']
            )
        )
    else:
        log.info(f"Unable to locate build via Travis API",
            extra=dict(
                commit=upload_params['commit'],
                repo_name=upload_params['repo'],
                job=upload_params['job'],
                owner=upload_params['owner']
            )
        )
        raise NotFound(errors['travis']['tokenless-general-error'].format(codecovUrl))

    # Check repo slug and commit sha
    # We check commit sha only for a push event since sha in arguments will not match if event type = pull request
    if (
        job['repository']['slug'] != slug
        or job['commit']['sha'] != upload_params['commit']
        and job['build']['event_type'] != 'pull_request'
    ):
        log.info(f"Repository slug: {slug} or commit sha: {upload_params['commit']} do not match travis arguments",
            extra=dict(
                commit=upload_params['commit'],
                repo_name=upload_params['repo'],
                job=upload_params['job'],
                owner=upload_params['owner']
            )
        )
        raise NotFound(errors['travis']['tokenless-general-error'].format(codecovUrl))

    # Verify job finished within the last 4 minutes or is still in progress
    if(job['finished_at'] != None):
        finishTimestamp = job['finished_at'].replace('T',' ').replace('Z','')
        buildFinishDateObj = datetime.strptime(finishTimestamp, '%Y-%m-%d %H:%M:%S')
        finishTimeWithBuffer = buildFinishDateObj + timedelta(minutes=4)
        now = datetime.utcnow()
        if not now <= finishTimeWithBuffer:
            log.info(f"Cancelling upload: 4 mins since build",
                extra=dict(
                    commit=upload_params['commit'],
                    repo_name=upload_params['repo'],
                    job=upload_params['job'],
                    owner=upload_params['owner']
                )
            )
            raise NotFound(errors['travis']['tokenless-stale-build'])
    else:
        # check if current state is correct (i.e not finished)
        if job['state'] != 'started':
            log.info(f"Cancelling upload: job state does not indicate that build is in progress",
                extra=dict(
                    commit=upload_params['commit'],
                    repo_name=upload_params['repo'],
                    job=upload_params['job'],
                    owner=upload_params['owner']
                )
            )
            raise NotFound(errors['travis']['tokenless-bad-status'])

    log.info(f"Finished travis tokenless upload",
        extra=dict(
            commit=upload_params['commit'],
            repo_name=upload_params['repo'],
            job=upload_params['job'],
            owner=upload_params['owner']
        )
    )
    return 'github'
