import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from core.models import Commit, PullStates
from webhook_handlers.constants import (
    GitLabHTTPHeaders,
    GitLabWebhookEvents,
    WebhookHandlerErrorMessages,
)


def get_config_mock(*args, **kwargs):
    if args == ("setup", "enterprise_license"):
        return False
    elif args == ("gitlab", "webhook_validation"):
        return False
    else:
        return kwargs.get("default")


class TestGitlabWebhookHandler(APITestCase):
    def _post_event_data(self, event, data):
        return self.client.post(
            reverse("gitlab-webhook"),
            data=data,
            format="json",
            **{
                GitLabHTTPHeaders.EVENT: event,
            },
        )

    def setUp(self):
        self.get_config_patcher = patch("webhook_handlers.views.gitlab.get_config")
        self.get_config_mock = self.get_config_patcher.start()
        self.get_config_mock.side_effect = get_config_mock

        self.repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab"), service_id=123, active=True
        )

    def tearDown(self):
        self.get_config_patcher.stop()

    def test_unknown_repo(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.PUSH, data={"project_id": 1404}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_push_event_no_yaml_cached(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.PUSH,
            data={"object_kind": "push", "project_id": self.repo.service_id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "No yaml cached yet."

    def test_push_event_yaml_cached(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.PUSH,
            data={"object_kind": "push", "project_id": self.repo.service_id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "No yaml cached yet."

    def test_job_event_build_pending(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.JOB,
            data={
                "object_kind": "build",
                "project_id": self.repo.service_id,
                "build_status": "pending",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES

    def test_job_event_repo_not_active(self):
        self.repo.active = False
        self.repo.save()

        response = self._post_event_data(
            event=GitLabWebhookEvents.JOB,
            data={
                "object_kind": "build",
                "project_id": self.repo.service_id,
                "build_status": "success",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    def test_job_event_commit_not_found(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.JOB,
            data={
                "object_kind": "build",
                "project_id": self.repo.service_id,
                "build_status": "success",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    def test_job_event_commit_not_complete(self):
        commit_sha = "2293ada6b400935a1378653304eaf6221e0fdb8f"
        CommitFactory(
            author=self.repo.author,
            repository=self.repo,
            commitid=commit_sha,
            state=Commit.CommitStates.PENDING,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.JOB,
            data={
                "object_kind": "build",
                "project_id": self.repo.service_id,
                "build_status": "success",
                "sha": commit_sha,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    @patch("services.task.TaskService.notify")
    def test_job_event_triggers_notify(self, notify_mock):
        commit_sha = "2293ada6b400935a1378653304eaf6221e0fdb8f"
        commit = CommitFactory(
            author=self.repo.author,
            repository=self.repo,
            commitid=commit_sha,
            state=Commit.CommitStates.COMPLETE,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.JOB,
            data={
                "object_kind": "build",
                "project_id": self.repo.service_id,
                "build_status": "success",
                "sha": commit_sha,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Notify queued."
        notify_mock.assert_called_once_with(
            repoid=self.repo.repoid, commitid=commit.commitid
        )

    def test_merge_request_event_repo_not_found(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "object_kind": "merge_request",
                "object_attributes": {"target_project_id": 1404},
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("services.task.TaskService.pulls_sync")
    def test_merge_request_event_action_open(self, pulls_sync_mock):
        pullid = 2
        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "object_kind": "merge_request",
                "object_attributes": {
                    "action": "open",
                    "target_project_id": self.repo.service_id,
                    "iid": pullid,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Opening pull request in Codecov"

        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid=pullid)

    def test_merge_request_event_action_close(self):
        pull = PullFactory(
            author=self.repo.author,
            repository=self.repo,
            pullid=1,
            state=PullStates.OPEN,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "object_kind": "merge_request",
                "object_attributes": {
                    "action": "close",
                    "target_project_id": self.repo.service_id,
                    "iid": pull.pullid,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Pull request closed"

        pull.refresh_from_db()
        assert pull.state == PullStates.CLOSED

    @patch("services.task.TaskService.pulls_sync")
    def test_merge_request_event_action_merge(self, pulls_sync_mock):
        pullid = 2
        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "object_kind": "merge_request",
                "object_attributes": {
                    "action": "merge",
                    "target_project_id": self.repo.service_id,
                    "iid": pullid,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Pull request merged"

        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid=pullid)

    @patch("services.task.TaskService.pulls_sync")
    def test_merge_request_event_action_update(self, pulls_sync_mock):
        pullid = 2
        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "object_kind": "merge_request",
                "object_attributes": {
                    "action": "update",
                    "target_project_id": self.repo.service_id,
                    "iid": pullid,
                },
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Pull request synchronize queued"

        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid=pullid)

    def test_handle_system_hook_when_not_enterprise(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(author=owner)

        system_hook_events = [
            "project_create",
            "project_destroy",
            "project_rename",
            "project_transfer",
            "user_add_to_team",
            "user_remove_from_team",
        ]

        event_data = {
            "event": GitLabWebhookEvents.SYSTEM,
            "data": {
                "event_name": "project_create",
                "project_id": repo.service_id,
            },
        }

        for event in system_hook_events:
            event_data["data"]["event_name"] = event
            response = self._post_event_data(**event_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_secret_validation(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=uuid.uuid4(),  # if repo has webhook secret, requires validation
        )
        owner.permission = [repo.repoid]
        owner.save()

        response = self.client.post(
            reverse("gitlab-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: "",
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = self.client.post(
            reverse("gitlab-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: repo.webhook_secret,
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
