import datetime
from base64 import b64encode
from typing import Any

import polars as pl
import pytest
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory
from shared.django_apps.core.tests.factories import RepositoryFactory
from shared.storage.exceptions import BucketAlreadyExistsError
from shared.storage.memory import MemoryStorageService

from graphql_api.types.enums import (
    OrderingDirection,
    TestResultsOrderingParameter,
)
from graphql_api.types.enums.enum_types import MeasurementInterval
from graphql_api.types.test_analytics.test_analytics import (
    TestResultConnection,
    TestResultsRow,
    encode_cursor,
    generate_test_results,
    get_results,
)
from services.redis_configuration import get_redis_connection

from .helper import GraphQLTestHelper


class RowFactory:
    idx = 0

    def __call__(self, updated_at: datetime.datetime) -> dict[str, Any]:
        RowFactory.idx += 1
        return {
            "name": f"test{RowFactory.idx}",
            "testsuite": f"testsuite{RowFactory.idx}",
            "flags": [f"flag{RowFactory.idx}"],
            "test_id": f"test_id{RowFactory.idx}",
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


@pytest.fixture
def mock_storage(mocker):
    m = mocker.patch("utils.test_results.StorageService")
    storage_server = MemoryStorageService({})
    m.return_value = storage_server
    yield storage_server


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


def row_to_camel_case(row: dict) -> dict:
    return {
        "commitsFailed"
        if key == "commits_where_fail"
        else "".join(
            part.capitalize() if i > 0 else part.lower()
            for i, part in enumerate(key.split("_"))
        ): value.isoformat() if key == "updated_at" else value
        for key, value in row.items()
        if key not in ("test_id", "testsuite", "flags")
    }


test_results_table = pl.DataFrame(rows)


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
def store_in_storage(repository, mock_storage):
    try:
        mock_storage.create_root_storage("codecov")
    except BucketAlreadyExistsError:
        pass

    mock_storage.write_file(
        "codecov",
        f"test_results/rollups/{repository.repoid}/{repository.branch}/30",
        test_results_table.write_ipc(None).getvalue(),
    )

    yield

    mock_storage.delete_file(
        "codecov",
        f"test_results/rollups/{repository.repoid}/{repository.branch}/30",
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
        mock_storage,
    ):
        results = get_results(repository.repoid, repository.branch, 30)
        assert results is not None
        assert results.equals(test_results_table)

    def test_get_test_results_no_storage(
        self, transactional_db, repository, mock_storage
    ):
        assert get_results(repository.repoid, repository.branch, 30) is None

    def test_get_test_results_no_redis(
        self, mocker, transactional_db, repository, store_in_storage, mock_storage
    ):
        m = mocker.patch("services.task.TaskService.cache_test_results_redis")
        results = get_results(repository.repoid, repository.branch, 30)
        assert results is not None
        assert results.equals(test_results_table)

        m.assert_called_once_with(repository.repoid, repository.branch)

    def test_test_results(
        self, transactional_db, repository, store_in_redis, mock_storage
    ):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=5,
            edges=[
                {
                    "cursor": cursor(row),
                    "node": TestResultsRow(**row),
                }
                for row in reversed(rows)
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": cursor(rows[4]),
                "end_cursor": cursor(rows[0]),
            },
        )

    def test_test_results_asc(
        self, transactional_db, repository, store_in_redis, mock_storage
    ):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.ASC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=5,
            edges=[
                {
                    "cursor": cursor(row),
                    "node": TestResultsRow(**row),
                }
                for row in rows
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": cursor(rows[0]),
                "end_cursor": cursor(rows[4]),
            },
        )

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
        mock_storage,
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
        assert test_results == TestResultConnection(
            total_count=5,
            edges=[
                {
                    "cursor": cursor(row),
                    "node": TestResultsRow(**row),
                }
                for row in expected_rows
            ],
            page_info={
                "has_next_page": has_next_page,
                "has_previous_page": has_previous_page,
                "start_cursor": start_cursor,
                "end_cursor": end_cursor,
            },
        )

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
        mock_storage,
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
        assert test_results == TestResultConnection(
            total_count=5,
            edges=[
                {
                    "cursor": cursor(row),
                    "node": TestResultsRow(**row),
                }
                for row in expected_rows
            ],
            page_info={
                "has_next_page": has_next_page,
                "has_previous_page": has_previous_page,
                "start_cursor": start_cursor,
                "end_cursor": end_cursor,
            },
        )

    def test_test_analytics_term_filter(self, repository, store_in_redis, mock_storage):
        test_results = generate_test_results(
            repoid=repository.repoid,
            term=rows[0]["name"],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=1,
            edges=[
                {
                    "cursor": cursor(rows[0]),
                    "node": TestResultsRow(**rows[0]),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": cursor(rows[0]),
                "end_cursor": cursor(rows[0]),
            },
        )

    def test_test_analytics_testsuite_filter(self, repository, store_in_redis):
        test_results = generate_test_results(
            repoid=repository.repoid,
            testsuites=[rows[0]["testsuite"]],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=1,
            edges=[
                {
                    "cursor": cursor(rows[0]),
                    "node": TestResultsRow(**rows[0]),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": cursor(rows[0]),
                "end_cursor": cursor(rows[0]),
            },
        )

    def test_test_analytics_flag_filter(self, repository, store_in_redis, mock_storage):
        test_results = generate_test_results(
            repoid=repository.repoid,
            flags=[rows[0]["flags"][0]],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=1,
            edges=[
                {
                    "cursor": cursor(rows[0]),
                    "node": TestResultsRow(**rows[0]),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": cursor(rows[0]),
                "end_cursor": cursor(rows[0]),
            },
        )

    def test_gql_query(self, repository, store_in_redis, mock_storage):
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
            for row in reversed(rows)
        ]

    def test_gql_query_aggregates(self, repository, store_in_redis, mock_storage):
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

    def test_gql_query_flake_aggregates(self, repository, store_in_redis, mock_storage):
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
