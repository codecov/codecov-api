import json
from unittest.mock import patch

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    RepositoryFactory,
    PullFactory,
    CommitFactory,
    BranchFactory,
)

from rest_framework.reverse import reverse
from rest_framework import status

get_permissions_method = (
    "internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions"
)


class ProfileTest(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username="Codecov")
        RepositoryFactory(author=org)
        self.user = OwnerFactory(
            username="codecov-user",
            organizations=[org.ownerid],
            private_access=False,
            staff=False,
        )
        RepositoryFactory(author=self.user)
        pass

    def test_get_profile_valid_user(self):
        self.client.force_login(user=self.user)
        response = self.client.get("/internal/profile/")
        self.assertEqual(response.status_code, 200)

    def test_get_profile_unauthed_user_returns_401(self):
        response = self.client.get("/internal/profile/")
        self.assertEqual(response.status_code, 401)

    def test_update_profile_private_access(self):
        self.client.force_login(user=self.user)
        response = self.client.patch(
            "/internal/profile/",
            data={"private_access": True},
            content_type="application/json",
        )

        self.user.refresh_from_db()
        assert self.user.private_access is True
        assert response.data["private_access"] is True

    def test_update_profile_read_only(self):
        self.client.force_login(user=self.user)
        response = self.client.patch(
            "/internal/profile/",
            data={"staff": True},
            content_type="application/json",
        )

        self.user.refresh_from_db()
        assert self.user.staff is False
        assert response.data["staff"] is False


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
        self.user = OwnerFactory(
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
            head=CommitFactory(repository=self.repo, author=self.user).commitid,
            base=CommitFactory(repository=self.repo, author=self.user).commitid,
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
        self.client.force_login(user=self.user)
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
        self.user.permission = []
        self.user.save()
        self.client.force_login(user=self.user)
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        self.assertEqual(response.status_code, 404)

    def test_get_pulls_filter_state(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
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
        self.client.force_login(user=self.user)
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
        self.client.force_login(user=self.user)
        # Test default ordering
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        content = self.json_content(response)
        pullids = [r["pullid"] for r in content["results"]]
        self.assertEqual(pullids, [11, 10, 1])

    def test_get_pull_wrong_org(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(reverse("pulls-list", kwargs=self.incorrect_kwargs))
        content = self.json_content(response)
        self.assertEqual(
            response.status_code, 404, "got unexpected response: {}".format(content)
        )

    def test_pulls_list_returns_most_recent_commiter(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))

        assert response.data["results"][1]["most_recent_commiter"] == self.user.username

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

        self.client.force_login(user=self.user)
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
            base=CommitFactory(repository=self.repo, author=self.user).commitid,
        )

        self.client.force_login(user=self.user)
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == status.HTTP_200_OK
        assert [p for p in response.data["results"] if p["pullid"] == 13][0][
            "head_totals"
        ] == None

    def test_get_pulls_no_base_commit_returns_null_for_base_totals(self, mock_provider):
        mock_provider.return_value = True, True

        PullFactory(
            pullid=13,
            author=self.org,
            repository=self.repo,
            state="open",
            base="",
            head=CommitFactory(repository=self.repo, author=self.user).commitid,
        )

        self.client.force_login(user=self.user)
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == status.HTTP_200_OK
        assert [p for p in response.data["results"] if p["pullid"] == 13][0][
            "base_totals"
        ] == None

    def test_get_pulls_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()
        self.client.force_login(user=self.user)
        response = self.client.get(reverse("pulls-list", kwargs=self.correct_kwargs))
        assert response.status_code == 403


@patch(get_permissions_method)
class RepoPullDetail(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        PullFactory(pullid=10, author=self.org, repository=repo, state="open")
        PullFactory(pullid=11, author=self.org, repository=repo, state="closed")

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
                    "pk": pull.pullid,
                },
            )
        )
        assert response.status_code == 200
        assert response.data["pullid"] == pull.pullid

    def test_get_pull(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(content["pullid"], 10)

    def test_get_pull_no_permissions(self, mock_provider):
        self.user.permission = []
        self.user.save()
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 404)

    def test_get_pull_as_inactive_user_returns_403(self, mock_provider):
        mock_provider = True, True
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()
        self.client.force_login(user=self.user)
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
        self.user = OwnerFactory(
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
        self.client.force_login(user=self.user)
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
                        "coverage": 79.17,
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
                        "coverage": 79.17,
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
        self.client.force_login(user=self.user)
        response = self.client.get("/internal/github/codecov/otherRepoName/commits/")
        content = self.json_content(response)
        self.assertEqual(
            response.status_code, 404, "got unexpected response: {}".format(content)
        )

    def test_filters_by_branch_name(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        repo = RepositoryFactory(
            author=self.user, active=True, private=True, name="banana"
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
        self.user.permission = []
        self.user.save()
        self.client.force_login(user=self.user)

        response = self.client.get("/internal/github/codecov/testRepoName/commits/")

        assert response.status_code == 404

    def test_fetch_commits_inactive_user_returns_403(self, mock_provider):
        mock_provider = True, True
        self.org.plan = "users-inappm"
        self.org.plan_auto_activate = False
        self.org.save()

        self.client.force_login(user=self.user)

        response = self.client.get("/internal/github/codecov/testRepoName/commits/")

        assert response.status_code == 403


@patch(get_permissions_method)
class BranchViewSetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.user = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.other_user = OwnerFactory(permission=[self.repo.repoid])

        self.branches = [
            BranchFactory(repository=self.repo),
            BranchFactory(repository=self.repo),
        ]

        self.client.force_login(user=self.user)

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
            repository=self.repo, author=self.user, branch=self.branches[0].name
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
        assert response.data["results"][1]["most_recent_commiter"] == self.user.username

    def test_list_as_inactive_user_returns_403(self, mock_provider):
        self.org.plan = "users-inappy"
        self.org.plan_auto_activate = False
        self.org.save()

        response = self._get_branches()

        assert response.status_code == 403
