import uuid
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from core.models import Commit, Pull, PullStates, Repository
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from webhook_handlers.constants import (
    GitLabHTTPHeaders,
    GitLabWebhookEvents,
    WebhookHandlerErrorMessages,
)


def get_config_mock(*args, **kwargs):
    if args == ("setup", "enterprise_license"):
        return False
    elif args == ("gitlab", "webhook_validation"):
        return True
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
                GitLabHTTPHeaders.TOKEN: self.repo.webhook_secret,
            },
        )

    def setUp(self):
        self.get_config_patcher = patch("webhook_handlers.views.gitlab.get_config")
        self.get_config_mock = self.get_config_patcher.start()
        self.get_config_mock.side_effect = get_config_mock

        self.repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab"),
            service_id=123,
            active=True,
            webhook_secret="secret",
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
            data={"event_name": "push", "project_id": self.repo.service_id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "No yaml cached yet."

    def test_push_event_yaml_cached(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.PUSH,
            data={"event_name": "push", "project_id": self.repo.service_id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "No yaml cached yet."

    def test_job_event_build_pending(self):
        response = self._post_event_data(
            event=GitLabWebhookEvents.JOB,
            data={
                "event_name": "build",
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
                "event_name": "build",
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
                "event_name": "build",
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
                "event_name": "build",
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
                "event_name": "build",
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
        pullid = 2
        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "event_name": "merge_request",
                "object_attributes": {
                    "action": "open",
                    "target_project_id": 1404,
                    "iid": pullid,
                },
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("services.task.TaskService.pulls_sync")
    def test_merge_request_event_action_open(self, pulls_sync_mock):
        pullid = 2
        response = self._post_event_data(
            event=GitLabWebhookEvents.MERGE_REQUEST,
            data={
                "event_name": "merge_request",
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
                "event_name": "merge_request",
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
                "event_name": "merge_request",
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
                "event_name": "merge_request",
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

    def test_handle_system_hook_project_create_not_enterprise(self):
        username = "jsmith"
        project_id = 74
        owner = OwnerFactory(service="gitlab", username=username)

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
                "path_with_namespace": f"{username}/storecloud",
                "project_id": project_id,
                "project_visibility": "private",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        new_repo = Repository.objects.filter(
            author__ownerid=owner.ownerid, service_id=project_id
        ).first()
        assert new_repo is None

    def test_handle_system_hook_project_destroy_not_enterprise(self):
        username = "jsmith"
        project_id = 73
        owner = OwnerFactory(service="gitlab", username=username)
        repo = RepositoryFactory(
            name="testing",
            author=owner,
            service_id=project_id,
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2020-01-21T07:30:58Z",
                "updated_at": "2020-01-21T07:38:22Z",
                "event_name": "project_destroy",
                "name": "Underscore",
                "owner_email": "johnsmith@gmail.com",
                "owner_name": "John Smith",
                "path": "underscore",
                "path_with_namespace": f"{username}/underscore",
                "project_id": project_id,
                "project_visibility": "internal",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        repo.refresh_from_db()
        assert repo.active is True
        assert repo.activated is True
        assert repo.deleted is False
        assert repo.name == "testing"

    def test_handle_system_hook_project_rename_not_enterprise(self):
        username = "jsmith"
        project_id = 73
        owner = OwnerFactory(service="gitlab", username=username)
        repo = RepositoryFactory(
            author=owner,
            service_id=project_id,
            name="overscore",
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2020-01-21T07:30:58Z",
                "updated_at": "2020-01-21T07:38:22Z",
                "event_name": "project_rename",
                "name": "Underscore",
                "path": "underscore",
                "path_with_namespace": f"{username}/underscore",
                "project_id": 73,
                "owner_name": "John Smith",
                "owner_email": "johnsmith@gmail.com",
                "project_visibility": "internal",
                "old_path_with_namespace": "jsmith/overscore",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        repo.refresh_from_db()
        assert repo.name == "overscore"

    def test_handle_system_hook_project_transfer_not_enterprise(self):
        old_owner_username = "jsmith"
        new_owner_username = "scores"
        project_id = 73
        OwnerFactory(service="gitlab", username=new_owner_username)
        old_owner = OwnerFactory(service="gitlab", username=old_owner_username)
        repo = RepositoryFactory(
            author=old_owner,
            service_id=project_id,
            name="overscore",
            active=True,
            activated=True,
            deleted=False,
        )

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2020-01-21T07:30:58Z",
                "updated_at": "2020-01-21T07:38:22Z",
                "event_name": "project_transfer",
                "name": "Underscore",
                "path": "underscore",
                "path_with_namespace": f"{new_owner_username}/underscore",
                "project_id": project_id,
                "owner_name": "John Smith",
                "owner_email": "johnsmith@gmail.com",
                "project_visibility": "internal",
                "old_path_with_namespace": f"{old_owner_username}/overscore",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        repo.refresh_from_db()
        assert repo.name == "overscore"
        assert repo.author == old_owner

    def test_handle_system_hook_user_create_not_enterprise(self):
        gl_user_id = 41
        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2012-07-21T07:44:07Z",
                "updated_at": "2012-07-21T07:38:22Z",
                "email": "js@gitlabhq.com",
                "event_name": "user_create",
                "name": "John Smith",
                "username": "js",
                "user_id": gl_user_id,
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        new_user = Owner.objects.filter(
            service="gitlab", service_id=gl_user_id
        ).exists()
        assert new_user is False

    def test_handle_system_hook_user_add_to_team_no_existing_permissions_not_enterprise(
        self,
    ):
        gl_user_id = 41
        project_id = 74
        username = "johnsmith"
        user = OwnerFactory(
            service="gitlab", service_id=gl_user_id, username=username, permission=None
        )
        RepositoryFactory(
            author=user,
            service_id=project_id,
            active=True,
            activated=True,
            deleted=False,
        )
        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2012-07-21T07:30:56Z",
                "updated_at": "2012-07-21T07:38:22Z",
                "event_name": "user_add_to_team",
                "access_level": "Maintainer",
                "project_id": project_id,
                "project_name": "StoreCloud",
                "project_path": "storecloud",
                "project_path_with_namespace": "jsmith/storecloud",
                "user_email": "johnsmith@gmail.com",
                "user_name": "John Smith",
                "user_username": username,
                "user_id": gl_user_id,
                "project_visibility": "private",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        user.refresh_from_db()
        assert user.permission is None  # no change

    def test_handle_system_hook_user_add_to_team_not_enterprise(self):
        gl_user_id = 41
        project_id = 74
        username = "johnsmith"
        user = OwnerFactory(
            service="gitlab",
            service_id=gl_user_id,
            username="johnsmith",
            permission=[1, 2, 3, 100],
        )
        repo = RepositoryFactory(
            author=user,
            service_id=project_id,
            active=True,
            activated=True,
            deleted=False,
        )
        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2012-07-21T07:30:56Z",
                "updated_at": "2012-07-21T07:38:22Z",
                "event_name": "user_add_to_team",
                "access_level": "Maintainer",
                "project_id": project_id,
                "project_name": "StoreCloud",
                "project_path": "storecloud",
                "project_path_with_namespace": "jsmith/storecloud",
                "user_email": "johnsmith@gmail.com",
                "user_name": "John Smith",
                "user_username": username,
                "user_id": gl_user_id,
                "project_visibility": "private",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        user.refresh_from_db()
        assert len(user.permission) == 4  # no change
        assert repo.repoid not in user.permission

    def test_handle_system_hook_user_add_to_team_repo_public_not_enterprise(self):
        gl_user_id = 41
        project_id = 74
        username = "johnsmith"
        user = OwnerFactory(
            service="gitlab",
            service_id=gl_user_id,
            username=username,
            permission=[1, 2, 3, 100],
        )
        RepositoryFactory(
            author=user,
            service_id=project_id,
            active=True,
            activated=True,
            deleted=False,
        )
        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2012-07-21T07:30:56Z",
                "updated_at": "2012-07-21T07:38:22Z",
                "event_name": "user_add_to_team",
                "access_level": "Maintainer",
                "project_id": project_id,
                "project_name": "StoreCloud",
                "project_path": "storecloud",
                "project_path_with_namespace": "jsmith/storecloud",
                "user_email": "johnsmith@gmail.com",
                "user_name": "John Smith",
                "user_username": username,
                "user_id": gl_user_id,
                "project_visibility": "public",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        user.refresh_from_db()
        assert user.permission == [1, 2, 3, 100]  # no change

    def test_handle_system_hook_user_remove_from_team_not_enterprise(self):
        gl_user_id = 41
        project_id = 74
        username = "johnsmith"
        user = OwnerFactory(
            service="gitlab", service_id=gl_user_id, username=username, permission=None
        )
        repo = RepositoryFactory(
            author=user,
            service_id=project_id,
            active=True,
            activated=True,
            deleted=False,
        )
        user.permission = [1, 2, 3, repo.repoid]
        user.save()

        response = self._post_event_data(
            event=GitLabWebhookEvents.SYSTEM,
            data={
                "created_at": "2012-07-21T07:30:56Z",
                "updated_at": "2012-07-21T07:38:22Z",
                "event_name": "user_remove_from_team",
                "access_level": "Maintainer",
                "project_id": project_id,
                "project_name": "StoreCloud",
                "project_path": "storecloud",
                "project_path_with_namespace": "jsmith/storecloud",
                "user_email": "johnsmith@gmail.com",
                "user_name": "John Smith",
                "user_username": username,
                "user_id": gl_user_id,
                "project_visibility": "private",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        user.refresh_from_db()
        assert user.permission == [1, 2, 3, repo.repoid]

    def _post_event_data_with_token_variable(self, event, data, token):
        return self.client.post(
            reverse("gitlab-webhook"),
            data=data,
            format="json",
            **{
                GitLabHTTPHeaders.EVENT: event,
                GitLabHTTPHeaders.TOKEN: token,
            },
        )

    def test_secret_validation(self):
        repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab"),
            service_id=uuid.uuid4(),
            webhook_secret=uuid.uuid4(),
        )

        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token="",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token=repo.webhook_secret,
        )
        assert response.status_code == status.HTTP_200_OK

    def test_webhook_validation(self):
        secret = str(uuid.uuid4())
        repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab"),
            service_id=uuid.uuid4(),
            webhook_secret=None,
        )
        # both none
        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token="",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        # none on repo
        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token=secret,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        # none from webhook
        repo.webhook_secret = secret
        repo.save()
        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token="",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("webhook_handlers.views.gitlab.get_config")
    def test_webhook_validation_off_in_config(self, patched_get_config):
        patched_get_config.return_value = False

        secret = str(uuid.uuid4())
        repo = RepositoryFactory(
            author=OwnerFactory(service="gitlab"),
            service_id=uuid.uuid4(),
            webhook_secret=None,
        )
        # both none
        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token="",
        )
        assert response.status_code == status.HTTP_200_OK
        # none on repo
        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token=secret,
        )
        assert response.status_code == status.HTTP_200_OK
        # none from webhook
        repo.webhook_secret = secret
        repo.save()
        response = self._post_event_data_with_token_variable(
            event="",
            data={
                "project_id": repo.service_id,
            },
            token="",
        )
        assert response.status_code == status.HTTP_200_OK
