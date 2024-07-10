import datetime as dt

from shared.django_apps.reports.models import TestInstance

from utils.test_results import aggregate_test_results


class TestSyncTestResults:
    def test_sync_test_results(
        self,
        transactional_db,
        repo_fixture,
        create_test_func,
        create_test_instance_func,
    ):
        test_1 = create_test_func()
        test_2 = create_test_func()

        create_test_instance_func(test_1, TestInstance.Outcome.FAILURE, "a", duration=1)
        create_test_instance_func(test_1, TestInstance.Outcome.PASS, "b", duration=2)
        create_test_instance_func(test_2, TestInstance.Outcome.SKIP, "c", duration=1)
        create_test_instance_func(test_2, TestInstance.Outcome.ERROR, "d", duration=1)
        create_test_instance_func(test_2, TestInstance.Outcome.PASS, "d", duration=1)
        create_test_instance_func(test_2, TestInstance.Outcome.FAILURE, "d", duration=1)
        create_test_instance_func(test_2, TestInstance.Outcome.FAILURE, "d", duration=1)
        create_test_instance_func(test_2, TestInstance.Outcome.ERROR, "e", duration=1)

        d = aggregate_test_results(repo_fixture.repoid)

        assert d[test_1.id]["failure_rate"] == 0.5
        assert d[test_1.id]["commits_where_fail"] == ["a"]
        assert d[test_1.id]["average_duration"] == 1.5

        assert d[test_2.id]["failure_rate"] == (4 / 5)
        assert d[test_2.id]["commits_where_fail"] == ["d", "e"]
        assert d[test_2.id]["average_duration"] == 1

    def test_filter_branch(
        self,
        transactional_db,
        repo_fixture,
        create_test_func,
        create_test_instance_func,
    ):
        test_1 = create_test_func()
        test_2 = create_test_func()

        create_test_instance_func(
            test_1,
            TestInstance.Outcome.FAILURE,
            "a",
            duration=1,
            branch="main",
        )
        create_test_instance_func(
            test_1,
            TestInstance.Outcome.PASS,
            "b",
            duration=2,
            branch="feat",
        )
        create_test_instance_func(
            test_2,
            TestInstance.Outcome.SKIP,
            "c",
            duration=1,
            branch="main",
        )
        create_test_instance_func(
            test_2,
            TestInstance.Outcome.ERROR,
            "d",
            duration=1,
            branch="feat",
        )
        create_test_instance_func(
            test_2,
            TestInstance.Outcome.PASS,
            "d",
            duration=1,
            branch="main",
        )
        create_test_instance_func(
            test_2,
            TestInstance.Outcome.FAILURE,
            "d",
            duration=1,
            branch="feat",
        )
        create_test_instance_func(
            test_2,
            TestInstance.Outcome.FAILURE,
            "d",
            duration=1,
            branch="main",
        )
        create_test_instance_func(
            test_2,
            TestInstance.Outcome.ERROR,
            "e",
            duration=1,
            branch="feat",
        )

        d = aggregate_test_results(repo_fixture.repoid, branch="feat")

        assert d[test_1.id]["failure_rate"] == 0
        assert d[test_1.id]["commits_where_fail"] is None
        assert d[test_1.id]["average_duration"] == 2

        assert d[test_2.id]["failure_rate"] == 1.0
        assert d[test_2.id]["commits_where_fail"] == ["d", "e"]
        assert d[test_2.id]["average_duration"] == 1

    def test_filter_time(
        self,
        transactional_db,
        repo_fixture,
        create_test_func,
        create_test_instance_func,
    ):
        test_1 = create_test_func()

        create_test_instance_func(
            test_1,
            TestInstance.Outcome.FAILURE,
            "a",
            duration=1,
            branch="main",
        )
        create_test_instance_func(
            test_1,
            TestInstance.Outcome.FAILURE,
            "b",
            duration=2,
            branch="feat",
            created_at=dt.datetime.now() - dt.timedelta(days=30),
        )

        d = aggregate_test_results(repo_fixture.repoid, branch="feat")

        assert d[test_1.id]["failure_rate"] == 1.0
        assert d[test_1.id]["commits_where_fail"] == ["b"]
        assert d[test_1.id]["average_duration"] == 2
