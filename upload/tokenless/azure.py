import logging
from datetime import datetime, timedelta

import requests
from requests.exceptions import ConnectionError, HTTPError
from rest_framework.exceptions import NotFound
from simplejson import JSONDecodeError

from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)


class TokenlessAzureHandler(BaseTokenlessUploadHandler):
    def get_build(self):
        try:
            response = requests.get(
                f"{self.server_uri}{self.project}/_apis/build/builds/{self.job}?api-version=5.0",
                headers={"Accept": "application/json", "User-Agent": "Codecov"},
            )
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
                "Unable to locate build via Azure API. Please upload with the Codecov repository upload token to resolve issue."
            )

        if not response:
            raise NotFound(
                "Unable to locate build via Azure API. Please upload with the Codecov repository upload token to resolve issue."
            )
        try:
            build = response.json()
        except (JSONDecodeError) as e:
            log.warning(
                f"Expected JSON in Azure response, got error {e} instead",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                    response=response,
                ),
            )
            raise NotFound(
                "Unable to locate build via Azure API. Project is likely private, please upload with the Codecov repository upload token to resolve issue."
            )
        return build

    def verify(self):

        if not self.upload_params.get("job"):
            raise NotFound(
                'Missing "job" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        self.job = self.upload_params.get("job")

        if not self.upload_params.get("project"):
            raise NotFound(
                'Missing "project" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        self.project = self.upload_params.get("project")

        if not self.upload_params.get("server_uri"):
            raise NotFound(
                'Missing "server_uri" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        self.server_uri = self.upload_params.get("server_uri")

        build = self.get_build()

        # Build should have finished within the last 4 mins OR should have an 'inProgress' flag
        if build["status"] == "completed":
            finishTimestamp = build["finishTime"].replace("T", " ").replace("Z", "")
            buildFinishDateObj = datetime.strptime(
                finishTimestamp, "%Y-%m-%d %H:%M:%S.%f"
            )
            finishTimeWithBuffer = buildFinishDateObj + timedelta(minutes=4)
            now = datetime.utcnow()
            if not now <= finishTimeWithBuffer:
                raise NotFound(
                    "Azure build has already finished. Please upload with the Codecov repository upload token to resolve issue."
                )
        else:
            if build["status"].lower() != "inprogress":
                raise NotFound(
                    "Azure build has already finished. Please upload with the Codecov repository upload token to resolve issue."
                )

        # Check build ID
        build["buildNumber"] = build["buildNumber"].replace("+", " ")
        self.upload_params["build"] = self.upload_params.get("build").replace("+", " ")
        if build["buildNumber"] != self.upload_params.get("build"):
            log.warning(
                f"Azure build numbers do not match. Upload build number: {self.upload_params.get('build')}, Azure build number: {self.upload_params.get('buildNumber')}",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                ),
            )
            raise NotFound(
                "Build numbers do not match. Please upload with the Codecov repository upload token to resolve issue."
            )

        # Make sure commit sha matches
        if build["sourceVersion"] != self.upload_params.get("commit") and (
            build.get("triggerInfo", {}).get("pr.sourceSha")
            != self.upload_params.get("commit")
        ):
            log.warning(
                "Commit sha does not match Azure build",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                ),
            )
            raise NotFound(
                "Commit sha does not match Azure build. Please upload with the Codecov repository upload token to resolve issue."
            )

        # Azure supports various repo types, ensure current repo type is supported on Codecov
        service = self.check_repository_type(build["repository"]["type"])

        # Validation step is complete, return repo type
        return service
