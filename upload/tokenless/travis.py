import logging
from datetime import datetime, timedelta
from json import load

import requests
from requests.exceptions import ConnectionError, HTTPError
from rest_framework.exceptions import NotFound

from upload.constants import errors
from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)


class TokenlessTravisHandler(BaseTokenlessUploadHandler):
    def get_build(self):
        travis_dot_com = False

        try:
            build = requests.get(
                "https://api.travis-ci.com/job/{}".format(self.upload_params["job"]),
                headers={"Travis-API-Version": "3", "User-Agent": "Codecov"},
            )
            travis_dot_com = (
                build.json()["repository"]["slug"]
                == f"{self.upload_params['owner']}/{self.upload_params['repo']}"
            )
        except (ConnectionError, HTTPError) as e:
            log.warning(
                f"Request error {e}",
                extra=dict(
                    commit=self.upload_params["commit"],
                    repo_name=self.upload_params["repo"],
                    job=self.upload_params["job"],
                    owner=self.upload_params["owner"],
                ),
            )
            pass
        except Exception as e:
            log.warning(
                f"Error {e}",
                extra=dict(
                    commit=self.upload_params["commit"],
                    repo_name=self.upload_params["repo"],
                    job=self.upload_params["job"],
                    owner=self.upload_params["owner"],
                ),
            )

        # if job not found in travis.com try travis.org
        if not travis_dot_com:
            log.info(
                f"Unable to verify using travis.com, trying travis.org",
                extra=dict(
                    commit=self.upload_params["commit"],
                    repo_name=self.upload_params["repo"],
                    job=self.upload_params["job"],
                    owner=self.upload_params["owner"],
                ),
            )
            try:
                build = requests.get(
                    "https://api.travis-ci.org/job/{}".format(
                        self.upload_params["job"]
                    ),
                    headers={"Travis-API-Version": "3", "User-Agent": "Codecov"},
                )
            except (ConnectionError, HTTPError) as e:
                log.warning(
                    f"Request error {e}",
                    extra=dict(
                        commit=self.upload_params["commit"],
                        repo_name=self.upload_params["repo"],
                        job=self.upload_params["job"],
                        owner=self.upload_params["owner"],
                    ),
                )
                raise NotFound(
                    errors["travis"]["tokenless-general-error"].format(
                        f"https://codecov.io/gh/{self.upload_params['owner']}/{self.upload_params['repo']}/settings"
                    )
                )
        if not build:
            raise NotFound(
                errors["travis"]["tokenless-general-error"].format(
                    f"https://codecov.io/gh/{self.upload_params['owner']}/{self.upload_params['repo']}/settings"
                )
            )

        return build.json()

    def verify(self):
        # find repo in travis.com
        job = self.get_build()

        slug = f"{self.upload_params['owner']}/{self.upload_params['repo']}"

        codecovUrl = f"https://codecov.io/gh/{self.upload_params['owner']}/{self.upload_params['repo']}/settings"

        # Check repo slug and commit sha
        # We check commit sha only for a push event since sha in arguments will not match if event type = pull request
        if (
            job["repository"]["slug"] != slug
            or job["commit"]["sha"] != self.upload_params["commit"]
            and job["build"]["event_type"] != "pull_request"
        ):
            log.warning(
                f"Repository slug: {slug} or commit sha: {self.upload_params['commit']} do not match travis arguments",
                extra=dict(
                    commit=self.upload_params["commit"],
                    repo_name=self.upload_params["repo"],
                    job=self.upload_params["job"],
                    owner=self.upload_params["owner"],
                ),
            )
            raise NotFound(
                errors["travis"]["tokenless-general-error"].format(codecovUrl)
            )

        # Verify job finished within the last 4 minutes or is still in progress
        if job["finished_at"] != None:
            finishTimestamp = job["finished_at"].replace("T", " ").replace("Z", "")
            buildFinishDateObj = datetime.strptime(finishTimestamp, "%Y-%m-%d %H:%M:%S")
            finishTimeWithBuffer = buildFinishDateObj + timedelta(minutes=4)
            now = datetime.utcnow()
            if not now <= finishTimeWithBuffer:
                log.warning(
                    f"Cancelling upload: 4 mins since build",
                    extra=dict(
                        commit=self.upload_params["commit"],
                        repo_name=self.upload_params["repo"],
                        job=self.upload_params["job"],
                        owner=self.upload_params["owner"],
                    ),
                )
                raise NotFound(errors["travis"]["tokenless-stale-build"])
        else:
            # check if current state is correct (i.e not finished)
            if job["state"] != "started":
                log.warning(
                    f"Cancelling upload: job state does not indicate that build is in progress",
                    extra=dict(
                        commit=self.upload_params["commit"],
                        repo_name=self.upload_params["repo"],
                        job=self.upload_params["job"],
                        owner=self.upload_params["owner"],
                    ),
                )
                raise NotFound(errors["travis"]["tokenless-bad-status"])

        log.info(
            f"Finished travis tokenless upload",
            extra=dict(
                commit=self.upload_params["commit"],
                repo_name=self.upload_params["repo"],
                job=self.upload_params["job"],
                owner=self.upload_params["owner"],
            ),
        )
        return "github"
