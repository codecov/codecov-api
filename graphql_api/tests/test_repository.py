import datetime
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase, override_settings
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
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

query_repositories = """
query Repositories($repoNames: [String!]!) {
    me {
        owner {
            repositories(filters: { repoNames: $repoNames }) {
                edges {
                    node {
                        %s
                    }
                }
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
    oldestCommitAt
    uploadToken
    defaultBranch
    author { username }
    profilingToken
    criticalFiles { name }
    graphToken
    yaml
    bot { username }
"""


class TestFetchRepository(GraphQLTestHelper, TransactionTestCase):
    def fetch_repository(self, name, fields=None):
        data = self.gql_request(
            query_repository % (fields or default_fields),
            user=self.user,
            variables={"name": name},
        )
        return data["me"]["owner"]["repository"]

    def fetch_repositories(self, repo_names, fields=None):
        data = self.gql_request(
            query_repositories % (fields or default_fields),
            user=self.user,
            variables={"repoNames": repo_names},
        )
        return [edge["node"] for edge in data["me"]["owner"]["repositories"]["edges"]]

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.yaml = {"test": "test"}

    @freeze_time("2021-01-01")
    def test_when_repository_has_no_coverage(self):

        repo = RepositoryFactory(
            author=self.user, active=True, private=True, name="a", yaml=self.yaml
        )
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
            "oldestCommitAt": None,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "master",
            "author": {"username": "codecov-user"},
            "profilingToken": profiling_token,
            "criticalFiles": [],
            "graphToken": graphToken,
            "yaml": "test: test\n",
            "bot": None,
        }

    @freeze_time("2021-01-01")
    def test_when_repository_has_coverage(self):
        repo = RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
            name="b",
            yaml=self.yaml,
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
            "oldestCommitAt": "2020-12-31T23:00:00",  # hour ago
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
            "yaml": "test: test\n",
            "bot": None,
        }

    @freeze_time("2021-01-01")
    def test_repositories_oldest_commit_at(self):
        repo = RepositoryFactory(author=self.user)

        CommitFactory(repository=repo, totals={"c": 75})
        CommitFactory(repository=repo, totals={"c": 85})

        # oldestCommitAt not loaded for multiple repos
        assert self.fetch_repositories([repo.name], fields="oldestCommitAt") == [
            {
                "oldestCommitAt": None,
            }
        ]

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

    def test_repository_resolve_yaml(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="has_yaml", yaml=self.yaml)
        data = self.gql_request(
            query_repository % "yaml",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["yaml"] == "test: test\n"

    def test_repository_resolve_yaml_no_yaml(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="no_yaml")
        data = self.gql_request(
            query_repository % "yaml",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["yaml"] == None

    def test_repository_resolve_bot(self):
        user = OwnerFactory()
        bot = OwnerFactory(username="random_bot")
        repo = RepositoryFactory(author=user, bot=bot)
        data = self.gql_request(
            query_repository % "bot {username}",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["bot"]["username"] == "random_bot"

    def test_repository_resolve_activated_true(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, activated=True)
        data = self.gql_request(
            query_repository % "activated",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["activated"] == True

    @override_settings(TIMESERIES_ENABLED=False)
    def test_repository_resolve_activated_false(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, activated=False)
        data = self.gql_request(
            query_repository % "activated",
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["activated"] == False

    @override_settings(TIMESERIES_ENABLED=False)
    def test_repository_flags_metadata(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user)
        data = self.gql_request(
            query_repository
            % """
                flagsMeasurementsActive
                flagsMeasurementsBackfilled
            """,
            user=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["flagsMeasurementsActive"] == False
        assert data["me"]["owner"]["repository"]["flagsMeasurementsBackfilled"] == False

    @patch("shared.yaml.user_yaml.UserYaml.get_final_yaml")
    def test_repository_repository_config_indication_range(self, mocked_useryaml):
        mocked_useryaml.return_value = {"coverage": {"range": [60, 80]}}

        repo = RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
        )

        data = self.gql_request(
            query_repository
            % "repositoryConfig { indicationRange { upperRange lowerRange } }",
            user=self.user,
            variables={"name": repo.name},
        )

        assert (
            data["me"]["owner"]["repository"]["repositoryConfig"]["indicationRange"][
                "lowerRange"
            ]
            == 60
        )
        assert (
            data["me"]["owner"]["repository"]["repositoryConfig"]["indicationRange"][
                "upperRange"
            ]
            == 80
        )
