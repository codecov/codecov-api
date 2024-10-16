from datetime import date, datetime, timedelta

from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory
from shared.django_apps.reports.tests.factories import FlakeFactory

from reports.tests.factories import DailyTestRollupFactory, TestFactory

from .helper import GraphQLTestHelper


@freeze_time(datetime.now().isoformat())
class TestResultTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="randomOwner")
        self.repository = RepositoryFactory(author=self.owner, branch="main")

        test = TestFactory(repository=self.repository)
        for i in range(0, 30):
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
                pass_count=1,
                flaky_fail_count=1 if i % 5 == 0 else 0,
                branch="main",
            )

        for i in range(30, 60):
            if i % 2 == 0:
                _ = FlakeFactory(
                    repository=self.repository,
                    test=test,
                    start_date=datetime.now() - timedelta(days=i + 1),
                    end_date=datetime.now() - timedelta(days=i),
                )
                _ = DailyTestRollupFactory(
                    test=test,
                    date=date.today() - timedelta(days=i),
                    avg_duration_seconds=float(i),
                    latest_run=datetime.now() - timedelta(days=i),
                    fail_count=3,
                    skip_count=1,
                    pass_count=1,
                    flaky_fail_count=3 if i % 5 == 0 else 0,
                    branch="main",
                )

    def test_fetch_test_result_total_runtime(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testAnalytics {
                                flakeAggregates {
                                    flakeRate
                                    flakeCount
                                    flakeRatePercentChange
                                    flakeCountPercentChange
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testAnalytics"]["flakeAggregates"] == {
            "flakeRate": 0.1,
            "flakeCount": 30,
            "flakeRatePercentChange": -33.33333,
            "flakeCountPercentChange": 100.0,
        }
