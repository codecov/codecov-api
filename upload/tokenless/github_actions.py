import logging
import asyncio
from shared.torngit import get
from django.conf import settings
from datetime import datetime, timedelta
from rest_framework.exceptions import NotFound
from shared.torngit.exceptions import TorngitClientError
from upload.tokenless.base import BaseTokenlessUploadHandler

log = logging.getLogger(__name__)

class TokenlessGithubActionsHandler(BaseTokenlessUploadHandler):

    actions_token = settings.GITHUB_ACTIONS_TOKEN
    client_id = settings.GITHUB_CLIENT_ID
    client_secret = settings.GITHUB_CLIENT_SECRET

    def get_build(self):
        git = get(
            'github',
            token=dict(key=self.actions_token),
            repo=dict(name=self.upload_params.get('repo')),
            owner=dict(username=self.upload_params.get('owner')),
            oauth_consumer_token=dict(
                key=self.client_id,
                secret=self.client_secret
            )
        )

        try:
            actions_response = asyncio.run(git.get_workflow_run(self.upload_params.get('build')))
        except TorngitClientError as e:
            log.error(f"Request error {e}",
                extra=dict(
                    commit=self.upload_params.get('commit'),
                    repo_name=self.upload_params.get('repo'),
                    job=self.upload_params.get('job'),
                    owner=self.upload_params.get('owner')
                )
            )
            raise NotFound('Unable to locate build via Github Actions API. Please upload with the Codecov repository upload token to resolve issue.')

        return actions_response

    def verify(self):
        if not self.upload_params.get('owner'): raise NotFound('Missing "owner" argument. Please upload with the Codecov repository upload token to resolve issue.')
        owner = self.upload_params.get('owner')

        if not self.upload_params.get('repo'): raise NotFound('Missing "repo" argument. Please upload with the Codecov repository upload token to resolve issue.')
        repo = self.upload_params.get('repo')

        build = self.get_build()

        if (
            build['public'] != True or
            build['slug'] != f'{owner}/{repo}' or
            (build['commit_sha'] != self.upload_params.get('commit') and self.upload_params.get('pr') == None)):
                log.warning(f"Repository slug or commit sha do not match Github actions arguments",
                    extra=dict(
                        commit=self.upload_params.get('commit'),
                        repo_name=self.upload_params.get('repo'),
                        job=self.upload_params.get('job'),
                        owner=self.upload_params.get('owner')
                    )
                )
                raise NotFound("Repository slug or commit sha do not match Github actions build. Please upload with the Codecov repository upload token to resolve issue.")

        # Check if current status is correct (not stale or in progress)
        if build.get('status') != 'in_progress':
            # Verify workflow finished within the last 4 minutes because it's not in-progress
            finishTimestamp = build['finish_time'].replace('T',' ').replace('Z','')
            buildFinishDateObj = datetime.strptime(finishTimestamp, '%Y-%m-%d %H:%M:%S')
            finishTimeWithBuffer = buildFinishDateObj + timedelta(minutes=4)
            now = datetime.utcnow()
            if not now <= finishTimeWithBuffer:
                log.error(f"Actions workflow run is stale",
                    extra=dict(
                        commit=self.upload_params.get('commit'),
                        repo_name=self.upload_params.get('repo'),
                        job=self.upload_params.get('job'),
                        owner=self.upload_params.get('owner')
                    )
                )
                log.warning(f"Actions workflow run is stale",
                    extra=dict(
                        commit=self.upload_params.get('commit'),
                        repo_name=self.upload_params.get('repo'),
                        job=self.upload_params.get('job'),
                        owner=self.upload_params.get('owner')
                    )
                )
                raise NotFound('Actions workflow run is stale')

        return 'github'
