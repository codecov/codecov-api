import datetime
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.commands import repository
from core.models import Repository
from core.tests.factories import (
    CommitFactory,
    PullFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper

query_repository = """
query Repository($name: String!){
    me {
        owner {
            repository(name: $name) {
                %s
            }
        }
    }
}
"""

default_fields = """
    name
    coverage
    coverageSha
    active
    private
    updatedAt
    latestCommitAt
    uploadToken
    defaultBranch
    author { username }
    profilingToken
    criticalFiles { name }
    graphToken
"""


class TestFetchRepository(GraphQLTestHelper, TransactionTestCase):
    def fetch_repository(self, name, fields=None):
        data = self.gql_request(
            query_repository % (fields or default_fields),
            user=self.user,
            variables={"name": name},
        )
        return data["me"]["owner"]["repository"]

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    @freeze_time("2021-01-01")
    def test_when_repository_has_no_coverage(self):

        repo = RepositoryFactory(author=self.user, active=True, private=True, name="a")
        profiling_token = RepositoryTokenFactory(
            repository_id=repo.repoid, token_type="profiling"
        ).key
        graphToken = repo.image_token
        assert self.fetch_repository(repo.name) == {
            "name": "a",
            "active": True,
            "private": True,
            "coverage": None,
            "coverageSha": None,
            "latestCommitAt": None,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "master",
            "author": {"username": "codecov-user"},
            "profilingToken": profiling_token,
            "criticalFiles": [],
            "graphToken": graphToken,
        }

    @freeze_time("2021-01-01")
    def test_when_repository_has_coverage(self):
        repo = RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
            name="b",
        )

        hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
        coverage_commit = CommitFactory(
            repository=repo, totals={"c": 75}, timestamp=hour_ago
        )
        CommitFactory(repository=repo, totals={"c": 85})

        # trigger in the database is updating `updatestamp` after creating
        # associated commits
        repo.updatestamp = datetime.datetime.now()
        repo.save()

        profiling_token = RepositoryTokenFactory(
            repository_id=repo.repoid, token_type="profiling"
        ).key
        graphToken = repo.image_token
        assert self.fetch_repository(repo.name) == {
            "name": "b",
            "active": True,
            "latestCommitAt": None,
            "private": True,
            "coverage": 75,
            "coverageSha": coverage_commit.commitid,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "master",
            "author": {"username": "codecov-user"},
            "profilingToken": profiling_token,
            "criticalFiles": [],
            "graphToken": graphToken,
        }

    def test_repository_pulls(self):
        repo = RepositoryFactory(author=self.user, active=True, private=True, name="a")
        PullFactory(repository=repo, pullid=2)
        PullFactory(repository=repo, pullid=3)

        res = self.fetch_repository(repo.name, "pulls { edges { node { pullId } } }")
        assert res["pulls"]["edges"][0]["node"]["pullId"] == 3
        assert res["pulls"]["edges"][1]["node"]["pullId"] == 2

    def test_repository_get_profiling_token(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="gazebo", active=True)
        RepositoryTokenFactory(repository=repo, key="random")

        data = self.gql_request(
            query_repository % "profilingToken",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["profilingToken"] == "random"

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    def test_repository_critical_files(self, critical_files):
        critical_files.return_value = [
            CriticalFile("one"),
            CriticalFile("two"),
            CriticalFile("three"),
        ]
        repo = RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
        )
        res = self.fetch_repository(repo.name)
        assert res["criticalFiles"] == [
            {"name": "one"},
            {"name": "two"},
            {"name": "three"},
        ]

    def test_repository_get_graph_token(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user)

        data = self.gql_request(
            query_repository % "graphToken",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["graphToken"] == repo.image_token
