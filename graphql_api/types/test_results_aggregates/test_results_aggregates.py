from typing import TypedDict

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

test_results_aggregates_bindable = ObjectType("TestResultsAggregates")


class TestResultsAggregates(TypedDict):
    total_run_time: float
    slowest_tests_duration: float
    fails: int
    skips: int


@test_results_aggregates_bindable.field("totalRunTime")
def resolve_total_run_time(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> float:
    return obj["total_run_time"]


@test_results_aggregates_bindable.field("slowestTestsRunTime")
def resolve_slowest_tests_run_time(
    obj: TestResultsAggregates, _: GraphQLResolveInfo
) -> float:
    return obj["slowest_tests_duration"]


@test_results_aggregates_bindable.field("totalFails")
def resolve_total_fails(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj["fails"]


@test_results_aggregates_bindable.field("totalSkips")
def resolve_total_skips(obj: TestResultsAggregates, _: GraphQLResolveInfo) -> int:
    return obj["skips"]
