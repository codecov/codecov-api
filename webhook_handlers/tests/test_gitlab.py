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
        return True
    elif args == ("gitlab", "webhook_validation"):
        return True
    else:
        return kwargs.get("default")


class TestGitlabWebhookHandler(APITestCase):
    def _post_event_data(self, event, data={}):
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

    def test_handle_system_hook_not_enterprise(self):
        def side_effect(*args, **kwargs):
            if args == ("setup", "enterprise_license"):
                return None
            else:
                return kwargs.get("default")

        self.get_config_mock.side_effect = side_effect

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
        assert response.data.get("detail") == "No enterprise license detected"

        new_repo = Repository.objects.filter(
            author__ownerid=owner.ownerid, service_id=project_id
        ).first()
        assert new_repo is None

    def test_handle_system_hook_project_create(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Repository created"

        new_repo = Repository.objects.get(
            author__ownerid=owner.ownerid, service_id=project_id
        )
        assert new_repo is not None
        assert new_repo.private is True
        assert new_repo.name == "storecloud"

    def test_handle_system_hook_project_destroy(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Repository deleted"

        repo.refresh_from_db()
        assert repo.active is False
        assert repo.activated is False
        assert repo.deleted is True
        assert repo.name == "testing-deleted"

    def test_handle_system_hook_project_rename(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Repository renamed"

        repo.refresh_from_db()
        assert repo.name == "underscore"

    def test_handle_system_hook_project_transfer(self):
        old_owner_username = "jsmith"
        new_owner_username = "scores"
        project_id = 73
        new_owner = OwnerFactory(service="gitlab", username=new_owner_username)
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Repository transfered"

        repo.refresh_from_db()
        assert repo.name == "underscore"
        assert repo.author == new_owner

    def test_handle_system_hook_user_create(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "User created"

        new_user = Owner.objects.get(service="gitlab", service_id=gl_user_id)
        assert new_user.name == "John Smith"
        assert new_user.email == "js@gitlabhq.com"
        assert new_user.username == "js"

    def test_handle_system_hook_user_add_to_team_no_existing_permissions(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Permission added"

        user.refresh_from_db()
        assert user.permission == [repo.repoid]

    def test_handle_system_hook_user_add_to_team(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Permission added"

        user.refresh_from_db()
        assert len(user.permission) == 5
        assert repo.repoid in user.permission

    def test_handle_system_hook_user_add_to_team_repo_public(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data is None

        user.refresh_from_db()

        assert user.permission == [1, 2, 3, 100]  # no change

    def test_handle_system_hook_user_remove_from_team(self):
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
        assert response.status_code == status.HTTP_200_OK
        assert response.data == "Permission removed"

        user.refresh_from_db()
        assert user.permission == [1, 2, 3]

    def test_secret_validation(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(
            author=owner,
            service_id=uuid.uuid4(),
            webhook_secret=uuid.uuid4(),
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
