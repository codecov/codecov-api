import logging
from datetime import datetime, timedelta

from asgiref.sync import async_to_sync
from django.conf import settings
from rest_framework.exceptions import NotFound
from shared.torngit import get
from shared.torngit.exceptions import TorngitClientError

from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)


class TokenlessGithubActionsHandler(BaseTokenlessUploadHandler):

    actions_token = settings.GITHUB_ACTIONS_TOKEN
    client_id = settings.GITHUB_CLIENT_ID
    client_secret = settings.GITHUB_CLIENT_SECRET

    def get_build(self):
        git = get(
            "github",
            token=dict(key=self.actions_token),
            repo=dict(name=self.upload_params.get("repo")),
            owner=dict(username=self.upload_params.get("owner")),
            oauth_consumer_token=dict(key=self.client_id, secret=self.client_secret),
        )

        try:
            actions_response = async_to_sync(git.get_workflow_run)(
                self.upload_params.get("build")
            )
        except TorngitClientError as e:
            log.warning(
                f"Request client error {e}",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                ),
            )
            raise NotFound(
                "Unable to locate build via Github Actions API. Please upload with the Codecov repository upload token to resolve issue."
            )
        except Exception as e:
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
                "Unable to locate build via Github Actions API. Please upload with the Codecov repository upload token to resolve issue."
            )

        return actions_response

    def verify(self):
        if not self.upload_params.get("owner"):
            raise NotFound(
                'Missing "owner" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        owner = self.upload_params.get("owner")

        if not self.upload_params.get("repo"):
            raise NotFound(
                'Missing "repo" argument. Please upload with the Codecov repository upload token to resolve issue.'
            )
        repo = self.upload_params.get("repo")

        build = self.get_build()

        if (
            build["public"] != True
            or build["slug"] != f"{owner}/{repo}"
            or (
                build["commit_sha"] != self.upload_params.get("commit")
                and self.upload_params.get("pr") == None
            )
        ):
            log.warning(
                f"Repository slug or commit sha do not match Github actions arguments",
                extra=dict(
                    commit=self.upload_params.get("commit"),
                    repo_name=self.upload_params.get("repo"),
                    job=self.upload_params.get("job"),
                    owner=self.upload_params.get("owner"),
                ),
            )
            raise NotFound(
                "Repository slug or commit sha do not match Github actions build. Please upload with the Codecov repository upload token to resolve issue."
            )

        # Check if current status is correct (not stale or in progress)
        if build.get("status") not in ["in_progress", "queued"]:
            # Verify workflow finished within the last 4 minutes because it's not in-progress
            try:
                build_finish_date_obj = datetime.strptime(
                    build["finish_time"], "%Y-%m-%dT%H:%M:%SZ"
                )
            except ValueError:
                build_finish_date_obj = datetime.strptime(
                    build["finish_time"], "%Y-%m-%d %H:%M:%S"
                )

            finish_time_with_buffer = build_finish_date_obj + timedelta(minutes=10)
            now = datetime.utcnow()
            if not now <= finish_time_with_buffer:
                log.warning(
                    "Actions workflow run is stale",
                    extra=dict(
                        build=build,
                        commit=self.upload_params.get("commit"),
                        finish_time_with_buffer=finish_time_with_buffer,
                        job=self.upload_params.get("job"),
                        now=now,
                        owner=self.upload_params.get("owner"),
                        repo_name=self.upload_params.get("repo"),
                        time_diff=now - finish_time_with_buffer,
                    ),
                )
                log.warning(
                    "Actions workflow run is stale",
                    extra=dict(
                        build=build,
                        commit=self.upload_params.get("commit"),
                        finish_time_with_buffer=finish_time_with_buffer,
                        job=self.upload_params.get("job"),
                        now=now,
                        owner=self.upload_params.get("owner"),
                        repo_name=self.upload_params.get("repo"),
                        time_diff=now - finish_time_with_buffer,
                    ),
                )
                raise NotFound("Actions workflow run is stale")

        return "github"
