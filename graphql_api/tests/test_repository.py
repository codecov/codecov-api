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
from reports.tests.factories import TestFactory, TestInstanceFactory
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
    name
    coverage
    coverageSha
    hits
    misses
    lines
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
        assert self.fetch_repository(repo.name) == {
            "__typename": "Repository",
            "name": "a",
            "active": True,
            "private": True,
            "coverage": None,
            "coverageSha": None,
            "hits": None,
            "misses": None,
            "lines": None,
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
        assert self.fetch_repository(repo.name) == {
            "__typename": "Repository",
            "name": "b",
            "active": True,
            "latestCommitAt": None,
            "oldestCommitAt": "2020-12-31T23:00:00",  # hour ago
            "private": True,
            "coverage": 75,
            "coverageSha": coverage_commit.commitid,
            "hits": 30,
            "misses": 10,
            "lines": 40,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "master",
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
            owner=user,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"]["flagsMeasurementsActive"] == False
        assert data["me"]["owner"]["repository"]["flagsMeasurementsBackfilled"] == False

    @override_settings(TIMESERIES_ENABLED=False)
    def test_repository_components_metadata(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user)
        data = self.gql_request(
            query_repository
            % """
                componentsMeasurementsActive
                componentsMeasurementsBackfilled
            """,
            owner=user,
            variables={"name": repo.name},
        )
        assert (
            data["me"]["owner"]["repository"]["componentsMeasurementsActive"] == False
        )
        assert (
            data["me"]["owner"]["repository"]["componentsMeasurementsBackfilled"]
            == False
        )

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
    def test_repository_not_activated(self, try_auto_activate, is_activated):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            coverage_enabled=True,
            bundle_analysis_enabled=True,
        )

        is_activated.return_value = False

        data = self.gql_request(
            query_repository % "name",
            owner=self.owner,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"] == {
            "__typename": "OwnerNotActivatedError",
            "message": "You must be activated in the org",
        }

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.activation.try_auto_activate")
    def test_repository_not_activated_self_hosted(self, try_auto_activate):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            coverage_enabled=True,
            bundle_analysis_enabled=True,
        )

        data = self.gql_request(
            query_repository % "name",
            owner=self.owner,
            variables={"name": repo.name},
        )
        assert data["me"]["owner"]["repository"] == {
            "__typename": "OwnerNotActivatedError",
            "message": "You must be activated in the org",
        }

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

    def test_repository_has_components_count(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={
                "component_management": {
                    "default_rules": {},
                    "individual_components": [
                        {"component_id": "blah", "paths": [r".*\.go"]},
                        {"component_id": "cool_rules"},
                    ],
                }
            },
        )

        data = self.gql_request(
            query_repository
            % """
                componentsCount
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["componentsCount"] == 2

    def test_repository_no_components_count(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        data = self.gql_request(
            query_repository
            % """
                componentsCount
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["componentsCount"] == 0

    def test_repository_components_select(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={
                "component_management": {
                    "default_rules": {},
                    "individual_components": [
                        {
                            "component_id": "blah",
                            "paths": [r".*\.go"],
                            "name": "blah_name",
                        },
                        {"component_id": "cool_rules", "name": "cool_name"},
                    ],
                }
            },
        )

        data = self.gql_request(
            query_repository
            % """
                componentsYaml(termId: null) {
                    id
                    name
                }
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["componentsYaml"] == [
            {"id": "blah", "name": "blah_name"},
            {"id": "cool_rules", "name": "cool_name"},
        ]

    def test_repository_components_select_with_search(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={
                "component_management": {
                    "default_rules": {},
                    "individual_components": [
                        {
                            "component_id": "blah",
                            "paths": [r".*\.go"],
                            "name": "blah_name",
                        },
                        {"component_id": "cool_rules", "name": "cool_name"},
                    ],
                }
            },
        )

        data = self.gql_request(
            query_repository
            % """
                componentsYaml(termId: "blah") {
                    id
                    name
                }
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["componentsYaml"] == [
            {"id": "blah", "name": "blah_name"},
        ]

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

        mock_log_warning.assert_called_once_with(
            "Error when checking rate limit",
            extra={
                "repo_id": repo.repoid,
                "has_owner": True,
            },
        )

    def test_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test, created_at=datetime.datetime.now(), repoid=repo.repoid
        )
        res = self.fetch_repository(
            repo.name, """testResults { edges { node { name } } }"""
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test.name}}]}

    def test_test_results_no_tests(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        res = self.fetch_repository(
            repo.name, """testResults { edges { node { name } } }"""
        )
        assert res["testResults"] == {"edges": []}

    def test_branch_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="feature",
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(filters: { branch: "main"}) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test.name}}]}

    def test_commits_failed_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            commitid="1",
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            commitid="2",
        )
        test_2 = TestFactory(repository=repo)
        _test_instance_3 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            commitid="3",
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(ordering: { parameter: COMMITS_WHERE_FAIL, direction: ASC }) { edges { node { name commitsFailed } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test_2.name, "commitsFailed": 1}},
                {"node": {"name": test.name, "commitsFailed": 2}},
            ]
        }

    def test_desc_commits_failed_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            commitid="1",
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            commitid="2",
        )
        test_2 = TestFactory(repository=repo)
        _test_instance_3 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            commitid="3",
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(ordering: { parameter: COMMITS_WHERE_FAIL, direction: DESC }) { edges { node { name commitsFailed } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "commitsFailed": 2}},
                {"node": {"name": test_2.name, "commitsFailed": 1}},
            ]
        }

    def test_avg_duration_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            duration_seconds=1,
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            duration_seconds=2,
        )
        test_2 = TestFactory(repository=repo)
        _test_instance_3 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            duration_seconds=3,
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(ordering: { parameter: AVG_DURATION, direction: ASC }) { edges { node { name avgDuration } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "avgDuration": 1.5}},
                {"node": {"name": test_2.name, "avgDuration": 3}},
            ]
        }

    def test_desc_avg_duration_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            duration_seconds=1,
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            duration_seconds=2,
        )
        test_2 = TestFactory(repository=repo)
        _test_instance_3 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            duration_seconds=3,
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(ordering: { parameter: AVG_DURATION, direction: DESC }) { edges { node { name avgDuration } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test_2.name, "avgDuration": 3}},
                {"node": {"name": test.name, "avgDuration": 1.5}},
            ]
        }

    def test_failure_rate_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="pass",
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="failure",
        )
        test_2 = TestFactory(repository=repo)
        _test_instance_3 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="failure",
        )
        _test_instance_4 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="failure",
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(ordering: { parameter: FAILURE_RATE, direction: ASC }) { edges { node { name failureRate } } }""",
        )

        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "failureRate": 0.5}},
                {"node": {"name": test_2.name, "failureRate": 1.0}},
            ]
        }

    def test_desc_failure_rate_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _test_instance_1 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="pass",
        )
        _test_instance_2 = TestInstanceFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="failure",
        )
        test_2 = TestFactory(repository=repo)
        _test_instance_3 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="failure",
        )
        _test_instance_4 = TestInstanceFactory(
            test=test_2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            outcome="failure",
        )
        res = self.fetch_repository(
            repo.name,
            """testResults(ordering: { parameter: FAILURE_RATE, direction: DESC }) { edges { node { name failureRate } } }""",
        )

        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test_2.name, "failureRate": 1.0}},
                {"node": {"name": test.name, "failureRate": 0.5}},
            ]
        }
