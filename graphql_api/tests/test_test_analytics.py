import datetime

from django.test import TransactionTestCase
from shared.django_apps.reports.tests.factories import FlakeFactory

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    RepositoryFactory,
)
from reports.tests.factories import (
    DailyTestRollupFactory,
    RepositoryFlagFactory,
    TestFactory,
    TestFlagBridgeFactory,
)

from .helper import GraphQLTestHelper


class TestAnalyticsTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self) -> None:
        self.owner = OwnerFactory(username="codecov-user")
        self.repo = RepositoryFactory(
            author=self.owner, name="testRepoName", active=True
        )

    query_builder = """
    query TestAnalytics($name: String!){
        me {
            owner {
                repository(name: $name) {
                    __typename
                    ... on Repository {
                        testAnalytics {
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

    def fetch_test_analytics(self, name, fields=None):
        data = self.gql_request(
            self.query_builder % fields,
            owner=self.owner,
            variables={"name": name},
        )
        return data["me"]["owner"]["repository"]["testAnalytics"]

    def test_repository_test_analytics_typename(self):
        response = self.gql_request(
            """
            query($owner: String!, $repo: String!) {
              owner(username: $owner) {
                repository(name: $repo) {
                  ... on Repository {
                    testAnalytics {
                      __typename
                    }
                  }
                  ... on ResolverError {
                    message
                  }
                }
              }
            }
            """,
            owner=self.owner,
            variables={"owner": self.owner.username, "repo": self.repo.name},
        )

        assert (
            response["owner"]["repository"]["testAnalytics"]["__typename"]
            == "TestAnalytics"
        )

    def test_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)

        _ = DailyTestRollupFactory(test=test)
        res = self.fetch_test_analytics(
            repo.name, """testResults { edges { node { name } } }"""
        )

        assert res["testResults"] == {"edges": [{"node": {"name": test.name}}]}

    def test_test_results_no_tests(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        res = self.fetch_test_analytics(
            repo.name, """testResults { edges { node { name } } }"""
        )
        assert res["testResults"] == {"edges": []}

    def test_branch_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="feature",
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { branch: "main"}) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test.name}}]}

    def test_flaky_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test2 = TestFactory(repository=repo)
        _ = FlakeFactory(test=test2, repository=repo, end_date=None)
        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="feature",
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { parameter: FLAKY_TESTS }) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test2.name}}]}

    def test_failed_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            fail_count=0,
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="feature",
            fail_count=1000,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { parameter: FAILED_TESTS }) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test2.name}}]}

    def test_skipped_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            skip_count=10,
            pass_count=10,
            fail_count=10,
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="feature",
            skip_count=1000,
            pass_count=0,
            fail_count=0,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { parameter: SKIPPED_TESTS }) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test2.name}}]}

    def test_slowest_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            avg_duration_seconds=0.1,
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            avg_duration_seconds=20.0,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { parameter: SLOWEST_TESTS }) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test2.name}}]}

    def test_flags_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test2 = TestFactory(repository=repo)

        repo_flag = RepositoryFlagFactory(repository=repo, flag_name="hello_world")

        _ = TestFlagBridgeFactory(flag=repo_flag, test=test)
        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            avg_duration_seconds=0.1,
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            avg_duration_seconds=20.0,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { flags: ["hello_world"] }) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test.name}}]}

    def test_testsuites_filter_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo, testsuite="hello")
        test2 = TestFactory(repository=repo, testsuite="world")

        _ = DailyTestRollupFactory(
            test=test,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            avg_duration_seconds=0.1,
        )
        _ = DailyTestRollupFactory(
            test=test2,
            created_at=datetime.datetime.now(),
            repoid=repo.repoid,
            branch="main",
            avg_duration_seconds=20.0,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(filters: { test_suites: ["hello"] }) { edges { node { name } } }""",
        )
        assert res["testResults"] == {"edges": [{"node": {"name": test.name}}]}

    def test_commits_failed_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            commits_where_fail=["1"],
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            commits_where_fail=["2"],
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            commits_where_fail=["3"],
        )
        res = self.fetch_test_analytics(
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
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            commits_where_fail=["1"],
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            commits_where_fail=["2"],
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            commits_where_fail=["3"],
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: COMMITS_WHERE_FAIL, direction: DESC }) { edges { node { name commitsFailed } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "commitsFailed": 2}},
                {"node": {"name": test_2.name, "commitsFailed": 1}},
            ]
        }

    def test_last_duration_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            last_duration_seconds=1,
            latest_run=datetime.datetime.now() - datetime.timedelta(days=1),
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            last_duration_seconds=2,
            latest_run=datetime.datetime.now(),
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            last_duration_seconds=3,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: LAST_DURATION, direction: ASC }) { edges { node { name lastDuration } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "lastDuration": 2.0}},
                {"node": {"name": test_2.name, "lastDuration": 3.0}},
            ]
        }

    def test_desc_last_duration_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            last_duration_seconds=1,
            latest_run=datetime.datetime.now() - datetime.timedelta(days=1),
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            last_duration_seconds=2,
            latest_run=datetime.datetime.now(),
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            last_duration_seconds=3,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: LAST_DURATION, direction: DESC }) { edges { node { name lastDuration } } }""",
        )
        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test_2.name, "lastDuration": 3}},
                {"node": {"name": test.name, "lastDuration": 2}},
            ]
        }

    def test_avg_duration_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            avg_duration_seconds=1,
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            avg_duration_seconds=2,
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            avg_duration_seconds=3,
        )
        res = self.fetch_test_analytics(
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
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            avg_duration_seconds=1,
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            avg_duration_seconds=2,
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            avg_duration_seconds=3,
        )
        res = self.fetch_test_analytics(
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
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            pass_count=1,
            fail_count=1,
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=3,
            fail_count=0,
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=2,
            fail_count=3,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: FAILURE_RATE, direction: ASC }) { edges { node { name failureRate } } }""",
        )

        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "failureRate": 0.2}},
                {"node": {"name": test_2.name, "failureRate": 0.6}},
            ]
        }

    def test_desc_failure_rate_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            pass_count=1,
            fail_count=1,
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=3,
            fail_count=0,
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=2,
            fail_count=3,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: FAILURE_RATE, direction: DESC }) { edges { node { name failureRate } } }""",
        )

        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test_2.name, "failureRate": 0.6}},
                {"node": {"name": test.name, "failureRate": 0.2}},
            ]
        }

    def test_flake_rate_filtering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            pass_count=1,
            fail_count=1,
            flaky_fail_count=1,
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=3,
            fail_count=0,
            flaky_fail_count=0,
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=2,
            fail_count=3,
            flaky_fail_count=1,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: FAILURE_RATE, direction: ASC }) { edges { node { name flakeRate } } }""",
        )

        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test.name, "flakeRate": 0.2}},
                {"node": {"name": test_2.name, "flakeRate": 0.2}},
            ]
        }

    def test_desc_flake_rate_ordering_on_test_results(self) -> None:
        repo = RepositoryFactory(author=self.owner, active=True, private=True)
        test = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today() - datetime.timedelta(days=1),
            repoid=repo.repoid,
            pass_count=1,
            fail_count=1,
            flaky_fail_count=1,
        )
        _ = DailyTestRollupFactory(
            test=test,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=3,
            fail_count=0,
            flaky_fail_count=0,
        )
        test_2 = TestFactory(repository=repo)
        _ = DailyTestRollupFactory(
            test=test_2,
            date=datetime.date.today(),
            repoid=repo.repoid,
            pass_count=2,
            fail_count=3,
            flaky_fail_count=1,
        )
        res = self.fetch_test_analytics(
            repo.name,
            """testResults(ordering: { parameter: FAILURE_RATE, direction: DESC }) { edges { node { name flakeRate } } }""",
        )

        assert res["testResults"] == {
            "edges": [
                {"node": {"name": test_2.name, "flakeRate": 0.2}},
                {"node": {"name": test.name, "flakeRate": 0.2}},
            ]
        }

    def test_test_results_aggregates(self) -> None:
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, branch="main"
        )

        for i in range(0, 30):
            test = TestFactory(repository=repo)
            _ = DailyTestRollupFactory(
                test=test,
                repoid=repo.repoid,
                branch="main",
                fail_count=1 if i % 3 == 0 else 0,
                skip_count=1 if i % 6 == 0 else 0,
                pass_count=1,
                avg_duration_seconds=float(i),
                last_duration_seconds=float(i),
                date=datetime.date.today() - datetime.timedelta(days=i),
            )

        for i in range(30, 60):
            test = TestFactory(repository=repo)
            _ = DailyTestRollupFactory(
                test=test,
                repoid=repo.repoid,
                branch="main",
                fail_count=1 if i % 6 == 0 else 0,
                skip_count=1 if i % 3 == 0 else 0,
                pass_count=1,
                avg_duration_seconds=float(i),
                last_duration_seconds=float(i),
                date=datetime.date.today() - datetime.timedelta(days=(i)),
            )
        res = self.fetch_test_analytics(
            repo.name,
            """testResultsAggregates { totalDuration, slowestTestsDuration, totalFails, totalSkips, totalDurationPercentChange, slowestTestsDurationPercentChange, totalFailsPercentChange, totalSkipsPercentChange }""",
        )
        assert res["testResultsAggregates"] == {
            "totalDuration": 570.0,
            "slowestTestsDuration": 29.0,
            "totalFails": 10,
            "totalSkips": 5,
            "totalDurationPercentChange": -63.10679611650486,
            "slowestTestsDurationPercentChange": -50.847457627118644,
            "totalFailsPercentChange": 100.0,
            "totalSkipsPercentChange": -50.0,
        }

    def test_test_results_aggregates_no_history(self) -> None:
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, branch="main"
        )

        for i in range(0, 30):
            test = TestFactory(repository=repo)
            _ = DailyTestRollupFactory(
                test=test,
                repoid=repo.repoid,
                branch="main",
                fail_count=1 if i % 3 == 0 else 0,
                skip_count=1 if i % 6 == 0 else 0,
                pass_count=1,
                avg_duration_seconds=float(i),
                last_duration_seconds=float(i),
                date=datetime.date.today() - datetime.timedelta(days=i),
            )

        res = self.fetch_test_analytics(
            repo.name,
            """testResultsAggregates { totalDuration, slowestTestsDuration, totalFails, totalSkips, totalDurationPercentChange, slowestTestsDurationPercentChange, totalFailsPercentChange, totalSkipsPercentChange }""",
        )

        assert res["testResultsAggregates"] == {
            "totalDuration": 570.0,
            "slowestTestsDuration": 29.0,
            "totalFails": 10,
            "totalSkips": 5,
            "totalDurationPercentChange": None,
            "slowestTestsDurationPercentChange": None,
            "totalFailsPercentChange": None,
            "totalSkipsPercentChange": None,
        }

    def test_flake_aggregates(self) -> None:
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, branch="main"
        )

        test = TestFactory(repository=repo)

        _ = FlakeFactory(
            repository=repo,
            test=test,
            start_date=datetime.datetime.now() - datetime.timedelta(days=1),
            end_date=None,
        )
        _ = FlakeFactory(
            repository=repo,
            test=test,
            start_date=datetime.datetime.now() - datetime.timedelta(days=90),
            end_date=None,
        )
        _ = FlakeFactory(
            repository=repo,
            test=test,
            start_date=datetime.datetime.now() - datetime.timedelta(days=70),
            end_date=datetime.datetime.now() - datetime.timedelta(days=30),
        )
        _ = FlakeFactory(
            repository=repo,
            test=test,
            start_date=datetime.datetime.now() - datetime.timedelta(days=80),
            end_date=datetime.datetime.now() - datetime.timedelta(days=59),
        )
        _ = FlakeFactory(
            repository=repo,
            test=test,
            start_date=datetime.datetime.now() - datetime.timedelta(days=70),
            end_date=datetime.datetime.now() - datetime.timedelta(days=61),
        )

        for i in range(0, 30):
            _ = DailyTestRollupFactory(
                test=test,
                repoid=repo.repoid,
                branch="main",
                flaky_fail_count=1 if i % 6 == 0 else 0,
                fail_count=1 if i % 3 == 0 else 0,
                skip_count=0,
                pass_count=1,
                avg_duration_seconds=float(i),
                last_duration_seconds=float(i),
                date=datetime.date.today() - datetime.timedelta(days=i),
            )
        for i in range(30, 60):
            _ = DailyTestRollupFactory(
                test=test,
                repoid=repo.repoid,
                branch="main",
                flaky_fail_count=5 if i % 3 == 0 else 0,
                fail_count=5 if i % 3 == 0 else 0,
                skip_count=0,
                pass_count=5,
                avg_duration_seconds=float(i),
                last_duration_seconds=float(i),
                date=datetime.date.today() - datetime.timedelta(days=i),
            )

        res = self.fetch_test_analytics(
            repo.name,
            """flakeAggregates { flakeCount, flakeRate, flakeCountPercentChange, flakeRatePercentChange }""",
        )

        assert res["flakeAggregates"] == {
            "flakeCount": 2,
            "flakeRate": 0.125,
            "flakeCountPercentChange": -50.0,
            "flakeRatePercentChange": -50.0,
        }

    def test_flake_aggregates_no_history(self) -> None:
        repo = RepositoryFactory(
            author=self.owner, active=True, private=True, branch="main"
        )

        test = TestFactory(repository=repo)
        _ = FlakeFactory(
            repository=repo,
            test=test,
            start_date=datetime.datetime.now() - datetime.timedelta(days=1),
            end_date=None,
        )

        for i in range(0, 30):
            _ = DailyTestRollupFactory(
                test=test,
                repoid=repo.repoid,
                branch="main",
                flaky_fail_count=1 if i % 3 == 0 else 0,
                fail_count=1 if i % 3 == 0 else 0,
                skip_count=0,
                pass_count=1,
                avg_duration_seconds=float(i),
                last_duration_seconds=float(i),
                date=datetime.date.today() - datetime.timedelta(days=i),
            )

        res = self.fetch_test_analytics(
            repo.name,
            """flakeAggregates { flakeCount, flakeRate, flakeCountPercentChange, flakeRatePercentChange }""",
        )

        assert res["flakeAggregates"] == {
            "flakeCount": 1,
            "flakeRate": 0.25,
            "flakeCountPercentChange": None,
            "flakeRatePercentChange": None,
        }
