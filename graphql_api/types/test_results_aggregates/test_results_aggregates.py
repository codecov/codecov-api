from typing import TypedDict

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

test_results_aggregates_bindable = ObjectType("TestResultsAggregates")


class TestResultsHeaders(TypedDict):
    total_run_time: float
    slowest_tests_duration: float
    fails: int
    skips: int


@test_results_aggregates_bindable.field("totalRunTime")
def resolve_name(obj: TestResultsHeaders, _: GraphQLResolveInfo) -> float:
    return obj["total_run_time"]


@test_results_aggregates_bindable.field("slowestTestsRunTime")
def resolve_updated_at(obj: TestResultsHeaders, _: GraphQLResolveInfo) -> float:
    return obj["slowest_tests_duration"]


@test_results_aggregates_bindable.field("totalFails")
def resolve_commits_failed(obj: TestResultsHeaders, _: GraphQLResolveInfo) -> int:
    return obj["fails"]


@test_results_aggregates_bindable.field("totalSkips")
def resolve_failure_rate(obj: TestResultsHeaders, _: GraphQLResolveInfo) -> int:
    return obj["skips"]
