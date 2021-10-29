import logging
import time

import requests
from requests.exceptions import ConnectionError, HTTPError
from rest_framework.exceptions import NotFound

from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)


class TokenlessCirrusHandler(BaseTokenlessUploadHandler):
    def get_build(self):
        query = f"""{{
            "query": "query ($buildId: ID!) {{
                build(id: $buildId) {{
                    buildCreatedTimestamp,
                    changeIdInRepo,
                    durationInSeconds,
                    repository {{
                        name,
                        owner
                    }},
                    status
                }}
            }}",
            "variables": {{
                "buildId": {self.upload_params.get('build')}
            }}
        }}"""

        try:
            response = requests.post(
                "https://api.cirrus-ci.com/graphql",
                data=query,
                headers={"Content-Type": "application/json", "User-Agent": "Codecov"},
            )
        except (ConnectionError, HTTPError) as e:
            log.warning(
                f"Request error {e}",
                extra=dict(
                    build=self.upload_params["build"],
                    commit=self.upload_params["commit"],
                    job=self.upload_params["job"],
                    owner=self.upload_params["owner"],
                    repo_name=self.upload_params["repo"],
                ),
            )
            raise NotFound(
                "Unable to locate build via Cirrus CI API. Please upload with the Codecov repository upload token to resolve this issue."
            )

        build = response.json()
        log.info(
            "Cirrus CI build response found.",
            extra=dict(build=build, upload_params=self.upload_params,),
        )
        if "errors" in build or build.get("data") is None:
            log.warning(
                "Build Error",
                extra=dict(
                    build=self.upload_params["build"],
                    commit=self.upload_params["commit"],
                    error=build["errors"],
                    job=self.upload_params["job"],
                    owner=self.upload_params["owner"],
                    repo_name=self.upload_params["repo"],
                ),
            )
            raise NotFound(
                "Could not retrieve build via Cirrus CI API. Please upload with the Codecov repository upload token to resolve this issue."
            )

        return build

    def verify(self):
        if not self.upload_params.get("owner"):
            raise NotFound(
                'Missing "owner" argument. Please upload with the Codecov repository upload token to resolve this issue.'
            )
        owner = self.upload_params.get("owner")

        if not self.upload_params.get("repo"):
            raise NotFound(
                'Missing "repo" argument. Please upload with the Codecov repository upload token to resolve this issue.'
            )
        repo = self.upload_params.get("repo")

        if not self.upload_params.get("commit"):
            raise NotFound(
                'Missing "commit" argument. Please upload with the Codecov repository upload token to resolve this issue.'
            )
        commit = self.upload_params.get("commit")

        raw_build = self.get_build()
        build = raw_build["data"]["build"]

        # Check repository
        if build["repository"]["owner"] != owner or build["repository"]["name"] != repo:
            log.warning(
                f"Repository slug does not match Cirrus arguments",
                extra=dict(
                    build_info=build,
                    commit=commit,
                    job=self.upload_params.get("job"),
                    owner=owner,
                    repo_name=repo,
                ),
            )
            raise NotFound(
                "Repository slug does not match Cirrus CI build. Please upload with the Codecov repository upload token to resolve this issue."
            )

        # Check commit SHA
        if build["changeIdInRepo"] != commit:
            log.warning(
                f"Commit sha does not match Github actions arguments",
                extra=dict(
                    build_info=build,
                    commit=commit,
                    job=self.upload_params.get("job"),
                    owner=owner,
                    repo_name=repo,
                ),
            )
            raise NotFound(
                "Commit sha does not match Cirrus CI build. Please upload with the Codecov repository upload token to resolve issue."
            )

        # Check if current status is correct
        if build.get("status") != "EXECUTING":
            finishTimestamp = (
                build.get("buildCreatedTimestamp")
                + build.get("durationInSeconds")
                + (4 * 60)  # Add 4 minutes buffer
            )
            now = time.time()
            if now > finishTimestamp:
                log.warning(
                    f"Cirrus run is stale",
                    extra=dict(
                        build_info=build,
                        commit=commit,
                        job=self.upload_params.get("job"),
                        owner=owner,
                        repo_name=repo,
                    ),
                )
                log.warning(
                    f"Cirrus run is stale",
                    extra=dict(
                        build_info=build,
                        commit=commit,
                        job=self.upload_params.get("job"),
                        owner=owner,
                        repo_name=repo,
                    ),
                )
                raise NotFound("Cirrus run is stale")

        return "github"
