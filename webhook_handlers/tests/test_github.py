import uuid
import pytest

from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from core.tests.factories import RepositoryFactory, BranchFactory, CommitFactory, PullFactory
from core.models import Repository
from codecov_auth.tests.factories import OwnerFactory

from webhook_handlers.constants import GitHubHTTPHeaders, GitHubWebhookEvents, WebhookHandlerErrorMessages


class GithubWebhookHandlerTests(APITestCase):
    def _post_event_data(self, event, data={}):
        return self.client.post(
            reverse("github-webhook"),
            **{
                GitHubHTTPHeaders.EVENT: event,
                GitHubHTTPHeaders.DELIVERY_TOKEN: uuid.UUID(int=5),
                GitHubHTTPHeaders.SIGNATURE: 0
            },
            data=data,
            format="json"
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service="github"),
            service_id=12345,
            active=True
        )

    def test_ping_returns_pong_and_200(self):
        response = self._post_event_data(event=GitHubWebhookEvents.PING)
        assert response.status_code == status.HTTP_200_OK

    def test_repository_publicized_sets_activated_false_and_private_false(self):
        self.repo.private = True
        self.repo.activated = True

        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "publicized",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK

        self.repo.refresh_from_db()

        assert self.repo.private == False
        assert self.repo.activated == False

    def test_repository_privatized_sets_private_true(self):
        self.repo.private = False
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "privatized",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK

        self.repo.refresh_from_db()

        assert self.repo.private == True

    @patch('services.archive.ArchiveService.create_root_storage', lambda _: None)
    @patch('services.archive.ArchiveService.delete_repo_files', lambda _: None)
    def test_repository_deleted_deletes_repo(self):
        repository_id = self.repo.repoid

        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "deleted",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert not Repository.objects.filter(repoid=repository_id).exists()

    @patch('services.archive.ArchiveService.create_root_storage', lambda _: None)
    @patch('services.archive.ArchiveService.delete_repo_files')
    def test_repository_delete_deletes_archive_data(self, delete_files_mock):
        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "deleted",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK
        delete_files_mock.assert_called_once()

    def test_delete_event_deletes_branch(self):
        branch = BranchFactory(repository=self.repo)

        response = self._post_event_data(
            event=GitHubWebhookEvents.DELETE,
            data={
                "ref": "refs/heads/" + branch.name,
                "ref_type": "branch",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert not self.repo.branches.filter(name=branch.name).exists()

    def test_public_sets_repo_private_false_and_activated_false(self):
        self.repo.private = True
        self.repo.activated = True
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUBLIC,
            data={
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK
        self.repo.refresh_from_db()
        assert not self.repo.private
        assert not self.repo.activated

    @patch('redis.Redis.sismember', lambda x, y, z: False)
    def test_push_updates_only_unmerged_commits_with_branch_name(self):
        commit1 = CommitFactory(merged=False, repository=self.repo)
        commit2 = CommitFactory(merged=False, repository=self.repo)

        merged_branch_name = "merged"
        unmerged_branch_name = "unmerged"

        merged_commit = CommitFactory(merged=True, repository=self.repo, branch=merged_branch_name)

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + unmerged_branch_name,
                "repository": {
                    "id": self.repo.service_id
                },
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message},
                    {"id": commit2.commitid, "message": commit2.message},
                    {"id": merged_commit.commitid, "message": merged_commit.message}
                ]
            }
        )

        commit1.refresh_from_db()
        commit2.refresh_from_db()
        merged_commit.refresh_from_db()

        assert commit1.branch == unmerged_branch_name
        assert commit2.branch == unmerged_branch_name

        assert merged_commit.branch == merged_branch_name

    def test_push_exits_early_with_200_if_repo_not_active(self):
        self.repo.active = False
        self.repo.save()
        unmerged_commit = CommitFactory(repository=self.repo, merged=False)
        branch_name = "new-branch-name"

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + branch_name,
                "repository": {
                    "id": self.repo.service_id
                },
                "commits": [
                    {"id": unmerged_commit.commitid, "message": unmerged_commit.message}
                ]
            }
        )

        assert response.status_code == status.HTTP_200_OK

        unmerged_commit.refresh_from_db()
        assert unmerged_commit.branch != branch_name

    @patch('redis.Redis.sismember', lambda x, y, z: True)
    @patch('services.task.TaskService.status_set_pending')
    def test_push_triggers_set_pending_task_on_most_recent_commit(self, set_pending_mock):
        commit1 = CommitFactory(merged=False, repository=self.repo)
        commit2 = CommitFactory(merged=False, repository=self.repo)
        unmerged_branch_name = "unmerged"

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + unmerged_branch_name,
                "repository": {
                    "id": self.repo.service_id
                },
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message},
                    {"id": commit2.commitid, "message": commit2.message}
                ]
            }
        )

        set_pending_mock.assert_called_once_with(
            repoid=self.repo.repoid,
            commitid=commit2.commitid,
            branch=unmerged_branch_name,
            on_a_pull_request=False
        )

    @patch('redis.Redis.sismember', lambda x, y, z: False)
    @patch('services.task.TaskService.status_set_pending')
    def test_push_doesnt_trigger_task_if_repo_not_part_of_beta_set(self, set_pending_mock):
        commit1 = CommitFactory(merged=False, repository=self.repo)
        unmerged_branch_name = "unmerged"

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + "derp",
                "repository": {
                    "id": self.repo.service_id
                },
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message}
                ]
            }
        )

        set_pending_mock.assert_not_called()

    @patch('redis.Redis.sismember', lambda x, y, z: True)
    @patch('services.task.TaskService.status_set_pending')
    def test_push_doesnt_trigger_task_if_ci_skipped(self, set_pending_mock):
        commit1 = CommitFactory(merged=False, repository=self.repo, message="[ci skip]")
        unmerged_branch_name = "unmerged"

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + "derp",
                "repository": {
                    "id": self.repo.service_id
                },
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message}
                ]
            }
        )

        assert response.data == "CI Skipped"
        set_pending_mock.assert_not_called()

    def test_status_exits_early_if_repo_not_active(self):
        self.repo.active = False
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={
                "repository": {
                    "id": self.repo.service_id
                },
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE

    def test_status_exits_early_for_codecov_statuses(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={
                "context": "codecov/",
                "repository": {
                    "id": self.repo.service_id
                },
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_CODECOV_STATUS

    def test_status_exits_early_for_pending_statuses(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={
                "state": "pending",
                "repository": {
                    "id": self.repo.service_id
                },
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES

    def test_status_exits_early_if_commit_not_complete(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={
                "repository": {
                    "id": self.repo.service_id
                },
                "sha": CommitFactory(repository=self.repo, state="pending").commitid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    @patch('services.task.TaskService.notify')
    def test_status_triggers_notify_task(self, notify_mock):
        commit = CommitFactory(repository=self.repo)
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={
                "repository": {
                    "id": self.repo.service_id
                },
                "sha": commit.commitid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        notify_mock.assert_called_once_with(repoid=self.repo.repoid, commitid=commit.commitid)

    def test_pull_request_exits_early_if_repo_not_active(self):
        self.repo.active = False
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.PULL_REQUEST,
            data={
                "repository": {
                    "id": self.repo.service_id
                },
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE

    @pytest.mark.xfail
    def test_pull_request_triggers_pulls_sync_task_for_valid_actions(self):
        assert False

    def test_pull_request_updates_title_if_edited(self):
        pull = PullFactory(repository=self.repo)
        new_title = "brand new dang title"
        response = self._post_event_data(
            event=GitHubWebhookEvents.PULL_REQUEST,
            data={
                "repository": {
                    "id": self.repo.service_id
                },
                "action": "edited",
                "number": pull.pullid,
                "pull_request": {
                    "title": new_title,
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK

        pull.refresh_from_db()
        assert pull.title == new_title
