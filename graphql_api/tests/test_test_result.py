from datetime import UTC, date, datetime, timedelta

from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

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
                                            updatedAt
                                            commitsFailed
                                            failureRate
                                            lastDuration
                                            avgDuration
                                            totalFailCount
                                            totalSkipCount
                                            totalPassCount
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
        assert result["owner"]["repository"]["testAnalytics"]["testResults"]["edges"][
            0
        ]["node"] == {
            "name": self.test.computed_name,
            "updatedAt": datetime.now(UTC).isoformat(),
            "commitsFailed": 3,
            "failureRate": 0.75,
            "lastDuration": 1.0,
            "avgDuration": (5.6 / 3),
            "totalFailCount": 9,
            "totalSkipCount": 6,
            "totalPassCount": 3,
            "totalFlakyFailCount": 2,
        }
