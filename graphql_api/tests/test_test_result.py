from datetime import UTC, date, datetime, timedelta

from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.tests.factories import (
    DailyTestRollupFactory,
    TestFactory,
)

from .helper import GraphQLTestHelper


@freeze_time(datetime.now().isoformat())
class TestResultTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="randomOwner")
        self.repository = RepositoryFactory(
            author=self.owner,
        )
        self.test = TestFactory(
            name="Test\x1fName",
            repository=self.repository,
        )

        _ = DailyTestRollupFactory(
            test=self.test,
            commits_where_fail=["123"],
            date=date.today() - timedelta(days=2),
            avg_duration_seconds=0.6,
            latest_run=datetime.now() - timedelta(days=2),
            flaky_fail_count=0,
        )
        _ = DailyTestRollupFactory(
            test=self.test,
            commits_where_fail=["123", "456"],
            date=datetime.now() - timedelta(days=1),
            avg_duration_seconds=2,
            latest_run=datetime.now() - timedelta(days=1),
            flaky_fail_count=1,
        )
        _ = DailyTestRollupFactory(
            test=self.test,
            commits_where_fail=["123", "789"],
            date=date.today(),
            last_duration_seconds=5.0,
            avg_duration_seconds=3,
            latest_run=datetime.now(),
            flaky_fail_count=1,
        )

    def test_fetch_test_result_name(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][
            0
        ]["node"]["name"] == self.test.name.replace("\x1f", " ")

    def test_fetch_test_result_name_with_computed_name(self) -> None:
        self.test.computed_name = "Computed Name"
        self.test.save()

        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["name"]
            == self.test.computed_name
        )

    def test_fetch_test_result_updated_at(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            updatedAt
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["updatedAt"]
            == datetime.now(UTC).isoformat()
        )

    def test_fetch_test_result_commits_failed(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            commitsFailed
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["commitsFailed"]
            == 3
        )

    def test_fetch_test_result_failure_rate(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            failureRate
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["failureRate"]
            == 0.75
        )

    def test_fetch_test_result_last_duration(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            lastDuration
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["lastDuration"]
            == 0.0
        )

    def test_fetch_test_result_avg_duration(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            avgDuration
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][
            0
        ]["node"]["avgDuration"] == (5.6 / 3)

    def test_fetch_test_result_total_fail_count(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            totalFailCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["totalFailCount"]
            == 9
        )

    def test_fetch_test_result_total_skip_count(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            totalSkipCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["totalSkipCount"]
            == 6
        )

    def test_fetch_test_result_total_pass_count(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            totalPassCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["totalPassCount"]
            == 3
        )

    def test_fetch_test_result_total_flaky_fail_count(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                testResults {
                                    edges {
                                        node {
                                            totalFlakyFailCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][0][
                "node"
            ]["totalFlakyFailCount"]
            == 2
        )
