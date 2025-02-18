import datetime
from typing import Any, Dict, Optional

from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from billing.helpers import mock_all_plans_and_tiers
from core.models import Commit, Repository
from graphql_api.tests.helper import GraphQLTestHelper
from graphql_api.types.coverage_analytics.coverage_analytics import (
    CoverageAnalyticsProps,
    resolve_coverage_analytics_result_type,
)
from graphql_api.types.errors.errors import NotFoundError


class TestFetchCoverageAnalytics(GraphQLTestHelper, TransactionTestCase):
    # SETUP
    def setUp(self) -> None:
        self.owner = OwnerFactory(username="codecov-user")
        self.yaml = {"test": "test"}

    # some field resolvers require access to postgres or timeseries db
    databases = {"default", "timeseries"}

    # HELPERS
    def run_gql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        owner = self.owner
        # Use the gql_request method from the parent class (GraphQLTestHelper)
        return super().gql_request(query=query, owner=owner, variables=variables)

    def create_repository(self, name: str) -> Repository:
        return RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            name=name,
            yaml=self.yaml,
            language="erlang",
            languages=[],
        )

    @staticmethod
    def create_commit(
        repository: Repository,
        coverage_totals: Dict[str, int],
        timestamp: Optional[datetime.datetime] = None,
    ) -> Commit:
        if timestamp is None:
            timestamp = timezone.now()
        return CommitFactory(
            repository=repository, totals=coverage_totals, timestamp=timestamp
        )

    query_builder = """
    query Repository($name: String!){
        me {
            owner {
                repository(name: $name) {
                    __typename
                    ... on Repository {
                        coverageAnalytics {
                            %s
                        }
                    }
                    ... on ResolverError {
                        message
                    }
                }
            }
        }
    }
    """

    # TESTS
    def test_coverage_analytics_base_fields(self) -> None:
        """Test case where to fetch coverage analytics fields"""

        # Create repo, commit, and coverage data
        repo = self.create_repository("myname")
        hour_ago = timezone.make_aware(datetime.datetime(2020, 12, 31, 23, 0))
        coverage_commit = self.create_commit(
            repository=repo,
            coverage_totals={"c": 75, "h": 30, "m": 10, "n": 40},
            timestamp=hour_ago,
        )
        self.create_commit(repository=repo, coverage_totals={"c": 85})
        repo.updatestamp = timezone.now()
        repo.save()
        self.assertTrue(repo.pk, "Repository should be saved and have a primary key.")

        # Set up the GraphQL query and run
        query = """
        query CoverageAnalytics($owner: String!, $repo: String!) {
            owner(username: $owner) {
                repository(name: $repo) {
                    __typename
                    ... on Repository {
                        name
                        coverageAnalytics {
                            percentCovered
                            commitSha
                            hits
                            misses
                            lines
                        }
                    }
                    ... on ResolverError {
                        message
                    }
                }
            }
        }
        """
        variables = {"owner": self.owner.username, "repo": repo.name}
        resp = self.run_gql_query(query=query, variables=variables)

        # Assert the response matches
        expected_response = {
            "__typename": "Repository",
            "name": repo.name,
            "coverageAnalytics": {
                "percentCovered": 75,
                "commitSha": coverage_commit.commitid,
                "hits": 30,
                "misses": 10,
                "lines": 40,
            },
        }
        assert resp["owner"]["repository"] == expected_response

    def test_coverage_analytics_base_fields_partial(self) -> None:
        """Test case where the query only expects one of the fields in CoverageAnalytics"""

        # Create repo and a single commit
        repo = self.create_repository("testtest")
        hour_ago = timezone.make_aware(datetime.datetime(2020, 12, 31, 23, 0))
        self.create_commit(
            repository=repo,
            coverage_totals={"c": 75, "h": 30, "m": 10, "n": 40},
            timestamp=hour_ago,
        )
        repo.updatestamp = timezone.now()
        repo.save()
        self.assertTrue(repo.pk, "Repository should be saved and have a primary key.")

        # Set up the GraphQL query and run - requests only the `percentCovered` field
        query = """
        query CoverageAnalytics($owner: String!, $repo: String!) {
            owner(username: $owner) {
                repository(name: $repo) {
                    __typename
                    ... on Repository {
                        coverageAnalytics {
                            percentCovered
                        }
                    }
                    ... on ResolverError {
                        message
                    }
                }
            }
        }
        """
        variables = {"owner": "codecov-user", "repo": repo.name}
        resp = self.run_gql_query(query=query, variables=variables)

        # Assert the response matches the expected percentCovered value
        assert resp["owner"]["repository"]["coverageAnalytics"]["percentCovered"] == 75

    def test_coverage_analytics_no_commit(self) -> None:
        """Test case where no commits exist for coverage data"""

        # Create repo without commits
        repo = self.create_repository("empty-repo")
        repo.updatestamp = timezone.now()
        repo.save()
        self.assertTrue(repo.pk, "Repository should be saved and have a primary key.")

        # Set up the GraphQL query and run
        query = """
        query CoverageAnalytics($owner: String!, $repo: String!) {
            owner(username: $owner) {
                repository(name: $repo) {
                    __typename
                    ... on Repository {
                        coverageAnalytics {
                            percentCovered
                            commitSha
                            hits
                            misses
                            lines
                        }
                    }
                    ... on ResolverError {
                        message
                    }
                }
            }
        }
        """
        variables = {"owner": "codecov-user", "repo": repo.name}
        resp = self.run_gql_query(query=query, variables=variables)

        # Assert the response matches the expected structure with `None` values
        assert resp["owner"]["repository"]["coverageAnalytics"] == {
            "percentCovered": None,
            "commitSha": None,
            "hits": None,
            "misses": None,
            "lines": None,
        }

    def test_coverage_analytics_resolves_to_error(self) -> None:
        """Test case where the query resolves to an error (e.g., repository not found)"""

        # Set up and run the query to simulate a repository that doesn't exist
        query = """
        query CoverageAnalytics($owner: String!, $repo: String!) {
            owner(username: $owner) {
                repository(name: $repo) {
                    __typename
                    ... on Repository {  # Use an inline fragment for the Repository type
                        coverageAnalytics {
                            percentCovered
                        }
                    }
                    ... on ResolverError {
                        message
                    }
                }
            }
        }
        """
        variables = {"owner": "codecov-user", "repo": "non-existent-repo"}
        coverage_data = self.run_gql_query(query=query, variables=variables)

        # Assert that the response resolves to an error
        assert coverage_data["owner"]["repository"]["__typename"] == "NotFoundError"
        assert coverage_data["owner"]["repository"]["message"] == "Not found"

    @freeze_time("2022-01-02")
    def test_coverage_analytics_with_interval(self):
        """Test with interval argument to fetch coverage data in a specific time range"""

        mock_all_plans_and_tiers()
        # Create data to populate the timeseries graph
        repo = self.create_repository("test-repo")
        one_day_ago = timezone.make_aware(datetime.datetime(2022, 1, 1, 0, 0))
        self.create_commit(
            repository=repo,
            coverage_totals={"c": 65, "h": 20, "m": 5, "n": 25},
            timestamp=one_day_ago,
        )

        two_days_ago = timezone.make_aware(datetime.datetime(2022, 1, 2, 0, 0))
        self.create_commit(
            repository=repo,
            coverage_totals={"c": 75, "h": 30, "m": 10, "n": 40},
            timestamp=two_days_ago,
        )

        repo.updatestamp = timezone.now()
        repo.save()
        self.assertTrue(repo.pk, "Repository should be saved and have a primary key.")

        # Set up GraphQL query and run
        query = """
        query CoverageAnalytics($owner:String!, $repo: String!, $interval: MeasurementInterval!) {
            owner(username:$owner) {
                repository(name: $repo) {
                    __typename
                    ... on Repository {
                        name
                        coverageAnalytics {
                            measurements(interval: $interval) {
                                timestamp
                                avg
                                min
                                max
                            }
                        }
                    }
                    ... on ResolverError {
                        message
                    }
                }
            }
        }
        """
        variables = {
            "owner": "codecov-user",
            "repo": repo.name,
            "interval": "INTERVAL_1_DAY",
        }
        resp = self.run_gql_query(query=query, variables=variables)

        expected_response = {
            "__typename": "Repository",
            "name": repo.name,
            "coverageAnalytics": {
                "measurements": [
                    {
                        "avg": 65.0,
                        "max": 65.0,
                        "min": 65.0,
                        "timestamp": "2022-01-01T00:00:00+00:00",
                    },
                    {
                        "avg": 75.0,
                        "max": 75.0,
                        "min": 75.0,
                        "timestamp": "2022-01-02T00:00:00+00:00",
                    },
                ]
            },
        }

        assert resp["owner"]["repository"] == expected_response

    def test_resolve_coverage_analytics_result_type_for_coverage_analytics_props(
        self,
    ) -> None:
        """Test that the resolver returns 'CoverageAnalyticsProps' when passed a CoverageAnalyticsProps object"""
        repo = self.create_repository("test")
        coverage_analytics_props = CoverageAnalyticsProps(repository=repo)
        result_type = resolve_coverage_analytics_result_type(coverage_analytics_props)
        self.assertEqual(result_type, "CoverageAnalyticsProps")

    def test_resolve_coverage_analytics_result_type_for_not_found_error(self) -> None:
        """Test that the resolver returns 'NotFoundError' when passed a NotFoundError object"""
        result_type = resolve_coverage_analytics_result_type(NotFoundError())
        self.assertEqual(result_type, "NotFoundError")

    def test_resolve_coverage_analytics_result_type_for_unexpected_type(self) -> None:
        """Test that the resolver returns None when passed an object of an unexpected type"""
        unexpected_object = "unexpected_string"
        result_type = resolve_coverage_analytics_result_type(unexpected_object)
        self.assertIsNone(result_type)

    @override_settings(TIMESERIES_ENABLED=False)
    def test_repository_flags_metadata(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user)
        data = self.gql_request(
            self.query_builder
            % """
            flagsMeasurementsActive
            flagsMeasurementsBackfilled
            """,
            owner=user,
            variables={"name": repo.name},
        )
        assert (
            data["me"]["owner"]["repository"]["coverageAnalytics"][
                "flagsMeasurementsActive"
            ]
            == False
        )
        assert (
            data["me"]["owner"]["repository"]["coverageAnalytics"][
                "flagsMeasurementsBackfilled"
            ]
            == False
        )

    @override_settings(TIMESERIES_ENABLED=False)
    def test_repository_components_metadata(self):
        user = OwnerFactory()
        repo = RepositoryFactory(author=user)
        data = self.gql_request(
            self.query_builder
            % """
            componentsMeasurementsActive
            componentsMeasurementsBackfilled
            """,
            owner=user,
            variables={"name": repo.name},
        )
        assert (
            data["me"]["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsActive"
            ]
            == False
        )
        assert (
            data["me"]["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsBackfilled"
            ]
            == False
        )

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
            self.query_builder
            % """
            componentsCount
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert (
            data["me"]["owner"]["repository"]["coverageAnalytics"]["componentsCount"]
            == 2
        )

    def test_repository_no_components_count(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            yaml={"component_management": {}},
        )

        data = self.gql_request(
            self.query_builder
            % """
            componentsCount
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert (
            data["me"]["owner"]["repository"]["coverageAnalytics"]["componentsCount"]
            == 0
        )

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
            self.query_builder
            % """
            componentsYaml(termId: null) {
                id
                name
            }
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["coverageAnalytics"][
            "componentsYaml"
        ] == [
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
            self.query_builder
            % """
            componentsYaml(termId: "blah") {
                id
                name
            }
            """,
            owner=self.owner,
            variables={"name": repo.name},
        )

        assert data["me"]["owner"]["repository"]["coverageAnalytics"][
            "componentsYaml"
        ] == [
            {"id": "blah", "name": "blah_name"},
        ]
