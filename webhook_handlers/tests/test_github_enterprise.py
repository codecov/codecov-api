import hmac
import json
import uuid
from hashlib import sha256
from unittest.mock import call, patch

import pytest
from freezegun import freeze_time
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.plan.constants import PlanName

from billing.helpers import mock_all_plans_and_tiers
from codecov_auth.models import GithubAppInstallation, Owner, Service
from utils.config import get_config
from webhook_handlers.constants import (
    GitHubHTTPHeaders,
    GitHubWebhookEvents,
    WebhookHandlerErrorMessages,
)
from webhook_handlers.tests.test_github import MockedSubscription

WEBHOOK_SECRET = b"testixik8qdauiab1yiffydimvi72ekq"


class GithubEnterpriseWebhookHandlerTests(APITestCase):
    @pytest.fixture(autouse=True)
    def mock_webhook_secret(self, mocker):
        orig_get_config = get_config

        def override(*args, default=None):
            if args[0] == "github" and args[1] == "webhook_secret":
                return WEBHOOK_SECRET

            return orig_get_config(*args, default=default)

        mock_get_config = mocker.patch("webhook_handlers.views.github.get_config")
        mock_get_config.side_effect = override

    def _post_event_data(self, event, data={}):
        return self.client.post(
            reverse("github_enterprise-webhook"),
            **{
                GitHubHTTPHeaders.EVENT: event,
                GitHubHTTPHeaders.DELIVERY_TOKEN: uuid.UUID(int=5),
                GitHubHTTPHeaders.SIGNATURE_256: "sha256="
                + hmac.new(
                    WEBHOOK_SECRET,
                    json.dumps(data, separators=(",", ":")).encode("utf-8"),
                    digestmod=sha256,
                ).hexdigest(),
            },
            data=data,
            format="json",
        )

    def setUp(self):
        self.repo = RepositoryFactory(
            author=OwnerFactory(service=Service.GITHUB_ENTERPRISE.value),
            service_id=12345,
            active=True,
        )

    def test_get_repo_paths_dont_crash(self):
        with self.subTest("with ownerid success"):
            self._post_event_data(
                event=GitHubWebhookEvents.REPOSITORY,
                data={
                    "action": "publicized",
                    "repository": {
                        "id": self.repo.service_id,
                        "owner": {"id": self.repo.author.service_id},
                    },
                },
            )

        with self.subTest("with not found owner"):
            self._post_event_data(
                event=GitHubWebhookEvents.REPOSITORY,
                data={
                    "action": "publicized",
                    "repository": {
                        "id": self.repo.service_id,
                        "owner": {"id": -239450},
                    },
                },
            )

        with self.subTest("with not found owner and not found repo"):
            self._post_event_data(
                event=GitHubWebhookEvents.REPOSITORY,
                data={
                    "action": "publicized",
                    "repository": {"id": -1948503, "owner": {"id": -239450}},
                },
            )

        with self.subTest("with owner and not found repo"):
            self._post_event_data(
                event=GitHubWebhookEvents.REPOSITORY,
                data={
                    "action": "publicized",
                    "repository": {
                        "id": -1948503,
                        "owner": {"id": self.repo.author.service_id},
                    },
                },
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
            data={"action": "publicized", "repository": {"id": self.repo.service_id}},
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
            data={"action": "privatized", "repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK

        self.repo.refresh_from_db()

        assert self.repo.private == True

    def test_repository_deleted_sets_deleted_activated_and_active(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={"action": "deleted", "repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK
        self.repo.refresh_from_db()
        assert self.repo.deleted is True
        assert self.repo.active is False
        assert self.repo.activated is False

    def test_delete_event_deletes_branch(self):
        branch = BranchFactory(repository=self.repo)

        response = self._post_event_data(
            event=GitHubWebhookEvents.DELETE,
            data={
                "ref": "refs/heads/" + branch.name,
                "ref_type": "branch",
                "repository": {"id": self.repo.service_id},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert not self.repo.branches.filter(name=branch.name).exists()

    def test_public_sets_repo_private_false_and_activated_false(self):
        self.repo.private = True
        self.repo.activated = True
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUBLIC,
            data={"repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK
        self.repo.refresh_from_db()
        assert not self.repo.private
        assert not self.repo.activated

    @patch("redis.Redis.sismember", lambda x, y, z: False)
    def test_push_updates_only_unmerged_commits_with_branch_name(self):
        commit1 = CommitFactory(merged=False, repository=self.repo)
        commit2 = CommitFactory(merged=False, repository=self.repo)

        merged_branch_name = "merged"
        unmerged_branch_name = "unmerged"

        merged_commit = CommitFactory(
            merged=True, repository=self.repo, branch=merged_branch_name
        )

        self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + unmerged_branch_name,
                "repository": {"id": self.repo.service_id},
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message},
                    {"id": commit2.commitid, "message": commit2.message},
                    {"id": merged_commit.commitid, "message": merged_commit.message},
                ],
            },
        )

        commit1.refresh_from_db()
        commit2.refresh_from_db()
        merged_commit.refresh_from_db()

        assert not commit1.merged
        assert not commit2.merged

        assert merged_commit.branch == merged_branch_name

    @patch("redis.Redis.sismember", lambda x, y, z: False)
    def test_push_updates_commit_on_default_branch(self):
        commit1 = CommitFactory(
            merged=False, repository=self.repo, branch="feature-branch"
        )
        commit2 = CommitFactory(
            merged=False, repository=self.repo, branch="feature-branch"
        )

        merged_branch_name = "merged"
        repo_branch = self.repo.branch

        merged_commit = CommitFactory(
            merged=True, repository=self.repo, branch=merged_branch_name
        )

        self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + repo_branch,
                "repository": {"id": self.repo.service_id},
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message},
                    {"id": commit2.commitid, "message": commit2.message},
                    {"id": merged_commit.commitid, "message": merged_commit.message},
                ],
            },
        )

        commit1.refresh_from_db()
        commit2.refresh_from_db()
        merged_commit.refresh_from_db()

        assert commit1.branch == repo_branch
        assert commit2.branch == repo_branch
        assert commit1.merged
        assert commit2.merged

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
                "repository": {"id": self.repo.service_id},
                "commits": [
                    {"id": unmerged_commit.commitid, "message": unmerged_commit.message}
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        unmerged_commit.refresh_from_db()
        assert unmerged_commit.branch != branch_name

    @patch("redis.Redis.sismember", lambda x, y, z: True)
    @patch("services.task.TaskService.status_set_pending")
    def test_push_triggers_set_pending_task_on_most_recent_commit(
        self, set_pending_mock
    ):
        commit1 = CommitFactory(merged=False, repository=self.repo)
        commit2 = CommitFactory(merged=False, repository=self.repo)
        unmerged_branch_name = "unmerged"

        self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + unmerged_branch_name,
                "repository": {"id": self.repo.service_id},
                "commits": [
                    {"id": commit1.commitid, "message": commit1.message},
                    {"id": commit2.commitid, "message": commit2.message},
                ],
            },
        )

        set_pending_mock.assert_called_once_with(
            repoid=self.repo.repoid,
            commitid=commit2.commitid,
            branch=unmerged_branch_name,
            on_a_pull_request=False,
        )

    @patch("redis.Redis.sismember", lambda x, y, z: False)
    @patch("services.task.TaskService.status_set_pending")
    def test_push_doesnt_trigger_task_if_repo_not_part_of_beta_set(
        self, set_pending_mock
    ):
        commit1 = CommitFactory(merged=False, repository=self.repo)

        self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + "derp",
                "repository": {"id": self.repo.service_id},
                "commits": [{"id": commit1.commitid, "message": commit1.message}],
            },
        )

        set_pending_mock.assert_not_called()

    @patch("redis.Redis.sismember", lambda x, y, z: True)
    @patch("services.task.TaskService.status_set_pending")
    def test_push_doesnt_trigger_task_if_ci_skipped(self, set_pending_mock):
        commit1 = CommitFactory(merged=False, repository=self.repo, message="[ci skip]")

        response = self._post_event_data(
            event=GitHubWebhookEvents.PUSH,
            data={
                "ref": "refs/heads/" + "derp",
                "repository": {"id": self.repo.service_id},
                "commits": [{"id": commit1.commitid, "message": commit1.message}],
            },
        )

        assert response.data == "CI Skipped"
        set_pending_mock.assert_not_called()

    def test_status_exits_early_if_repo_not_active(self):
        self.repo.active = False
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={"repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE

    def test_status_exits_early_for_codecov_statuses(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={"context": "codecov/", "repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_CODECOV_STATUS

    def test_status_exits_early_for_pending_statuses(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={"state": "pending", "repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES

    def test_status_exits_early_if_commit_not_complete(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={
                "repository": {"id": self.repo.service_id},
                "sha": CommitFactory(repository=self.repo, state="pending").commitid,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_PROCESSING

    @patch("services.task.TaskService.notify")
    def test_status_triggers_notify_task(self, notify_mock):
        commit = CommitFactory(repository=self.repo)
        response = self._post_event_data(
            event=GitHubWebhookEvents.STATUS,
            data={"repository": {"id": self.repo.service_id}, "sha": commit.commitid},
        )

        assert response.status_code == status.HTTP_200_OK
        notify_mock.assert_called_once_with(
            repoid=self.repo.repoid, commitid=commit.commitid
        )

    def test_pull_request_exits_early_if_repo_not_active(self):
        self.repo.active = False
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.PULL_REQUEST,
            data={"repository": {"id": self.repo.service_id}},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE

    @patch("services.task.TaskService.pulls_sync")
    def test_pull_request_triggers_pulls_sync_task_for_valid_actions(
        self, pulls_sync_mock
    ):
        pull = PullFactory(repository=self.repo)

        valid_actions = ["opened", "closed", "reopened", "synchronize"]

        for action in valid_actions:
            self._post_event_data(
                event=GitHubWebhookEvents.PULL_REQUEST,
                data={
                    "repository": {"id": self.repo.service_id},
                    "action": action,
                    "number": pull.pullid,
                },
            )

        pulls_sync_mock.assert_has_calls(
            [call(repoid=self.repo.repoid, pullid=pull.pullid)] * len(valid_actions)
        )

    def test_pull_request_updates_title_if_edited(self):
        pull = PullFactory(repository=self.repo)
        new_title = "brand new dang title"
        response = self._post_event_data(
            event=GitHubWebhookEvents.PULL_REQUEST,
            data={
                "repository": {"id": self.repo.service_id},
                "action": "edited",
                "number": pull.pullid,
                "pull_request": {"title": new_title},
            },
        )

        assert response.status_code == status.HTTP_200_OK

        pull.refresh_from_db()
        assert pull.title == new_title

    @freeze_time("2024-03-28T00:00:00")
    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_creates_new_owner_if_dne(self):
        username, service_id = "newuser", 123456

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION,
            data={
                "installation": {
                    "id": 4,
                    "repository_selection": "selected",
                    "account": {"id": service_id, "login": username},
                    "app_id": 15,
                },
                "repositories": [
                    {"id": "12321", "node_id": "R_kgDOG2tZYQ"},
                    {"id": "12343", "node_id": "R_kgDOG2tABC"},
                ],
                "sender": {"type": "User"},
            },
        )

        owner_set = Owner.objects.filter(
            service=Service.GITHUB_ENTERPRISE.value,
            service_id=service_id,
            username=username,
        )

        assert owner_set.exists()

        owner = owner_set.first()
        assert owner.createstamp.isoformat() == "2024-03-28T00:00:00+00:00"

        ghapp_installations_set = GithubAppInstallation.objects.filter(
            owner_id=owner.ownerid
        )
        assert ghapp_installations_set.count() == 1
        installation = ghapp_installations_set.first()
        assert installation.installation_id == 4
        assert installation.repository_service_ids == ["12321", "12343"]

    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_creates_new_owner_if_dne_all_repos(self):
        username, service_id = "newuser", 123456

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION,
            data={
                "installation": {
                    "id": 4,
                    "repository_selection": "all",
                    "account": {"id": service_id, "login": username},
                    "app_id": 15,
                },
                "repositories": [
                    {"id": "12321", "node_id": "R_kgDOG2tZYQ"},
                    {"id": "12343", "node_id": "R_kgDOG2tABC"},
                ],
                "sender": {"type": "User"},
            },
        )

        owner_set = Owner.objects.filter(
            service=Service.GITHUB_ENTERPRISE.value,
            service_id=service_id,
            username=username,
        )

        assert owner_set.exists()

        owner = owner_set.first()

        ghapp_installations_set = GithubAppInstallation.objects.filter(
            owner_id=owner.ownerid
        )
        assert ghapp_installations_set.count() == 1
        installation = ghapp_installations_set.first()
        assert installation.installation_id == 4
        assert installation.repository_service_ids is None

    @freeze_time("2024-03-28T00:00:00")
    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_repositories_creates_new_owner_if_dne(self):
        username, service_id = "newuser", 123456

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION_REPOSITORIES,
            data={
                "installation": {
                    "id": 4,
                    "repository_selection": "all",
                    "account": {"id": service_id, "login": username},
                    "app_id": 15,
                },
                "repository_selection": "all",
                "sender": {"type": "User"},
            },
        )

        owner_set = Owner.objects.filter(
            service=Service.GITHUB_ENTERPRISE.value,
            service_id=service_id,
            username=username,
        )

        assert owner_set.exists()

        owner = owner_set.first()
        assert owner.createstamp.isoformat() == "2024-03-28T00:00:00+00:00"

        ghapp_installations_set = GithubAppInstallation.objects.filter(
            owner_id=owner.ownerid
        )
        assert ghapp_installations_set.count() == 1
        installation = ghapp_installations_set.first()
        assert installation.installation_id == 4
        assert installation.repository_service_ids is None

    def test_installation_with_deleted_action_nulls_values(self):
        # Should set integration_id to null for owner,
        # and set using_integration=False and bot=null for repos
        owner = OwnerFactory(service=Service.GITHUB_ENTERPRISE.value)
        repo1 = RepositoryFactory(author=owner)
        repo2 = RepositoryFactory(author=owner)

        owner.integration_id = 12
        owner.save()

        repo1.using_integration, repo2.using_integration = True, True
        repo1.bot, repo2.bot = owner, owner

        repo1.save()
        repo2.save()

        ghapp_installation = GithubAppInstallation(
            installation_id=25,
            repository_service_ids=[repo1.service_id, repo2.service_id],
            owner=owner,
        )
        ghapp_installation.save()

        assert owner.github_app_installations.exists()

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION,
            data={
                "installation": {
                    "id": 25,
                    "repository_selection": "selected",
                    "account": {"id": owner.service_id, "login": owner.username},
                    "app_id": 15,
                },
                "repositories": [
                    {"id": "12321", "node_id": "R_kgDOG2tZYQ"},
                    {"id": "12343", "node_id": "R_kgDOG2tABC"},
                ],
                "action": "deleted",
                "sender": {"type": "User"},
            },
        )

        owner.refresh_from_db()
        repo1.refresh_from_db()
        repo2.refresh_from_db()

        assert owner.integration_id is None
        assert repo1.using_integration == False
        assert repo2.using_integration == False

        assert repo1.bot is None
        assert repo2.bot is None

        assert not owner.github_app_installations.exists()

    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_repositories_update_existing_ghapp(self):
        # Should set integration_id to null for owner,
        # and set using_integration=False and bot=null for repos
        owner = OwnerFactory(service=Service.GITHUB_ENTERPRISE.value)
        repo1 = RepositoryFactory(author=owner)
        repo2 = RepositoryFactory(author=owner)
        installation = GithubAppInstallation(
            owner=owner, repository_service_ids=[repo1.service_id], installation_id=12
        )

        owner.integration_id = 12
        owner.save()

        repo1.using_integration, repo2.using_integration = True, True
        repo1.bot, repo2.bot = owner, owner

        repo1.save()
        repo2.save()

        installation.save()

        assert owner.github_app_installations.exists()

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION_REPOSITORIES,
            data={
                "installation": {
                    "id": 12,
                    "repository_selection": "selected",
                    "account": {"id": owner.service_id, "login": owner.username},
                    "app_id": 15,
                },
                "repositories_added": [{"id": repo2.service_id, "node_id": "R_repo2"}],
                "repositories_removed": [
                    {"id": repo1.service_id, "node_id": "R_repo1"}
                ],
                "repository_selection": "selected",
                "action": "added",
                "sender": {"type": "User"},
            },
        )

        installation.refresh_from_db()
        assert installation.installation_id == 12
        assert installation.repository_service_ids == [repo2.service_id]

    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_repositories_update_existing_ghapp_all_repos(self):
        # Should set integration_id to null for owner,
        # and set using_integration=False and bot=null for repos
        owner = OwnerFactory(service=Service.GITHUB_ENTERPRISE.value)
        repo1 = RepositoryFactory(author=owner)
        repo2 = RepositoryFactory(author=owner)
        installation = GithubAppInstallation(
            owner=owner, repository_service_ids=[repo1.service_id], installation_id=12
        )

        owner.integration_id = 12
        owner.save()

        repo1.using_integration, repo2.using_integration = True, True
        repo1.bot, repo2.bot = owner, owner

        repo1.save()
        repo2.save()

        installation.save()

        assert owner.github_app_installations.exists()

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION_REPOSITORIES,
            data={
                "installation": {
                    "id": 12,
                    "repository_selection": "all",
                    "account": {"id": owner.service_id, "login": owner.username},
                    "app_id": 15,
                },
                "repositories_added": [{"id": repo2.service_id, "node_id": "R_repo2"}],
                "repositories_removed": [],
                "repository_selection": "all",
                "action": "deleted",
                "sender": {"type": "User"},
            },
        )

        installation.refresh_from_db()
        assert installation.installation_id == 12
        assert installation.repository_service_ids is None

    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_with_other_actions_sets_owner_itegration_id_if_none(
        self,
    ):
        installation_id = 44
        owner = OwnerFactory(service=Service.GITHUB_ENTERPRISE.value)

        owner.integration_id = None
        owner.save()

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION,
            data={
                "installation": {
                    "id": installation_id,
                    "repository_selection": "selected",
                    "account": {"id": owner.service_id, "login": owner.username},
                    "app_id": 15,
                },
                "repositories": [
                    {"id": "12321", "node_id": "R_12321CAT"},
                    {"id": "12343", "node_id": "R_12343DOG"},
                ],
                "action": "added",
                "sender": {"type": "User"},
            },
        )

        owner.refresh_from_db()

        assert owner.integration_id == installation_id

        ghapp_installations_set = GithubAppInstallation.objects.filter(
            owner_id=owner.ownerid
        )
        assert ghapp_installations_set.count() == 1
        installation = ghapp_installations_set.first()
        assert installation.installation_id == installation_id
        assert installation.repository_service_ids == ["12321", "12343"]

    @patch(
        "services.task.TaskService.refresh",
        lambda self,
        ownerid,
        username,
        sync_teams,
        sync_repos,
        using_integration,
        repos_affected: None,
    )
    def test_installation_repositories_with_other_actions_sets_owner_itegration_id_if_none(
        self,
    ):
        installation_id = 44
        owner = OwnerFactory(service=Service.GITHUB_ENTERPRISE.value)

        owner.integration_id = None
        owner.save()

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION_REPOSITORIES,
            data={
                "installation": {
                    "id": installation_id,
                    "repository_selection": "all",
                    "account": {"id": owner.service_id, "login": owner.username},
                    "app_id": 15,
                },
                "repository_selection": "all",
                "action": "added",
                "sender": {"type": "User"},
            },
        )

        owner.refresh_from_db()

        assert owner.integration_id == installation_id

        ghapp_installations_set = GithubAppInstallation.objects.filter(
            owner_id=owner.ownerid
        )
        assert ghapp_installations_set.count() == 1
        installation = ghapp_installations_set.first()
        assert installation.installation_id == installation_id
        assert installation.repository_service_ids is None

    @patch("services.task.TaskService.refresh")
    def test_installation_trigger_refresh_with_other_actions(self, refresh_mock):
        owner = OwnerFactory(service=Service.GITHUB_ENTERPRISE.value)

        self._post_event_data(
            event=GitHubWebhookEvents.INSTALLATION,
            data={
                "installation": {
                    "id": 11,
                    "repository_selection": "selected",
                    "account": {"id": owner.service_id, "login": owner.username},
                    "app_id": 15,
                },
                "action": "added",
                "sender": {"type": "User"},
                "repositories": [
                    {"id": "12321", "node_id": "R_12321CAT"},
                    {"id": "12343", "node_id": "R_12343DOG"},
                ],
            },
        )

        assert refresh_mock.call_count == 1
        _, kwargs = refresh_mock.call_args_list[0]
        # Because we throw these into a set we need to order them here
        # In practive it doesn't matter, but for the test it does.
        kwargs["repos_affected"].sort()
        assert kwargs == dict(
            ownerid=owner.ownerid,
            username=owner.username,
            sync_teams=False,
            sync_repos=True,
            using_integration=True,
            repos_affected=[("12321", "R_12321CAT"), ("12343", "R_12343DOG")],
        )

    @patch("services.task.TaskService.refresh")
    def test_organization_with_removed_action_removes_user_from_org_and_activated_user_list(
        self,
        mock_refresh,
    ):
        org = OwnerFactory(service_id="4321", service=Service.GITHUB_ENTERPRISE.value)
        user = OwnerFactory(
            organizations=[org.ownerid],
            service_id="12",
            service=Service.GITHUB_ENTERPRISE.value,
        )
        org.plan_activated_users = [user.ownerid]
        org.save()

        self._post_event_data(
            event=GitHubWebhookEvents.ORGANIZATION,
            data={
                "action": "member_removed",
                "membership": {"user": {"id": user.service_id}},
                "organization": {"id": org.service_id},
            },
        )

        user.refresh_from_db()
        org.refresh_from_db()

        mock_refresh.assert_called_with(
            ownerid=user.ownerid,
            username=user.username,
            sync_teams=True,
            sync_repos=True,
            using_integration=False,
        )
        assert user.ownerid not in org.plan_activated_users

    def test_organization_member_removed_with_nonexistent_org_doesnt_crash(self):
        user = OwnerFactory(service_id="12", service=Service.GITHUB_ENTERPRISE.value)

        response = self._post_event_data(
            event=GitHubWebhookEvents.ORGANIZATION,
            data={
                "action": "member_removed",
                "membership": {"user": {"id": user.service_id}},
                "organization": {"id": 65000},
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_organization_member_removed_with_nonexistent_or_nonactivated_member(self):
        mock_all_plans_and_tiers()
        org = OwnerFactory(
            service_id="4321",
            plan_activated_users=[50392],
            service=Service.GITHUB_ENTERPRISE.value,
        )
        user = OwnerFactory(
            service_id="12",
            organizations=[60798],
            service=Service.GITHUB_ENTERPRISE.value,
        )

        response = self._post_event_data(
            event=GitHubWebhookEvents.ORGANIZATION,
            data={
                "action": "member_removed",
                "membership": {"user": {"id": user.service_id}},
                "organization": {"id": org.service_id},
            },
        )

        assert response.status_code == status.HTTP_200_OK

    def test_organization_member_removed_with_nonexistent_member_doesnt_crash(self):
        org = OwnerFactory(service_id="4321", service=Service.GITHUB_ENTERPRISE.value)

        response = self._post_event_data(
            event=GitHubWebhookEvents.ORGANIZATION,
            data={
                "action": "member_removed",
                "membership": {"user": {"id": 101010}},
                "organization": {"id": org.service_id},
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.task.TaskService.sync_plans")
    def test_marketplace_purchase_triggers_sync_plans_task(
        self, sync_plans_mock, subscription_retrieve_mock
    ):
        sender = {"id": 545, "login": "buddy@guy.com"}
        action = "purchased"
        account = {"type": "Organization", "id": 54678, "login": "username"}
        subscription_retrieve_mock.return_value = None
        self._post_event_data(
            event=GitHubWebhookEvents.MARKETPLACE_PURCHASE,
            data={
                "action": action,
                "sender": sender,
                "marketplace_purchase": {"account": account},
            },
        )

        sync_plans_mock.assert_called_once_with(
            sender=sender, account=account, action=action
        )

    @patch("logging.Logger.warning")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.task.TaskService.sync_plans")
    def test_marketplace_purchase_but_user_has_stripe_subscription(
        self, sync_plans_mock, subscription_retrieve_mock, log_warning_mock
    ):
        sender = {"id": 545, "login": "buddy@guy.com"}
        action = "purchased"
        account = {"type": "Organization", "id": 54678, "login": "username"}
        OwnerFactory(
            username=account["login"],
            service="github_enterprise",
            stripe_subscription_id="abc",
        )
        quantity = 14
        plan = PlanName.CODECOV_PRO_MONTHLY.value
        subscription_retrieve_mock.return_value = MockedSubscription(
            "active", plan, quantity
        )
        self._post_event_data(
            event=GitHubWebhookEvents.MARKETPLACE_PURCHASE,
            data={
                "action": action,
                "sender": sender,
                "marketplace_purchase": {
                    "account": account,
                    "plan": {"name": "gh-marketplace"},
                    "unit_count": 14,
                },
            },
        )

        log_warning_mock.assert_called_with(
            "GHM webhook - user purchasing but has a Stripe Subscription",
            extra={
                "username": "username",
                "old_plan_name": plan,
                "old_plan_seats": quantity,
                "new_plan_name": "gh-marketplace",
                "new_plan_seats": 14,
            },
        )

        sync_plans_mock.assert_called_once_with(
            sender=sender, account=account, action=action
        )

    def test_signature_validation(self):
        response = self.client.post(
            reverse("github-webhook"),
            **{
                GitHubHTTPHeaders.EVENT: "",
                GitHubHTTPHeaders.DELIVERY_TOKEN: uuid.UUID(int=5),
                GitHubHTTPHeaders.SIGNATURE: "",
            },
            data={},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("webhook_handlers.views.github.get_config")
    def test_signature_validation_with_string_key(self, get_config_mock):
        # make get_config return string
        get_config_mock.return_value = "testixik8qdauiab1yiffydimvi72ekq"
        response = self._post_event_data(event="", data={})
        assert response.status_code == status.HTTP_200_OK

    def test_member_removes_repo_permissions_if_member_removed(self):
        member = OwnerFactory(
            permission=[self.repo.repoid],
            service_id=6098,
            service=Service.GITHUB_ENTERPRISE.value,
        )
        self._post_event_data(
            event=GitHubWebhookEvents.MEMBER,
            data={
                "action": "removed",
                "member": {"id": member.service_id},
                "repository": {"id": self.repo.service_id},
            },
        )

        member.refresh_from_db()
        assert self.repo.repoid not in member.permission

    def test_member_doesnt_crash_if_member_permission_array_is_None(self):
        member = OwnerFactory(
            permission=None, service_id=6098, service=Service.GITHUB_ENTERPRISE.value
        )
        self._post_event_data(
            event=GitHubWebhookEvents.MEMBER,
            data={
                "action": "removed",
                "member": {"id": member.service_id},
                "repository": {"id": self.repo.service_id},
            },
        )

    def test_member_doesnt_crash_if_member_didnt_have_permission(self):
        member = OwnerFactory(
            permission=[self.repo.service_id + 1],
            service_id=6098,
            service=Service.GITHUB_ENTERPRISE.value,
        )
        self._post_event_data(
            event=GitHubWebhookEvents.MEMBER,
            data={
                "action": "removed",
                "member": {"id": member.service_id},
                "repository": {"id": self.repo.service_id},
            },
        )

    def test_member_doesnt_crash_if_member_dne(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.MEMBER,
            data={
                "action": "removed",
                "member": {"id": 604945829},  # some random number
                "repository": {"id": self.repo.service_id},
            },
        )

        assert response.status_code == 404

    def test_returns_404_if_repo_not_found(self):
        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={"action": "publicized", "repository": {"id": -29384}},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_repo_not_found_when_owner_has_integration_creates_repo(self):
        owner = OwnerFactory(
            integration_id=4850403,
            service_id=97968493,
            service=Service.GITHUB_ENTERPRISE.value,
        )
        self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "publicized",
                "repository": {
                    "id": 506003,
                    "name": "testrepo",
                    "private": False,
                    "default_branch": "master",
                    "owner": {"id": owner.service_id},
                },
            },
        )

        assert owner.repository_set.filter(name="testrepo").exists()

    def test_repo_creation_doesnt_crash_for_forked_repo(self):
        owner = OwnerFactory(
            integration_id=4850403,
            service_id=97968493,
            service=Service.GITHUB_ENTERPRISE.value,
        )
        self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "publicized",
                "repository": {
                    "id": 506003,
                    "name": "testrepo",
                    "private": False,
                    "default_branch": "master",
                    "owner": {"id": owner.service_id},
                    "fork": True,
                    "parent": {
                        "name": "mainrepo",
                        "language": "python",
                        "id": 7940284,
                        "private": False,
                        "default_branch": "master",
                        "owner": {"id": 8495712939, "login": "alogin"},
                    },
                },
            },
        )

        assert owner.repository_set.filter(name="testrepo").exists()
