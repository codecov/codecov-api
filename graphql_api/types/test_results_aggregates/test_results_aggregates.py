from typing import TypedDict

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

test_results_aggregates_bindable = ObjectType("TestResultsAggregates")


class TestResultsAggregates(TypedDict):
    total_duration: float
    total_duration_percent_change: float | None
    slowest_tests_duration: float
    slowest_tests_duration_percent_change: float | None
    fails: int
    fails_percent_change: float | None
    skips: int
    skips_percent_change: float | None


@test_results_aggregates_bindable.field("totalDuration")
def resolve_total_duration(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float:
    return obj["total_duration"]

@test_results_aggregates_bindable.field("totalDurationPercentChange")
def resolve_total_duration_percent_change(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float | None:
    return obj.get("total_duration_percent_change")


@test_results_aggregates_bindable.field("slowestTestsDuration")
def resolve_slowest_tests_duration(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float:
    return obj["slowest_tests_duration"]

@test_results_aggregates_bindable.field("slowestTestsDurationPercentChange")
def resolve_slowest_tests_duration_percent_change(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float | None:
    return obj.get("slowest_tests_duration_percent_change")


@test_results_aggregates_bindable.field("totalFails")
def resolve_total_fails(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj["fails"]

@test_results_aggregates_bindable.field("totalFailsPercentChange")
def resolve_total_fails_percent_change(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float | None:
    return obj.get("fails_percent_change")


@test_results_aggregates_bindable.field("totalSkips")
def resolve_total_skips(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj["skips"]

@test_results_aggregates_bindable.field("totalSkipsPercentChange")
def resolve_total_skips_percent_change(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float | None:
    return obj.get("skips_percent_change")
