import uuid
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory
from core.models import Branch, Commit, Pull, PullStates, Repository
from core.tests.factories import (
    BranchFactory,
    CommitFactory,
    PullFactory,
    RepositoryFactory,
)
from webhook_handlers.constants import (
    BitbucketServerHTTPHeaders,
    BitbucketServerWebhookEvents,
    WebhookHandlerErrorMessages,
)


class TestBitbucketServerWebhookHandler(APITestCase):
    def _post_event_data(
        self, event, data={}, hookid="f2e634c1-63db-44ac-b119-019fa6a71a2c"
    ):
        return self.client.post(
            reverse("bitbucket-server-webhook"),
            **{BitbucketServerHTTPHeaders.EVENT: event, BitbucketServerHTTPHeaders.UUID: hookid},
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="bitbucket_server"),
            service_id="673a6070-3421-46c9-9d48-90745f7bfe8e",
            active=True,
            hookid="f2e634c1-63db-44ac-b119-019fa6a71a2c",
        )
        self.pull = PullFactory(
            author=self.repo.author,
            repository=self.repo,
            pullid=1,
            state=PullStates.OPEN,
        )

    def test_unknown_repo(self):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.PULL_REQUEST_CREATED,
            data={"pullRequest": {"id": pullid, "toRef": { "repository": { "id": "some-unknown-value"}}}},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_repo(self):
        self.repo.active = False
        self.repo.save()
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.PULL_REQUEST_CREATED,
            data={"pullRequest": {"toRef": { "repository": { "id": "673a6070-3421-46c9-9d48-90745f7bfe8e"}}}},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE

    @patch("services.task.TaskService.pulls_sync")
    def test_pull_request_created(self, pulls_sync_mock):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.PULL_REQUEST_CREATED,
            data={"pullRequest": {"id": pullid, "toRef": { "repository": { "id": "673a6070-3421-46c9-9d48-90745f7bfe8e"}}}},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Opening pull request in Codecov"

        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid=pullid)

    def test_pull_request_fulfilled(self):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.PULL_REQUEST_MERGED,
            data={"pullRequest": {"id": pullid, "toRef": { "repository": { "id": "673a6070-3421-46c9-9d48-90745f7bfe8e"}}}},

        )
        assert response.status_code == status.HTTP_200_OK
        self.pull.refresh_from_db()
        assert self.pull.state == PullStates.MERGED

    def test_pull_request_rejected(self):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.PULL_REQUEST_REJECTED,
            data={"pullRequest": {"id": pullid, "toRef": { "repository": { "id": "673a6070-3421-46c9-9d48-90745f7bfe8e"}}}},
        )
        assert response.status_code == status.HTTP_200_OK
        self.pull.refresh_from_db()
        assert self.pull.state == PullStates.CLOSED

    def test_repo_push_branch_deleted(self):
        branch = BranchFactory(repository=self.repo, name="name-of-branch")
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.REPO_REFS_CHANGED,
            data={
                "repository": {"id": "673a6070-3421-46c9-9d48-90745f7bfe8e"},
                "push": {
                    "changes": {
                            "new": None,
                            "old": {
                                "type": "branch",
                                "name": "name-of-branch",
                                "target": {},
                            },
                            "links": {},
                            "created": False,
                            "forced": False,
                            "closed": False,
                            "commits": [
                                {
                                    "hash": "03f4a7270240708834de475bcf21532d6134777e",
                                    "type": "commit",
                                    "message": "commit message\n",
                                    "author": {},
                                    "links": {},
                                }
                            ],
                            "truncated": False,
                    }
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data is None
        assert not Branch.objects.filter(
            repository=self.repo, name="name-of-branch"
        ).exists()

    def test_repo_push_new_branch_sync_yaml_skipped(self):
        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.REPO_REFS_CHANGED,
            data={
                "repository": {"id": "673a6070-3421-46c9-9d48-90745f7bfe8e"},
                "push": {
                    "changes":
                        {
                            "new": {
                                "type": "branch",
                                "name": "name-of-branch",
                                "target": {},
                            },
                            "old": {
                                "type": "branch",
                                "name": "name-of-branch",
                                "target": {},
                            },
                            "links": {},
                            "created": False,
                            "forced": False,
                            "closed": False,
                            "commits": [
                                {
                                    "hash": "03f4a7270240708834de475bcf21532d6134777e",
                                    "type": "commit",
                                    "message": "commit message\n",
                                    "author": {},
                                    "links": {},
                                }
                            ],
                            "truncated": False,
                        }
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Synchronize codecov.yml skipped"

    def test_repo_push_new_branch_sync_yaml(self):
        self.repo.cache = {"yaml": "codecov.yaml"}
        self.repo.save()

        response = self._post_event_data(
            event=BitbucketServerWebhookEvents.REPO_REFS_CHANGED,
            data={
                "repository": {"id": "673a6070-3421-46c9-9d48-90745f7bfe8e"},
                "push": {
                    "changes":
                        {
                            "new": {
                                "type": "branch",
                                "name": "name-of-branch",
                                "target": {},
                            },
                            "old": {
                                "type": "branch",
                                "name": "name-of-branch",
                                "target": {},
                            },
                            "links": {},
                            "created": False,
                            "forced": False,
                            "closed": False,
                            "commits": [
                                {
                                    "hash": "03f4a7270240708834de475bcf21532d6134777e",
                                    "type": "commit",
                                    "message": "commit message\n",
                                    "author": {},
                                    "links": {},
                                }
                            ],
                            "truncated": False,
                        }
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Synchronize codecov.yml"
