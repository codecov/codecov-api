from datetime import date, datetime, timedelta

from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.django_apps.reports.tests.factories import FlakeFactory

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
            _ = FlakeFactory(
                repository=self.repository,
                test=test,
                end_date=datetime.now() - timedelta(days=i),
            )
            _ = DailyTestRollupFactory(
                test=test,
                date=date.today() - timedelta(days=i),
                avg_duration_seconds=float(i),
                latest_run=datetime.now() - timedelta(days=i),
                fail_count=1,
                skip_count=1,
                pass_count=0,
                flaky_fail_count=1 if i % 5 == 0 else 0,
                branch="main",
            )

    def test_fetch_test_result_total_runtime(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            flakeAggregates {
                                flakeCount
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["flakeAggregates"]["flakeCount"] == 29

    def test_fetch_test_result_slowest_tests_runtime(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            flakeAggregates {
                                flakeRate
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["flakeAggregates"]["flakeRate"] == 5 / 29
