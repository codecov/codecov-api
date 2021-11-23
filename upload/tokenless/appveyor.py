import logging
from datetime import datetime, timedelta

import requests
from requests.exceptions import ConnectionError, HTTPError
from rest_framework.exceptions import NotFound

from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)


class TokenlessAppveyorHandler(BaseTokenlessUploadHandler):
    def get_build(self):
        try:
            build = requests.get(
                "https://ci.appveyor.com/api/projects/{}/{}/build/{}".format(
                    *self.job.split("/", 2)
                ),
                headers={"Accept": "application/json", "User-Agent": "Codecov"},
            )
        except (ConnectionError, HTTPError) as e:
            log.warning(
                f"HTTP error {e}",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                ),
            )
            raise NotFound(
                "Unable to locate build via Appveyor API. Please upload with the Codecov repository upload token to resolve issue."
            )

        if not build:
            raise NotFound(
                "Unable to locate build via Appveyor API. Please upload with the Codecov repository upload token to resolve issue."
            )

        return build.json()

    def verify(self):
        if not self.upload_params.get("job"):
            raise NotFound(
                'Missing "job" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )

        self.job = (
            self.upload_params.get("job")
            if "/" in self.upload_params.get("job")
            else (
                f'{self.upload_params.get("owner")}/{self.upload_params.get("repo")}/{self.upload_params.get("job")}'
            )
        )

        self.job = self.job.replace("+", "%20").replace(" ", "%20")

        build = self.get_build()

        # validate build
        if not any(
            filter(
                lambda j: j["jobId"] == self.upload_params.get("build")
                and j.get("finished") is None,
                build["build"]["jobs"],
            )
        ):
            raise NotFound(
                "Build already finished, unable to accept new reports. Please upload with the Codecov repository upload token to resolve issue."
            )

        service = self.check_repository_type(build["project"]["repositoryType"])

        return service
