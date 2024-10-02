import uuid
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.utils.test_utils import mock_config_helper

from core.models import Commit, PullStates, Repository
from webhook_handlers.constants import (
    GitLabHTTPHeaders,
    GitLabWebhookEvents,
    WebhookHandlerErrorMessages,
)


class TestGitlabEnterpriseWebhookHandler(APITestCase):
    @pytest.fixture(scope="function", autouse=True)
    def inject_mocker(request, mocker):
        request.mocker = mocker

    @pytest.fixture(autouse=True)
    def mock_config(self, mocker):
        mock_config_helper(
            mocker,
            configs={
                "setup.enterprise_license": True,
                "gitlab_enterprise.webhook_validation": False,
            },
        )

    def _post_event_data(self, event, data, token=None):
        return self.client.post(
            reverse("gitlab_enterprise-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: event,
                GitLabHTTPHeaders.TOKEN: token,
            },
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab_enterprise"),
            service_id=123,
            active=True,
        )

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

    def test_handle_system_hook_not_enterprise(self):
        mock_config_helper(self.mocker, configs={"setup.enterprise_license": None})
        owner = OwnerFactory(service="gitlab_enterprise", username="jsmith")

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2020-01-21T07:30:54Z",
                "updated_at": "2020-01-21T07:38:22Z",
                "event_name": "project_create",
                "name": "StoreCloud",
                "owner_email": "johnsmith@gmail.com",
                "owner_name": "John Smith",
                "path": "storecloud",
                "path_with_namespace": f"{owner.username}/storecloud",
                "project_id": 74,
                "project_visibility": "private",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        new_repo = Repository.objects.filter(
            author__ownerid=owner.ownerid, service_id=74
        ).first()
        assert new_repo is None

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_project_create(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:54Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "project_create",
            "name": "StoreCloud",
            "owner_email": "johnsmith@example.com",
            "owner_name": "John Smith",
            "owners": [{"name": "John", "email": "user1@example.com"}],
            "path": "storecloud",
            "path_with_namespace": "jsmith/storecloud",
            "project_id": 74,
            "project_visibility": "private",
        }

        owner = OwnerFactory(
            service="gitlab_enterprise",
            username="jsmith",
            name=sample_payload_from_gitlab_docs["owner_name"],
            email=sample_payload_from_gitlab_docs["owner_email"],
            oauth_token="123",
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_called_once_with(
            ownerid=owner.ownerid,
            username=owner.username,
            using_integration=False,
            manual_trigger=False,
        )

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_project_destroy(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:58Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "project_destroy",
            "name": "Underscore",
            "owner_email": "johnsmith@example.com",
            "owner_name": "John Smith",
            "owners": [{"name": "John", "email": "user1@example.com"}],
            "path": "underscore",
            "path_with_namespace": "jsmith/underscore",
            "project_id": 73,
            "project_visibility": "internal",
        }

        OwnerFactory(
            service="gitlab_enterprise",
            username="jsmith",
            name=sample_payload_from_gitlab_docs["owner_name"],
            email=sample_payload_from_gitlab_docs["owner_email"],
            oauth_token="123",
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
        )

        repo = RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Repository deleted"

        mock_refresh_task.assert_not_called()

        repo.refresh_from_db()
        assert repo.active is False
        assert repo.activated is False
        assert repo.deleted is True

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_project_rename(self, mock_refresh_task):
        # testing get owner by namespace in payload
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:58Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "project_rename",
            "name": "Underscore",
            "path": "underscore",
            "path_with_namespace": "jsmith/underscore",
            "project_id": 73,
            "owner_name": "John Smith",
            "owner_email": "johnsmith@example.com",
            "owners": [{"name": "John", "email": "user1@example.com"}],
            "project_visibility": "internal",
            "old_path_with_namespace": "jsmith/overscore",
        }

        OwnerFactory(
            service="gitlab_enterprise",
            oauth_token="123",
            username="jsmith",
        )

        owner_bot = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token="123",
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
            bot=owner_bot,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_called_once_with(
            ownerid=owner_bot.ownerid,
            username=owner_bot.username,
            using_integration=False,
            manual_trigger=False,
        )

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_project_transfer(self, mock_refresh_task):
        # moving this repo from one namespace to another
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:58Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "project_transfer",
            "name": "Underscore",
            "path": "underscore",
            "path_with_namespace": "scores/underscore",
            "project_id": 73,
            "owner_name": "John Smith",
            "owner_email": "johnsmith@example.com",
            "owners": [{"name": "John", "email": "user1@example.com"}],
            "project_visibility": "internal",
            "old_path_with_namespace": "jsmith/overscore",
        }

        owner_user = OwnerFactory(
            service="gitlab_enterprise",
            name=sample_payload_from_gitlab_docs["owner_name"],
            email=sample_payload_from_gitlab_docs["owner_email"],
            oauth_token="123",
        )

        non_usable_bot = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
            bot=non_usable_bot,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_called_once_with(
            ownerid=owner_user.ownerid,
            username=owner_user.username,
            using_integration=False,
            manual_trigger=False,
        )

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_user_create(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:44:07Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "email": "js@gitlabhq.com",
            "event_name": "user_create",
            "name": "John Smith",
            "username": "js",
            "user_id": 41,
        }
        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_refresh_task.assert_not_called()

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_user_add_to_team(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:56Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "user_add_to_team",
            "access_level": "Maintainer",
            "project_id": 74,
            "project_name": "StoreCloud",
            "project_path": "storecloud",
            "project_path_with_namespace": "jsmith/storecloud",
            "user_email": "johnsmith@example.com",
            "user_name": "John Smith",
            "user_username": "johnsmith",
            "user_id": 41,
            "project_visibility": "private",
        }

        owner_user = OwnerFactory(
            service="gitlab_enterprise",
            name=sample_payload_from_gitlab_docs["user_name"],
            email=sample_payload_from_gitlab_docs["user_email"],
            oauth_token="123",
            username=sample_payload_from_gitlab_docs["user_username"],
            service_id=sample_payload_from_gitlab_docs["user_id"],
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_called_once_with(
            ownerid=owner_user.ownerid,
            username=owner_user.username,
            using_integration=False,
            manual_trigger=False,
        )

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_user_add_to_team_repo_public(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:56Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "user_add_to_team",
            "access_level": "Maintainer",
            "project_id": 74,
            "project_name": "StoreCloud",
            "project_path": "storecloud",
            "project_path_with_namespace": "jsmith/storecloud",
            "user_email": "johnsmith@example.com",
            "user_name": "John Smith",
            "user_username": "johnsmith",
            "user_id": 41,
            "project_visibility": "public",
        }

        OwnerFactory(
            service="gitlab_enterprise",
            name=sample_payload_from_gitlab_docs["user_name"],
            email=sample_payload_from_gitlab_docs["user_email"],
            oauth_token="123",
            username=sample_payload_from_gitlab_docs["user_username"],
            service_id=sample_payload_from_gitlab_docs["user_id"],
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data is None

        mock_refresh_task.assert_not_called()

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_user_remove_from_team(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:56Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "user_remove_from_team",
            "access_level": "Maintainer",
            "project_id": 74,
            "project_name": "StoreCloud",
            "project_path": "storecloud",
            "project_path_with_namespace": "jsmith/storecloud",
            "user_email": "johnsmith@example.com",
            "user_name": "John Smith",
            "user_username": "johnsmith",
            "user_id": 41,
            "project_visibility": "private",
        }

        owner_user = OwnerFactory(
            service="gitlab_enterprise",
            name=sample_payload_from_gitlab_docs["user_name"],
            email=sample_payload_from_gitlab_docs["user_email"],
            oauth_token="123",
            username=sample_payload_from_gitlab_docs["user_username"],
            service_id=sample_payload_from_gitlab_docs["user_id"],
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_called_once_with(
            ownerid=owner_user.ownerid,
            username=owner_user.username,
            using_integration=False,
            manual_trigger=False,
        )

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_unknown_repo(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:56Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "user_add_to_team",
            "access_level": "Maintainer",
            "project_id": 74,
            "project_name": "StoreCloud",
            "project_path": "storecloud",
            "project_path_with_namespace": "jsmith/storecloud",
            "user_email": "johnsmith@example.com",
            "user_name": "John Smith",
            "user_username": "johnsmith",
            "user_id": 41,
            "project_visibility": "private",
        }

        OwnerFactory(
            service="gitlab_enterprise",
            name=sample_payload_from_gitlab_docs["user_name"],
            email=sample_payload_from_gitlab_docs["user_email"],
            oauth_token="123",
            username=sample_payload_from_gitlab_docs["user_username"],
            service_id=sample_payload_from_gitlab_docs["user_id"],
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"] + 1,
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_user_add_to_team_unknown_user(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:56Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "user_add_to_team",
            "access_level": "Maintainer",
            "project_id": 74,
            "project_name": "StoreCloud",
            "project_path": "storecloud",
            "project_path_with_namespace": "jsmith/storecloud",
            "user_email": "johnsmith@example.com",
            "user_name": "John Smith",
            "user_username": "johnsmith",
            "user_id": 41,
            "project_visibility": "private",
        }

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_not_called()

    @patch("services.refresh.RefreshService.trigger_refresh")
    def test_handle_system_hook_no_bot_or_user_match(self, mock_refresh_task):
        sample_payload_from_gitlab_docs = {
            "created_at": "2012-07-21T07:30:58Z",
            "updated_at": "2012-07-21T07:38:22Z",
            "event_name": "project_rename",
            "name": "Underscore",
            "path": "underscore",
            "path_with_namespace": "jsmith/underscore",
            "project_id": 73,
            "owner_name": "John Smith",
            "owner_email": "johnsmith@example.com",
            "owners": [{"name": "John", "email": "user1@example.com"}],
            "project_visibility": "internal",
            "old_path_with_namespace": "jsmith/overscore",
        }

        OwnerFactory(
            service="gitlab_enterprise",
            name=sample_payload_from_gitlab_docs["owner_name"],
            oauth_token="123",
        )

        owner_org = OwnerFactory(
            service="gitlab_enterprise",
            oauth_token=None,
            username="jsmith",
        )

        RepositoryFactory(
            author=owner_org,
            service_id=sample_payload_from_gitlab_docs["project_id"],
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data=sample_payload_from_gitlab_docs,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Sync initiated"

        mock_refresh_task.assert_not_called()

    def test_secret_validation(self):
        owner = OwnerFactory(service="gitlab_enterprise")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=uuid.uuid4(),  # if repo has webhook secret, requires validation
        )
        owner.permission = [repo.repoid]
        owner.save()

        response = self.client.post(
            reverse("gitlab_enterprise-webhook"),
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
            reverse("gitlab_enterprise-webhook"),
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

    def test_secret_validation_required_by_config(self):
        webhook_secret = uuid.uuid4()
        # if repo has webhook_validation config set to True, requires validation
        mock_config_helper(
            self.mocker,
            configs={
                "gitlab_enterprise.webhook_validation": True,
            },
        )
        owner = OwnerFactory(service="gitlab_enterprise")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=None,
        )
        owner.permission = [repo.repoid]
        owner.save()

        response = self.client.post(
            reverse("gitlab_enterprise-webhook"),
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
            reverse("gitlab_enterprise-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: webhook_secret,
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        repo.webhook_secret = webhook_secret
        repo.save()
        response = self.client.post(
            reverse("gitlab_enterprise-webhook"),
            **{
                GitLabHTTPHeaders.EVENT: "",
                GitLabHTTPHeaders.TOKEN: webhook_secret,
            },
            data={
                "project_id": repo.service_id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
