import datetime
from base64 import b64encode
from itertools import chain
from typing import Any

import polars as pl
import pytest
from django.conf import settings
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory
from shared.django_apps.core.tests.factories import RepositoryFactory
from shared.helpers.redis import get_redis_connection
from shared.storage import get_appropriate_storage_service
from shared.storage.exceptions import BucketAlreadyExistsError

from graphql_api.types.enums import (
    OrderingDirection,
    TestResultsOrderingParameter,
)
from graphql_api.types.enums.enum_types import MeasurementInterval
from graphql_api.types.test_analytics.test_analytics import (
    TestResultsRow,
    encode_cursor,
    generate_test_results,
    get_results,
)
from utils.test_results import dedup_table

from .helper import GraphQLTestHelper


class RowFactory:
    idx = 0

    def __call__(self, updated_at: datetime.datetime) -> dict[str, Any]:
        RowFactory.idx += 1
        return {
            "name": f"test{RowFactory.idx}",
            "testsuite": f"testsuite{RowFactory.idx}",
            "flags": [f"flag{RowFactory.idx}"],
            "failure_rate": 0.1,
            "flake_rate": 0.0,
            "updated_at": updated_at,
            "avg_duration": 100.0,
            "total_fail_count": 1,
            "total_flaky_fail_count": 1 if RowFactory.idx == 1 else 0,
            "total_pass_count": 1,
            "total_skip_count": 1,
            "commits_where_fail": 1,
            "last_duration": 100.0,
        }


def create_no_version_row(updated_at: datetime.datetime) -> list[dict[str, Any]]:
    return [
        {
            "timestamp_bin": datetime.datetime(
                updated_at.year, updated_at.month, updated_at.day
            ),
            "computed_name": f"test{i}",
            "flags": [f"flag{i}"],
            "updated_at": updated_at,
            "avg_duration": 100.0,
            "fail_count": i,
            "flaky_fail_count": 1 if i == 1 else 0,
            "pass_count": 1,
            "skip_count": 1,
            "failing_commits": 1,
            "last_duration": 100.0,
        }
        for i in range(5)
    ]


def create_v1_row(updated_at: datetime.datetime) -> list[dict[str, Any]]:
    return [
        {**row, "testsuite": f"testsuite{i}"}
        for i, row in enumerate(create_no_version_row(updated_at))
    ]


base_gql_query = """
    query {
        owner(username: "%s") {
            repository(name: "%s") {
                ... on Repository {
                    testAnalytics {
                        %s
                    }
                }
            }
        }
    }
"""


rows = [RowFactory()(datetime.datetime(2024, 1, 1 + i)) for i in range(5)]


rows_with_duplicate_names = [
    RowFactory()(datetime.datetime(2024, 1, 1 + i)) for i in range(5)
]
for i in range(0, len(rows_with_duplicate_names) - 1, 2):
    rows_with_duplicate_names[i]["name"] = rows_with_duplicate_names[i + 1]["name"]

no_version_rows = list(
    chain.from_iterable(
        create_no_version_row(datetime.datetime.now()) for i in range(5)
    )
)
v1_rows = list(
    chain.from_iterable(create_v1_row(datetime.datetime.now()) for i in range(5))
)


def dedup(rows: list[dict]) -> list[dict]:
    by_name = {}
    for row in rows:
        if row["name"] not in by_name:
            by_name[row["name"]] = []
        by_name[row["name"]].append(row)

    result = []
    for name, group in by_name.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        weights = [r["total_pass_count"] + r["total_fail_count"] for r in group]
        total_weight = sum(weights)

        merged = {
            "name": name,
            "testsuite": sorted({r["testsuite"] for r in group}),
            "flags": sorted({flag for r in group for flag in r["flags"]}),
            "failure_rate": sum(r["failure_rate"] * w for r, w in zip(group, weights))
            / total_weight,
            "flake_rate": sum(r["flake_rate"] * w for r, w in zip(group, weights))
            / total_weight,
            "updated_at": max(r["updated_at"] for r in group),
            "avg_duration": sum(r["avg_duration"] * w for r, w in zip(group, weights))
            / total_weight,
            "total_fail_count": sum(r["total_fail_count"] for r in group),
            "total_flaky_fail_count": sum(r["total_flaky_fail_count"] for r in group),
            "total_pass_count": sum(r["total_pass_count"] for r in group),
            "total_skip_count": sum(r["total_skip_count"] for r in group),
            "commits_where_fail": sum(r["commits_where_fail"] for r in group),
            "last_duration": max(r["last_duration"] for r in group),
        }
        result.append(merged)

    return sorted(result, key=lambda x: x["updated_at"], reverse=True)


def row_to_camel_case(row: dict) -> dict:
    return {
        "commitsFailed"
        if key == "commits_where_fail"
        else "".join(
            part.capitalize() if i > 0 else part.lower()
            for i, part in enumerate(key.split("_"))
        ): value.isoformat() if key == "updated_at" else value
        for key, value in row.items()
        if key not in ("testsuite", "flags")
    }


test_results_table = pl.DataFrame(rows)
test_results_table_with_duplicate_names = pl.DataFrame(rows_with_duplicate_names)
test_results_table_no_version = pl.DataFrame(no_version_rows)
test_results_table_v1 = pl.DataFrame(v1_rows)


def base64_encode_string(x: str) -> str:
    return b64encode(x.encode()).decode("utf-8")


def cursor(row: dict) -> str:
    return encode_cursor(TestResultsRow(**row), TestResultsOrderingParameter.UPDATED_AT)


@pytest.fixture(autouse=True)
def repository(mocker, transactional_db):
    owner = OwnerFactory(username="codecov-user")
    repo = RepositoryFactory(author=owner, name="testRepoName", active=True)

    return repo


@pytest.fixture
def store_in_redis(repository):
    redis = get_redis_connection()
    redis.set(
        f"test_results:{repository.repoid}:{repository.branch}:30",
        test_results_table.write_ipc(None).getvalue(),
    )

    yield

    redis.delete(
        f"test_results:{repository.repoid}:{repository.branch}:30",
    )


@pytest.fixture
def store_in_storage(repository):
    storage = get_appropriate_storage_service()

    try:
        storage.create_root_storage(settings.GCS_BUCKET_NAME)
    except BucketAlreadyExistsError:
        pass

    storage.write_file(
        settings.GCS_BUCKET_NAME,
        f"test_results/rollups/{repository.repoid}/{repository.branch}/30",
        test_results_table.write_ipc(None).getvalue(),
    )

    yield

    storage.delete_file(
        settings.GCS_BUCKET_NAME,
        f"test_results/rollups/{repository.repoid}/{repository.branch}/30",
    )


@pytest.fixture
def store_in_redis_with_duplicate_names(repository):
    redis = get_redis_connection()
    redis.set(
        f"test_results:{repository.repoid}:{repository.branch}:30",
        test_results_table_with_duplicate_names.write_ipc(None).getvalue(),
    )

    yield

    redis.delete(
        f"test_results:{repository.repoid}:{repository.branch}:30",
    )


class TestAnalyticsTestCase(
    GraphQLTestHelper,
):
    def test_get_test_results(
        self,
        transactional_db,
        repository,
        store_in_redis,
        store_in_storage,
    ):
        results = get_results(repository.repoid, repository.branch, 30)
        assert results is not None

        assert results.equals(dedup_table(test_results_table))

    def test_get_test_results_no_storage(self, transactional_db, repository):
        assert get_results(repository.repoid, repository.branch, 30) is None

    def test_get_test_results_no_redis(
        self, mocker, transactional_db, repository, store_in_storage
    ):
        m = mocker.patch("services.task.TaskService.cache_test_results_redis")
        results = get_results(repository.repoid, repository.branch, 30)
        assert results is not None
        assert results.equals(dedup_table(test_results_table))

        m.assert_called_once_with(repository.repoid, repository.branch)

    def test_test_results(self, transactional_db, repository, store_in_redis, snapshot):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results.total_count == 5
        assert test_results.page_info == {
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": cursor(rows[4]),
            "end_cursor": cursor(rows[0]),
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    def test_test_results_asc(
        self, transactional_db, repository, store_in_redis, snapshot
    ):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.ASC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results.total_count == 5
        assert test_results.page_info == {
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": cursor(rows[0]),
            "end_cursor": cursor(rows[4]),
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    @pytest.mark.parametrize(
        "first, after, last, before, has_next_page, has_previous_page, start_cursor, end_cursor, expected_rows",
        [
            pytest.param(
                1,
                None,
                None,
                None,
                True,
                False,
                cursor(rows[4]),
                cursor(rows[4]),
                [rows[4]],
                id="first_1",
            ),
            pytest.param(
                1,
                cursor(rows[4]),
                None,
                None,
                True,
                False,
                cursor(rows[3]),
                cursor(rows[3]),
                [rows[3]],
                id="first_1_after",
            ),
            pytest.param(
                1,
                cursor(rows[1]),
                None,
                None,
                False,
                False,
                cursor(rows[0]),
                cursor(rows[0]),
                [rows[0]],
                id="first_1_after_no_next",
            ),
            pytest.param(
                None,
                None,
                1,
                None,
                False,
                True,
                cursor(rows[0]),
                cursor(rows[0]),
                [rows[0]],
                id="last_1",
            ),
            pytest.param(
                None,
                None,
                1,
                cursor(rows[0]),
                False,
                True,
                cursor(rows[1]),
                cursor(rows[1]),
                [rows[1]],
                id="last_1_before",
            ),
            pytest.param(
                None,
                None,
                1,
                cursor(rows[3]),
                False,
                False,
                cursor(rows[4]),
                cursor(rows[4]),
                [rows[4]],
                id="last_1_before_no_previous",
            ),
        ],
    )
    def test_test_results_pagination(
        self,
        first,
        after,
        before,
        last,
        has_next_page,
        has_previous_page,
        expected_rows,
        start_cursor,
        end_cursor,
        repository,
        store_in_redis,
        snapshot,
    ):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
            first=first,
            after=after,
            before=before,
            last=last,
        )
        assert test_results.total_count == 5
        assert test_results.page_info == {
            "has_next_page": has_next_page,
            "has_previous_page": has_previous_page,
            "start_cursor": start_cursor,
            "end_cursor": end_cursor,
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    @pytest.mark.parametrize(
        "first, after, last, before, has_next_page, has_previous_page, start_cursor, end_cursor, expected_rows",
        [
            pytest.param(
                1,
                None,
                None,
                None,
                True,
                False,
                cursor(rows[0]),
                cursor(rows[0]),
                [rows[0]],
                id="first_1",
            ),
            pytest.param(
                1,
                cursor(rows[0]),
                None,
                None,
                True,
                False,
                cursor(rows[1]),
                cursor(rows[1]),
                [rows[1]],
                id="first_1_after",
            ),
            pytest.param(
                1,
                cursor(rows[3]),
                None,
                None,
                False,
                False,
                cursor(rows[4]),
                cursor(rows[4]),
                [rows[4]],
                id="first_1_after_no_next",
            ),
            pytest.param(
                None,
                None,
                1,
                None,
                False,
                True,
                cursor(rows[4]),
                cursor(rows[4]),
                [rows[4]],
                id="last_1",
            ),
            pytest.param(
                None,
                None,
                1,
                cursor(rows[4]),
                False,
                True,
                cursor(rows[3]),
                cursor(rows[3]),
                [rows[3]],
                id="last_1_before",
            ),
            pytest.param(
                None,
                None,
                1,
                cursor(rows[1]),
                False,
                False,
                cursor(rows[0]),
                cursor(rows[0]),
                [rows[0]],
                id="last_1_before_no_previous",
            ),
        ],
    )
    def test_test_results_pagination_asc(
        self,
        first,
        after,
        before,
        last,
        has_next_page,
        has_previous_page,
        expected_rows,
        start_cursor,
        end_cursor,
        repository,
        store_in_redis,
        snapshot,
    ):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.ASC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
            first=first,
            after=after,
            before=before,
            last=last,
        )
        assert test_results.total_count == 5
        assert test_results.page_info == {
            "has_next_page": has_next_page,
            "has_previous_page": has_previous_page,
            "start_cursor": start_cursor,
            "end_cursor": end_cursor,
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    def test_test_analytics_term_filter(self, repository, store_in_redis, snapshot):
        test_results = generate_test_results(
            repoid=repository.repoid,
            term=rows[0]["name"][2:],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results.total_count == 1
        assert test_results.page_info == {
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": cursor(rows[0]),
            "end_cursor": cursor(rows[0]),
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    def test_test_analytics_testsuite_filter(
        self, repository, store_in_redis, snapshot
    ):
        test_results = generate_test_results(
            repoid=repository.repoid,
            testsuites=[rows[0]["testsuite"]],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results.total_count == 1
        assert test_results.page_info == {
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": cursor(rows[0]),
            "end_cursor": cursor(rows[0]),
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    def test_test_analytics_flag_filter(self, repository, store_in_redis, snapshot):
        test_results = generate_test_results(
            repoid=repository.repoid,
            flags=[rows[0]["flags"][0]],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        # rows = dedup(rows)
        assert test_results.total_count == 1
        assert test_results.page_info == {
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": cursor(rows[0]),
            "end_cursor": cursor(rows[0]),
        }
        assert snapshot("json") == [
            row["node"].to_dict()
            for row in test_results.edges
            if isinstance(row["node"], TestResultsRow)
        ]

    def test_gql_query(self, repository, store_in_redis):
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            testResults(ordering: { parameter: UPDATED_AT, direction: DESC } ) {
                totalCount
                edges {
                    cursor
                    node {
                        name
                        failureRate
                        flakeRate
                        updatedAt
                        avgDuration
                        totalFailCount
                        totalFlakyFailCount
                        totalPassCount
                        totalSkipCount
                        commitsFailed
                        lastDuration
                    }
                }
            }
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["totalCount"]
            == 5
        )
        assert result["owner"]["repository"]["testAnalytics"]["testResults"][
            "edges"
        ] == [
            {
                "cursor": cursor(row),
                "node": row_to_camel_case(row),
            }
            for row in dedup(rows)
        ]

    def test_gql_query_with_duplicate_names(
        self, repository, store_in_redis_with_duplicate_names
    ):
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            testResults(ordering: { parameter: UPDATED_AT, direction: DESC } ) {
                totalCount
                edges {
                    cursor
                    node {
                        name
                        failureRate
                        flakeRate
                        updatedAt
                        avgDuration
                        totalFailCount
                        totalFlakyFailCount
                        totalPassCount
                        totalSkipCount
                        commitsFailed
                        lastDuration
                    }
                }
            }
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["totalCount"]
            == 3
        )
        assert result["owner"]["repository"]["testAnalytics"]["testResults"][
            "edges"
        ] == [
            {
                "cursor": cursor(row),
                "node": row_to_camel_case(row),
            }
            for row in dedup(rows_with_duplicate_names)
        ]

    def test_gql_query_aggregates(self, repository, store_in_redis):
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            testResultsAggregates {
                totalDuration
                slowestTestsDuration
                totalFails
                totalSkips
                totalSlowTests
            }
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        assert result["owner"]["repository"]["testAnalytics"][
            "testResultsAggregates"
        ] == {
            "totalDuration": 1000.0,
            "slowestTestsDuration": 200.0,
            "totalFails": 5,
            "totalSkips": 5,
            "totalSlowTests": 1,
        }

    def test_gql_query_flake_aggregates(self, repository, store_in_redis):
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            flakeAggregates {
                flakeRate
                flakeCount
            }
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        assert result["owner"]["repository"]["testAnalytics"]["flakeAggregates"] == {
            "flakeRate": 0.1,
            "flakeCount": 1,
        }

    def test_gql_query_test_suites(self, repository, store_in_redis):
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            testSuites
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        assert sorted(result["owner"]["repository"]["testAnalytics"]["testSuites"]) == [
            "testsuite1",
            "testsuite2",
            "testsuite3",
            "testsuite4",
            "testsuite5",
        ]

    def test_gql_query_test_suites_term(self, repository, store_in_redis):
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            testSuites(term: "testsuite1")
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        assert result["owner"]["repository"]["testAnalytics"]["testSuites"] == [
            "testsuite1",
        ]

    def test_gql_query_with_new_ta_v1(self, mocker, repository, snapshot):
        # set the feature flag
        mocker.patch("rollouts.READ_NEW_TA.check_value", return_value=True)

        # read file from samples
        storage = get_appropriate_storage_service()
        try:
            storage.create_root_storage(settings.GCS_BUCKET_NAME)
        except BucketAlreadyExistsError:
            pass
        storage.write_file(
            settings.GCS_BUCKET_NAME,
            f"test_analytics/branch_rollups/{repository.repoid}/{repository.branch}.arrow",
            test_results_table_v1.write_ipc(None).getvalue(),
            metadata={"version": "1"},
        )

        # run the GQL query
        query = base_gql_query % (
            repository.author.username,
            repository.name,
            """
            testResults(ordering: { parameter: FAILURE_RATE, direction: DESC } ) {
                totalCount
                edges {
                    cursor
                    node {
                        name
                        failureRate
                        flakeRate
                        updatedAt
                        avgDuration
                        totalFailCount
                        totalFlakyFailCount
                        totalPassCount
                        totalSkipCount
                        commitsFailed
                        lastDuration
                    }
                }
            }
            flakeAggregates {
                flakeRate
                flakeCount
            }
            testResultsAggregates {
                totalDuration
                slowestTestsDuration
                totalFails
                totalSkips
                totalSlowTests
            }
            testSuites
            """,
        )

        result = self.gql_request(query, owner=repository.author)

        # take a snapshot of the results
        assert (
            result["owner"]["repository"]["testAnalytics"]["testResults"]["totalCount"]
            == 5
        )
        assert snapshot("json") == [
            {
                **edge,
                "node": {k: v for k, v in edge["node"].items() if k != "updatedAt"},
            }
            for edge in result["owner"]["repository"]["testAnalytics"]["testResults"][
                "edges"
            ]
        ]

        assert sorted(result["owner"]["repository"]["testAnalytics"]["testSuites"]) == [
            "testsuite0",
            "testsuite1",
            "testsuite2",
            "testsuite3",
            "testsuite4",
        ]

        assert result["owner"]["repository"]["testAnalytics"]["flakeAggregates"] == {
            "flakeRate": (1 / 15),
            "flakeCount": 1,
        }

        assert result["owner"]["repository"]["testAnalytics"][
            "testResultsAggregates"
        ] == {
            "totalDuration": 7500.0,
            "slowestTestsDuration": 2500.0,
            "totalFails": 50,
            "totalSkips": 25,
            "totalSlowTests": 1,
        }
        storage.delete_file(
            settings.GCS_BUCKET_NAME,
            f"test_analytics/branch_rollups/{repository.repoid}/{repository.branch}.arrow",
        )
