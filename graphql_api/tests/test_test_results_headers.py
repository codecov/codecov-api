from datetime import date, datetime, timedelta

from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.tests.factories import DailyTestRollupFactory, TestFactory

from .helper import GraphQLTestHelper


@freeze_time(datetime.now().isoformat())
class TestResultTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="randomOwner")
        self.repository = RepositoryFactory(author=self.owner, branch="main")

        for i in range(1, 31):
            test = TestFactory(repository=self.repository)

            _ = DailyTestRollupFactory(
                test=test,
                date=date.today() - timedelta(days=i),
                avg_duration_seconds=float(i),
                latest_run=datetime.now() - timedelta(days=i),
                fail_count=1,
                skip_count=1,
                pass_count=0,
                branch="main",
            )

    def test_fetch_test_result_total_runtime(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResultsHeaders {
                                totalRunTime
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testResultsHeaders"]["totalRunTime"] == 435.0
        )

    def test_fetch_test_result_slowest_tests_runtime(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResultsHeaders {
                                slowestTestsRunTime
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["repository"]["testResultsHeaders"]["slowestTestsRunTime"]
            == 29.0
        )

    def test_fetch_test_result_failed_tests(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResultsHeaders {
                                totalFails
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResultsHeaders"]["totalFails"] == 29

    def test_fetch_test_result_skipped_tests(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResultsHeaders {
                                totalSkips
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResultsHeaders"]["totalSkips"] == 29
