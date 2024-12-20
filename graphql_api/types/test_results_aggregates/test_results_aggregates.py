from dataclasses import dataclass

import polars as pl
from ariadne import ObjectType
from graphql import GraphQLResolveInfo
from shared.django_apps.core.models import Repository

from graphql_api.types.enums.enum_types import MeasurementInterval
from utils.test_results import get_results


@dataclass
class TestResultsAggregates:
    total_duration: float
    slowest_tests_duration: float
    total_slow_tests: int
    fails: int
    skips: int
    total_duration_percent_change: float | None = None
    slowest_tests_duration_percent_change: float | None = None
    total_slow_tests_percent_change: float | None = None
    fails_percent_change: float | None = None
    skips_percent_change: float | None = None


def calculate_aggregates(table: pl.DataFrame) -> pl.DataFrame:
    return table.select(
        (
            pl.col("avg_duration")
            * (pl.col("total_pass_count") + pl.col("total_fail_count"))
        )
        .sum()
        .alias("total_duration"),
        (
            pl.when(pl.col("avg_duration") >= pl.col("avg_duration").quantile(0.95))
            .then(
                pl.col("avg_duration")
                * (pl.col("total_pass_count") + pl.col("total_fail_count"))
            )
            .otherwise(0)
            .top_k(min(100, max(table.height // 20, 1)))
            .sum()
            .alias("slowest_tests_duration")
        ),
        (pl.col("total_skip_count").sum()).alias("skips"),
        (pl.col("total_fail_count").sum()).alias("fails"),
        (
            (pl.col("avg_duration") >= pl.col("avg_duration").quantile(0.95))
            .top_k(min(100, max(table.height // 20, 1)))
            .sum()
        ).alias("total_slow_tests"),
    )


def test_results_aggregates_from_table(
    table: pl.DataFrame,
) -> TestResultsAggregates:
    aggregates = calculate_aggregates(table).row(0, named=True)
    return TestResultsAggregates(**aggregates)


def test_results_aggregates_with_percentage(
    curr_results: pl.DataFrame,
    past_results: pl.DataFrame,
) -> TestResultsAggregates:
    curr_aggregates = calculate_aggregates(curr_results)
    past_aggregates = calculate_aggregates(past_results)

    merged_results: pl.DataFrame = pl.concat([past_aggregates, curr_aggregates])

    # with_columns upserts the new columns, so if the name already exists it get overwritten
    # otherwise it's just added
    merged_results = merged_results.with_columns(
        pl.all()
        .pct_change()
        .replace([float("inf"), float("-inf")], None)
        .fill_nan(0)
        .name.suffix("_percent_change")
    )
    aggregates = merged_results.row(1, named=True)

    return TestResultsAggregates(**aggregates)


def generate_test_results_aggregates(
    repoid: int, interval: MeasurementInterval
) -> TestResultsAggregates | None:
    repo = Repository.objects.get(repoid=repoid)

    curr_results = get_results(repo.repoid, repo.branch, interval.value)
    if curr_results is None:
        return None
    past_results = get_results(
        repo.repoid, repo.branch, interval.value * 2, interval.value
    )
    if past_results is None:
        return test_results_aggregates_from_table(curr_results)
    else:
        return test_results_aggregates_with_percentage(curr_results, past_results)


test_results_aggregates_bindable = ObjectType("TestResultsAggregates")


@test_results_aggregates_bindable.field("totalDuration")
def resolve_total_duration(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float:
    return obj.total_duration


@test_results_aggregates_bindable.field("totalDurationPercentChange")
def resolve_total_duration_percent_change(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.total_duration_percent_change


@test_results_aggregates_bindable.field("slowestTestsDuration")
def resolve_slowest_tests_duration(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float:
    return obj.slowest_tests_duration


@test_results_aggregates_bindable.field("slowestTestsDurationPercentChange")
def resolve_slowest_tests_duration_percent_change(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.slowest_tests_duration_percent_change


@test_results_aggregates_bindable.field("totalSlowTests")
def resolve_total_slow_tests(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj.total_slow_tests


@test_results_aggregates_bindable.field("totalSlowTestsPercentChange")
def resolve_total_slow_tests_percent_change(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.total_slow_tests_percent_change


@test_results_aggregates_bindable.field("totalFails")
def resolve_total_fails(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj.fails


@test_results_aggregates_bindable.field("totalFailsPercentChange")
def resolve_total_fails_percent_change(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.fails_percent_change


@test_results_aggregates_bindable.field("totalSkips")
def resolve_total_skips(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj.skips


@test_results_aggregates_bindable.field("totalSkipsPercentChange")
def resolve_total_skips_percent_change(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.skips_percent_change
