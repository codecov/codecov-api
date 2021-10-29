import logging
from datetime import datetime, timedelta

import requests
from django.conf import settings
from requests.exceptions import ConnectionError, HTTPError
from rest_framework.exceptions import NotFound

from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)


class TokenlessCircleciHandler(BaseTokenlessUploadHandler):

    circleci_token = settings.CIRCLECI_TOKEN

    def get_build(self):
        build_num = self.build.split(".")[0]
        try:
            build = requests.get(
                f"https://circleci.com/api/v1/project/{self.owner}/{self.repo}/{build_num}?circle-token={self.circleci_token}",
                headers={"Accept": "application/json", "User-Agent": "Codecov"},
            )
            return build.json()
        except (ConnectionError, HTTPError) as e:
            log.warning(
                f"Request error {e}",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                ),
            )
            raise NotFound(
                "Unable to locate build via CircleCI API. Please upload with the Codecov repository upload token to resolve issue."
            )

    def verify(self):
        if not self.upload_params.get("build"):
            raise NotFound(
                'Missing "build" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        self.build = self.upload_params.get("build")

        if not self.upload_params.get("owner"):
            raise NotFound(
                'Missing "owner" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        self.owner = self.upload_params.get("owner")

        if not self.upload_params.get("repo"):
            raise NotFound(
                'Missing "repo" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        self.repo = self.upload_params.get("repo")

        build = self.get_build()

        if build.get("vcs_revision", "") != self.upload_params["commit"]:
            raise NotFound(
                "Commit sha does not match Circle build. Please upload with the Codecov repository upload token to resolve issue."
            )

        if build.get("stop_time") is not None:
            raise NotFound("Build has already finished, uploads rejected.")

        return build["vcs_type"]
