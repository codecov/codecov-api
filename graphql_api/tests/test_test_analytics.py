import datetime
from base64 import b64encode

import polars as pl
import pytest
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory
from shared.django_apps.core.tests.factories import RepositoryFactory
from shared.storage.exceptions import BucketAlreadyExistsError

from graphql_api.types.enums import (
    OrderingDirection,
    TestResultsOrderingParameter,
)
from graphql_api.types.enums.enum_types import MeasurementInterval
from graphql_api.types.test_analytics.test_analytics import (
    TestResultConnection,
    TestResultsRow,
    generate_test_results,
    get_results,
)
from services.redis_configuration import get_redis_connection
from services.storage import StorageService

from .helper import GraphQLTestHelper

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

row_1 = {
    "name": "test1",
    "testsuite": "testsuite1",
    "flags": ["flag1"],
    "test_id": "test_id1",
    "failure_rate": 0.1,
    "flake_rate": 0.0,
    "updated_at": datetime.datetime(2024, 1, 1),
    "avg_duration": 100.0,
    "total_fail_count": 1,
    "total_flaky_fail_count": 0,
    "total_pass_count": 1,
    "total_skip_count": 1,
    "commits_where_fail": 1,
    "last_duration": 100.0,
}


row_2 = {
    "name": "test2",
    "testsuite": "testsuite2",
    "flags": ["flag2"],
    "test_id": "test_id2",
    "failure_rate": 0.2,
    "flake_rate": 0.3,
    "updated_at": datetime.datetime(2024, 1, 2),
    "avg_duration": 200.0,
    "total_fail_count": 2,
    "total_flaky_fail_count": 2,
    "total_pass_count": 2,
    "total_skip_count": 2,
    "commits_where_fail": 2,
    "last_duration": 200.0,
}


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


test_results_table = pl.DataFrame(
    [row_1, row_2],
)


def base64_encode_string(x: str) -> str:
    return b64encode(x.encode()).decode("utf-8")


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
    storage = StorageService()
    try:
        storage.create_root_storage("codecov")
    except BucketAlreadyExistsError:
        pass

    storage.write_file(
        "codecov",
        f"test_results/rollups/{repository.repoid}/{repository.branch}/30",
        test_results_table.write_ipc(None).getvalue(),
    )

    yield

    storage.delete_file(
        "codecov",
        f"test_results/rollups/{repository.repoid}/{repository.branch}/30",
    )


class TestAnalyticsTestCase(
    GraphQLTestHelper,
):
    def test_get_test_results(
        self, transactional_db, repository, store_in_redis, store_in_storage
    ):
        results = get_results(repository.repoid, repository.branch, 30)
        assert results is not None
        assert results.equals(test_results_table)

    def test_get_test_results_no_storage(self, transactional_db, repository):
        with pytest.raises(FileNotFoundError):
            get_results(repository.repoid, repository.branch, 30)

    def test_get_test_results_no_redis(
        self, transactional_db, repository, store_in_storage
    ):
        results = get_results(repository.repoid, repository.branch, 30)
        assert results is not None
        assert results.equals(test_results_table)

    def test_test_results(self, transactional_db, repository, store_in_redis):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=2,
            edges=[
                {
                    "cursor": "MjAyNC0wMS0wMiAwMDowMDowMHx0ZXN0Mg==",
                    "node": TestResultsRow(**row_2),
                },
                {
                    "cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                    "node": TestResultsRow(**row_1),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": "MjAyNC0wMS0wMiAwMDowMDowMHx0ZXN0Mg==",
                "end_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
            },
        )

    def test_test_results_asc(self, transactional_db, repository, store_in_redis):
        test_results = generate_test_results(
            repoid=repository.repoid,
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.ASC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=2,
            edges=[
                {
                    "cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                    "node": TestResultsRow(**row_1),
                },
                {
                    "cursor": "MjAyNC0wMS0wMiAwMDowMDowMHx0ZXN0Mg==",
                    "node": TestResultsRow(**row_2),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                "end_cursor": "MjAyNC0wMS0wMiAwMDowMDowMHx0ZXN0Mg==",
            },
        )

    @pytest.mark.parametrize(
        "first, after, before, last, has_next_page, has_previous_page, rows",
        [
            (1, None, None, None, True, False, [row_2]),
            (
                1,
                base64_encode_string(f"{row_2['updated_at']}|{row_2['name']}"),
                None,
                None,
                False,
                False,
                [row_1],
            ),
            (None, None, None, 1, False, True, [row_1]),
            (
                None,
                None,
                base64_encode_string(f"{row_1['updated_at']}|{row_1['name']}"),
                1,
                False,
                False,
                [row_2],
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
        rows,
        repository,
        store_in_redis,
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
            total_count=2,
            edges=[
                {
                    "cursor": base64_encode_string(
                        f"{row['updated_at']}|{row['name']}"
                    ),
                    "node": TestResultsRow(**row),
                }
                for row in rows
            ],
            page_info={
                "has_next_page": has_next_page,
                "has_previous_page": has_previous_page,
                "start_cursor": base64_encode_string(
                    f"{rows[0]['updated_at']}|{rows[0]['name']}"
                )
                if after
                else base64_encode_string(
                    f"{rows[-1]['updated_at']}|{rows[-1]['name']}"
                ),
                "end_cursor": base64_encode_string(
                    f"{rows[-1]['updated_at']}|{rows[-1]['name']}"
                )
                if before
                else base64_encode_string(f"{rows[0]['updated_at']}|{rows[0]['name']}"),
            },
        )

    @pytest.mark.parametrize(
        "first, after, before, last, has_next_page, has_previous_page, rows",
        [
            (1, None, None, None, True, False, [row_1]),
            (
                1,
                base64_encode_string(f"{row_1['updated_at']}|{row_1['name']}"),
                None,
                None,
                False,
                False,
                [row_2],
            ),
            (None, None, None, 1, False, True, [row_2]),
            (
                None,
                None,
                base64_encode_string(f"{row_2['updated_at']}|{row_2['name']}"),
                1,
                False,
                False,
                [row_1],
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
        rows,
        repository,
        store_in_redis,
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
            total_count=2,
            edges=[
                {
                    "cursor": base64_encode_string(
                        f"{row['updated_at']}|{row['name']}"
                    ),
                    "node": TestResultsRow(**row),
                }
                for row in rows
            ],
            page_info={
                "has_next_page": has_next_page,
                "has_previous_page": has_previous_page,
                "start_cursor": base64_encode_string(
                    f"{rows[0]['updated_at']}|{rows[0]['name']}"
                )
                if after
                else base64_encode_string(
                    f"{rows[-1]['updated_at']}|{rows[-1]['name']}"
                ),
                "end_cursor": base64_encode_string(
                    f"{rows[-1]['updated_at']}|{rows[-1]['name']}"
                )
                if before
                else base64_encode_string(f"{rows[0]['updated_at']}|{rows[0]['name']}"),
            },
        )

    def test_test_analytics_term_filter(self, repository, store_in_redis):
        test_results = generate_test_results(
            repoid=repository.repoid,
            term="test1",
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=1,
            edges=[
                {
                    "cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                    "node": TestResultsRow(**row_1),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                "end_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
            },
        )

    def test_test_analytics_testsuite_filter(self, repository, store_in_redis):
        test_results = generate_test_results(
            repoid=repository.repoid,
            testsuites=["testsuite1"],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=1,
            edges=[
                {
                    "cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                    "node": TestResultsRow(**row_1),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                "end_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
            },
        )

    def test_test_analytics_flag_filter(self, repository, store_in_redis):
        test_results = generate_test_results(
            repoid=repository.repoid,
            flags=["flag1"],
            ordering=TestResultsOrderingParameter.UPDATED_AT,
            ordering_direction=OrderingDirection.DESC,
            measurement_interval=MeasurementInterval.INTERVAL_30_DAY,
        )
        assert test_results is not None
        assert test_results == TestResultConnection(
            total_count=1,
            edges=[
                {
                    "cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                    "node": TestResultsRow(**row_1),
                },
            ],
            page_info={
                "has_next_page": False,
                "has_previous_page": False,
                "start_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                "end_cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
            },
        )

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
            == 2
        )
        assert result["owner"]["repository"]["testAnalytics"]["testResults"][
            "edges"
        ] == [
            {
                "cursor": "MjAyNC0wMS0wMiAwMDowMDowMHx0ZXN0Mg==",
                "node": row_to_camel_case(row_2),
            },
            {
                "cursor": "MjAyNC0wMS0wMSAwMDowMDowMHx0ZXN0MQ==",
                "node": row_to_camel_case(row_1),
            },
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
            "slowestTestsDuration": 800.0,
            "totalFails": 3,
            "totalSkips": 3,
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
            "flakeRate": 1 / 3,
            "flakeCount": 1,
        }
