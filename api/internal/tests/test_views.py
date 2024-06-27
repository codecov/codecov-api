import json
from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    BranchFactory,
    CommitFactory,
    PullFactory,
    RepositoryFactory,
)
from utils.test_utils import Client

get_permissions_method = (
    "api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions"
)


@patch(get_permissions_method)
class RepoPullList(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        self.repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [self.repo.repoid]
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        PullFactory(
            pullid=10,
            author=self.org,
            repository=self.repo,
            state="open",
            head=CommitFactory(
                repository=self.repo, author=self.current_owner
            ).commitid,
            base=CommitFactory(
                repository=self.repo, author=self.current_owner
            ).commitid,
        )
        PullFactory(pullid=11, author=self.org, repository=self.repo, state="closed")
        PullFactory(pullid=12, author=other_org, repository=other_repo)
        self.correct_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "testRepoName",
        }
        self.incorrect_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "otherRepoName",
        }

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def test_can_get_public_repo_pulls_when_not_authenticated(self, mock_provider):
        self.client.logout()
        mock_provider.return_value = True, True
        author = OwnerFactory()
        repo = RepositoryFactory(private=False, author=author)
        response = self.client.get(
            reverse(
                "pulls-list",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo.name,
                },
            )
        )
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_get_pulls(self, mock_provider):
        mock_provider.return_value = True, True
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(
            len(content["results"]),
            3,
            "got the wrong number of pulls: {}".format(content["results"]),
        )

    def test_get_pulls_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.current_owner.permission = []
        self.current_owner.save()
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        self.assertEqual(response.status_code, 404)

    def test_get_pulls_filter_state(self, mock_provider):
        mock_provider.return_value = True, True
        response = self.client.get(
            reverse("pulls-list", kwargs=self.correct_kwargs), data={"state": "open"}
        )
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(
            len(content["results"]),
            2,
            "got the wrong number of open pulls: {}".format(content["results"]),
        )

    def test_get_pulls_ordered_by_pullid(self, mock_provider):
        mock_provider.return_value = True, True
        # Test increasing ordering
        response = self.client.get(
            reverse("pulls-list", kwargs=self.correct_kwargs),
            data={"ordering": "pullid"},
        )
        content = self.json_content(response)
        pullids = [r["pullid"] for r in content["results"]]
        self.assertEqual(pullids, [1, 10, 11])
        # Test decreasing ordering
        response = self.client.get(
            reverse("pulls-list", kwargs=self.correct_kwargs),
            data={"ordering": "-pullid"},
        )
        content = self.json_content(response)
        pullids = [r["pullid"] for r in content["results"]]
        self.assertEqual(pullids, [11, 10, 1])

    def test_get_pulls_default_ordering(self, mock_provider):
        mock_provider.return_value = True, True
        # Test default ordering
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        content = self.json_content(response)
        pullids = [r["pullid"] for r in content["results"]]
        self.assertEqual(pullids, [11, 10, 1])

    def test_get_pull_wrong_org(self, mock_provider):
        mock_provider.return_value = True, True
        response = self.client.get(reverse("pulls-list", kwargs=self.incorrect_kwargs))
        content = self.json_content(response)
        self.assertEqual(
            response.status_code, 404, "got unexpected response: {}".format(content)
        )

    def test_pulls_list_returns_most_recent_commiter(self, mock_provider):
        mock_provider.return_value = True, True
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))

        assert (
            response.data["results"][1]["most_recent_commiter"]
            == self.current_owner.username
        )

    def test_get_pulls_null_head_author_doesnt_crash(self, mock_provider):
        mock_provider.return_value = True, True
        new_owner = OwnerFactory()

        PullFactory(
            pullid=13,
            author=self.org,
            repository=self.repo,
            state="open",
            head=CommitFactory(repository=self.repo, author=new_owner).commitid,
            base=CommitFactory(repository=self.repo, author=new_owner).commitid,
        )

        new_owner.delete()

        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == status.HTTP_200_OK

    def test_get_pulls_no_head_commit_returns_null_for_head_totals(self, mock_provider):
        mock_provider.return_value = True, True

        PullFactory(
            pullid=13,
            author=self.org,
            repository=self.repo,
            state="open",
            head="",
            base=CommitFactory(
                repository=self.repo, author=self.current_owner
            ).commitid,
        )

        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == status.HTTP_200_OK
        assert [p for p in response.data["results"] if p["pullid"] == 13][0][
            "head_totals"
        ] is None

    def test_get_pulls_no_base_commit_returns_null_for_base_totals(self, mock_provider):
        mock_provider.return_value = True, True

        PullFactory(
            pullid=13,
            author=self.org,
            repository=self.repo,
            state="open",
            base="",
            head=CommitFactory(
                repository=self.repo, author=self.current_owner
            ).commitid,
        )

        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == status.HTTP_200_OK
        assert [p for p in response.data["results"] if p["pullid"] == 13][0][
            "base_totals"
        ] is None

    def test_get_pulls_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == 403

    def test_list_pulls_comparedto_not_base(self, mock_provider):
        repo = RepositoryFactory.create(
            author=self.org, name="test_list_pulls_comparedto_not_base", active=True
        )
        repo.save()
        user = OwnerFactory.create(
            username="test_list_pulls_comparedto_not_base",
            service="github",
            organizations=[self.org.ownerid],
            permission=[repo.repoid],
        )
        user.save()
        mock_provider.return_value = True, True
        pull = PullFactory.create(
            pullid=101,
            author=self.org,
            repository=repo,
            state="open",
            head=CommitFactory(repository=repo, author=user, pullid=None).commitid,
            base=CommitFactory(
                repository=repo, pullid=None, author=user, totals=None
            ).commitid,
            compared_to=CommitFactory(
                pullid=None,
                repository=repo,
                author=user,
                totals={
                    "C": 0,
                    "M": 0,
                    "N": 0,
                    "b": 0,
                    "c": "30.00000",
                    "d": 0,
                    "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
                    "f": 3,
                    "h": 6,
                    "m": 10,
                    "n": 20,
                    "p": 4,
                    "s": 1,
                },
            ).commitid,
        )
        response = self.client.get(
            reverse(
                "pulls-list",
                kwargs={
                    "service": "github",
                    "owner_username": "codecov",
                    "repo_name": "test_list_pulls_comparedto_not_base",
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        expected_content = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "pullid": 101,
                    "title": pull.title,
                    "most_recent_commiter": "test_list_pulls_comparedto_not_base",
                    "base_totals": {
                        "files": 3,
                        "lines": 20,
                        "hits": 6,
                        "misses": 10,
                        "partials": 4,
                        "coverage": 30.0,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 1,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "head_totals": {
                        "files": 3,
                        "lines": 20,
                        "hits": 17,
                        "misses": 3,
                        "partials": 0,
                        "coverage": 85.0,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 1,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    # This whole TZ settings is messing things up a bit
                    "updatestamp": pull.updatestamp.replace(tzinfo=None).isoformat()
                    + "Z",
                    "state": "open",
                    "ci_passed": True,
                }
            ],
            "total_pages": 1,
        }
        assert content["results"][0] == expected_content["results"][0]
        assert content == expected_content


@patch(get_permissions_method)
class RepoPullDetail(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        RepositoryFactory(author=other_org, name="otherRepoName", active=True)
        repo_with_permission = [repo.repoid]
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        PullFactory(pullid=10, author=self.org, repository=repo, state="open")
        PullFactory(pullid=11, author=self.org, repository=repo, state="closed")

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def test_can_get_public_repo_pull_detail_when_not_authenticated(
        self, mock_provider
    ):
        self.client.logout()
        mock_provider.return_value = True, True
        author = OwnerFactory()
        repo = RepositoryFactory(private=False, author=author)
        pull = PullFactory(repository=repo)
        response = self.client.get(
            reverse(
                "pulls-detail",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo.name,
                    "pullid": pull.pullid,
                },
            )
        )
        assert response.status_code == 200
        assert response.data["pullid"] == pull.pullid

    def test_get_pull(self, mock_provider):
        mock_provider.return_value = True, True
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(content["pullid"], 10)

    def test_get_pull_no_permissions(self, mock_provider):
        self.current_owner.permission = []
        self.current_owner.save()
        mock_provider.return_value = False, False
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 404)

    def test_get_pull_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        assert response.status_code == 403


@patch(get_permissions_method)
class RepoCommitList(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / commits
        self.repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [self.repo.repoid]
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        self.first_test_commit = CommitFactory(
            author=self.org,
            repository=self.repo,
            totals={
                "C": 2,
                "M": 0,
                "N": 5,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )
        self.second_test_commit = CommitFactory(
            author=self.org,
            repository=self.repo,
            totals={
                "C": 3,
                "M": 0,
                "N": 5,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )
        self.third_test_commit = CommitFactory(
            author=other_org,
            repository=other_repo,
            totals={
                "C": 3,
                "M": 0,
                "N": 6,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def test_can_get_public_repo_commits_if_not_authenticated(self, mocked_provider):
        mocked_provider.return_value = True, True
        self.client.logout()
        author = OwnerFactory()
        repo = RepositoryFactory(author=author, private=False)
        response = self.client.get(
            reverse(
                "commits-list",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo.name,
                },
            )
        )
        assert response.status_code == 200

    # TODO: Improve this test to not assert the pagination data
    def test_get_commits(self, mock_provider):
        mock_provider.return_value = True, True
        response = self.client.get("/internal/github/codecov/testRepoName/commits/")
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(
            len(content["results"]),
            2,
            "got the wrong number of commits: {}".format(content["results"]),
        )
        expected_result = {
            "count": 2,
            "next": None,
            "previous": None,
            "total_pages": 1,
            "results": [
                {
                    "commitid": self.second_test_commit.commitid,
                    "message": self.second_test_commit.message,
                    "timestamp": self.second_test_commit.timestamp.strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                    "ci_passed": self.second_test_commit.ci_passed,
                    "author": {
                        "service": self.org.service,
                        "username": self.org.username,
                        "avatar_url": self.org.avatar_url,
                        "stats": self.org.cache["stats"]
                        if self.org.cache and "stats" in self.org.cache
                        else None,
                        "name": self.org.name,
                        "ownerid": self.org.ownerid,
                        "integration_id": self.org.integration_id,
                    },
                    "branch": self.second_test_commit.branch,
                    "totals": {
                        "branches": 0,
                        "complexity": 3.0,
                        "complexity_total": 5.0,
                        "complexity_ratio": 60.0,
                        "coverage": 79.16,
                        "diff": 0,
                        "files": 3,
                        "hits": 19,
                        "lines": 24,
                        "methods": 0,
                        "misses": 5,
                        "partials": 0,
                        "sessions": 2,
                    },
                    "state": self.second_test_commit.state,
                },
                {
                    "commitid": self.first_test_commit.commitid,
                    "message": self.first_test_commit.message,
                    "timestamp": self.first_test_commit.timestamp.strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                    "ci_passed": self.first_test_commit.ci_passed,
                    "author": {
                        "service": self.org.service,
                        "username": self.org.username,
                        "avatar_url": self.org.avatar_url,
                        "stats": self.org.cache["stats"]
                        if self.org.cache and "stats" in self.org.cache
                        else None,
                        "name": self.org.name,
                        "ownerid": self.org.ownerid,
                        "integration_id": self.org.integration_id,
                    },
                    "branch": self.first_test_commit.branch,
                    "totals": {
                        "branches": 0,
                        "complexity": 2.0,
                        "complexity_total": 5.0,
                        "complexity_ratio": 40.0,
                        "coverage": 79.16,
                        "diff": 0,
                        "files": 3,
                        "hits": 19,
                        "lines": 24,
                        "methods": 0,
                        "misses": 5,
                        "partials": 0,
                        "sessions": 2,
                    },
                    "state": self.first_test_commit.state,
                },
            ],
        }
        assert content == expected_result

    def test_get_commits_wrong_org(self, mock_provider):
        response = self.client.get("/internal/github/codecov/otherRepoName/commits/")
        content = self.json_content(response)
        self.assertEqual(
            response.status_code, 404, "got unexpected response: {}".format(content)
        )

    def test_filters_by_branch_name(self, mock_provider):
        mock_provider.return_value = True, True
        repo = RepositoryFactory(
            author=self.current_owner, active=True, private=True, name="banana"
        )
        CommitFactory.create(
            message="test_commits_base",
            commitid="9193232a8fe3429496956ba82b5fed2583d1b5ec",
            repository=repo,
        )
        commit_non_master = CommitFactory.create(
            message="another_commit_not_on_master",
            commitid="ddcc232a8fe3429496956ba82b5fed2583d1b5ec",
            repository=repo,
            branch="other-branch",
        )

        response = self.client.get("/internal/github/codecov-user/banana/commits/")
        content = json.loads(response.content.decode())
        assert len(content["results"]) == 2
        assert content["results"][0]["commitid"] == commit_non_master.commitid

        response = self.client.get(
            "/internal/github/codecov-user/banana/commits/?branch=other-branch"
        )
        content = json.loads(response.content.decode())
        assert len(content["results"]) == 1
        assert content["results"][0]["commitid"] == commit_non_master.commitid

    def test_fetch_commits_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.current_owner.permission = []
        self.current_owner.save()

        response = self.client.get("/internal/github/codecov/testRepoName/commits/")

        assert response.status_code == 404

    def test_fetch_commits_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()

        response = self.client.get("/internal/github/codecov/testRepoName/commits/")

        assert response.status_code == 403


@patch(get_permissions_method)
class BranchViewSetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.other_user = OwnerFactory(permission=[self.repo.repoid])

        self.branches = [
            BranchFactory(repository=self.repo, name="foo"),
            BranchFactory(repository=self.repo, name="bar"),
        ]

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def _get_branches(self, kwargs={}, query={}):
        if not kwargs:
            kwargs = {
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            }
        return self.client.get(reverse("branches-list", kwargs=kwargs), data=query)

    def test_can_get_public_repo_branches_if_not_authenticated(self, mocked_provider):
        mocked_provider.return_value = True, True
        self.client.logout()
        author = OwnerFactory()
        repo = RepositoryFactory(author=author, private=False)
        response = self._get_branches(
            kwargs={
                "service": author.service,
                "owner_username": author.username,
                "repo_name": repo.name,
            }
        )
        assert response.status_code == 200

    def test_list_returns_200_and_expected_branches(self, mock_provider):
        response = self._get_branches()
        assert response.status_code == 200
        assert response.data["results"][0]["name"] == self.branches[1].name
        assert response.data["results"][1]["name"] == self.branches[0].name

    def test_list_without_permission_returns_403(self, mock_provider):
        mock_provider.return_value = False, False
        repo_no_permissions = RepositoryFactory(author=self.org)
        response = self._get_branches(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": repo_no_permissions.name,
            }
        )
        assert response.status_code == 404

    def test_list_with_nonexistent_repo_returns_404(self, mock_provider):
        nonexistent_repo_name = "existant"
        response = self._get_branches(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": nonexistent_repo_name,
            }
        )
        assert response.status_code == 404

    def test_branch_data_includes_most_recent_commiter_of_each_branch(
        self, mock_provider
    ):
        self.branches[0].head = CommitFactory(
            repository=self.repo,
            author=self.current_owner,
            branch=self.branches[0].name,
        ).commitid
        self.branches[0].save()
        self.branches[1].head = CommitFactory(
            repository=self.repo, author=self.other_user, branch=self.branches[1].name
        ).commitid
        self.branches[1].save()

        response = self._get_branches()

        assert (
            response.data["results"][0]["most_recent_commiter"]
            == self.other_user.username
        )
        assert (
            response.data["results"][1]["most_recent_commiter"]
            == self.current_owner.username
        )

    def test_list_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappy"
        self.org.plan_auto_activate = False
        self.org.save()

        response = self._get_branches()

        assert response.status_code == 403
