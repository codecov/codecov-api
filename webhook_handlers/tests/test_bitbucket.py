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
    BitbucketHTTPHeaders,
    BitbucketWebhookEvents,
    WebhookHandlerErrorMessages,
)


class TestBitbucketWebhookHandler(APITestCase):
    def _post_event_data(
        self, event, data={}, hookid="f2e634c1-63db-44ac-b119-019fa6a71a2c"
    ):
        return self.client.post(
            reverse("bitbucket-webhook"),
            **{BitbucketHTTPHeaders.EVENT: event, BitbucketHTTPHeaders.UUID: hookid},
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="bitbucket"),
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
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_PUSH,
            data={"repository": {"uuid": "{94f4c9b4-254f-46cf-a39e-97ce03fe58af}"},},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_repo(self):
        self.repo.active = False
        self.repo.save()
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_PUSH,
            data={"repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE

    @patch("services.task.TaskService.pulls_sync")
    def test_pull_request_created(self, pulls_sync_mock):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketWebhookEvents.PULL_REQUEST_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "pullrequest": {"id": pullid},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Opening pull request in Codecov"

        pulls_sync_mock.assert_called_once_with(
            repoid=self.repo.repoid, pullid=pullid,
        )

    def test_pull_request_fulfilled(self):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketWebhookEvents.PULL_REQUEST_FULFILLED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "pullrequest": {"id": pullid},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        self.pull.refresh_from_db()
        assert self.pull.state == PullStates.MERGED

    def test_pull_request_rejected(self):
        pullid = 1
        response = self._post_event_data(
            event=BitbucketWebhookEvents.PULL_REQUEST_REJECTED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "pullrequest": {"id": pullid},
            },
        )
        assert response.status_code == status.HTTP_200_OK
        self.pull.refresh_from_db()
        assert self.pull.state == PullStates.CLOSED

    def test_repo_push_branch_deleted(self):
        branch = BranchFactory(repository=self.repo, name="name-of-branch")
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_PUSH,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "push": {
                    "changes": [
                        {
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
                    ]
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
            event=BitbucketWebhookEvents.REPO_PUSH,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "push": {
                    "changes": [
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
                    ]
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Synchronize codecov.yml skipped"

    def test_repo_push_new_branch_sync_yaml(self):
        self.repo.cache = {"yaml": "codecov.yaml"}
        self.repo.save()

        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_PUSH,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "push": {
                    "changes": [
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
                    ]
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Synchronize codecov.yml"

    def test_repo_commit_status_change_wrong_context(self):
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "commit_status": {
                    "name": "Unit Tests (Python)",
                    "description": "Build started",
                    "state": "INPROGRESS",
                    "key": "codecov",
                    "url": "https://my-build-tool.com/builds/MY-PROJECT/BUILD-777",
                    "type": "build",
                    "created_on": "2015-11-19T20:37:35.547563+00:00",
                    "updated_on": "2015-11-19T20:37:35.547563+00:00",
                    "links": {
                        "commit": {
                            "href": "http://api.bitbucket.org/2.0/repositories/tk/test/commit/9fec847784abb10b2fa567ee63b85bd238955d0e"
                        },
                        "self": {
                            "href": "http://api.bitbucket.org/2.0/repositories/tk/test/commit/9fec847784abb10b2fa567ee63b85bd238955d0e/statuses/build/mybuildtool"
                        },
                    },
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_CODECOV_STATUS

    def test_repo_commit_status_change_in_progress(self):
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "commit_status": {
                    "name": "Unit Tests (Python)",
                    "description": "Build started",
                    "state": "INPROGRESS",
                    "key": "not_codecov_context",
                    "url": "https://my-build-tool.com/builds/MY-PROJECT/BUILD-777",
                    "type": "build",
                    "created_on": "2015-11-19T20:37:35.547563+00:00",
                    "updated_on": "2015-11-19T20:37:35.547563+00:00",
                    "links": {
                        "commit": {
                            "href": "http://api.bitbucket.org/2.0/repositories/tk/test/commit/9fec847784abb10b2fa567ee63b85bd238955d0e"
                        },
                        "self": {
                            "href": "http://api.bitbucket.org/2.0/repositories/tk/test/commit/9fec847784abb10b2fa567ee63b85bd238955d0e/statuses/build/mybuildtool"
                        },
                    },
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES

    def test_repo_commit_status_change_commit_skip_processing(self):
        commitid = "9fec847784abb10b2fa567ee63b85bd238955d0e"
        commit = CommitFactory(
            commitid=commitid, repository=self.repo, state=Commit.CommitStates.PENDING
        )
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "commit_status": {
                    "name": "Unit Tests (Python)",
                    "description": "Build started",
                    "state": "SUCCESSFUL",
                    "key": "not_codecov_context",
                    "url": "https://my-build-tool.com/builds/MY-PROJECT/BUILD-777",
                    "type": "build",
                    "created_on": "2015-11-19T20:37:35.547563+00:00",
                    "updated_on": "2015-11-19T20:37:35.547563+00:00",
                    "links": {
                        "commit": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}"
                        },
                        "self": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}/statuses/build/mybuildtool"
                        },
                    },
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    @patch("services.task.TaskService.notify")
    def test_repo_commit_status_change_commit_notifies(self, notify_mock):
        commitid = "9fec847784abb10b2fa567ee63b85bd238955d0e"
        commit = CommitFactory(
            commitid=commitid, repository=self.repo, state=Commit.CommitStates.COMPLETE
        )
        response = self._post_event_data(
            event=BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            data={
                "repository": {"uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}"},
                "commit_status": {
                    "name": "Unit Tests (Python)",
                    "description": "Build started",
                    "state": "SUCCESSFUL",
                    "key": "not_codecov_context",
                    "url": "https://my-build-tool.com/builds/MY-PROJECT/BUILD-777",
                    "type": "build",
                    "created_on": "2015-11-19T20:37:35.547563+00:00",
                    "updated_on": "2015-11-19T20:37:35.547563+00:00",
                    "links": {
                        "commit": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}"
                        },
                        "self": {
                            "href": f"http://api.bitbucket.org/2.0/repositories/tk/test/commit/{commitid}/statuses/build/mybuildtool"
                        },
                    },
                },
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Notify queued"
        notify_mock.assert_called_once_with(repoid=self.repo.repoid, commitid=commitid)
