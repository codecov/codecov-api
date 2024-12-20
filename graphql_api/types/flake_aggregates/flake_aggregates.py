from dataclasses import dataclass

import polars as pl
from ariadne import ObjectType
from graphql import GraphQLResolveInfo
from shared.django_apps.core.models import Repository

from graphql_api.types.enums.enum_types import MeasurementInterval
from utils.test_results import get_results


@dataclass
class FlakeAggregates:
    flake_count: int
    flake_rate: float
    flake_count_percent_change: float | None = None
    flake_rate_percent_change: float | None = None


def calculate_flake_aggregates(table: pl.DataFrame) -> pl.DataFrame:
    return table.select(
        (pl.col("total_flaky_fail_count") > 0).sum().alias("flake_count"),
        (
            pl.col("total_flaky_fail_count").sum()
            / (pl.col("total_fail_count").sum() + pl.col("total_pass_count").sum())
        ).alias("flake_rate"),
    )


def flake_aggregates_from_table(table: pl.DataFrame) -> FlakeAggregates:
    aggregates = calculate_flake_aggregates(table).row(0, named=True)
    return FlakeAggregates(**aggregates)


def flake_aggregates_with_percentage(
    curr_results: pl.DataFrame,
    past_results: pl.DataFrame,
) -> FlakeAggregates:
    curr_aggregates = calculate_flake_aggregates(curr_results)
    past_aggregates = calculate_flake_aggregates(past_results)

    merged_results: pl.DataFrame = pl.concat([past_aggregates, curr_aggregates])

    merged_results = merged_results.with_columns(
        pl.all()
        .pct_change()
        .replace([float("inf"), float("-inf")], None)
        .fill_nan(0)
        .name.suffix("_percent_change")
    )
    aggregates = merged_results.row(1, named=True)

    return FlakeAggregates(**aggregates)


def generate_flake_aggregates(
    repoid: int, interval: MeasurementInterval
) -> FlakeAggregates | None:
    repo = Repository.objects.get(repoid=repoid)

    curr_results = get_results(repo.repoid, repo.branch, interval.value)
    if curr_results is None:
        return None
    past_results = get_results(
        repo.repoid, repo.branch, interval.value * 2, interval.value
    )
    if past_results is None:
        return flake_aggregates_from_table(curr_results)
    else:
        return flake_aggregates_with_percentage(curr_results, past_results)


flake_aggregates_bindable = ObjectType("FlakeAggregates")


@flake_aggregates_bindable.field("flakeCount")
def resolve_flake_count(obj: FlakeAggregates, _: GraphQLResolveInfo) -> int:
    return obj.flake_count


@flake_aggregates_bindable.field("flakeCountPercentChange")
def resolve_flake_count_percent_change(
    obj: FlakeAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.flake_count_percent_change


@flake_aggregates_bindable.field("flakeRate")
def resolve_flake_rate(obj: FlakeAggregates, _: GraphQLResolveInfo) -> float:
    return obj.flake_rate


@flake_aggregates_bindable.field("flakeRatePercentChange")
def resolve_flake_rate_percent_change(
    obj: FlakeAggregates, _: GraphQLResolveInfo
) -> float | None:
    return obj.flake_rate_percent_change
