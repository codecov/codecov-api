import json
from unittest.mock import PropertyMock, patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.reverse import reverse
from shared.reports.resources import ReportFile

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    BranchFactory,
    CommitFactory,
    PullFactory,
    RepositoryFactory,
)
from internal_api.commit.serializers import CommitTotalsSerializer
from services.archive import ArchiveService, SerializableReport
from services.comparison import Comparison


def build_commits(client):
    """
        build commits in mock_db that are based on a real git commit for using VCR
    :param user:
    :param client:
    :return: repo, commit_base, commit_head
    """
    repo = RepositoryFactory.create(
        author__unencrypted_oauth_token="testqmit3okrgutcoyzscveipor3toi3nsmb927v",
        author__username="ThiagoCodecov",
    )
    parent_commit = CommitFactory.create(
        message="test_compare_parent", commitid="c5b6730", repository=repo,
    )
    commit_base = CommitFactory.create(
        message="test_compare_commits_base",
        commitid="9193232a8fe3429496956ba82b5fed2583d1b5eb",
        parent_commit_id=parent_commit.commitid,
        repository=repo,
    )
    commit_head = CommitFactory.create(
        message="test_compare_commits_head",
        commitid="abf6d4df662c47e32460020ab14abf9303581429",
        parent_commit_id=parent_commit.commitid,
        repository=repo,
    )
    client.force_login(user=repo.author)
    return repo, commit_base, commit_head


@patch("services.comparison.Comparison.has_unmerged_base_commits", lambda self: False)
@patch("services.archive.ArchiveService.read_chunks", lambda obj, sha: "")
@patch(
    "internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions",
    lambda self, repo, user: (True, True),
)
class TestCompareCommitsView(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username="Codecov")
        self.user = OwnerFactory(
            username="codecov-user",
            email="codecov-user@codecov.io",
            organizations=[org.ownerid],
        )
        self.repo, self.commit_base, self.commit_head = build_commits(self.client)
        self.commit_base_totals_serialized = {
            "files": self.commit_base.totals["f"],
            "lines": self.commit_base.totals["n"],
            "hits": self.commit_base.totals["h"],
            "misses": self.commit_base.totals["m"],
            "partials": self.commit_base.totals["p"],
            "coverage": round(float(self.commit_base.totals["c"]), 2),
            "branches": self.commit_base.totals["b"],
            "methods": self.commit_base.totals["d"],
            "sessions": self.commit_base.totals["s"],
            "diff": self.commit_base.totals["diff"],
            "complexity": self.commit_base.totals["C"],
            "complexity_total": self.commit_base.totals["N"],
        }
        self.commit_head_totals_serialized = {
            "files": self.commit_head.totals["f"],
            "lines": self.commit_head.totals["n"],
            "hits": self.commit_head.totals["h"],
            "misses": self.commit_head.totals["m"],
            "partials": self.commit_head.totals["p"],
            "coverage": round(float(self.commit_head.totals["c"]), 2),
            "branches": self.commit_head.totals["b"],
            "methods": self.commit_head.totals["d"],
            "sessions": self.commit_head.totals["s"],
            "diff": self.commit_head.totals["diff"],
            "complexity": self.commit_head.totals["C"],
            "complexity_total": self.commit_head.totals["N"],
        }

    def _get_commits_comparison(self, kwargs, query_params):
        return self.client.get(
            reverse("compare-detail", kwargs=kwargs), data=query_params
        )

    def _configure_mocked_comparison_with_commits(self, mock):
        mock.return_value = {
            "diff": {"files": {}},
            "commits": [
                {
                    "commitid": self.commit_base.commitid,
                    "message": self.commit_base.message,
                    "timestamp": "2019-03-31T02:28:02Z",
                    "author": {
                        "id": self.repo.author.ownerid,
                        "username": self.repo.author.username,
                        "name": self.repo.author.name,
                        "email": self.repo.author.email,
                    },
                },
                {
                    "commitid": self.commit_head.commitid,
                    "message": self.commit_head.message,
                    "timestamp": "2019-03-31T07:23:19Z",
                    "author": {
                        "id": self.repo.author.ownerid,
                        "username": self.repo.author.username,
                        "name": self.repo.author.name,
                        "email": self.repo.author.email,
                    },
                },
            ],
        }

    def test_compare_commits_bad_commit(self):
        bad_commitid = "9193232a8fe3429496123ba82b5fed2583d1b5eb"
        response = self._get_commits_comparison(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={"base": self.commit_base.commitid, "head": bad_commitid},
        )
        assert response.status_code == 404

    def test_compare_commits_bad_branch(self):
        bad_branch = "bad-branch"
        branch_base = BranchFactory.create(head=self.commit_base, repository=self.repo)
        response = self._get_commits_comparison(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={"base": branch_base.name, "head": bad_branch},
        )
        assert response.status_code == 404

    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    def test_compare_commits_view_with_branchname(self, mocked_comparison):
        self._configure_mocked_comparison_with_commits(mocked_comparison)
        branch_base = BranchFactory.create(
            head=self.commit_base.commitid, repository=self.commit_base.repository
        )
        branch_head = BranchFactory.create(
            head=self.commit_head.commitid, repository=self.commit_head.repository
        )

        response = self._get_commits_comparison(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={"base": branch_base.name, "head": branch_head.name},
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert (
            content["diff"]["git_commits"] == mocked_comparison.return_value["commits"]
        )

        head_upload = next(
            commit
            for commit in content["commit_uploads"]
            if commit["commitid"] == self.commit_head.commitid
        )
        assert (
            head_upload["totals"]
            == CommitTotalsSerializer(self.commit_head.totals).data
        )

        base_upload = next(
            commit
            for commit in content["commit_uploads"]
            if commit["commitid"] == self.commit_base.commitid
        )
        assert (
            base_upload["totals"]
            == CommitTotalsSerializer(self.commit_base.totals).data
        )

    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    def test_compare_commits_view_with_commitid(self, mocked_comparison):
        self._configure_mocked_comparison_with_commits(mocked_comparison)
        response = self._get_commits_comparison(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={
                "base": self.commit_base.commitid,
                "head": self.commit_head.commitid,
            },
        )
        assert response.status_code == 200
        content = json.loads(response.content.decode())

        assert (
            content["diff"]["git_commits"] == mocked_comparison.return_value["commits"]
        )

        head_upload = next(
            commit
            for commit in content["commit_uploads"]
            if commit["commitid"] == self.commit_head.commitid
        )
        assert (
            head_upload["totals"]
            == CommitTotalsSerializer(self.commit_head.totals).data
        )

        base_upload = next(
            commit
            for commit in content["commit_uploads"]
            if commit["commitid"] == self.commit_base.commitid
        )
        assert (
            base_upload["totals"]
            == CommitTotalsSerializer(self.commit_base.totals).data
        )

    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    @patch("redis.Redis.get", lambda self, key: None)
    @patch("redis.Redis.set", lambda self, key, val, ex: None)
    def test_compare_commits_view_with_pullid(self, mocked_comparison):
        self._configure_mocked_comparison_with_commits(mocked_comparison)
        pull = PullFactory(
            pullid=2,
            repository=self.repo,
            author=self.repo.author,
            base=self.commit_base.commitid,
            compared_to=self.commit_base.commitid,
            head=self.commit_head.commitid,
        )

        response = self._get_commits_comparison(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={"pullid": pull.pullid},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = json.loads(response.content.decode())

        assert (
            content["diff"]["git_commits"] == mocked_comparison.return_value["commits"]
        )

        head_upload = next(
            commit
            for commit in content["commit_uploads"]
            if commit["commitid"] == self.commit_head.commitid
        )
        assert (
            head_upload["totals"]
            == CommitTotalsSerializer(self.commit_head.totals).data
        )

        base_upload = next(
            commit
            for commit in content["commit_uploads"]
            if commit["commitid"] == self.commit_base.commitid
        )
        assert (
            base_upload["totals"]
            == CommitTotalsSerializer(self.commit_base.totals).data
        )
