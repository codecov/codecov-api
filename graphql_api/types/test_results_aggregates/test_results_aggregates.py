from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from utils.test_results import TestResultsAggregates

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
