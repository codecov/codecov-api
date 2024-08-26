from datetime import UTC, datetime

from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.models import TestInstance
from reports.tests.factories import TestFactory, TestInstanceFactory

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
        _ = TestInstanceFactory(
            test=self.test,
            outcome=TestInstance.Outcome.FAILURE.value,
            duration_seconds=1.1,
            repoid=self.repository.repoid,
            created_at=datetime.now(),
        )
        _ = TestInstanceFactory(
            test=self.test,
            outcome=TestInstance.Outcome.FAILURE.value,
            duration_seconds=1.3,
            repoid=self.repository.repoid,
            created_at=datetime.now(),
        )
        _ = TestInstanceFactory(
            test=self.test,
            outcome=TestInstance.Outcome.PASS.value,
            duration_seconds=1.5,
            repoid=self.repository.repoid,
            created_at=datetime.now(),
            commitid="456123",
        )

    def test_fetch_test_result_name(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
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
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResults"]["edges"][0]["node"][
            "name"
        ] == self.test.name.replace("\x1f", " ")

    def test_fetch_test_result_updated_at(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
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
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testResults"]["edges"][0]["node"][
                "updatedAt"
            ]
            == datetime.now(UTC).isoformat()
        )

    def test_fetch_test_result_commits_failed(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
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
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testResults"]["edges"][0]["node"][
                "commitsFailed"
            ]
            == 1
        )

    def test_fetch_test_result_failure_rate(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
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
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testResults"]["edges"][0]["node"][
                "failureRate"
            ]
            == 2 / 3
        )

    def test_fetch_test_result_avg_duration(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
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
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testResults"]["edges"][0]["node"][
                "avgDuration"
            ]
            == 1.3
        )
