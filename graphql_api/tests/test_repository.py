import datetime
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase, override_settings
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)

from graphql_api.types.repository.repository import TOKEN_UNAVAILABLE
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper

query_repository = """
query Repository($name: String!){
    me {
        owner {
            repository(name: $name) {
                __typename
                ... on Repository {
                    %s
                }
                ... on ResolverError {
                    message
                }
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
    repoid
    name
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
    isATSConfigured
    primaryLanguage
    languages
    bundleAnalysisEnabled
    coverageEnabled
    bot { username }
    testAnalyticsEnabled
"""


def mock_get_config_global_upload_tokens(*args):
    if args == ("setup", "hide_all_codecov_tokens"):
        return True


class TestFetchRepository(GraphQLTestHelper, TransactionTestCase):
    def fetch_repository(self, name, fields=None):
        data = self.gql_request(
            query_repository % (fields or default_fields),
            owner=self.owner,
            variables={"name": name},
        )
        return data["me"]["owner"]["repository"]

    def fetch_repositories(self, repo_names, fields=None):
        data = self.gql_request(
            query_repositories % (fields or default_fields),
            owner=self.owner,
            variables={"repoNames": repo_names},
        )
        return [edge["node"] for edge in data["me"]["owner"]["repositories"]["edges"]]

    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.yaml = {"test": "test"}

    @freeze_time("2021-01-01")
    def test_when_repository_has_no_coverage(self):
        repo = RepositoryFactory(
            repoid=1,
            author=self.owner,
            active=True,
            private=True,
            name="a",
            yaml=self.yaml,
            language="rust",
            languages=["python", "rust"],
            test_analytics_enabled=True,
        )
        profiling_token = RepositoryTokenFactory(
            repository_id=repo.repoid, token_type="profiling"
        ).key
        graphToken = repo.image_token
        assert self.fetch_repository(
            repo.name,
            default_fields
            + "coverageAnalytics { percentCovered commitSha hits misses lines },",
        ) == {
            "__typename": "Repository",
            "repoid": 1,
            "name": "a",
            "active": True,
            "private": True,
            "coverageAnalytics": {
                "percentCovered": None,
                "commitSha": None,
                "hits": None,
                "misses": None,
                "lines": None,
            },
            "latestCommitAt": None,
            "oldestCommitAt": None,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "main",
            "author": {"username": "codecov-user"},
            "profilingToken": profiling_token,
            "criticalFiles": [],
            "graphToken": graphToken,
            "yaml": "test: test\n",
            "isATSConfigured": False,
            "primaryLanguage": "rust",
            "languages": ["python", "rust"],
            "bundleAnalysisEnabled": False,
            "coverageEnabled": False,
            "bot": None,
            "testAnalyticsEnabled": True,
        }

    @freeze_time("2021-01-01")
    def test_when_repository_has_coverage(self):
        repo = RepositoryFactory(
            repoid=1,
            author=self.owner,
            active=True,
            private=True,
            name="b",
            yaml=self.yaml,
            language="erlang",
            languages=[],
        )

        hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
        coverage_commit = CommitFactory(
            repository=repo,
            totals={"c": 75, "h": 30, "m": 10, "n": 40},
            timestamp=hour_ago,
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
        assert self.fetch_repository(
            repo.name,
            default_fields
            + "coverageAnalytics { percentCovered commitSha hits misses lines },",
        ) == {
            "__typename": "Repository",
            "repoid": 1,
            "name": "b",
            "active": True,
            "latestCommitAt": None,
            "oldestCommitAt": "2020-12-31T23:00:00",  # hour ago
            "private": True,
            "coverageAnalytics": {
                "percentCovered": 75,
                "commitSha": coverage_commit.commitid,
                "hits": 30,
                "misses": 10,
                "lines": 40,
            },
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "main",
            "author": {"username": "codecov-user"},
            "profilingToken": profiling_token,
            "criticalFiles": [],
            "graphToken": graphToken,
            "yaml": "test: test\n",
            "isATSConfigured": False,
            "primaryLanguage": "erlang",
            "languages": [],
            "bundleAnalysisEnabled": False,
            "coverageEnabled": False,
            "bot": None,
            "testAnalyticsEnabled": False,
        }

    @freeze_time("2021-01-01")
    def test_repositories_oldest_commit_at(self):
        repo = RepositoryFactory(author=self.owner)

        CommitFactory(repository=repo, totals={"c": 75})
        CommitFactory(repository=repo, totals={"c": 85})

        # oldestCommitAt not loaded for multiple repos
        assert self.fetch_repositories([repo.name], fields="oldestCommitAt") == [
            {
                "oldestCommitAt": None,
            }
        ]

    def test_repository_pulls(self):
        repo = RepositoryFactory(author=self.owner, active=True, private=True, name="a")
        PullFactory(repository=repo, pullid=2)
        PullFactory(repository=repo, pullid=3)

        res = self.fetch_repository(repo.name, "pulls { edges { node { pullId } } }")
        assert res["pulls"]["edges"][0]["node"]["pullId"] == 3
        assert res["pulls"]["edges"][1]["node"]["pullId"] == 2

    def test_repository_get_profiling_token(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="gazebo", active=True)
        RepositoryTokenFactory(repository=repo, key="random", token_type="profiling")

        data = self.gql_request(
            query_repository % "profilingToken",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["profilingToken"] == "random"

    def test_repository_get_static_analysis_token(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="gazebo", active=True)
        RepositoryTokenFactory(
            repository=repo, key="random", token_type="static_analysis"
        )

        data = self.gql_request(
            query_repository % "staticAnalysisToken",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["staticAnalysisToken"] == "random"

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
            author=self.owner,
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
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["graphToken"] == repo.image_token

    def test_repository_resolve_yaml(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="has_yaml", yaml=self.yaml)
        data = self.gql_request(
            query_repository % "yaml",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["yaml"] == "test: test\n"

    def test_repository_resolve_yaml_no_yaml(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, name="no_yaml")
        data = self.gql_request(
            query_repository % "yaml",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["yaml"] is None

    def test_repository_resolve_bot(self):
        user = OwnerFactory()
        bot = OwnerFactory(username="random_bot")
        repo = RepositoryFactory(author=user, bot=bot)
        data = self.gql_request(
            query_repository % "bot {username}",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["bot"]["username"] == "random_bot"

    def test_repository_resolve_activated_true(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, activated=True)
        data = self.gql_request(
            query_repository % "activated",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["activated"] == True

    @override_settings(TIMESERIES_ENABLED=False)
    def test_repository_resolve_activated_false(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user, activated=False)
        data = self.gql_request(
            query_repository % "activated",
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["activated"] == False

    @patch("shared.yaml.user_yaml.UserYaml.get_final_yaml")
    def test_repository_repository_config_indication_range(self, mocked_useryaml):
        mocked_useryaml.return_value = {"coverage": {"range": [60, 80]}}

        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
        )

        data = self.gql_request(
            query_repository
            % "repositoryConfig { indicationRange { upperRange lowerRange } }",
            owner=self.owner,
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

    @patch("shared.yaml.user_yaml.UserYaml.get_final_yaml")
    def test_repository_repository_config_indication_range_float(self, mocked_useryaml):
        mocked_useryaml.return_value = {"coverage": {"range": [61.1, 82.2]}}

        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
        )

        data = self.gql_request(
            query_repository
            % "repositoryConfig { indicationRange { upperRange lowerRange } }",
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert (
            data["me"]["owner"]["repository"]["repositoryConfig"]["indicationRange"][
                "lowerRange"
            ]
            == 61.1
        )
        assert (
            data["me"]["owner"]["repository"]["repositoryConfig"]["indicationRange"][
                "upperRange"
            ]
            == 82.2
        )

    @patch("services.activation.try_auto_activate")
    def test_repository_auto_activate(self, try_auto_activate):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            coverage_enabled=True,
            bundle_analysis_enabled=True,
        )

        self.gql_request(
            query_repository % "name",
            owner=self.owner,
            variables={"name": repo.name},
        )

        try_auto_activate.assert_called_once_with(
            self.owner,
            self.owner,
        )

    @patch("services.activation.is_activated")
    @patch("services.activation.try_auto_activate")
    def test_resolve_inactive_user_on_unconfigured_repo(
        self, try_auto_activate, is_activated
    ):
        repo = RepositoryFactory(
            author=self.owner,
            active=False,
            activated=False,
            private=True,
            name="test-one",
            coverage_enabled=True,
            bundle_analysis_enabled=False,
        )

        is_activated.return_value = False

        data = self.gql_request(
            query_repository % "name",
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["name"] == "test-one"

    def test_repository_not_found(self):
        data = self.gql_request(
            query_repository % "name",
            owner=self.owner,
            variables={"name": "nonexistent-repo-name"},
        )
        assert data["me"]["owner"]["repository"] == {
            "__typename": "NotFoundError",
            "message": "Not found",
        }

    def test_repository_has_ats_configured(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={
                "flag_management": {"individual_flags": {"carryforward_mode": "labels"}}
            },
        )

        res = self.fetch_repository(repo.name)
        assert res["isATSConfigured"] == True

    def test_repository_get_language(self):
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, language="python"
        )

        res = self.fetch_repository(repo.name)
        assert res["primaryLanguage"] == "python"

    def test_repository_get_bundle_analysis_enabled(self):
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, bundle_analysis_enabled=True
        )
        res = self.fetch_repository(repo.name)
        assert res["bundleAnalysisEnabled"] == True

    def test_repository_get_coverage_enabled(self):
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, coverage_enabled=True
        )
        res = self.fetch_repository(repo.name)
        assert res["coverageEnabled"] == True

    def test_repository_get_test_analytics_enabled(self) -> None:
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, test_analytics_enabled=True
        )
        res = self.fetch_repository(repo.name)
        assert res["testAnalyticsEnabled"] == True

    def test_repository_get_test_analytics_disabled(self) -> None:
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, test_analytics_enabled=False
        )
        res = self.fetch_repository(repo.name)
        assert res["testAnalyticsEnabled"] == False

    def test_repository_get_languages_null(self):
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, languages=None
        )
        res = self.fetch_repository(repo.name)
        assert res["languages"] is None

    def test_repository_get_languages_empty(self):
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        res = self.fetch_repository(repo.name)
        assert res["languages"] == []

    def test_repository_get_languages_with_values(self):
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, languages=["C", "C++"]
        )
        res = self.fetch_repository(repo.name)
        assert res["languages"] == ["C", "C++"]

    def test_repository_is_first_pull_request(self) -> None:
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        PullFactory(repository=repo, pullid=1, compared_to=None)

        data = self.gql_request(
            query_repository
            % """
                isFirstPullRequest
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["isFirstPullRequest"] == True

    def test_repository_is_first_pull_request_compared_to_not_none(self) -> None:
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        PullFactory(repository=repo, pullid=1, compared_to=1)

        data = self.gql_request(
            query_repository
            % """
                isFirstPullRequest
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["isFirstPullRequest"] == False

    def test_repository_when_is_first_pull_request_false(self) -> None:
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        PullFactory(repository=repo, pullid=1)
        PullFactory(repository=repo, pullid=2)

        data = self.gql_request(
            query_repository
            % """
                isFirstPullRequest
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["isFirstPullRequest"] == False

    @patch("shared.rate_limits.determine_entity_redis_key")
    @patch("shared.rate_limits.determine_if_entity_is_rate_limited")
    @override_settings(IS_ENTERPRISE=True, GUEST_ACCESS=False)
    def test_fetch_is_github_rate_limited(
        self, mock_determine_rate_limit, mock_determine_redis_key
    ):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        mock_determine_redis_key.return_value = "test"
        mock_determine_rate_limit.return_value = True

        data = self.gql_request(
            query_repository
            % """
                isGithubRateLimited
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["isGithubRateLimited"] == True

    def test_fetch_is_github_rate_limited_not_on_gh_service(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(
            author=owner,
            author__service="gitlab",
            service_id=12345,
            active=True,
        )

        data = self.gql_request(
            query_repository
            % """
                isGithubRateLimited
            """,
            owner=owner,
            variables={"name": repo.name},
            provider="gitlab",
        )

        assert data["me"]["owner"]["repository"]["isGithubRateLimited"] == False

    @override_settings(HIDE_ALL_CODECOV_TOKENS=True)
    def test_repo_upload_token_not_available_config_setting_owner_not_admin(self):
        owner = OwnerFactory(service="gitlab")

        repo = RepositoryFactory(
            author=owner,
            author__service="gitlab",
            service_id=12345,
            active=True,
        )
        new_owner = OwnerFactory(service="gitlab", organizations=[owner.ownerid])
        new_owner.permission = [repo.repoid]
        new_owner.save()
        owner.admins = []

        query = """
            query {
                owner(username: "%s") {
                    repository(name: "%s") {
                                    ... on Repository {
                            uploadToken
                            }
                    }
                }
            }
        """ % (
            owner.username,
            repo.name,
        )

        data = self.gql_request(
            query,
            owner=new_owner,
            variables={"name": repo.name},
            provider="gitlab",
        )

        assert data["owner"]["repository"]["uploadToken"] == TOKEN_UNAVAILABLE

    @override_settings(HIDE_ALL_CODECOV_TOKENS=True)
    def test_repo_upload_token_not_available_config_setting_owner_is_anonymous(self):
        owner = OwnerFactory(service="gitlab")

        repo = RepositoryFactory(
            author=owner,
            author__service="gitlab",
            service_id=12345,
            active=True,
            private=False,
        )

        query = """
            query {
                owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            uploadToken
                        }
                    }
                }
            }
        """ % (
            owner.username,
            repo.name,
        )

        data = self.gql_request(
            query,
            variables={"name": repo.name},
            provider="gitlab",
        )

        assert data["owner"]["repository"]["uploadToken"] == TOKEN_UNAVAILABLE

    @override_settings(HIDE_ALL_CODECOV_TOKENS=True)
    def test_repo_upload_token_not_available_config_setting_owner_is_admin(self):
        owner = OwnerFactory(service="gitlab")
        repo = RepositoryFactory(
            author=owner,
            author__service="gitlab",
            service_id=12345,
            active=True,
        )
        owner.admins = [owner.ownerid]

        data = self.gql_request(
            query_repository
            % """
                uploadToken
            """,
            owner=owner,
            variables={"name": repo.name},
            provider="gitlab",
        )

        assert data["me"]["owner"]["repository"]["uploadToken"] != TOKEN_UNAVAILABLE

    @patch("shared.rate_limits.determine_entity_redis_key")
    @patch("shared.rate_limits.determine_if_entity_is_rate_limited")
    @patch("logging.Logger.warning")
    @override_settings(IS_ENTERPRISE=True, GUEST_ACCESS=False)
    def test_fetch_is_github_rate_limited_but_errors(
        self,
        mock_log_warning,
        mock_determine_rate_limit,
        mock_determine_redis_key,
    ):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        mock_determine_redis_key.side_effect = Exception("some random error lol")
        mock_determine_rate_limit.return_value = True

        data = self.gql_request(
            query_repository
            % """
                isGithubRateLimited
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["isGithubRateLimited"] is None

        mock_log_warning.assert_any_call(
            "Error when checking rate limit",
            extra={
                "repo_id": repo.repoid,
                "has_owner": True,
            },
        )
